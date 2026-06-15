import datetime
from pathlib import Path
from typing import Generator

import pytest
from dulwich import porcelain
from dulwich.repo import Repo


def _now_minus_days(days: int) -> int:
    """Returns a UTC Unix timestamp for N days ago."""
    dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    return int(dt.timestamp())


@pytest.fixture
def temp_workspace(tmp_path: Path) -> Path:
    """Provides a clean temporary directory path for scratching file structures."""
    return tmp_path


@pytest.fixture
def mock_git_repo(tmp_path: Path) -> Generator[Path, None, None]:
    """Creates an ephemeral, initialized Git repository with two sample commits
    at known timestamps and yields the absolute path to the repository root.

    Commit layout:
        - commit 1 (Alice Tester): 5 days ago  — 2 additions, 0 deletions
        - commit 2 (Bob Developer): 2 days ago — 1 addition, 1 deletion (net)
    """
    repo_dir = tmp_path / "test_project"
    repo_dir.mkdir()

    repo = Repo.init(str(repo_dir))

    # Disable GPG signing so global ~/.gitconfig settings don't interfere
    config = repo.get_config()
    config.set((b"commit",), b"gpgsign", False)
    config.write_to_path()

    try:
        file_path = repo_dir / "main.py"

        # --- Commit 1: Alice Tester — 5 days ago ---
        file_path.write_bytes(b"Hello World\nInitial code line\n")
        porcelain.add(repo, paths=["main.py"])
        porcelain.commit(
            repo,
            message=b"Initial commit",
            author=b"Alice Tester <alice@example.com>",
            committer=b"Alice Tester <alice@example.com>",
            author_timestamp=_now_minus_days(5),
            commit_timestamp=_now_minus_days(5),
        )

        # --- Commit 2: Bob Developer — 2 days ago ---
        file_path.write_bytes(b"Hello World\nRefactored secondary line\n")
        porcelain.add(repo, paths=["main.py"])
        porcelain.commit(
            repo,
            message=b"Refactored logic",
            author=b"Bob Developer <bob@example.com>",
            committer=b"Bob Developer <bob@example.com>",
            author_timestamp=_now_minus_days(2),
            commit_timestamp=_now_minus_days(2),
        )

        yield repo_dir

    finally:
        repo.close()


@pytest.fixture
def multi_repo_workspace(tmp_path: Path) -> Generator[Path, None, None]:
    """Creates a workspace directory containing two independent Git repositories,
    each with one recent commit, for use in aggregator-level tests.

    Layout:
        workspace/
            repo_alpha/   — 1 commit (Alice, 1 day ago)
            repo_beta/    — 1 commit (Bob, 1 day ago)
    """
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    repos: list[Repo] = []

    for repo_name, author, content in [
        ("repo_alpha", b"Alice Tester <alice@example.com>", b"alpha content\n"),
        ("repo_beta", b"Bob Developer <bob@example.com>", b"beta content\n"),
    ]:
        repo_dir = workspace / repo_name
        repo_dir.mkdir()
        repo = Repo.init(str(repo_dir))

        config = repo.get_config()
        config.set((b"commit",), b"gpgsign", False)
        config.write_to_path()

        (repo_dir / "file.py").write_bytes(content)
        porcelain.add(repo, paths=["file.py"])
        porcelain.commit(
            repo,
            message=b"Initial commit",
            author=author,
            committer=author,
            author_timestamp=_now_minus_days(1),
            commit_timestamp=_now_minus_days(1),
        )

        repos.append(repo)

    try:
        yield workspace
    finally:
        for r in repos:
            r.close()
