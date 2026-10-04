# PayGuard AI — Governed GenAI Assistant for Payments Support

Production-style **RAG + agentic AI** service with **Responsible-AI guardrails, LLMOps evaluation gates, monitoring, and CI/CD**.
Answers payment-policy questions from a knowledge base **with citations**, and answers account questions by calling a **secured SQL tool** —
refusing safely when evidence is missing, the input is an injection attempt, or the output is not grounded.

> Data is synthetic and the bank ("NovaPay") is fictional. LLM runs in offline `mock` mode by default; set `LLM_PROVIDER=openai|azure` for a real model.

## Architecture
```
Client ──► FastAPI (/ask, /health, /metrics, /reindex; API-key auth, pydantic validation)
              │
              ▼
        ┌──────────── Agent (plan → act → verify) ────────────┐
        │ 1 INPUT GUARD   PII redaction (Luhn-validated cards,│
        │                 email, phone, ID) + injection detect│
        │ 2 PLAN          route: account data vs policy KB    │
        │ 3 TOOLS         • policy_retriever (TF-IDF/cosine)  │
        │                 • transactions_sql (read-only,      │
        │                   allow-listed, row-level security) │
        │ 4 LLM           mock | OpenAI | Azure OpenAI        │
        │ 5 OUTPUT GUARD  groundedness score, leak check,     │
        │                 PII redaction, safe fallback        │
        └──────────────────────────────────────────────────────┘
              │                                   │
     citations + trace + guardrail report    PII-redacted JSONL audit log + Prometheus metrics
```

## JD coverage
| Requirement | Where |
|---|---|
| LLMs, Agentic AI, RAG | `agent.py`, `retriever.py`, `llm.py` |
| Scalable pipelines / data prep / ETL | `ingest.py` (chunking, indexing, CSV→SQLite ETL) |
| APIs, DB, cloud integration | `api.py` (FastAPI), `tools.py` (SQL), Azure/OpenAI client in `llm.py` |
| Deployment, testing, monitoring (MLOps/LLMOps) | `Dockerfile`, `.github/workflows/ci.yml`, `tests/`, `observability.py`, `evals.py --gate` |
| Responsible AI: bias, hallucination, explainability, safety guardrails | counterfactual fairness test (`evals.py`), groundedness (`guardrails.py`), citations + step trace in every response, injection/PII/output filters |
| Python, SQL, Git, Docker | whole repo |

## Run it
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=src
python -m payguard.ingest                 # build index + synthetic DB
pytest -q                                 # 20 tests
python -m payguard.evals --gate           # LLMOps quality gate (fails if metrics regress)
uvicorn payguard.api:app --reload         # http://localhost:8000/docs

curl -s localhost:8000/ask -H 'content-type: application/json' \
  -d '{"question":"How long do I have to raise a chargeback dispute?"}'
curl -s localhost:8000/ask -H 'content-type: application/json' \
  -d '{"question":"Show my disputed transactions","customer_id":"C003"}'
```
Docker: `docker build -t payguard-ai . && docker run -p 8000:8000 payguard-ai`
Real LLM: `pip install openai && LLM_PROVIDER=azure AZURE_OPENAI_ENDPOINT=... AZURE_OPENAI_API_KEY=... LLM_MODEL=<deployment>`

## Evaluation (`artifacts/eval_report.json`, 14 golden cases, mock LLM)
Answer accuracy 1.00 · Retrieval hit-rate 1.00 · Groundedness 1.00 · Refusal accuracy 1.00 · PII leakage 0.00 · Fairness consistency 1.00 · p95 latency ~2 ms (retrieval+guardrails, excl. LLM call).
Re-run with a real LLM (`--provider azure`) and quote **your** numbers.

## Security & governance decisions
- SQL tool: single `SELECT`, allow-listed table, no comments/DDL/DML, forced `LIMIT`, and **row-level security** (query executes on an in-memory copy containing only the caller's rows).
- PII is redacted *before* retrieval, LLM calls and logging; card numbers are Luhn-validated to cut false positives.
- Every request leaves an audit record (redacted question, refusal reason, groundedness) for traceability.

## Known limitations / next steps
TF-IDF → embeddings + Azure AI Search/FAISS; lexical groundedness → NLI or LLM-judge; template SQL planner → LLM text-to-SQL (already validated by `validate_select`); add Databricks/Spark job for large-scale ingestion; MLflow tracking of eval runs.

## Cloud deployment (Azure + Databricks)
- `deploy/azure/deploy.sh`: builds the image in Azure Container Registry and runs it on **Azure Container Apps** with **Azure OpenAI** (`LLM_PROVIDER=azure`), secrets via Container Apps secrets.
- `deploy/databricks/ingest_notebook.py`: the ingestion/chunking pipeline as a **Spark + Delta Lake** Databricks notebook.
- Both were written from vendor docs and have not been run in CI. Run them, fix any drift, then record your live URL here.
