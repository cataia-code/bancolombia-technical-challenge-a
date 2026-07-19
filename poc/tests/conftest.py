import pathlib
import sys

# Allows tests to import the package from poc/src without installing it.
SRC = pathlib.Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
