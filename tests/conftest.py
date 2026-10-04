import pytest
from payguard.ingest import build_db, build_index
from payguard.agent import Agent
from payguard.llm import MockLLM


@pytest.fixture(scope="session")
def agent():
    build_db()
    return Agent(build_index(), MockLLM())
