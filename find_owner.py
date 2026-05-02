#!/usr/bin/env python3
"""Given a repo-relative path, print the CODEOWNERS line with the longest matching prefix."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent
CODEOWNERS = REPO_ROOT / ".github" / "CODEOWNERS"


def find_owner(filepath: str) -> str | None:
    # Normalise input to start with /
    target = "/" + filepath.lstrip("/")

    best_pattern = ""
    best_line = None

    for line in CODEOWNERS.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        pattern = stripped.split()[0]
        if target.startswith(pattern) and len(pattern) > len(best_pattern):
            best_pattern = pattern
            best_line = line

    return best_line


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        print(f"Usage: {sys.argv[0]} <repo-relative-path> [username]", file=sys.stderr)
        sys.exit(1)

    result = find_owner(sys.argv[1])
    if result is None:
        print("No matching CODEOWNERS entry found.", file=sys.stderr)
        sys.exit(1)
    print(result)

    if len(sys.argv) == 3:
        username = sys.argv[2].lstrip("@")
        owners = [o.lstrip("@") for o in result.split()[1:]]
        sys.exit(0 if username in owners else 1)
