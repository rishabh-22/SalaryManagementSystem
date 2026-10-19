"""Pure statistics helpers (no DB access)."""

import statistics


def _r2(value: float) -> float:
    return round(value, 2)


def summarize(values: list[float]) -> dict:
    if not values:
        return {
            "headcount": 0,
            "min": None,
            "p25": None,
            "median": None,
            "p75": None,
            "max": None,
            "mean": None,
            "total_payroll": None,
        }
    median = statistics.median(values)
    if len(values) == 1:
        p25 = p75 = median
    else:
        quartiles = statistics.quantiles(values, n=4, method="inclusive")
        p25, p75 = quartiles[0], quartiles[2]
    return {
        "headcount": len(values),
        "min": _r2(min(values)),
        "p25": _r2(p25),
        "median": _r2(median),
        "p75": _r2(p75),
        "max": _r2(max(values)),
        "mean": _r2(statistics.fmean(values)),
        "total_payroll": _r2(sum(values)),
    }


def histogram(values: list[float], bins: int) -> list[dict]:
    """Equal-width bins; each is [lower, upper) except the last, which includes upper."""
    if not values:
        return []
    low, high = min(values), max(values)
    if low == high:
        return [{"lower": _r2(low), "upper": _r2(high), "count": len(values)}]
    width = (high - low) / bins
    counts = [0] * bins
    for value in values:
        index = min(int((value - low) / width), bins - 1)
        counts[index] += 1
    return [
        {
            "lower": _r2(low + i * width),
            "upper": _r2(high if i == bins - 1 else low + (i + 1) * width),
            "count": count,
        }
        for i, count in enumerate(counts)
    ]


def deviation(salary: float, median: float) -> float:
    """Signed relative distance from the median, rounded to 4 dp."""
    return round((salary - median) / median, 4)
