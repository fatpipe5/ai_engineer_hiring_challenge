"""
run_python: execute the agent's self-written Python code SAFELY.

The agent (an LLM) can generate arbitrary code, so we treat that code as
untrusted and run it inside a throwaway, locked-down Docker container:

  - no network            -> can't leak data or download anything
  - read-only filesystem  -> can't tamper with anything that persists
  - non-root, no caps      -> no privileges to escalate
  - memory / cpu / pid caps -> a runaway loop can't freeze the machine
  - hard timeout           -> infinite loops get killed
  - NO secrets passed in   -> your API keys / gcloud creds stay on the host

Data flow: the agent fetches GA4 data on the host with get_ga4_data, then
passes those rows here as `input_data`. We drop them into the container as a
file, and the agent's code can read them via the pre-loaded `data` variable.
The container only ever sees the numbers, never the credentials.

We write the script + data to a temp folder on the host and bind-mount it into
the container READ-ONLY at /workspace. The container can read its inputs but
can't modify them, and its only writable space is an in-memory /tmp.
"""

import json
import shutil
import subprocess
import tempfile
import uuid

# ---- knobs you can tune ----------------------------------------------------
IMAGE = "ga4-agent-sandbox"   # built from sandbox/Dockerfile
TIMEOUT_SECONDS = 30          # max wall-clock time for the code to run
MEMORY = "512m"               # max RAM
CPUS = "1"                    # max CPU cores
PIDS_LIMIT = "128"            # max processes/threads (stops fork bombs)
MAX_OUTPUT_CHARS = 10_000     # trim huge output so it can't flood the LLM context

# A tiny preamble we put ABOVE the agent's code. It loads the data we passed in
# (if any) into a `data` variable, so the agent's code can just use `data`.
PREAMBLE = (
    "import json as _json\n"
    "try:\n"
    "    with open('/workspace/data.json') as _f:\n"
    "        data = _json.load(_f)\n"
    "except FileNotFoundError:\n"
    "    data = None\n"
)


def _run(cmd: list[str], timeout: int) -> subprocess.CompletedProcess:
    """Run a docker command, capturing output. Raises on timeout."""
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def run_python(code: str, input_data: dict | list | None = None) -> dict:
    """
    Execute `code` inside the locked-down Docker sandbox.

    code:       the Python source the agent wants to run. Whatever it prints to
                stdout is returned. A `data` variable holds `input_data`.
    input_data: optional GA4 rows (or any JSON-able value) to analyse.

    Returns {"stdout", "stderr", "exit_code", "timed_out"} on a normal run,
    or {"error": "<message>"} if the sandbox itself couldn't be started — same
    self-correcting shape the get_ga4_data tool uses.
    """
    # A unique, predictable container name so we can always clean it up.
    container = f"ga4-sandbox-{uuid.uuid4().hex[:12]}"

    # 1) Write the script (preamble + agent code) and the data to a temp folder.
    workdir = tempfile.mkdtemp(prefix="ga4-sandbox-")
    try:
        script_path = f"{workdir}/script.py"
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(PREAMBLE + "\n" + code)

        data_path = f"{workdir}/data.json"
        with open(data_path, "w", encoding="utf-8") as f:
            json.dump(input_data, f)

        # 2) Run the container with all the safety limits. The temp folder is
        #    bind-mounted READ-ONLY at /workspace, so the code can read script.py
        #    and data.json but can't change them. --rm auto-deletes it on exit.
        run_cmd = [
            "docker", "run", "--rm",
            "--name", container,
            "--network", "none",                     # no internet at all
            "--read-only",                           # root filesystem is read-only
            "--tmpfs", "/tmp:rw,size=64m",           # small writable scratch space
            "--mount", f"type=bind,source={workdir},target=/workspace,readonly",
            "--memory", MEMORY,
            "--memory-swap", MEMORY,                 # = memory -> disable swap
            "--cpus", CPUS,
            "--pids-limit", PIDS_LIMIT,
            "--cap-drop", "ALL",                     # drop all Linux capabilities
            "--security-opt", "no-new-privileges",   # can't gain privileges
            "-e", "HOME=/tmp",                       # libs that write to HOME use /tmp
            "-e", "MPLCONFIGDIR=/tmp",
            IMAGE,
            "python", "/workspace/script.py",
        ]
        try:
            result = _run(run_cmd, timeout=TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            return {
                "stdout": "",
                "stderr": f"Execution exceeded {TIMEOUT_SECONDS}s and was stopped.",
                "exit_code": None,
                "timed_out": True,
            }

        # Docker's OWN startup errors (bad image, daemon down) are printed on
        # stderr prefixed with "docker:". Tell those apart from the code failing.
        if result.returncode != 0 and result.stderr.lstrip().startswith("docker:"):
            return {"error": _explain_docker_error(result.stderr)}

        return {
            "stdout": _trim(result.stdout),
            "stderr": _trim(result.stderr),
            "exit_code": result.returncode,
            "timed_out": False,
        }

    except FileNotFoundError:
        # `docker` itself isn't installed / not on PATH.
        return {"error": "Docker not found. Is Docker Desktop installed and running?"}
    finally:
        # 5) Always clean up: kill+remove the container and delete temp files.
        subprocess.run(
            ["docker", "rm", "-f", container],
            capture_output=True, text=True,
        )
        shutil.rmtree(workdir, ignore_errors=True)


def _trim(text: str) -> str:
    """Keep output from flooding the LLM's context window."""
    if text and len(text) > MAX_OUTPUT_CHARS:
        return text[:MAX_OUTPUT_CHARS] + "\n...[output truncated]"
    return text


def _explain_docker_error(stderr: str) -> str:
    """Turn common docker errors into a friendlier hint."""
    msg = (stderr or "").strip()
    if "Unable to find image" in msg or "No such image" in msg:
        return (
            "Sandbox image not found. Build it once with: "
            "docker build -t ga4-agent-sandbox ./sandbox"
        )
    if "Cannot connect to the Docker daemon" in msg or "dockerDesktopLinuxEngine" in msg:
        return "Docker daemon not reachable. Start Docker Desktop and try again."
    return f"Could not create sandbox container: {msg}"
