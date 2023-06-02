import datetime
import os
from collections import defaultdict
from typing import Dict
from typing import List
from typing import Optional
from typing import Type
from typing import TypeVar

from evidently.base_metric import Metric
from evidently.base_metric import MetricResult
from evidently.report import Report
from evidently.suite.base_suite import Display
from evidently.tests.base_test import Test


def load_metric_time_series(
    path: str,
    date_from: Optional[datetime.datetime] = None,
    date_to: Optional[datetime.datetime] = None,
    metrics: Optional[List[Metric]] = None,
) -> Dict[Metric, Dict[datetime.datetime, MetricResult]]:
    reports = load_time_series_data(path, Report, date_from, date_to)
    result: Dict[Metric, Dict[datetime.datetime, MetricResult]] = defaultdict(dict)
    if metrics is None:
        for timestamp, report in reports.items():
            for metric in report._first_level_metrics:
                result[metric][timestamp] = metric.get_result()
        return result
    for metric in metrics:
        for timestamp, report in reports.items():
            if metric in report._first_level_metrics:
                metric.set_context(report._inner_suite.context)
                result[metric][timestamp] = metric.get_result()
    return result


T = TypeVar("T", bound=Display)


def load_time_series_data(
    path: str, cls: Type[T], date_from: Optional[datetime.datetime] = None, date_to: Optional[datetime.datetime] = None
) -> Dict[datetime.datetime, T]:
    result = {}
    for file in os.listdir(path):
        filepath = os.path.join(path, file)
        suite = cls._load(filepath)
        if date_from is not None and suite.timestamp < date_from:
            continue
        if date_to is not None and suite.timestamp > date_to:
            continue
        result[suite.timestamp] = suite
    return result