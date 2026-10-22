"""
Entrypoint for python -m macguard and python3 macguard.
"""

import sys
from pathlib import Path

# Ensure parent directory is on sys.path
parent_dir = str(Path(__file__).resolve().parent.parent)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from macguard.cli import main

if __name__ == "__main__":
    main()
