# Image for running the AI agent's self-written Python code in isolation.
#
# Build it once (from the project root) with:
#     docker build -t ga4-agent-sandbox ./sandbox
#
# It's deliberately minimal: a small Python plus the data libraries the agent
# is likely to want (pandas/numpy). No network tools, no project code, no secrets.

FROM python:3.13-slim

# Data-analysis libraries the agent can use for "advanced" work.
# Pinned-ish so the image is reproducible.
RUN pip install --no-cache-dir pandas==2.2.3 numpy==2.1.3

# Create an unprivileged user. Code must NOT run as root inside the container,
# so that even if something escapes the Python process it has no power.
RUN useradd --create-home --uid 1000 sandboxuser
USER sandboxuser

# Where the agent's script + data get copied to and run from.
WORKDIR /workspace

# No ENTRYPOINT/CMD: we always pass the exact command at `docker run` time
# (python /workspace/script.py), so the image can't be relied on to auto-run.
