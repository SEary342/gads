from pathlib import Path

from gads.engine import scan_for_repos


def main():
    # TODO wire this up to the real CLI
    print([str(x) for x in scan_for_repos(Path("/home/sameary/Code/"), True)])
    pass
