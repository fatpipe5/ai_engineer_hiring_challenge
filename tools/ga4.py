import os
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    RunReportRequest,
    Metric,
    Dimension,
    DateRange,
)


def get_ga4_data(
    metrics: list[str],
    date_ranges: list[dict],
    dimensions: list[str] | None = None,
    limit: int = 1000,
) -> dict:
    """
    Fetch data from GA4.


    metrics: e.g. ["sessions", "activeUsers", "screenPageViews"]
    date_ranges: e.g. [{"start_date": "2024-01-01", "end_date": "2024-01-31"}]
    dimensions: e.g. ["pagePath", "country"] - optional
    limit: max rows to return (protects context size)

    On success returns {"metrics", "dimensions", "rows", "row_count", "truncated"}.
    On failure returns {"error": "<message>"} so the agent can read it and retry.
    """
    dimensions = dimensions or []

    property_id = os.getenv("GA4_PROPERTY_ID")
    if not property_id:
        return {"error": "GA4_PROPERTY_ID is not set in the environment."}

    try:
        client = BetaAnalyticsDataClient()

        request = RunReportRequest(
            property=f"properties/{property_id}",
            metrics=[Metric(name=m) for m in metrics],
            date_ranges=[
                DateRange(start_date=dr["start_date"], end_date=dr["end_date"])
                for dr in date_ranges
            ],
            dimensions=[Dimension(name=d) for d in dimensions],
            limit=limit,
        )

        response = client.run_report(request)
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}

    result = {
        "metrics": metrics,
        "dimensions": dimensions,
        "rows": [],
        "row_count": response.row_count,
        "truncated": response.row_count > len(response.rows),
    }

    for row in response.rows:
        parsed_row = {}
        for i, dim_value in enumerate(row.dimension_values):
            parsed_row[dimensions[i]] = dim_value.value
        for i, metric_value in enumerate(row.metric_values):
            parsed_row[metrics[i]] = metric_value.value
        result["rows"].append(parsed_row)

    return result
