import pathlib
import sys

# Permite importar el paquete desde poc/src sin instalación.
SRC = pathlib.Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
