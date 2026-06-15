from pathlib import Path

from dulwich.refs import Ref
from dulwich.repo import Repo

from gads.engine import (
    get_commit_history,
    get_repo_instance,
    parse_patch_stats,
    safe_resolve_dir,
    scan_for_repos,
)

# ---------------------------------------------------------------------------
# safe_resolve_dir
# ---------------------------------------------------------------------------


def test_safe_resolve_dir_valid(temp_workspace: Path) -> None:
    """A real directory resolves cleanly."""
    resolved = safe_resolve_dir(temp_workspace)
    assert resolved == temp_workspace.resolve()


def test_safe_resolve_dir_invalid() -> None:
    """A non-existent path returns None without raising."""
    assert safe_resolve_dir(Path("/nonexistent/directory/path/here")) is None


def test_safe_resolve_dir_file_not_dir(tmp_path: Path) -> None:
    """A path that points to a file (not a directory) returns None."""
    f = tmp_path / "notadir.txt"
    f.write_text("hello")
    assert safe_resolve_dir(f) is None


# ---------------------------------------------------------------------------
# get_repo_instance
# ---------------------------------------------------------------------------


def test_get_repo_instance_valid(mock_git_repo: Path) -> None:
    """An initialized git path yields an operational Repo instance."""
    repo = get_repo_instance(mock_git_repo)
    assert isinstance(repo, Repo)
    if repo:
        repo.close()


def test_get_repo_instance_invalid(temp_workspace: Path) -> None:
    """A plain directory returns None instead of raising NotGitRepository."""
    assert get_repo_instance(temp_workspace) is None


# ---------------------------------------------------------------------------
# scan_for_repos
# ---------------------------------------------------------------------------


def test_scan_for_repos_finds_top_level(mock_git_repo: Path) -> None:
    """Scanning a repo root directly captures it."""
    found = scan_for_repos(mock_git_repo)
    assert len(found) == 1

    repo_path, repo_instance = found[0]
    assert repo_path == mock_git_repo
    assert isinstance(repo_instance, Repo)
    repo_instance.close()


def test_scan_for_repos_non_recursive_stops_at_first_repo(temp_workspace: Path) -> None:
    """With recursive=False, scanning stops after finding the first-level repo
    and does not descend into nested sub-repositories."""
    parent_dir = temp_workspace / "parent_project"
    parent_dir.mkdir()
    Repo.init(str(parent_dir)).close()

    nested_dir = parent_dir / "nested_submodule"
    nested_dir.mkdir()
    Repo.init(str(nested_dir)).close()

    found = scan_for_repos(temp_workspace, recursive=False)

    assert len(found) == 1
    repo_path, repo_instance = found[0]
    assert repo_path == parent_dir
    assert isinstance(repo_instance, Repo)
    repo_instance.close()


def test_scan_for_repos_recursive_keeps_digging(temp_workspace: Path) -> None:
    """With recursive=True, both parent and nested repos are discovered."""
    parent_dir = temp_workspace / "parent_project"
    parent_dir.mkdir()
    Repo.init(str(parent_dir)).close()

    nested_dir = parent_dir / "nested_submodule"
    nested_dir.mkdir()
    Repo.init(str(nested_dir)).close()

    found = scan_for_repos(temp_workspace, recursive=True)

    assert len(found) == 2
    paths = [item[0] for item in found]
    assert parent_dir in paths
    assert nested_dir in paths

    for _, repo_instance in found:
        assert isinstance(repo_instance, Repo)
        repo_instance.close()


def test_scan_for_repos_handles_missing_path() -> None:
    """A completely non-existent path returns an empty list."""
    assert scan_for_repos(Path("/nonexistent/path/on/disk")) == []


def test_scan_for_repos_empty_dir_returns_empty(temp_workspace: Path) -> None:
    """A real directory with no repos returns an empty list."""
    assert scan_for_repos(temp_workspace) == []


# ---------------------------------------------------------------------------
# parse_patch_stats
# ---------------------------------------------------------------------------


def test_parse_patch_stats_counts_additions_and_deletions() -> None:
    """Added (+) and deleted (-) content lines are counted correctly."""
    patch = (
        b"--- a/file.py\n"
        b"+++ b/file.py\n"
        b"@@ -1,2 +1,3 @@\n"
        b" context line\n"
        b"-removed line\n"
        b"+added line one\n"
        b"+added line two\n"
    )
    additions, deletions = parse_patch_stats(patch)
    assert additions == 2
    assert deletions == 1


def test_parse_patch_stats_ignores_diff_headers() -> None:
    """Header frames (---, +++, @@) are never counted as content changes."""
    patch = b"--- a/x.py\n+++ b/x.py\n@@ -0,0 +1 @@\n+new line\n"
    additions, deletions = parse_patch_stats(patch)
    assert additions == 1
    assert deletions == 0


def test_parse_patch_stats_empty_patch() -> None:
    """An empty patch returns (0, 0)."""
    assert parse_patch_stats(b"") == (0, 0)


def test_parse_patch_stats_only_additions() -> None:
    """Pure addition patch (e.g. first commit) counts only additions."""
    patch = b"+line one\n+line two\n+line three\n"
    additions, deletions = parse_patch_stats(patch)
    assert additions == 3
    assert deletions == 0


def test_parse_patch_stats_only_deletions() -> None:
    """Pure deletion patch counts only deletions."""
    patch = b"-line one\n-line two\n"
    additions, deletions = parse_patch_stats(patch)
    assert additions == 0
    assert deletions == 2


# ---------------------------------------------------------------------------
# get_commit_history
# ---------------------------------------------------------------------------


def test_get_commit_history_populates_records(mock_git_repo: Path) -> None:
    """Commit records carry correct authors, hashes, and line stats."""
    repo = Repo(str(mock_git_repo))
    try:
        history = get_commit_history(repo)

        # Fixture builds exactly 2 commits
        assert len(history) == 2

        # Walker surfaces commits in reverse-chronological order (latest first)
        latest, initial = history[0], history[1]

        assert latest.author == "Bob Developer"
        assert initial.author == "Alice Tester"

        # Alice's initial commit: 2 new lines, nothing removed
        assert initial.additions == 2
        assert initial.deletions == 0

        # Hash is truncated to 8 characters
        assert len(latest.hash) == 8
    finally:
        repo.close()


def test_get_commit_history_since_days_filters_old_commits(mock_git_repo: Path) -> None:
    """since_days=3 drops Alice's commit (5 days ago) and keeps Bob's (2 days ago)."""
    repo = Repo(str(mock_git_repo))
    try:
        history = get_commit_history(repo, since_days=3)
        assert len(history) == 1
        assert history[0].author == "Bob Developer"
    finally:
        repo.close()


def test_get_commit_history_since_days_includes_all(mock_git_repo: Path) -> None:
    """since_days=7 should include both commits."""
    repo = Repo(str(mock_git_repo))
    try:
        history = get_commit_history(repo, since_days=7)
        assert len(history) == 2
    finally:
        repo.close()


def test_get_commit_history_branch_fallbacks(mock_git_repo: Path) -> None:
    """Branch resolution works for default, explicit branch, and invalid branch."""
    repo = Repo(str(mock_git_repo))
    try:
        # Default resolution (main/master/HEAD fallback)
        default_history = get_commit_history(repo)
        assert len(default_history) == 2

        # Create a feature branch pointing at HEAD and resolve it explicitly
        repo.refs.set_if_equals(Ref(b"refs/heads/feature-work"), None, repo.head())
        explicit_history = get_commit_history(repo, branch="feature-work")
        assert len(explicit_history) == 2
        assert explicit_history[0].author == "Bob Developer"

        # Non-existent branch returns empty list
        bad_history = get_commit_history(repo, branch="non-existent-branch")
        assert len(bad_history) == 0
    finally:
        repo.close()


def test_get_commit_history_empty_repo(temp_workspace: Path) -> None:
    """An empty (no commits) repository returns an empty history list."""
    repo_dir = temp_workspace / "empty_repo"
    repo_dir.mkdir()
    repo = Repo.init(str(repo_dir))
    try:
        history = get_commit_history(repo)
        assert history == []
    finally:
        repo.close()
