import dataclasses
import datetime
import uuid
from collections import defaultdict
from typing import Dict
from typing import List
from typing import Optional
from typing import Union

import pandas as pd

from evidently.base_metric import InputData
from evidently.base_metric import Metric
from evidently.core import IncludeOptions
from evidently.metric_preset.metric_preset import MetricPreset
from evidently.metric_results import DatasetColumns
from evidently.model.dashboard import DashboardInfo
from evidently.model.widget import AdditionalGraphInfo
from evidently.options.base import AnyOptions
from evidently.pipeline.column_mapping import ColumnMapping
from evidently.renderers.base_renderer import DetailsInfo
from evidently.suite.base_suite import MetadataValueType
from evidently.suite.base_suite import ReportBase
from evidently.suite.base_suite import Snapshot
from evidently.suite.base_suite import Suite
from evidently.suite.base_suite import find_metric_renderer
from evidently.utils.data_operations import process_columns
from evidently.utils.data_preprocessing import create_data_definition
from evidently.utils.generators import BaseGenerator

METRIC_GENERATORS = "metric_generators"
METRIC_PRESETS = "metric_presets"


class Report(ReportBase):
    _columns_info: DatasetColumns
    _first_level_metrics: List[Union[Metric]]
    metrics: List[Union[Metric, MetricPreset, BaseGenerator]]

    def __init__(
        self,
        metrics: List[Union[Metric, MetricPreset, BaseGenerator]],
        options: AnyOptions = None,
        timestamp: Optional[datetime.datetime] = None,
        id: uuid.UUID = None,
        metadata: Dict[str, MetadataValueType] = None,
        tags: List[str] = None,
        model_id: str = None,
        reference_id: str = None,
        batch_size: str = None,
        dataset_id: str = None,
    ):
        super().__init__(options, timestamp)
        # just save all metrics and metric presets
        self.metrics = metrics
        self._inner_suite = Suite(self.options)
        self._first_level_metrics = []
        self.id = id or uuid.uuid4()
        self.metadata = metadata or {}
        self.tags = tags or []
        if model_id is not None:
            self.set_model_id(model_id)
        if batch_size is not None:
            self.set_batch_size(batch_size)
        if reference_id is not None:
            self.set_reference_id(reference_id)
        if dataset_id is not None:
            self.set_dataset_id(dataset_id)

    def run(
        self,
        *,
        reference_data: Optional[pd.DataFrame],
        current_data: pd.DataFrame,
        column_mapping: Optional[ColumnMapping] = None,
    ) -> None:
        if column_mapping is None:
            column_mapping = ColumnMapping()

        if current_data is None:
            raise ValueError("Current dataset should be present")

        self._columns_info = process_columns(current_data, column_mapping)
        self._inner_suite.reset()
        self._inner_suite.verify()

        data_definition = create_data_definition(reference_data, current_data, column_mapping)
        data = InputData(reference_data, current_data, None, None, column_mapping, data_definition)

        # get each item from metrics/presets and add to metrics list
        # do it in one loop because we want to save metrics and presets order
        for item in self.metrics:
            # if the item is a metric generator, then we need to generate metrics and add them to the report
            if isinstance(item, BaseGenerator):
                for metric in item.generate(columns_info=self._columns_info):
                    if isinstance(metric, Metric):
                        self._first_level_metrics.append(metric)
                        self._inner_suite.add_metric(metric)

                    else:
                        # if generated item is not a metric, raise an error
                        raise ValueError(f"Incorrect metric type in generator {item}")
                if METRIC_GENERATORS not in self.metadata:
                    self.metadata[METRIC_GENERATORS] = []
                self.metadata[METRIC_GENERATORS].append(item.__class__.__name__)  # type: ignore[union-attr]
            elif isinstance(item, MetricPreset):
                metrics = []

                for metric_item in item.generate_metrics(data=data, columns=self._columns_info):
                    if isinstance(metric_item, BaseGenerator):
                        metrics.extend(metric_item.generate(columns_info=self._columns_info))

                    else:
                        metrics.append(metric_item)

                for metric in metrics:
                    self._first_level_metrics.append(metric)
                    self._inner_suite.add_metric(metric)

                if METRIC_PRESETS not in self.metadata:
                    self.metadata[METRIC_PRESETS] = []
                self.metadata[METRIC_PRESETS].append(item.__class__.__name__)  # type: ignore[union-attr]

            elif isinstance(item, Metric):
                self._first_level_metrics.append(item)
                self._inner_suite.add_metric(item)

            else:
                raise ValueError("Incorrect item instead of a metric or metric preset was passed to Report")

        data_definition = create_data_definition(reference_data, current_data, column_mapping)
        curr_add, ref_add = self._inner_suite.create_additional_features(current_data, reference_data, data_definition)
        data = InputData(
            reference_data,
            current_data,
            ref_add,
            curr_add,
            column_mapping,
            data_definition,
        )
        self._inner_suite.run_calculate(data)

    def as_dict(  # type: ignore[override]
        self,
        include_render: bool = False,
        include: Dict[str, IncludeOptions] = None,
        exclude: Dict[str, IncludeOptions] = None,
        **kwargs,
    ) -> dict:
        metrics = []
        include = include or {}
        exclude = exclude or {}
        for metric in self._first_level_metrics:
            renderer = find_metric_renderer(type(metric), self._inner_suite.context.renderers)
            metric_id = metric.get_id()
            metrics.append(
                {
                    "metric": metric_id,
                    "result": renderer.render_json(
                        metric,
                        include_render=include_render,
                        include=include.get(metric_id),
                        exclude=exclude.get(metric_id),
                    ),
                }
            )

        return {
            "metrics": metrics,
        }

    def as_pandas(self, group: str = None) -> Union[Dict[str, pd.DataFrame], pd.DataFrame]:
        metrics = defaultdict(list)

        for metric in self._first_level_metrics:
            renderer = find_metric_renderer(type(metric), self._inner_suite.context.renderers)
            metric_id = metric.get_id()
            if group is not None and metric_id != group:
                continue
            metrics[metric_id].append(renderer.render_pandas(metric))

        result = {cls: pd.concat(val) for cls, val in metrics.items()}
        if group is None and len(result) == 1:
            return next(iter(result.values()))
        if group is None:
            return result
        if group not in result:
            raise ValueError(f"Metric group {group} not found in this report")
        return result[group]

    def _build_dashboard_info(self):
        metrics_results = []
        additional_graphs = []

        color_options = self.options.color_options

        for test in self._first_level_metrics:
            renderer = find_metric_renderer(type(test), self._inner_suite.context.renderers)
            # set the color scheme from the report for each render
            renderer.color_options = color_options
            html_info = renderer.render_html(test)

            for info_item in html_info:
                for additional_graph in info_item.get_additional_graphs():
                    if isinstance(additional_graph, AdditionalGraphInfo):
                        additional_graphs.append(DetailsInfo("", additional_graph.params, additional_graph.id))

                    else:
                        additional_graphs.append(DetailsInfo("", additional_graph, additional_graph.id))

            metrics_results.extend(html_info)

        return (
            "evidently_dashboard_" + str(uuid.uuid4()).replace("-", ""),
            DashboardInfo("Report", widgets=[result for result in metrics_results]),
            {
                f"{item.id}": dataclasses.asdict(item.info) if dataclasses.is_dataclass(item.info) else item.info
                for item in additional_graphs
            },
        )

    def set_batch_size(self, batch_size: str):
        self.metadata["batch_size"] = batch_size
        return self

    def set_model_id(self, model_id: str):
        self.metadata["model_id"] = model_id
        return self

    def set_reference_id(self, reference_id: str):
        self.metadata["reference_id"] = reference_id
        return self

    def set_dataset_id(self, dataset_id: str):
        self.metadata["dataset_id"] = dataset_id
        return self

    def _get_snapshot(self) -> Snapshot:
        snapshot = super()._get_snapshot()
        snapshot.metrics_ids = [snapshot.suite.metrics.index(m) for m in self._first_level_metrics]
        return snapshot

    @classmethod
    def _parse_snapshot(cls, snapshot: Snapshot) -> "Report":
        ctx = snapshot.suite.to_context()
        metrics = [ctx.metrics[i] for i in snapshot.metrics_ids]
        report = Report(
            metrics=metrics,
            timestamp=snapshot.timestamp,
            id=snapshot.id,
            metadata=snapshot.metadata,
            tags=snapshot.tags,
            options=snapshot.options,
        )
        report._first_level_metrics = metrics
        report._inner_suite.context = ctx
        return report
