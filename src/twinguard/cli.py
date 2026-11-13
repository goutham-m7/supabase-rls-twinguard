"""Local composition root for the demo and upstream pack export."""

import argparse
import json
from pathlib import Path
import subprocess
from .controls import CONTROLS
from .export import export_pack, UPSTREAM
from .postgres import Cluster
from .report import render, summarize
from .runner import run_attempt
from .scenario import scenarios


def positive(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("runs must be positive")
    return number


def main():
    parser = argparse.ArgumentParser(
        description="Real PostgreSQL RLS repair conformance; local only"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    demo = commands.add_parser(
        "demo", help="run all 12 seeded tasks, safe/unsafe/no-tools controls"
    )
    demo.add_argument("--runs", type=positive, default=3)
    demo.add_argument("--out", type=Path, default=Path("artifacts"))
    export = commands.add_parser(
        "export-evals", help="write Supabase Evals regression scenario folders"
    )
    export.add_argument("destination", type=Path)
    args = parser.parse_args()
    if args.command == "export-evals":
        export_pack(args.destination)
        print(f"Exported 12 Supabase Evals scenarios to {args.destination}")
        return
    attempts = []
    with Cluster() as cluster:
        version = subprocess.check_output(
            [str(cluster.bin / "postgres"), "--version"], text=True
        ).strip()
        for label, control in CONTROLS.items():
            for task in scenarios():
                for run in range(1, args.runs + 1):
                    attempts.append(run_attempt(cluster, task, control, label, run))
    summary = summarize(attempts)
    args.out.mkdir(parents=True, exist_ok=True)
    result = {
        "engine": version,
        "upstream": UPSTREAM,
        "boundary": "real SQL/RLS; synthetic claims; deterministic candidate controls",
        "tasks": 12,
        "runs": args.runs,
        "summary": summary,
        "attempts": attempts,
    }
    (args.out / "results.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    (args.out / "report.html").write_text(render(attempts))
    print("RLS TwinGuard | real PostgreSQL RLS | deterministic controls")
    print(f"12 seeded tasks x {args.runs} runs x 3 controls = {len(attempts)} isolated attempts")
    print("control     safe passes   happy path   unauthorized reads   unauthorized writes")
    for label, s in summary.items():
        print(
            f"{label:<10} {s['passed']:>2}/{s['attempts']:<10} {s['happy_path']:>2}/{s['attempts']:<8} {s['unauthorized_reads']:>10} {s['unauthorized_writes']:>21}"
        )
    print("Leak counts are unexpected row observations, never averaged into success.")
    print("Synthetic claims + deterministic repairs; no hosted service or LLM measured.")
    print(f"Evidence: {args.out / 'results.json'} and {args.out / 'report.html'}")
    expected = {"safe": 12 * args.runs, "unsafe": 0, "no-tools": 2 * args.runs}
    if any(summary[label]["passed"] != value for label, value in expected.items()):
        raise SystemExit("Control regression: observed verdicts differ from the specified oracle")
