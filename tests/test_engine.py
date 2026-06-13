from pathlib import Path

from dulwich.refs import Ref
from dulwich.repo import Repo

from gads.engine import (
    get_commit_history,
    get_repo_instance,
    safe_resolve_dir,
    scan_for_repos,
)


def test_safe_resolve_dir_valid(temp_workspace: Path) -> None:
    """Ensures a valid directory path resolves cleanly."""
    resolved = safe_resolve_dir(temp_workspace)
    assert resolved == temp_workspace.resolve()


def test_safe_resolve_dir_invalid() -> None:
    """Ensures non-existent directories or broken descriptors return None safely."""
    bad_path = Path("/nonexistent/directory/path/here")
    assert safe_resolve_dir(bad_path) is None


def test_get_repo_instance_valid(mock_git_repo: Path) -> None:
    """Ensures an initialized git path yields an operational Repo instance."""
    repo = get_repo_instance(mock_git_repo)
    assert isinstance(repo, Repo)
    if repo:
        repo.close()


def test_get_repo_instance_invalid(temp_workspace: Path) -> None:
    """
    Ensures a generic directory returns None instead of throwing a NotGitRepository
    exception.
    """
    assert get_repo_instance(temp_workspace) is None


def test_scan_for_repos_finds_top_level(mock_git_repo: Path) -> None:
    """
    Ensures scanning a direct repository root catches it and bundles the open instance.
    """
    found = scan_for_repos(mock_git_repo)
    assert len(found) == 1

    repo_path, repo_instance = found[0]
    assert repo_path == mock_git_repo
    assert isinstance(repo_instance, Repo)
    repo_instance.close()


def test_scan_for_repos_non_recursive_stops_at_first_repo(temp_workspace: Path) -> None:
    """
    Ensures recursive=False drops out of a directory branch completely
    once a root is encountered, missing any nested sub-repositories.
    """
    # Create structure: workspace / parent_project / nested_submodule
    parent_dir = temp_workspace / "parent_project"
    parent_dir.mkdir()
    p_repo = Repo.init(str(parent_dir))
    p_repo.close()

    nested_dir = parent_dir / "nested_submodule"
    nested_dir.mkdir()
    n_repo = Repo.init(str(nested_dir))
    n_repo.close()

    # Action: Run a shallow non-recursive sweep
    found = scan_for_repos(temp_workspace, recursive=False)

    # Verification: Only the parent repository should be registered
    assert len(found) == 1
    repo_path, repo_instance = found[0]
    assert repo_path == parent_dir
    assert isinstance(repo_instance, Repo)
    repo_instance.close()


def test_scan_for_repos_recursive_keeps_digging(temp_workspace: Path) -> None:
    """
    Ensures recursive=True skips the internal .git metadata tracking directories,
    but keeps diving down structural subfolders to catch nested sub-repositories.
    """
    parent_dir = temp_workspace / "parent_project"
    parent_dir.mkdir()
    p_repo = Repo.init(str(parent_dir))
    p_repo.close()

    nested_dir = parent_dir / "nested_submodule"
    nested_dir.mkdir()
    n_repo = Repo.init(str(nested_dir))
    n_repo.close()

    # Action: Run a deep recursive sweep
    found = scan_for_repos(temp_workspace, recursive=True)

    # Verification: Both tracking points are successfully accumulated
    assert len(found) == 2

    paths = [item[0] for item in found]
    assert parent_dir in paths
    assert nested_dir in paths

    for _, repo_instance in found:
        assert isinstance(repo_instance, Repo)
        repo_instance.close()


def test_scan_for_repos_handles_missing_or_invalid_paths() -> None:
    """
    Ensures broken inputs or non-existent files fail gracefully without throwing
    exceptions.
    """
    bad_path = Path("/nonexistent/path/on/disk/structure")
    assert scan_for_repos(bad_path) == []


def test_get_commit_history_populates_records(mock_git_repo: Path) -> None:
    """Ensures raw commit histories unpack accurate line stats, hashes, and dates."""
    repo = Repo(str(mock_git_repo))
    try:
        history = get_commit_history(repo)

        # Our mock repo fixture builds exactly 2 commits
        assert len(history) == 2

        # The walker surfaces commits in reverse-chronological order (latest first)
        latest_commit = history[0]
        initial_commit = history[1]

        assert latest_commit.author == "Bob Developer"
        assert initial_commit.author == "Alice Tester"

        # Verify line-by-line metrics parsing from our fixture setup
        assert initial_commit.additions == 2
        assert initial_commit.deletions == 0

        assert len(latest_commit.hash) == 8
    finally:
        repo.close()


def test_get_commit_history_branch_fallbacks(mock_git_repo: Path) -> None:
    """Ensures fallback cascades find main/master or explicit overrides."""
    repo = Repo(str(mock_git_repo))
    try:
        # 1. Test standard default behavior (resolves to main in our mock)
        default_history = get_commit_history(repo)
        assert len(default_history) == 2

        repo.refs.set_if_equals(Ref(b"refs/heads/feature-work"), None, repo.head())

        explicit_history = get_commit_history(repo, branch="feature-work")
        assert len(explicit_history) == 2
        assert explicit_history[0].author == "Bob Developer"

        # 3. Test an invalid branch name handles empty loops gracefully
        bad_history = get_commit_history(repo, branch="non-existent-branch")
        assert len(bad_history) == 0
    finally:
        repo.close()
