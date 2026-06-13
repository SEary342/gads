from pathlib import Path

from dulwich.errors import NotGitRepository
from dulwich.repo import Repo


def is_git_repo(path: Path) -> bool:
    try:
        Repo(str(path))
        return True
    except NotGitRepository:
        return False


def scan_for_repos(dir_path: Path, recursive: bool = False) -> list[Path]:
    """
    Finds paths to Git repository roots within a directory using native pathlib walking.
    """
    valid_repos = []

    try:
        base_path = dir_path.expanduser().resolve()
    except FileNotFoundError, OSError:
        return valid_repos

    if not base_path.is_dir():
        return valid_repos

    if is_git_repo(base_path):
        valid_repos.append(base_path)
        if not recursive:
            return valid_repos

    for root, dirs, _ in base_path.walk():
        if ".git" in dirs:
            valid_repos.append(root)

            dirs.remove(".git")

            if not recursive:
                dirs.clear()

    return valid_repos


def get_repo_stats(repo_path: str):
    pass
