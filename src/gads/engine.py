import datetime
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from dulwich.errors import NotGitRepository
from dulwich.objects import Commit, ObjectID
from dulwich.patch import write_tree_diff
from dulwich.refs import Ref
from dulwich.repo import Repo


@dataclass(frozen=True, slots=True)
class CommitRecord:
    hash: str
    author: str
    date: datetime.datetime
    additions: int
    deletions: int


def safe_resolve_dir(dir_path: Path) -> Path | None:
    """
    Shared guard to safely expand, resolve, and verify that a path
    is a valid, accessible directory. Returns None on failure.
    """
    try:
        base_path = dir_path.expanduser().resolve()
        if base_path.is_dir():
            return base_path
    except FileNotFoundError, OSError:
        pass
    return None


def get_repo_instance(path: Path) -> Repo | None:
    """
    Attempts to initialize a Repo object out of a target path.
    Returns the Repo instance if valid, or None if it's not a git repository.
    """
    try:
        return Repo(str(path))
    except NotGitRepository:
        return None


def scan_for_repos(dir_path: Path, recursive: bool = False) -> list[tuple[Path, Repo]]:
    """
    Finds valid Git repositories within a directory using native pathlib walking.
    Returns a list of tuples containing the (Repo_Root_Path, Repo_Instance).
    """
    valid_repos: list[tuple[Path, Repo]] = []
    base_path = safe_resolve_dir(dir_path)

    if not base_path:
        return valid_repos

    root_repo = get_repo_instance(base_path)
    if root_repo:
        valid_repos.append((base_path, root_repo))
        if not recursive:
            return valid_repos

    for root, dirs, _ in base_path.walk():
        if ".git" in dirs:
            repo = get_repo_instance(root)
            if repo:
                valid_repos.append((root, repo))

            dirs.remove(".git")

            if not recursive:
                dirs.clear()

    return valid_repos


def parse_patch_stats(patch_bytes: bytes) -> tuple[int, int]:
    """
    Parses a raw patch byte stream to count added lines (+) and deleted lines (-).
    Strictly filters out unified diff metadata header frames.
    """
    additions = 0
    deletions = 0
    lines = patch_bytes.split(b"\n")

    for line in lines:
        # Ignore structural file diff target descriptors
        if line.startswith(b"--- ") or line.startswith(b"+++ "):
            continue
        # Ignore hunk chunk positioning details
        if line.startswith(b"@@"):
            continue

        # Safely count actual raw text changes
        if line.startswith(b"+"):
            additions += 1
        elif line.startswith(b"-"):
            deletions += 1

    return additions, deletions


def resolve_target_sha(repo: Repo, branch: str | None = None) -> ObjectID | None:
    """
    Resolves a target reference to its corresponding commit SHA ObjectID based on
    the following cascade rules:
    1. Explicit branch name parameter (if provided).
    2. Local 'main' branch.
    3. Local 'master' branch.
    4. Current active HEAD.

    Returns None if an explicit branch is missing or the repository is empty.
    """
    refs_dict = repo.refs.as_dict()

    if branch:
        ref_bytes = branch.encode("utf-8")
        # Accept both short name and full ref path
        for candidate in (ref_bytes, b"refs/heads/" + ref_bytes):
            sha = refs_dict.get(Ref(candidate))
            if sha is not None:
                return sha
        return None

    # Precedence fallback chain
    for candidate in (b"refs/heads/main", b"refs/heads/master"):
        sha = refs_dict.get(Ref(candidate))
        if sha is not None:
            return sha

    try:
        return repo.head()
    except KeyError:
        # HEAD is unborn / empty repository state
        return None


def get_commit_history(
    repo: Repo, since_days: int | None = None, branch: str | None = None
) -> list[CommitRecord]:
    """
    Extracts high-fi chronological tracking metadata for commits in the repository.
    """
    records: list[CommitRecord] = []

    target_sha = resolve_target_sha(repo, branch)
    if not target_sha:
        return records

    cutoff_timestamp: float | None = None
    if since_days is not None:
        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
            days=since_days
        )
        cutoff_timestamp = cutoff.timestamp()

    # Walk the graph starting from our resolved target head commit using 'include'
    for entry in repo.get_walker(include=[target_sha]):
        commit = entry.commit
        if not isinstance(commit, Commit):
            continue

        if cutoff_timestamp and commit.commit_time < cutoff_timestamp:
            break

        # Decode tracking strings safely
        commit_id = commit.id
        commit_hash = (
            commit_id.decode("utf-8")
            if isinstance(commit_id, bytes)
            else str(commit_id)
        )
        author = commit.author.decode("utf-8", errors="ignore").split(" <")[0]
        commit_date = datetime.datetime.fromtimestamp(
            commit.commit_time, datetime.timezone.utc
        )

        parent_tree_id: bytes | None = None
        if commit.parents:
            parent_commit = repo.object_store[commit.parents[0]]
            if isinstance(parent_commit, Commit):
                parent_tree_id = parent_commit.tree

        patch_buffer = BytesIO()
        write_tree_diff(patch_buffer, repo.object_store, parent_tree_id, commit.tree)
        additions, deletions = parse_patch_stats(patch_buffer.getvalue())

        records.append(
            CommitRecord(
                hash=commit_hash[:8],
                author=author,
                date=commit_date,
                additions=additions,
                deletions=deletions,
            )
        )

    return records
