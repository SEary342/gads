from pathlib import Path
from pprint import pprint

from gads.engine import get_commit_history, scan_for_repos


def main():
    # TODO wire this up to the real CLI
    repos = scan_for_repos(Path("/home/sameary/Code/"), True)
    print(repos[0][0])
    pprint(get_commit_history(repos[0][1]), indent=4)
