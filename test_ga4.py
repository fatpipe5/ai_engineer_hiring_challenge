"""
Quick standalone test for the GA4 tool — no Claude involved.

Run it to confirm authentication (gcloud ADC) and property permissions work,
before wiring the agent on top. If this prints rows, the hard part is done.

    python test_ga4.py
"""

import json
from dotenv import load_dotenv
from tools.ga4 import get_ga4_data

# Load GA4_PROPERTY_ID (and friends) from the .env file into the environment.
load_dotenv()

# A simple, low-risk question: how many sessions / users in the last 7 days?
result = get_ga4_data(
    metrics=["sessions", "activeUsers"],
    date_ranges=[{"start_date": "7daysAgo", "end_date": "today"}],
)

print(json.dumps(result, indent=2))
