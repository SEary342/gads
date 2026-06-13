from pathlib import Path

from dulwich.repo import Repo

from gads.engine import is_git_repo, scan_for_repos


def test_is_git_repo_valid(mock_git_repo: Path) -> None:
    """Ensures a verified repository folder evaluates to True."""
    assert is_git_repo(mock_git_repo) is True


def test_is_git_repo_invalid(temp_workspace: Path) -> None:
    """Ensures a generic non-git directory evaluates to False."""
    assert is_git_repo(temp_workspace) is False


def test_scan_for_repos_finds_top_level(mock_git_repo: Path) -> None:
    """Ensures scanning a direct repository root catches it instantly."""
    found = scan_for_repos(mock_git_repo)
    assert mock_git_repo in found
    assert len(found) == 1


def test_scan_for_repos_non_recursive_stops_at_first_repo(temp_workspace: Path) -> None:
    """
    Ensures recursive=False drops out of a directory branch completely
    once a root is encountered, missing any nested sub-repositories.
    """
    # Create structure: workspace / parent_repo / nested_repo
    parent_dir = temp_workspace / "parent_project"
    parent_dir.mkdir()
    Repo.init(str(parent_dir))

    nested_dir = parent_dir / "nested_submodule"
    nested_dir.mkdir()
    Repo.init(str(nested_dir))

    # Action: Run a shallow non-recursive sweep
    found = scan_for_repos(temp_workspace, recursive=False)

    # Verification: Only the parent repository should be registered
    assert parent_dir in found
    assert nested_dir not in found
    assert len(found) == 1


def test_scan_for_repos_recursive_keeps_digging(temp_workspace: Path) -> None:
    """
    Ensures recursive=True skips the internal .git metadata tracking directories,
    but keeps diving down structural subfolders to catch nested sub-repositories.
    """
    # Create structure: workspace / parent_repo / nested_repo
    parent_dir = temp_workspace / "parent_project"
    parent_dir.mkdir()
    Repo.init(str(parent_dir))

    nested_dir = parent_dir / "nested_submodule"
    nested_dir.mkdir()
    Repo.init(str(nested_dir))

    # Action: Run a deep recursive sweep
    found = scan_for_repos(temp_workspace, recursive=True)

    # Verification: Both tracking points are successfully accumulated
    assert parent_dir in found
    assert nested_dir in found
    assert len(found) == 2


def test_scan_for_repos_handles_missing_or_invalid_paths() -> None:
    """
    Ensures broken inputs or non-existent files fail gracefully without throwing
    exceptions.
    """
    bad_path = Path("/nonexistent/path/on/disk/structure")
    assert scan_for_repos(bad_path) == []
