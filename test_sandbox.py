"""
Standalone test for the secure code-execution sandbox without claude.

Checks three things:
  1. Normal run: pandas works and `data` (input_data) is available.
  2. Network is really blocked (a fetch attempt must fail).
  3. The timeout actually kills an infinite loop.
"""

import json
from tools.sandbox import run_python


def show(title, result):
    print(f"\n=== {title} ===")
    print(json.dumps(result, indent=2))


#1) normal analysis: sum sessions across fake GA4 rows using pandas
fake_rows = [
    {"country": "Slovakia", "sessions": "120"},
    {"country": "Czechia", "sessions": "80"},
    {"country": "Poland", "sessions": "50"},
]
code_ok = """
import pandas as pd
df = pd.DataFrame(data)              #`data` is the input_data we passed in
df["sessions"] = df["sessions"].astype(int)
print("total sessions:", df["sessions"].sum())
print("top country:", df.loc[df["sessions"].idxmax(), "country"])
"""
show("1. normal pandas run", run_python(code_ok, input_data=fake_rows))

#2) network must be blocked, this shouldnt succeed
code_net = """
import urllib.request
urllib.request.urlopen("http://example.com", timeout=5)
print("network worked")
"""
show("2. network blocked (expect an error in stderr)", run_python(code_net))

#3) infinite loop must hit the timeout
code_loop = "while True:\n    pass\n"
show("3. timeout (expect timed_out: true)", run_python(code_loop))
