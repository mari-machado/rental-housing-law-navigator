from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INCIAL_DATA_DIR = PROJECT_ROOT / "incial-data"
CORPUS_DIR = INCIAL_DATA_DIR / "corpus"
DATA_DIR = INCIAL_DATA_DIR / "data"
SCHEMA_DIR = INCIAL_DATA_DIR / "schema"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
DEFAULT_AS_OF = "2026-10-01"


def ensure_output_dir() -> None:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
