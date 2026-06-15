from dataclasses import dataclass, field
from pathlib import Path

from gads.engine import CommitRecord, get_commit_history, scan_for_repos


@dataclass(slots=True)
class RepoActivity:
    path: Path
    name: str
    commits: list[CommitRecord] = field(default_factory=list)


@dataclass(slots=True)
class GlobalSummary:
    total_repos_scanned: int
    active_repos_count: int
    total_commits: int = 0
    total_additions: int = 0
    total_deletions: int = 0
    activity_by_repo: list[RepoActivity] = field(default_factory=list)


def harvest_workspace_metrics(
    root_path: Path, days: int, branch: str | None = None
) -> GlobalSummary:
    """
    Scans a root directory context recursively, harvesting chronological
    commit data and aggregating line changes across all active repositories.
    """
    discovered = scan_for_repos(root_path, recursive=True)

    summary = GlobalSummary(
        total_repos_scanned=len(discovered),
        active_repos_count=0,
    )

    if not discovered:
        return summary

    for repo_path, repo_instance in discovered:
        try:
            history = get_commit_history(repo_instance, since_days=days, branch=branch)

            if not history:
                continue

            repo_activity = RepoActivity(
                path=repo_path, name=repo_path.name, commits=history
            )
            summary.activity_by_repo.append(repo_activity)

            summary.active_repos_count += 1
            for record in history:
                summary.total_commits += 1
                summary.total_additions += record.additions
                summary.total_deletions += record.deletions
        finally:
            repo_instance.close()

    return summary
