"""Entry point: python pipeline/gk.py <command> <garment> ...  (see pipeline/garmentkit/__main__.py)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from garmentkit.__main__ import main  # noqa: E402

main()
