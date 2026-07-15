"""Render a Report to the terminal / JSON."""
from __future__ import annotations

from .schema import Report


def to_json(report: Report) -> str:
    return report.model_dump_json(indent=2)


def print_human(report: Report) -> None:
    """Pretty terminal table of findings. Falls back to plain text if rich is absent."""
    try:
        from rich.console import Console
        from rich.table import Table
    except ImportError:  # rich is a listed dep, but degrade gracefully
        _print_plain(report)
        return

    console = Console()
    if not report.findings:
        console.print(f"[green]✓ {report.trace_id}: no MAST failure modes detected.[/green]")
        return

    table = Table(title=f"MAST findings — {report.trace_id}", show_lines=True)
    table.add_column("Mode", style="bold red", no_wrap=True)
    table.add_column("Name", no_wrap=True)
    table.add_column("Cat", no_wrap=True)
    table.add_column("Spans", no_wrap=True)
    table.add_column("Conf", justify="right", no_wrap=True)
    table.add_column("Rationale")

    for f in sorted(report.findings, key=lambda x: (x.failure_mode_id, -x.confidence)):
        table.add_row(
            f.failure_mode_id,
            f.failure_mode_name,
            f.category,
            ", ".join(f.span_ids),
            f"{f.confidence:.2f}",
            f.rationale,
        )

    console.print(table)
    console.print(
        f"[bold]{len(report.findings)} finding(s)[/bold] across "
        f"{len(report.modes_fired)} mode(s): {', '.join(report.modes_fired)}"
    )


def _print_plain(report: Report) -> None:
    if not report.findings:
        print(f"OK {report.trace_id}: no MAST failure modes detected.")
        return
    print(f"MAST findings — {report.trace_id}")
    for f in sorted(report.findings, key=lambda x: (x.failure_mode_id, -x.confidence)):
        print(f"  {f.failure_mode_id} {f.failure_mode_name} [{f.category}] "
              f"spans={','.join(f.span_ids)} conf={f.confidence:.2f}")
        if f.rationale:
            print(f"      {f.rationale}")
    print(f"{len(report.findings)} finding(s); modes: {', '.join(report.modes_fired)}")
