"""Bootstrap entrypoint for the DocIntel desktop launcher."""

from __future__ import annotations

import argparse
import json
import sys

from docintel.gui.runtime import collect_runtime_context, ensure_runtime_ready


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch the DocIntel desktop control center.")
    parser.add_argument(
        "--health-check",
        action="store_true",
        help="Validate the runtime environment and print a JSON summary without opening the GUI.",
    )
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Open the GUI briefly and close it automatically. Requires PySide6.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    ensure_runtime_ready()
    context = collect_runtime_context()

    if args.health_check:
        print(
            json.dumps(
                {
                    "repo_root": str(context.repo_root),
                    "python": context.python_executable,
                    "db_path": str(context.db_path),
                    "reports_dir": str(context.reports_dir),
                    "dashboard_path": str(context.dashboard_path),
                    "git_branch": context.git_branch,
                    "git_commit": context.git_commit,
                    "git_remote": context.git_remote,
                    "stage3_summary": context.stage3_summary,
                },
                ensure_ascii=True,
                indent=2,
            )
        )
        return 0

    try:
        from docintel.gui.app import run_gui
    except ModuleNotFoundError as exc:
        if exc.name == "PySide6":
            print(
                "[DocIntel] PySide6 nao esta disponivel. "
                "Instale as dependencias de GUI com: python -m pip install -e .[gui]",
                file=sys.stderr,
            )
            return 2
        raise

    return run_gui(smoke_test=args.smoke_test)


if __name__ == "__main__":
    raise SystemExit(main())
