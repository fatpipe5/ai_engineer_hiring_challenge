# GA4 AI Agent

An AI agent, powered by Claude, that answers questions about a
website's **Google Analytics 4 (GA4)** data. It picks the right metrics for the
question, fetches the data from the GA4 Data API, and when a question needs
more than simple lookups it writes its own Python code and runs it in a secure,
isolated Docker sandbox. It can also export the answer to a PDF report.

```
you> How did sessions trend over the last 7 days, and which day was an outlier?
  [agent calls get_ga4_data({"metrics": ["sessions"], "dimensions": ["date"], ...})]
  [agent calls run_python({"code": "import pandas as pd ...", "input_data": [...]})]
agent> Sessions averaged ~110/day. Wednesday was a clear outlier at 200 (about
       1.8x the mean) ...
```

## What it does

- **Accesses GA4 data**: metrics, dimensions, and date ranges via the GA4 Data API.
- **Returns results in plain language** instead of raw number dumps.
- **Writes and runs its own Python** for advanced work inside a sandbox.
- **Exports the answers to PDF** 

## Architecture

The agent utilizes the Claude API: we send Claude the
question plus a list of tools, then Claude either answers or asks to call a tool. We
run the tool, hand back the result, and repeat until it gives a final answer.

```
                ┌────────────────── agent.py (the loop) ──────────────────┐
   you ──▶ question ──▶ Claude ──▶ wants a tool? ──▶ run it ──▶ result ──┐  │
                          ▲                                              │  │
                          └──────────────────────────────────────────────┘  │
                                       (repeat until final answer)         │
                └──────────────────────────────────────────────────────────┘
                                    │            │            │
                            get_ga4_data    run_python     export_pdf
                            (GA4 Data API)  (Docker sandbox) (fpdf2 -> PDF)
```

| File | Role |
|------|------|
| `agent.py` | The agent loop, tool schemas, system prompt, and a CLI |
| `tools/ga4.py` | `get_ga4_data` — fetch metrics/dimensions from GA4 |
| `tools/sandbox.py` | `run_python` — run agent-written code in an isolated container |
| `tools/report.py` | `export_pdf` — render an answer to a PDF |
| `sandbox/Dockerfile` | The minimal, non-root image the sandbox runs in |

## Security

- No secrets are committed. `.env`, `oauth_client.json`, and generated
  `reports/` are git-ignored; only `.env.example` (with placeholders) is tracked.

**The agent's self-written Python is treated as untrusted** and runs in a
throwaway Docker container (`tools/sandbox.py`) that is:
- **network-isolated** (`--network none`) — code cant reach the internet or download anything
- **read-only** root filesystem, with only a small in-memory `/tmp`;
- **non-root** (`USER sandboxuser`) with **all Linux capabilities dropped**
  and `--no-new-privileges`;
- **resource-capped** — memory, CPU, and PID limits stop runaway code;
- **time-limited** — a hard timeout kills infinite loops;
- the container gets cleaned up after every run

## Prerequisites

- **Python 3.13+**
- **Docker** — for the code-execution sandbox
- **Google Cloud CLI (`gcloud`)** — for GA4 authentication
- An **Anthropic API key** and a **GA4 property** you have access to

## Setup

### 1. Install dependencies

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Authenticate to GA4 (gcloud user login)

This project reads GA4 as **you** (your Google account), not via a
service-account key. Install the [Google Cloud CLI](https://cloud.google.com/sdk/docs/install),
then log in with the Analytics scope:

```bash
gcloud auth application-default login \
  --scopes=https://www.googleapis.com/auth/analytics.readonly,https://www.googleapis.com/auth/cloud-platform

# Point billing/quota at a Google Cloud project that has the
# "Google Analytics Data API" enabled:
gcloud auth application-default set-quota-project YOUR_GCP_PROJECT_ID
```

Make sure the **Google Analytics Data API** is enabled for that project
(Cloud Console → APIs & Services → Library), and that your Google account has
at least **Viewer** access to the GA4 property.

> Why user login instead of a service account? Google currently has a
> [confirmed bug](https://piunikaweb.com/2026/05/01/google-service-account-email-not-found-bug/)
> that blocks adding new service accounts to GA4. User-based ADC
> sidesteps it.

### 3. Build the sandbox image (once)

```bash
docker build -t ga4-agent-sandbox ./sandbox
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Then edit `.env` and set `ANTHROPIC_API_KEY` and `GA4_PROPERTY_ID`.

## Run

```bash
python agent.py
```

Then ask questions, e.g.:
- `How many sessions and active users did the site get in the last 7 days?`
- `What were the top 5 pages by views last month?`
- `Show daily sessions for the last 14 days, compute the trend, and flag any outlier days.`
- `Summarize last week's traffic and save it as a PDF report.`

PDFs are written to the `reports/` folder.

## Tests

Each test is a standalone script (no external test runner needed):

```bash
python test_ga4.py             # GA4 auth + a real query (needs steps 2 & 4)
python test_sandbox.py         # sandbox: pandas works, network blocked, timeout kills loops (needs Docker)
```

## Sample output

```
you> Summarize sessions and active users for the last 7 days, and save it as a PDF.

  [agent calls get_ga4_data({"metrics": ["sessions", "activeUsers"],
                             "date_ranges": [{"start_date": "7daysAgo", "end_date": "today"}]})]
  [agent calls export_pdf({"title": "GA4 Weekly Traffic Summary", "content": "# GA4 ..."})]

agent> In the last 7 days the site had 1,240 sessions from 980 active users.
       I've saved a formatted summary to reports/ga4-weekly-traffic-summary-20260601-123154.pdf.
```

## Project layout

```
.
├── agent.py                 # agent loop + tool definitions + CLI
├── tools/
│   ├── ga4.py               # get_ga4_data  (GA4 Data API)
│   ├── sandbox.py           # run_python    (Docker sandbox)
│   └── report.py            # export_pdf    
├── sandbox/Dockerfile       # minimal non-root image for the sandbox
├── test_ga4.py
├── test_sandbox.py
├── requirements.txt
├── .env.example
└── README.md
```
