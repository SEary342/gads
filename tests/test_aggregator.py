from pathlib import Path

from gads.aggregator import GlobalSummary, harvest_workspace_metrics


def test_harvest_workspace_finds_both_repos(multi_repo_workspace: Path) -> None:
    """Both repos in the workspace are discovered and their commits harvested."""
    summary = harvest_workspace_metrics(multi_repo_workspace, days=7)

    assert isinstance(summary, GlobalSummary)
    assert summary.total_repos_scanned == 2
    assert summary.active_repos_count == 2
    assert summary.total_commits == 2


def test_harvest_workspace_totals_are_summed(multi_repo_workspace: Path) -> None:
    """total_additions and total_deletions correctly aggregate across repos."""
    summary = harvest_workspace_metrics(multi_repo_workspace, days=7)

    # Each fixture repo has exactly 1 commit adding lines with no prior content
    assert summary.total_additions > 0
    assert summary.total_deletions == 0


def test_harvest_workspace_day_window_excludes_old_commits(
    multi_repo_workspace: Path,
) -> None:
    """days=0 finds no commits since all fixture commits are at least 1 day old."""
    summary = harvest_workspace_metrics(multi_repo_workspace, days=0)

    assert summary.total_repos_scanned == 2
    assert summary.active_repos_count == 0
    assert summary.total_commits == 0
    assert summary.activity_by_repo == []


def test_harvest_workspace_empty_dir_returns_empty_summary(tmp_path: Path) -> None:
    """An empty directory (no repos) returns a zeroed-out GlobalSummary."""
    empty_dir = tmp_path / "empty_workspace"
    empty_dir.mkdir()

    summary = harvest_workspace_metrics(empty_dir, days=7)

    assert summary.total_repos_scanned == 0
    assert summary.active_repos_count == 0
    assert summary.total_commits == 0
    assert summary.activity_by_repo == []


def test_harvest_workspace_activity_by_repo_names(multi_repo_workspace: Path) -> None:
    """RepoActivity entries carry the correct repo directory names."""
    summary = harvest_workspace_metrics(multi_repo_workspace, days=7)

    names = {r.name for r in summary.activity_by_repo}
    assert names == {"repo_alpha", "repo_beta"}
