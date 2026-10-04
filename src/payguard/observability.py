"""Monitoring: in-process counters/latency histogram exposed in Prometheus text format,
plus a PII-redacted JSONL audit log (supports AI governance / traceability)."""
import json
import threading
import time
from collections import Counter

from .config import settings


class Metrics:
    def __init__(self):
        self.lock = threading.Lock()
        self.counters: Counter = Counter()
        self.latencies: list[float] = []

    def record(self, resp) -> None:
        with self.lock:
            self.counters["requests_total"] += 1
            if resp.refused:
                self.counters[f"refusals_total{{reason=\"{resp.refusal_reason}\"}}"] += 1
            if resp.guardrails.get("pii_redacted"):
                self.counters["pii_redactions_total"] += 1
            self.latencies.append(resp.latency_ms)
            self.latencies = self.latencies[-1000:]

    def prometheus(self) -> str:
        with self.lock:
            lines = [f"payguard_{k} {v}" for k, v in sorted(self.counters.items())]
            if self.latencies:
                s = sorted(self.latencies)
                lines.append(f"payguard_latency_ms_p50 {s[len(s) // 2]:.2f}")
                lines.append(f"payguard_latency_ms_p95 {s[min(len(s) - 1, int(len(s) * .95))]:.2f}")
        return "\n".join(lines) + "\n"


def audit(event: dict) -> None:
    settings.artifacts.mkdir(exist_ok=True)
    with open(settings.artifacts / "audit.jsonl", "a") as fh:
        fh.write(json.dumps({"ts": time.time(), **event}) + "\n")
