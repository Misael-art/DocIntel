"""
DocIntel - Continuity supervisor for Stage 3.

Responsibilities:
  - monitor Stage 3 progress via status_execucao.md
  - relaunch run_extraction.py if progress is incomplete and no extractor is running
  - trigger supervise_post_extraction.py once Stage 3 is complete
  - never execute copy/apply actions automatically
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime

from config.settings import LOGS_DIR, ORGANIZATION_REPORTS_DIR, REPORTS_DIR
from docintel.observability import get_logger


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
RUN_SCRIPT = os.path.join(ROOT_DIR, "run_extraction.py")
POST_SCRIPT = os.path.join(ROOT_DIR, "supervise_post_extraction.py")
STATUS_REPORT = os.path.join(REPORTS_DIR, "status_execucao.md")
STATE_PATH = os.path.join(ORGANIZATION_REPORTS_DIR, "continuity_state.json")
SUPERVISOR_LOG = os.path.join(LOGS_DIR, "continuity_supervisor.log")
EXTRACTION_RESUME_LOG = os.path.join(LOGS_DIR, "run_extraction_resume.log")

DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_NO_WINDOW = 0x08000000

LOGGER = get_logger("docintel.continuity_supervisor", os.path.join(LOGS_DIR, "continuity_supervisor.jsonl"))


def parse_args():
    parser = argparse.ArgumentParser(description="Keep Stage 3 running until safe post-processing is ready.")
    parser.add_argument("--poll-seconds", type=int, default=60,
                        help="Polling interval while monitoring.")
    parser.add_argument("--once", action="store_true",
                        help="Run a single supervision cycle and exit.")
    return parser.parse_args()


def log(message: str):
    os.makedirs(LOGS_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {message}"
    print(line)
    LOGGER.info(message)
    with open(SUPERVISOR_LOG, "a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def read_state() -> dict:
    if not os.path.exists(STATE_PATH):
        return {"post_processing_done": False, "launch_count": 0}
    with open(STATE_PATH, "r", encoding="utf-8") as handle:
        return json.load(handle)


def write_state(state: dict):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=True, indent=2)


def read_status() -> dict | None:
    if not os.path.exists(STATUS_REPORT):
        return None

    raw = open(STATUS_REPORT, "r", encoding="utf-8").read()
    match = re.search(r"\*\*Arquivos Processados\*\* \| ([0-9,]+) / ([0-9,]+)", raw)
    ts_match = re.search(r"Ultima atualizacao: ([^\n]+)", raw)
    if not match:
        return None

    processed = int(match.group(1).replace(",", ""))
    total = int(match.group(2).replace(",", ""))
    return {
        "processed": processed,
        "total": total,
        "pending": max(total - processed, 0),
        "updated_at": ts_match.group(1).strip() if ts_match else "",
    }


def extractor_running() -> bool:
    cmd = (
        "$p = Get-CimInstance Win32_Process | "
        "Where-Object { $_.Name -match 'python|py' -and $_.CommandLine -match 'run_extraction\\.py' }; "
        "($p | Measure-Object).Count"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", cmd],
        capture_output=True,
        text=True,
        cwd=ROOT_DIR,
        timeout=20,
        check=False,
    )
    try:
        return int((result.stdout or "0").strip()) > 0
    except ValueError:
        return False


def launch_extractor(state: dict, reason: str):
    os.makedirs(LOGS_DIR, exist_ok=True)
    out = open(EXTRACTION_RESUME_LOG, "a", encoding="utf-8")
    subprocess.Popen(
        [sys.executable, RUN_SCRIPT],
        cwd=ROOT_DIR,
        stdout=out,
        stderr=out,
        creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW,
        close_fds=True,
    )
    state["launch_count"] = int(state.get("launch_count", 0)) + 1
    state["last_launch_at"] = datetime.now().isoformat(timespec="seconds")
    state["last_launch_reason"] = reason
    write_state(state)
    log(f"Extractor launched. Reason: {reason}")


def run_post_processing(state: dict):
    log("Stage 3 complete. Running safe post-processing supervisor without apply/copy.")
    subprocess.run([sys.executable, POST_SCRIPT], check=True, cwd=ROOT_DIR)

    state["post_processing_done"] = True
    state["organization_planned"] = True
    state["post_processed_at"] = datetime.now().isoformat(timespec="seconds")
    write_state(state)


def supervision_cycle(state: dict) -> tuple[bool, dict]:
    status = read_status()
    running = extractor_running()

    if not status:
        if not running:
            launch_extractor(state, "status_execucao.md missing or unreadable")
        else:
            log("Status unreadable, but extractor process is running.")
        return False, state

    log(
        f"Status check: {status['processed']:,}/{status['total']:,} processed, "
        f"{status['pending']:,} pending, updated at {status['updated_at'] or 'unknown'}."
    )

    if status["pending"] > 0:
        if running:
            log("Extractor is active. Monitoring will continue.")
        else:
            launch_extractor(state, f"{status['pending']:,} pending and no extractor process detected")
        return False, state

    if not state.get("post_processing_done"):
        run_post_processing(state)
    else:
        log("Stage 3 already complete and post-processing was already executed.")
    return True, state


def main():
    args = parse_args()
    state = read_state()

    while True:
        completed, state = supervision_cycle(state)
        if args.once or completed:
            break
        time.sleep(max(15, int(args.poll_seconds)))


if __name__ == "__main__":
    main()
