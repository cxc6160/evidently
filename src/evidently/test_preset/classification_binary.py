from typing import Optional

from evidently.base_metric import InputData
from evidently.calculations.stattests import PossibleStatTestType
from evidently.metric_results import DatasetColumns
from evidently.test_preset.test_preset import TestPreset
from evidently.tests import TestAccuracyScore
from evidently.tests import TestColumnDrift
from evidently.tests import TestF1Score
from evidently.tests import TestPrecisionScore
from evidently.tests import TestRecallScore
from evidently.tests import TestRocAuc


class BinaryClassificationTestPreset(TestPreset):
    """
    Binary Classification Tests.
    Args:
        stattest: statistical test for target drift test.
        stattest_threshold: threshold for statistical test for target drift test.
        probas_threshold: threshold for label calculation for prediction.

    Contains:
    - `TestColumnValueDrift` for target
    - `TestPrecisionScore`
    - `TestRecallScore`
    - `TestF1Score`
    - `TestAccuracyScore`
    """

    def __init__(
        self,
        stattest: Optional[PossibleStatTestType] = None,
        stattest_threshold: Optional[float] = None,
        probas_threshold: Optional[float] = None,
    ):
        super().__init__()
        self.stattest = stattest
        self.stattest_threshold = stattest_threshold
        self.probas_threshold = probas_threshold

    def generate_tests(self, data: InputData, columns: DatasetColumns):
        target = columns.utility_columns.target

        if target is None:
            raise ValueError("Target column should be set in mapping and be present in data")
        prediction_columns = data.data_definition.get_prediction_columns()
        is_probas_present = prediction_columns is not None and prediction_columns.prediction_probas is not None
        if not is_probas_present:
            return [
                TestColumnDrift(column_name=target, stattest=self.stattest, stattest_threshold=self.stattest_threshold),
                TestPrecisionScore(probas_threshold=self.probas_threshold),
                TestRecallScore(probas_threshold=self.probas_threshold),
                TestF1Score(probas_threshold=self.probas_threshold),
                TestAccuracyScore(probas_threshold=self.probas_threshold),
            ]

        return [
            TestColumnDrift(column_name=target, stattest=self.stattest, stattest_threshold=self.stattest_threshold),
            TestRocAuc(),
            TestPrecisionScore(probas_threshold=self.probas_threshold),
            TestRecallScore(probas_threshold=self.probas_threshold),
            TestAccuracyScore(probas_threshold=self.probas_threshold),
            TestF1Score(probas_threshold=self.probas_threshold),
        ]
