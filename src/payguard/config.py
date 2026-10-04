import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    docs_dir: Path = ROOT / "data" / "docs"
    artifacts: Path = ROOT / "artifacts"
    llm_provider: str = os.getenv("LLM_PROVIDER", "mock")  # mock | openai | azure
    llm_model: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
    top_k: int = int(os.getenv("TOP_K", "3"))
    min_score: float = float(os.getenv("MIN_SCORE", "0.12"))        # retrieval relevance floor
    min_groundedness: float = float(os.getenv("MIN_GROUNDEDNESS", "0.6"))
    api_key: str | None = os.getenv("API_KEY")                       # optional API auth


settings = Settings()
