import os
from pathlib import Path
from typing import Generator

import pytest
from dulwich import porcelain
from dulwich.objects import Commit
from dulwich.repo import Repo


@pytest.fixture
def temp_workspace(tmp_path: Path) -> Path:
    """Provides a clean temporary directory path for scratching file structures."""
    return tmp_path


@pytest.fixture
def mock_git_repo(tmp_path: Path) -> Generator[Path, None, None]:
    """Creates an ephemeral, initialized Git repository containing programmatic

    sample commits and returns the absolute Path to the repository root.
    """
    repo_dir = tmp_path / "test_project"
    repo_dir.mkdir()

    repo = Repo.init(str(repo_dir))

    # --- Force-Disable GPG Signing for the Test Repository ---
    # This prevents Dulwich from inheriting global ~/.gitconfig gpg signing settings
    config = repo.get_config()
    config.set((b"commit",), b"gpgsign", False)
    config.write_to_path()

    old_cwd = os.getcwd()
    os.chdir(str(repo_dir))

    try:
        # --- Commit 1: Alice Tester ---
        file_path = repo_dir / "main.py"
        file_path.write_bytes(b"Hello World\nInitial code line\n")

        porcelain.add(repo, paths=["main.py"])
        porcelain.commit(
            repo,
            message=b"Initial commit",
            author=b"Alice Tester <alice@example.com>",
            committer=b"Alice Tester <alice@example.com>",
        )

        commit1 = repo[repo.head()]
        if isinstance(commit1, Commit):
            commit1.commit_time = commit1.author_time = commit1.commit_time - (
                86400 * 5
            )
            repo.object_store.add_object(commit1)

        # --- Commit 2: Bob Developer ---
        file_path.write_bytes(
            b"Hello World\nInitial code line\nRefactored secondary line\n"
        )

        porcelain.add(repo, paths=["main.py"])
        porcelain.commit(
            repo,
            message=b"Refactored logic",
            author=b"Bob Developer <bob@example.com>",
            committer=b"Bob Developer <bob@example.com>",
        )

        commit2 = repo[repo.head()]
        if isinstance(commit2, Commit):
            commit2.commit_time = commit2.author_time = commit2.commit_time - (
                86400 * 2
            )
            repo.object_store.add_object(commit2)

        yield repo_dir

    finally:
        os.chdir(old_cwd)
        repo.close()
