from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    project_root: Path = PROJECT_ROOT
    corpus_dir: Path = PROJECT_ROOT / "incial-data" / "corpus"
    data_dir: Path = PROJECT_ROOT / "incial-data" / "data"
    outputs_dir: Path = PROJECT_ROOT / "outputs"
    as_of_date: str = "2026-10-01"
    api_title: str = "Rental Housing Law Navigator API"
    api_version: str = "0.1.0"


settings = Settings()
