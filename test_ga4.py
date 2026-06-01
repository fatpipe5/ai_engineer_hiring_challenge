"""
Quick standalone test for the GA4 tool to confirm authentication (gcloud ADC) and property permissions work,
before adding the claude agent
"""

import json
from dotenv import load_dotenv
from tools.ga4 import get_ga4_data

load_dotenv()

result = get_ga4_data(
    metrics=["sessions", "activeUsers"],
    date_ranges=[{"start_date": "7daysAgo", "end_date": "today"}],
)

print(json.dumps(result, indent=2))
