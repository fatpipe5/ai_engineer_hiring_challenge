import os
import json
from anthropic import Anthropic
from dotenv import load_dotenv
from tools.ga4 import get_ga4_data
from tools.sandbox import run_python


load_dotenv()
MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
client = Anthropic()

SYSTEM_PROMPT = """You are a Google Analytics 4 (GA4) data assistant.

Given a question about a website's analytics, you:
- Choose the right GA4 metrics (e.g. sessions, activeUsers, screenPageViews) and
  dimensions (e.g. country, pagePath, date) for the question.
- Call the get_ga4_data tool to fetch real data.
- Explain the results in clear, plain language. Don't just dump raw numbers.

Dates may be absolute ("2024-01-31") or relative GA4 keywords like "today",
"yesterday", or "7daysAgo". Prefer relative dates when the user is vague.

For advanced work that's awkward to do in your head -- multi-step math,
growth/trend percentages, sorting/ranking many rows, correlations, reshaping,
or forecasting -- use the run_python tool:
- First fetch the numbers with get_ga4_data.
- Then call run_python, passing those rows as `input_data`. Inside the code
  they are available as a variable named `data`. print() whatever you want back.
- The sandbox has pandas and numpy, but NO internet and NO access to GA4 or any
  credentials -- so always fetch data first and pass it in; don't try to call
  GA4 from inside the code.

If a tool returns an {"error": ...}, read it, fix your request, and try again."""

TOOLS = [
    {
        "name": "get_ga4_data",
        "description": (
            "Fetch analytics data from Google Analytics 4. Returns rows of "
            "metrics optionally sliced by dimensions, for the given date ranges."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "metrics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "GA4 metric names, e.g. ['sessions', 'activeUsers'].",
                },
                "date_ranges": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "start_date": {"type": "string"},
                            "end_date": {"type": "string"},
                        },
                        "required": ["start_date", "end_date"],
                    },
                    "description": "One or more date ranges. Dates are YYYY-MM-DD or "
                    "relative keywords like 'today', 'yesterday', '7daysAgo'.",
                },
                "dimensions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional GA4 dimensions to slice by, e.g. ['country'].",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max rows to return (default 1000).",
                },
            },
            "required": ["metrics", "date_ranges"],
        },
    },
    {
        "name": "run_python",
        "description": (
            "Run Python code in a secure, isolated sandbox (has pandas & numpy, "
            "but no internet and no credentials). Use it for advanced analysis of "
            "data you already fetched with get_ga4_data. Pass the rows as "
            "input_data; inside the code they are available as the variable `data`. "
            "Whatever the code print()s is returned to you."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The Python source to execute. print() your results.",
                },
                "input_data": {
                    "type": ["object", "array", "null"],
                    "description": "JSON data to analyse, exposed in the code as `data`. "
                    "Usually the 'rows' returned by get_ga4_data.",
                },
            },
            "required": ["code"],
        },
    },
]

TOOL_FUNCTIONS = {
    "get_ga4_data": get_ga4_data,
    "run_python": run_python,
}


def run_tool(name: str, tool_input: dict) -> dict:
    func = TOOL_FUNCTIONS.get(name)
    if func is None:
        return {"error": f"Unknown tool: {name}"}
    return func(**tool_input)


def run_agent(question: str) -> str:
    """Run the full agent loop for one question and return the final text answer."""
    messages = [{"role": "user", "content": question}]      #the conversation so far, we keep appending to this list each turn

    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        messages.append({"role": "assistant", "content": response.content})     #record claudes turn (text and/or tool-use requests) in the history

        if response.stop_reason != "tool_use":
            return "".join(
                block.text for block in response.content if block.type == "text"
            )

        #run every tool claude asked for this turn, collecting the results
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                print(f"  [agent calls {block.name}({json.dumps(block.input)})]")
                result = run_tool(block.name, block.input)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,  #links the result to the request
                        "content": json.dumps(result),
                    }
                )

        messages.append({"role": "user", "content": tool_results})


if __name__ == "__main__":
    print("GA4 agent ready. Ask a question (Ctrl+C to quit).\n")
    while True:
        try:
            question = input("you> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nbye")
            break
        if not question:
            continue
        answer = run_agent(question)
        print(f"\nagent> {answer}\n")
