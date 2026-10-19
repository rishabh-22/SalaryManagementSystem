# ruff: noqa: E501
import pytest

from app.services import stats

SUMMARY_KEYS = {"headcount", "min", "p25", "median", "p75", "max", "mean", "total_payroll"}


def test_summarize_empty_returns_zero_headcount_and_nones():
    result = stats.summarize([])
    assert set(result) == SUMMARY_KEYS
    assert result["headcount"] == 0
    assert all(v is None for k, v in result.items() if k != "headcount")


def test_summarize_single_value_collapses_percentiles():
    result = stats.summarize([50000.0])
    assert result == {
        "headcount": 1, "min": 50000.0, "p25": 50000.0, "median": 50000.0,
        "p75": 50000.0, "max": 50000.0, "mean": 50000.0, "total_payroll": 50000.0,
    }


def test_summarize_all_equal_values():
    result = stats.summarize([70.0, 70.0, 70.0, 70.0])
    assert result["p25"] == result["median"] == result["p75"] == 70.0
    assert result["total_payroll"] == 280.0


def test_summarize_odd_count_inclusive_percentiles():
    result = stats.summarize([5, 1, 3, 2, 4])  # unsorted on purpose
    assert result["headcount"] == 5
    assert (result["min"], result["p25"], result["median"], result["p75"], result["max"]) == (1, 2, 3, 4, 5)
    assert result["mean"] == 3
    assert result["total_payroll"] == 15


def test_summarize_even_count_inclusive_percentiles():
    result = stats.summarize([1, 2, 3, 4])
    assert result["p25"] == 1.75
    assert result["median"] == 2.5
    assert result["p75"] == 3.25


def test_summarize_two_values():
    result = stats.summarize([100.0, 200.0])
    assert (result["p25"], result["median"], result["p75"]) == (125.0, 150.0, 175.0)


def test_summarize_rounds_to_two_decimals():
    result = stats.summarize([1.0, 1.0, 2.0])
    assert result["mean"] == 1.33
    result = stats.summarize([10.005, 10.0])
    for key in ("p25", "median", "p75", "mean", "total_payroll"):
        assert round(result[key], 2) == result[key]


def test_summarize_does_not_mutate_input():
    values = [3.0, 1.0, 2.0]
    stats.summarize(values)
    assert values == [3.0, 1.0, 2.0]


def test_histogram_empty_returns_no_bins():
    assert stats.histogram([], 10) == []


def test_histogram_equal_width_and_last_bin_inclusive():
    bins = stats.histogram([0, 5, 10], 2)
    assert [(b["lower"], b["upper"], b["count"]) for b in bins] == [(0, 5, 1), (5, 10, 2)]


def test_histogram_counts_sum_to_total():
    values = [100, 150, 200, 250, 300, 350, 400, 999, 1000]
    bins = stats.histogram(values, 7)
    assert len(bins) == 7
    assert sum(b["count"] for b in bins) == len(values)
    assert bins[-1]["upper"] == 1000
    assert bins[-1]["count"] >= 1  # max value lands in the last bin


def test_histogram_bins_are_contiguous():
    bins = stats.histogram([10, 20, 30, 40], 3)
    for left, right in zip(bins, bins[1:], strict=False):
        assert left["upper"] == pytest.approx(right["lower"])


def test_histogram_all_equal_returns_single_degenerate_bin():
    bins = stats.histogram([500.0, 500.0, 500.0], 10)
    assert bins == [{"lower": 500.0, "upper": 500.0, "count": 3}]


def test_histogram_single_bin():
    bins = stats.histogram([1, 2, 3], 1)
    assert len(bins) == 1 and bins[0]["count"] == 3


def test_deviation_signed_and_rounded_to_four_places():
    assert stats.deviation(150.0, 100.0) == 0.5
    assert stats.deviation(70.0, 100.0) == -0.3
    assert stats.deviation(100.0, 3.0) == 32.3333
    assert stats.deviation(100.0, 100.0) == 0
