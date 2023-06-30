import datetime

from sklearn import datasets

from evidently.metrics import DatasetDriftMetric, DatasetMissingValuesMetric, ColumnDriftMetric, ColumnQuantileMetric
from evidently.report import Report
from evidently.test_suite import TestSuite
from evidently.test_preset import DataDriftTestPreset

from evidently.ui.dashboards import CounterAgg
from evidently.ui.dashboards import DashboardPanelCounter
from evidently.ui.dashboards import DashboardPanelPlot
from evidently.ui.dashboards import PanelValue
from evidently.ui.dashboards import PlotType
from evidently.ui.dashboards import ReportFilter
from evidently.ui.workspace import Workspace


adult_data = datasets.fetch_openml(name="adult", version=2, as_frame="auto")
adult = adult_data.frame

adult_ref = adult[~adult.education.isin(["Some-college", "HS-grad", "Bachelors"])]
adult_cur = adult[adult.education.isin(["Some-college", "HS-grad", "Bachelors"])]

WORKSPACE = "workspace"


def create_report(i: int, tags=[]):
    data_drift_report = Report(
        metrics=[
            DatasetDriftMetric(),
            DatasetMissingValuesMetric(),
            ColumnDriftMetric(column_name="age"),
            ColumnQuantileMetric(column_name="age", quantile=0.5),
            ColumnDriftMetric(column_name="education-num"),
            ColumnQuantileMetric(column_name="education-num", quantile=0.5),
        ],
        metadata={"type": "data_quality"},
        tags=tags,
        timestamp=datetime.datetime.now() + datetime.timedelta(days=i),
    )

    data_drift_report.set_batch_size("daily")
    data_drift_report.set_dataset_id("adult")

    data_drift_report.run(reference_data=adult_ref, current_data=adult_cur.iloc[100 * i: 100 * (i + 1), :])
    return data_drift_report


def create_test_suite(i: int, tags=[]):
    data_drift_test_suite = TestSuite(
        tests=[
            DataDriftTestPreset()
        ],
        timestamp=datetime.datetime.now() + datetime.timedelta(days=i),
    )

    data_drift_test_suite.run(reference_data=adult_ref, current_data=adult_cur.iloc[100 * i: 100 * (i + 1), :])
    return data_drift_test_suite


def create_project(workspace: Workspace):
    project = workspace.create_project("Example Project")
    project.add_panel(
        DashboardPanelCounter(
            filter=ReportFilter(metadata_values={}, tag_values=[]),
            agg=CounterAgg.NONE,
            title="Census Income Dataset (Adult)",
        )
    )
    project.add_panel(
        DashboardPanelPlot(
            title="Dataset Quality",
            filter=ReportFilter(metadata_values={"type": "data_quality"}, tag_values=[]),
            values=[
                PanelValue(metric_id="DatasetDriftMetric", field_path="share_of_drifted_columns", legend="Drift Share"),
                PanelValue(metric_id="DatasetMissingValuesMetric", field_path="current.share_of_missing_values", legend="Missing Values Share"),
            ],
            plot_type=PlotType.LINE,
        )
    )
    project.add_panel(
        DashboardPanelPlot(
            title="Age: Wasserstein drift distance",
            filter=ReportFilter(metadata_values={"type": "data_quality"}, tag_values=[]),
            values=[
                PanelValue(metric_id="ColumnDriftMetric",
                           metric_args={"column_name.name": "age"},
                           field_path="drift_score",
                           legend="Drift Score"),
            ],
            plot_type=PlotType.LINE,
            size=1
        )
    )
    project.add_panel(
        DashboardPanelPlot(
            title="Age: quantile=0.5",
            filter=ReportFilter(metadata_values={"type": "data_quality"}, tag_values=[]),
            values=[
                PanelValue(metric_id="ColumnQuantileMetric",
                           metric_args={"column_name.name": "age", "quantile": 0.5},
                           field_path="current.value",
                           legend="Quantile"),
            ],
            plot_type=PlotType.LINE,
            size=1
        )
    )
    project.add_panel(
        DashboardPanelPlot(
            title="Education-num: Wasserstein drift distance",
            filter=ReportFilter(metadata_values={"type": "data_quality"}, tag_values=[]),
            values=[
                PanelValue(metric_id="ColumnDriftMetric",
                           metric_args={"column_name.name": "education-num"},
                           field_path="drift_score",
                           legend="Drift Score"),
            ],
            plot_type=PlotType.LINE,
            size=1
        )
    )
    project.add_panel(
        DashboardPanelPlot(
            title="Education-num: quantile=0.5",
            filter=ReportFilter(metadata_values={"type": "data_quality"}, tag_values=[]),
            values=[
                PanelValue(metric_id="ColumnQuantileMetric",
                           metric_args={"column_name.name": "education-num", "quantile": 0.5},
                           field_path="current.value",
                           legend="Quantile"),
            ],
            plot_type=PlotType.LINE,
            size=1
        )
    )
    return project


def main(workspace: str):
    ws = Workspace.create("workspace")
    project = create_project(ws)
    project.save()

    for i in range(0, 19):
        report = create_report(i=i)
        ws.add_report(project.id, report)

        test_suite = create_test_suite(i=i)
        ws.add_report(project.id, test_suite)


if __name__ == "__main__":
    main("workspace")
