# CLI Performance Baseline

Captured: 2026-05-25 00:19:03 CDT

Environment:

- OS: macOS Darwin 25.5.0 arm64
- Python: 3.11.12
- Command: `uv run python scripts/benchmark_cli_startup.py`
- Measurement: fresh Python process per sample, one warmup run, five measured runs
- Data isolation: temporary config, data, and backup directories per task-count dataset

## Startup And Common Commands

| tasks | command | median ms | p95 ms | min ms | max ms | runs |
|---:|---|---:|---:|---:|---:|---:|
| 0 | todo --help | 507.64 | 516.04 | 497.75 | 516.04 | 5 |
| 0 | todo | 563.09 | 611.24 | 550.37 | 611.24 | 5 |
| 0 | todo list | 640.06 | 648.97 | 609.09 | 648.97 | 5 |
| 0 | todo add --dry-run | 536.61 | 577.04 | 518.41 | 577.04 | 5 |
| 100 | todo --help | 524.09 | 557.84 | 510.70 | 557.84 | 5 |
| 100 | todo | 619.21 | 672.77 | 593.88 | 672.77 | 5 |
| 100 | todo list | 618.90 | 639.83 | 579.91 | 639.83 | 5 |
| 100 | todo add --dry-run | 525.66 | 548.31 | 523.31 | 548.31 | 5 |
| 1,000 | todo --help | 524.47 | 540.63 | 487.77 | 540.63 | 5 |
| 1,000 | todo | 579.14 | 633.23 | 560.65 | 633.23 | 5 |
| 1,000 | todo list | 617.26 | 648.73 | 582.54 | 648.73 | 5 |
| 1,000 | todo add --dry-run | 515.24 | 535.62 | 494.53 | 535.62 | 5 |
| 10,000 | todo --help | 568.53 | 597.83 | 508.32 | 597.83 | 5 |
| 10,000 | todo | 581.02 | 627.45 | 541.41 | 627.45 | 5 |
| 10,000 | todo list | 631.25 | 656.64 | 608.41 | 656.64 | 5 |
| 10,000 | todo add --dry-run | 547.19 | 576.79 | 531.97 | 576.79 | 5 |

## Readout

Startup/import cost dominates the current measurements. The common commands stay in a narrow band even as the isolated inbox project grows from empty to 10,000 tasks. That means the next useful performance work is import profiling and lazy-loading, not task-volume caching.
