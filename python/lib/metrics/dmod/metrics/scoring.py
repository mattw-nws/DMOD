#!/usr/bin/env python3
import typing
import abc
from collections import defaultdict
from collections import abc as abstract_collections

from math import inf as infinity

import pandas
import numpy

from ..metrics.threshold import Threshold
from ..metrics.common import CommonTypes
from ..metrics.common import EPSILON


def scale_value(metric: "Metric", raw_value: CommonTypes.NUMBER) -> CommonTypes.NUMBER:
    if numpy.isnan(raw_value):
        return numpy.nan

    rise = 0
    run = 1

    if metric.has_ideal_value and metric.bounded:
        if metric.ideal_value == metric.lower_bound:
            # Lower should be higher and the max scale factor is 1.0 and the minimum is 0.0
            rise = -1
            run = metric.upper_bound - metric.lower_bound
        elif metric.ideal_value == metric.upper_bound:
            # lower should stay lower, meaning that the the scale should move from 0 to 1
            rise = 1
            run = metric.upper_bound - metric.lower_bound
        elif metric.lower_bound < metric.ideal_value < metric.upper_bound and raw_value <= metric.ideal_value:
            rise = 1
            run = metric.ideal_value - metric.lower_bound
        elif metric.lower_bound < metric.ideal_value < metric.upper_bound and raw_value > metric.ideal_value:
            rise = -1
            run = metric.upper_bound - metric.ideal_value

        slope = rise / run
        y_intercept = 1 - (slope * metric.ideal_value)
        scaled_value = slope * raw_value + y_intercept

        if metric.has_upper_bound:
            scaled_value = min(scaled_value, metric.upper_bound)

        if metric.has_lower_bound:
            scaled_value = max(scaled_value, metric.lower_bound)

        return scaled_value
    return raw_value


class Metric(abc.ABC):
    """
    A functional that may be called to evaluate metrics based around thresholds, providing access to attributes
    such as its name and bounds
    """
    def __init__(
            self,
            weight: CommonTypes.NUMBER,
            lower_bound: CommonTypes.NUMBER = -infinity,
            upper_bound: CommonTypes.NUMBER = infinity,
            ideal_value: CommonTypes.NUMBER = numpy.nan,
            failure: CommonTypes.NUMBER = None,
            greater_is_better: bool = True
    ):
        """
        Constructor

        Args:
            weight: The relative, numeric significance of the metric itself
            lower_bound: The lowest acknowledged value - this doesn't necessarily need to be the lower bound of the
                statistical function
            upper_bound: The highest acknowledged value - this doesn't necessarily need to be the upper bound of the
                statistical function
            ideal_value: The value deemed to be perfect for the metric
            failure: A value indicating a complete failure for the metric, triggering a failure among all accompanying
                metrics
            greater_is_better: Whether or not a higher value is perferred over a lower value
        """
        if weight is None or not (isinstance(weight, int) or isinstance(weight, float)) or numpy.isnan(weight):
            raise ValueError("Weight must be supplied and must be numeric")

        self.__lower_bound = lower_bound if lower_bound is not None else -infinity
        self.__upper_bound = upper_bound if upper_bound is not None else infinity
        self.__ideal_value = ideal_value if ideal_value is not None else numpy.nan
        self.__weight = weight
        self.__greater_is_better = greater_is_better if greater_is_better is not None else True
        self.__failure = failure

    @classmethod
    @abc.abstractmethod
    def get_description(cls):
        """
        Returns:
            A description of how the metric works and how it's supposed be be interpreted
        """
        pass

    @property
    def name(self) -> str:
        """
        Returns:
            The name of the metric
        """
        return self.get_name()

    @property
    def fails_on(self) -> CommonTypes.NUMBER:
        """
        Returns:
            The value that might trigger a failing evaluation
        """
        return self.__failure

    @property
    def weight(self) -> CommonTypes.NUMBER:
        """
        Returns:
            The relative numeric significance of the metric
        """
        return self.__weight

    @property
    def ideal_value(self) -> CommonTypes.NUMBER:
        """
        Returns:
            The perfect value
        """
        return self.__ideal_value

    @property
    def lower_bound(self) -> CommonTypes.NUMBER:
        """
        The lowest possible value to consider when scaling the result

        NOTE: While the lower and upper bound generally correspond to the upper and lower bound of the metric,
              the lower bound on this corresponds to the lowers number that has any affect on the scaling process.
              For instance, a metric might have a bounds of [-1, 1], but we only want to consider [0, 1] for scoring
              purposes, where anything under 0 is translated as 0

        Returns:
            The lowest value to consider when scaling
        """
        return self.__lower_bound

    @property
    def upper_bound(self) -> CommonTypes.NUMBER:
        """
        The highest possible value to consider when scaling the result

        NOTE: While the lower and upper bound generally correspond to the upper and lower bound of the metric,
              the lower bound on this corresponds to the lowers number that has any affect on the scaling process.
              For instance, a metric might have a bounds of [-1, 1], but we only want to consider [0, 1] for scoring
              purposes, where anything under 0 is translated as 0

        Returns:
            The highest value to consider when scaling
        """
        return self.__upper_bound

    @property
    def greater_is_better(self) -> bool:
        """
        Returns:
            Whether or not a greater value is considered better
        """
        return self.__greater_is_better

    @property
    def has_upper_bound(self) -> bool:
        return not numpy.isnan(self.__upper_bound) and self.__upper_bound < infinity

    @property
    def has_lower_bound(self) -> bool:
        return not numpy.isnan(self.__lower_bound) and self.__lower_bound > -infinity

    @property
    def has_ideal_value(self) -> bool:
        return self.__ideal_value is not None and \
               not numpy.isnan(self.__ideal_value) and \
               not numpy.isinf(self.__ideal_value)

    @property
    def fully_bounded(self) -> bool:
        return self.has_lower_bound and self.has_upper_bound

    @property
    def partially_bounded(self) -> bool:
        return self.has_lower_bound ^ self.has_upper_bound

    @property
    def bounded(self) -> bool:
        return self.has_lower_bound or self.has_upper_bound

    @classmethod
    @abc.abstractmethod
    def get_name(cls):
        pass

    @abc.abstractmethod
    def __call__(
            self,
            pairs: pandas.DataFrame,
            observed_value_label: str,
            predicted_value_label: str,
            thresholds: typing.Sequence[Threshold] = None,
            *args,
            **kwargs
    ) -> "Scores":
        pass

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        return "Metric(name=" + self.name + ")"


class Score(object):
    def __init__(self, metric: Metric, value: CommonTypes.NUMBER, threshold: Threshold = None):
        self.__metric = metric
        self.__value = value
        self.__threshold = threshold or Threshold.default()

    @property
    def value(self) -> CommonTypes.NUMBER:
        return self.__value

    @property
    def scaled_value(self) -> CommonTypes.NUMBER:
        return scale_value(self.__metric, self.__value) * self.__threshold.weight

    @property
    def metric(self) -> Metric:
        return self.__metric

    @property
    def threshold(self) -> Threshold:
        return self.__threshold

    @property
    def failed(self) -> bool:
        if self.__metric.fails_on is None:
            return False
        elif numpy.isnan(self.__metric.fails_on) and numpy.isnan(self.__value):
            return True
        elif numpy.isnan(self.__metric.fails_on):
            return False

        difference = self.__value - self.__metric.fails_on
        difference = abs(difference)

        failed = difference < EPSILON

        return failed

    def __str__(self) -> str:
        return f"{self.metric} => ({self.threshold}: {self.scaled_value})"

    def __repr__(self) -> str:
        return self.__str__()


class Scores(abstract_collections.Sized, abstract_collections.Iterable):
    def __len__(self) -> int:
        return len(self.__results)

    def __init__(self, metric: Metric, scores: typing.Sequence[Score]):
        self.__metric = metric

        self.__results = {
            score.threshold: score
            for score in scores
        }

    @property
    def metric(self) -> Metric:
        return self.__metric

    @property
    def total(self) -> CommonTypes.NUMBER:
        if len(self.__results) == 0:
            raise ValueError("There are no scores to total")

        return sum([score.scaled_value for score in self.__results])

    def __getitem__(self, key: typing.Union[str, Threshold]) -> Score:
        if isinstance(key, Threshold):
            key = key.name

        for threshold, score in self.__results.items():
            if threshold.name == key:
                return score

        raise ValueError(f"There is not a score for '{key}'")

    def __iter__(self):
        return iter(self.__results.values())

    def __str__(self) -> str:
        return ", ".join([str(score) for score in self.__results])

    def __repr__(self) -> str:
        return self.__str__()


class MetricResults(object):
    def __init__(
            self,
            aggregator: CommonTypes.NUMERIC_OPERATOR,
            metric_scores: typing.Sequence[Scores] = None,
            weight: CommonTypes.NUMBER = None
    ):
        if not metric_scores:
            metric_scores = list()

        self.__aggregator = aggregator
        self.__results: typing.Dict[Threshold, typing.List[Score]] = defaultdict(list)

        for scores in metric_scores:
            self.add_scores(scores)

        self.__weight = weight or 1

    def to_dataframe(self) -> pandas.DataFrame:
        rows = list()

        for threshold, scores in self.__results.items():
            threshold_rows: typing.List[dict] = list()

            for score in scores:
                row_values = dict()
                row_values['threshold_name'] = threshold.name
                row_values['threshold_weight'] = threshold.weight
                row_values['threshold_value'] = threshold.value
                row_values['result'] = score.value
                row_values['scaled_result'] = score.scaled_value
                row_values['metric'] = score.metric.name
                row_values['metric_weight'] = score.metric.weight
                row_values['desired_metric_value'] = score.metric.ideal_value
                row_values['failing_metric_value'] = score.metric.fails_on
                row_values['metric_lower_bound'] = score.metric.lower_bound
                row_values['metric_upper_bound'] = score.metric.upper_bound

                threshold_rows.append(row_values)

            rows.extend(threshold_rows)

        return pandas.DataFrame(rows)

    def score_threshold(self, threshold: Threshold) -> CommonTypes.NUMBER:
        threshold_score = numpy.nan

        for score in self.__results[threshold]:
            if score.failed:
                return 0

            scaled_value = score.scaled_value

            if score is None or numpy.isnan(scaled_value):
                continue

            if numpy.isnan(threshold_score):
                threshold_score = scaled_value
            else:
                threshold_score += scaled_value

        return threshold_score

    @property
    def total(self) -> CommonTypes.NUMBER:
        total_score = numpy.nan
        count = 0

        for threshold in self.__results.keys():
            threshold_score = self.score_threshold(threshold)
            count += 1
            total_score = self.__aggregator(total_score, threshold_score, count)

        return total_score

    def add_scores(self, scores: Scores):
        for score in scores:
            self.__results[score.threshold].append(score)

    def __getitem__(self, key: str) -> typing.Sequence[Score]:
        result_key = None
        for threshold in self.__results.keys():
            if threshold.name.lower() == key.lower():
                result_key = threshold
                break

        if result_key:
            return self.__results[result_key]

        available_thresholds = [threshold.name for threshold in self.__results.keys()]

        raise KeyError(f"There are no thresholds named '{key}'. Available keys are: {', '.join(available_thresholds)}")

    def __iter__(self) -> typing.ItemsView[Threshold, typing.List[Score]]:
        return self.__results.items()


class ScoringScheme(object):
    @staticmethod
    def get_default_aggregator() -> CommonTypes.NUMERIC_OPERATOR:
        def operator(
                first_score_value: CommonTypes.NUMBER,
                second_score_value: CommonTypes.NUMBER,
                count: CommonTypes.NUMBER = None
        ) -> CommonTypes.NUMBER:
            if numpy.isnan(first_score_value) and numpy.isnan(second_score_value):
                return numpy.nan
            elif numpy.isnan(first_score_value):
                return second_score_value
            elif numpy.isnan(second_score_value):
                return first_score_value

            return first_score_value + second_score_value
        return operator

    def __init__(
            self,
            metrics: typing.Sequence[Metric] = None,
            aggregator: CommonTypes.NUMERIC_OPERATOR = None
    ):
        self.__aggregator = aggregator or ScoringScheme.get_default_aggregator()
        self.__metrics = metrics or list()
    
    def score(
            self,
            pairs: pandas.DataFrame,
            observed_value_label: str,
            predicted_value_label: str,
            thresholds: typing.Sequence[Threshold] = None,
            weight: CommonTypes.NUMBER = None,
            *args,
            **kwargs
    ) -> MetricResults:
        if len(self.__metrics) == 0:
            raise ValueError(
                "No metrics were attached to the scoring scheme - values cannot be scored and aggregated"
            )

        weight = 1 if not weight or numpy.isnan(weight) else weight

        results = MetricResults(aggregator=self.__aggregator, weight=weight)

        for metric in self.__metrics:
            scores = metric(
                pairs=pairs,
                observed_value_label=observed_value_label,
                predicted_value_label=predicted_value_label,
                thresholds=thresholds,
                *args,
                **kwargs
            )
            results.add_scores(scores)

        return results
