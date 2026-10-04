from dataclasses import dataclass, field


@dataclass
class Chunk:
    id: str
    source: str
    text: str
    score: float = 0.0


@dataclass
class Evidence:
    id: str
    source: str   # file name or "sql"
    text: str


@dataclass
class AgentResponse:
    answer: str
    refused: bool = False
    refusal_reason: str | None = None
    citations: list[dict] = field(default_factory=list)
    trace: list[dict] = field(default_factory=list)
    guardrails: dict = field(default_factory=dict)
    latency_ms: float = 0.0
