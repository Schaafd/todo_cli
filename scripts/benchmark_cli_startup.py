#!/usr/bin/env python3
"""Benchmark common Todo CLI startup paths against isolated datasets."""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"


@dataclass(frozen=True)
class CommandCase:
    name: str
    args: tuple[str, ...]


COMMANDS = (
    CommandCase("todo --help", ("--help",)),
    CommandCase("todo", ()),
    CommandCase("todo list", ("list",)),
    CommandCase(
        "todo add --dry-run",
        ("add", "Benchmark task @bench due tomorrow", "--dry-run"),
    ),
)


def percentile(values: list[float], pct: float) -> float:
    """Return a percentile from a non-empty list using nearest-rank indexing."""
    if not values:
        raise ValueError("percentile requires at least one value")
    sorted_values = sorted(values)
    index = round((pct / 100) * (len(sorted_values) - 1))
    return sorted_values[index]


def write_config(root: Path) -> Path:
    """Create an isolated config file for one benchmark dataset."""
    data_dir = root / "data"
    backup_dir = root / "backups"
    config_path = root / "config.yaml"
    data_dir.mkdir(parents=True, exist_ok=True)
    backup_dir.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        "\n".join(
            [
                "default_project: inbox",
                f"data_dir: {data_dir}",
                f"backup_dir: {backup_dir}",
                "theme_name: city_lights",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return config_path


def seed_tasks(config_path: Path, count: int) -> None:
    """Populate the isolated inbox project with benchmark tasks."""
    if count == 0:
        return

    sys.path.insert(0, str(SRC))
    from todo_cli.config import ConfigModel
    from todo_cli.domain import Priority, Project, Todo
    from todo_cli.storage import Storage

    data_dir = config_path.parent / "data"
    backup_dir = config_path.parent / "backups"
    config = ConfigModel(data_dir=str(data_dir), backup_dir=str(backup_dir))
    storage = Storage(config)
    project = Project(name="inbox", display_name="Inbox")

    priorities = [Priority.CRITICAL, Priority.HIGH, Priority.MEDIUM, Priority.LOW]
    todos = [
        Todo(
            id=index + 1,
            text=f"Benchmark task {index + 1}",
            project="inbox",
            tags=["bench", f"batch{index % 10}"],
            context=["cli"],
            priority=priorities[index % len(priorities)],
            completed=(index % 5 == 0),
        )
        for index in range(count)
    ]
    storage.save_project(project, todos)


def command_argv(config_path: Path, case: CommandCase) -> list[str]:
    """Build the subprocess command for a benchmark case."""
    code = "from todo_cli.cli import main; main()"
    return [
        sys.executable,
        "-c",
        code,
        "--config",
        str(config_path),
        *case.args,
    ]


def run_once(config_path: Path, case: CommandCase, timeout: int) -> float:
    """Run one command once and return elapsed milliseconds."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(SRC)
    env["NO_COLOR"] = "1"
    start = time.perf_counter()
    result = subprocess.run(
        command_argv(config_path, case),
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
    )
    elapsed_ms = (time.perf_counter() - start) * 1000
    if result.returncode != 0:
        raise RuntimeError(
            f"{case.name} failed with exit {result.returncode}: {result.stderr.strip()}"
        )
    return elapsed_ms


def benchmark_case(
    config_path: Path,
    case: CommandCase,
    warmups: int,
    runs: int,
    timeout: int,
) -> dict[str, Any]:
    """Benchmark one command case."""
    for _ in range(warmups):
        run_once(config_path, case, timeout)

    samples = [run_once(config_path, case, timeout) for _ in range(runs)]
    return {
        "command": case.name,
        "median_ms": round(statistics.median(samples), 2),
        "p95_ms": round(percentile(samples, 95), 2),
        "min_ms": round(min(samples), 2),
        "max_ms": round(max(samples), 2),
        "runs": runs,
    }


def benchmark_dataset(
    task_count: int,
    warmups: int,
    runs: int,
    timeout: int,
) -> dict[str, Any]:
    """Create one dataset and benchmark all command cases against it."""
    with tempfile.TemporaryDirectory(prefix=f"todo-cli-bench-{task_count}-") as tmp:
        root = Path(tmp)
        config_path = write_config(root)
        seed_tasks(config_path, task_count)
        return {
            "task_count": task_count,
            "commands": [
                benchmark_case(config_path, case, warmups, runs, timeout)
                for case in COMMANDS
            ],
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--task-counts",
        default="0,100,1000,10000",
        help="Comma-separated task counts to benchmark.",
    )
    parser.add_argument("--runs", type=int, default=5, help="Measured runs per case.")
    parser.add_argument("--warmups", type=int, default=1, help="Warmup runs per case.")
    parser.add_argument("--timeout", type=int, default=60, help="Per-command timeout.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of markdown.")
    args = parser.parse_args()

    task_counts = [int(value.strip()) for value in args.task_counts.split(",") if value.strip()]
    results = [
        benchmark_dataset(count, args.warmups, args.runs, args.timeout)
        for count in task_counts
    ]

    if args.json:
        print(json.dumps({"datasets": results}, indent=2))
        return

    print("| tasks | command | median ms | p95 ms | min ms | max ms | runs |")
    print("|---:|---|---:|---:|---:|---:|---:|")
    for dataset in results:
        for command in dataset["commands"]:
            print(
                "| {tasks} | {command} | {median:.2f} | {p95:.2f} | "
                "{min_ms:.2f} | {max_ms:.2f} | {runs} |".format(
                    tasks=dataset["task_count"],
                    command=command["command"],
                    median=command["median_ms"],
                    p95=command["p95_ms"],
                    min_ms=command["min_ms"],
                    max_ms=command["max_ms"],
                    runs=command["runs"],
                )
            )


if __name__ == "__main__":
    main()
