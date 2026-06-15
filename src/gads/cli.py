import importlib.metadata
from pathlib import Path

import typer

from gads.aggregator import harvest_workspace_metrics
from gads.engine import get_commit_history, get_repo_instance, scan_for_repos

try:
    __version__ = importlib.metadata.version("gads")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.1-dev"


def version_callback(value: bool) -> None:
    """Prints the application version and safely aborts execution."""
    if value:
        typer.echo(f"gads version {__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="gads",
    help=f"Git Author & Date Statistics aggregator (v{__version__})",
    no_args_is_help=True,
)


@app.callback()
def base_options(
    version: bool | None = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show tool version and exit.",
    ),
) -> None:
    """Global options shared across all gads commands."""


@app.command(name="log")
def log(
    path: Path = typer.Argument(
        Path("."),
        help="Target directory containing the git repository.",
    ),
    branch: str | None = typer.Option(
        None,
        "--branch",
        "-b",
        help="Target branch name (falls back to main -> master -> HEAD).",
    ),
    days: int | None = typer.Option(
        None,
        "--days",
        "-d",
        help="Number of days back to scan for commits.",
    ),
) -> None:
    """Extract and aggregate high-fidelity git metrics for a repository branch."""
    repo = get_repo_instance(path)
    if not repo:
        typer.secho(
            f"Error: '{path}' is not a valid Git repository.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    try:
        history = get_commit_history(repo, since_days=days, branch=branch)
        if not history:
            typer.echo("No records returned for current selection parameters.")
            return

        for record in history:
            typer.echo(
                f"{record.hash} | {record.date:%Y-%m-%d} | {record.author:<15} "
                f"| +{record.additions:<4} | -{record.deletions:<4}"
            )
    finally:
        repo.close()


@app.command(name="list")
def list_repos(
    path: Path = typer.Argument(
        Path("."),
        help="Base directory to start scanning from.",
    ),
    recursive: bool = typer.Option(
        False,
        "--recursive",
        "-r",
        help=("Recursively walk down subdirectories looking for valid repositories."),
    ),
) -> None:
    """Scan a directory space and list discovered valid Git repositories."""
    discovered = scan_for_repos(path, recursive=recursive)
    if not discovered:
        typer.echo("No valid Git repositories found in the target directory context.")
        return

    typer.echo(f"Discovered {len(discovered)} repository context(s):")
    typer.echo("-" * 60)

    # Unify the user's targeted input path to its underlying canonical format
    resolved_target = path.resolve()

    for repo_path, repo_instance in discovered:
        try:
            resolved_repo = repo_path.resolve()

            # Mask paths relative to the scan's root directory anchor
            if resolved_repo.is_relative_to(resolved_target):
                display_path = resolved_repo.relative_to(resolved_target)
                if str(display_path) == ".":
                    display_path = Path(resolved_repo.name)
            else:
                # Absolute fallback if it somehow escapes the target boundary
                display_path = repo_path

            typer.echo(f"• {display_path}")
        finally:
            repo_instance.close()


@app.command(name="aggregate")
def aggregate(
    path: Path = typer.Argument(
        Path("."),
        help="Root directory containing multiple project repositories.",
    ),
    days: int = typer.Option(
        7,
        "--days",
        "-d",
        help="Number of days back to collect history across all discovered repos.",
    ),
    branch: str | None = typer.Option(
        None,
        "--branch",
        "-b",
        help="Override to target a specific branch name globally across repositories.",
    ),
) -> None:
    """Scan a directory space recursively and harvest commit metrics."""
    typer.echo(f"Scanning for repositories under: {path.resolve().name}")

    summary = harvest_workspace_metrics(path, days=days, branch=branch)

    if not summary.activity_by_repo:
        typer.echo(
            "No active commits found across any workspaces "
            "within the specified day window."
        )
        return

    typer.echo(
        f"Found {summary.total_repos_scanned} repositories. "
        "Processing history summaries...\n"
    )

    resolved_target = path.resolve()

    for repo in summary.activity_by_repo:
        resolved_repo = repo.path.resolve()

        # Mask paths relative to the scan's root directory anchor
        if resolved_repo.is_relative_to(resolved_target):
            display_path = resolved_repo.relative_to(resolved_target)
            if str(display_path) == ".":
                display_path = Path(resolved_repo.name)
        else:
            display_path = repo.path

        typer.secho(f"📁 {repo.name}", fg=typer.colors.CYAN, bold=True)
        typer.echo(f"Location: {display_path}")
        typer.echo("-" * 50)

        for record in repo.commits:
            typer.echo(
                f"  [{record.hash}] {record.date:%Y-%m-%d} | {record.author:<15} "
                f"(+{record.additions}, -{record.deletions})"
            )
        typer.echo()

    active_ratio = f"{summary.active_repos_count} / {summary.total_repos_scanned}"
    changes_str = f"+{summary.total_additions} lines, -{summary.total_deletions} lines"

    typer.secho(
        "============ Global Summary ============",
        fg=typer.colors.GREEN,
        bold=True,
    )
    typer.echo(f"Total Repos with Activity: {active_ratio}")
    typer.echo(f"Total Combined Commits:    {summary.total_commits}")
    typer.echo(f"Total Code Changes:        {changes_str}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
