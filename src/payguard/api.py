from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from .agent import Agent
from .config import settings
from .ingest import build_db, build_index, load_index
from .llm import get_llm

app = FastAPI(title="PayGuard AI", version="1.0.0",
              description="Governed RAG + agentic assistant for payments support")
_agent: Agent | None = None


def agent() -> Agent:
    global _agent
    if _agent is None:
        if not (settings.artifacts / "payguard.db").exists():
            build_db()
        _agent = Agent(load_index(), get_llm())
    return _agent


def auth(x_api_key: str | None = Header(default=None)):
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(401, "invalid API key")


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    customer_id: str = Field(default="C001", pattern=r"^C\d{3}$")


@app.get("/health")
def health():
    return {"status": "ok", "llm": agent().llm.name}


@app.post("/ask", dependencies=[Depends(auth)])
def ask(req: AskRequest):
    return agent().ask(req.question, req.customer_id)


@app.post("/reindex", dependencies=[Depends(auth)])
def reindex():
    global _agent
    _agent = None
    r = build_index()
    return {"chunks": len(r.chunks)}


@app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    return agent().metrics.prometheus()
