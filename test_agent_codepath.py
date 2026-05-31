"""
End-to-end test: drive the real agent with a question that should make Claude
reach for the run_python tool. Confirms the tool is registered and the loop
handles it. Makes one Anthropic API call.

    python test_agent_codepath.py
"""

from agent import run_agent

question = (
    "Here are daily sessions for 5 days: 120, 95, 140, 0, 200. "
    "Use Python to compute the mean, median and standard deviation, "
    "and tell me which day looks like an outlier."
)

print(f"you> {question}\n")
print("agent>", run_agent(question))
