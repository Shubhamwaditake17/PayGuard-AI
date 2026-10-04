"""Plan-and-execute agent: guard input -> plan tools -> retrieve + query -> generate -> guard output."""
import re
import time

from . import guardrails as g
from .config import settings
from .models import AgentResponse, Evidence
from .observability import Metrics, audit
from .tools import TransactionTool, UnsafeSQL, plan_sql

FALLBACK = "I don't have enough reliable information to answer that. Please contact NovaPay support."


class Agent:
    def __init__(self, retriever, llm, tool: TransactionTool | None = None, metrics: Metrics | None = None):
        self.retriever, self.llm = retriever, llm
        self.tool = tool or TransactionTool()
        self.metrics = metrics or Metrics()

    def ask(self, question: str, customer_id: str = "C001") -> AgentResponse:
        t0, trace = time.perf_counter(), []
        clean_q, pii = g.redact_pii(question)
        inj = g.detect_injection(clean_q)
        rails = {"pii_redacted": pii, "injection": inj}
        trace.append({"step": "input_guard", "pii": pii, "injection": inj["flagged"]})

        def finish(resp: AgentResponse) -> AgentResponse:
            resp.guardrails, resp.trace = {**rails, **resp.guardrails}, trace
            resp.latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            self.metrics.record(resp)
            audit({"customer": customer_id, "question": clean_q, "refused": resp.refused,
                   "reason": resp.refusal_reason, "latency_ms": resp.latency_ms,
                   "groundedness": resp.guardrails.get("groundedness")})
            return resp

        if inj["flagged"]:
            return finish(AgentResponse("I can't help with that request.", True, "prompt_injection"))

        evidence: list[Evidence] = []
        sql = plan_sql(clean_q)
        trace.append({"step": "plan", "tools": ["transactions_sql"] if sql else ["policy_retriever"]})
        if sql:
            try:
                rows = self.tool.run(customer_id, sql)
                trace.append({"step": "tool:transactions_sql", "sql": sql, "rows": len(rows)})
                text = "\n".join(", ".join(f"{k}={v}" for k, v in r.items()) for r in rows[:10])
                evidence.append(Evidence("sql", "sql", text or "No matching transactions found for this customer."))
            except UnsafeSQL as e:
                trace.append({"step": "tool:transactions_sql", "blocked": str(e)})
        else:
            search_q = re.sub(r"\[(CARD|EMAIL|PHONE|ID)[^\]]*\]", " ", clean_q)  # placeholders are noise for retrieval
            chunks = self.retriever.search(search_q, settings.top_k, settings.min_score)
            trace.append({"step": "tool:policy_retriever",
                          "hits": [{"id": c.id, "score": round(c.score, 3)} for c in chunks]})
            evidence += [Evidence(c.id, c.source, c.text) for c in chunks]

        if not evidence:
            return finish(AgentResponse(FALLBACK, True, "no_evidence"))

        answer = self.llm.generate(clean_q, evidence)
        gr = g.groundedness(answer, [e.text for e in evidence])
        safety = g.output_safety(answer)
        trace.append({"step": "output_guard", "groundedness": gr["score"], "safe": safety["safe"]})
        answer, _ = g.redact_pii(answer)
        rails.update({"groundedness": gr["score"], "unsupported_sentences": gr["unsupported"], "output_safety": safety})
        if gr["score"] < settings.min_groundedness or not safety["safe"]:
            return finish(AgentResponse(FALLBACK, True, "ungrounded_or_unsafe"))
        cites = [{"ref": i, "source": e.source, "id": e.id} for i, e in enumerate(evidence, 1)]
        return finish(AgentResponse(answer, citations=cites))
