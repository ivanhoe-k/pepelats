"""Run the background worker example.

From repo root: ``uv run python examples/background-worker/main.py``
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from examples.shared.background_worker_host import build_host

    build_host(Path(__file__).resolve().parent).run()


if __name__ == "__main__":
    main()
