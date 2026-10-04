"""Responsible-AI guardrails: PII redaction, prompt-injection detection, groundedness
(hallucination) scoring and output safety."""
import re

STOP = set("""a an the and or of to in on for with is are was were be been it this that these those as at by from
you your i my me we our can will would should do does did not no any if then than so such have has had what which who
how when where why about into over after before within""".split())

# ---------------- PII ----------------
_CARD = re.compile(r"\b(?:\d[ -]?){13,19}\b")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"(?<![\w])(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)")
_AADHAAR = re.compile(r"\b\d{4}\s\d{4}\s\d{4}\b")


def luhn_ok(num: str) -> bool:
    d = [int(c) for c in num if c.isdigit()]
    if not 13 <= len(d) <= 19:
        return False
    s = 0
    for i, x in enumerate(reversed(d)):
        if i % 2:
            x = x * 2 - 9 if x * 2 > 9 else x * 2
        s += x
    return s % 10 == 0


def redact_pii(text: str) -> tuple[str, dict]:
    found = {"card": 0, "email": 0, "phone": 0, "national_id": 0}

    def card(m):
        raw = m.group(0)
        if luhn_ok(raw):
            found["card"] += 1
            return f"[CARD ****{re.sub(r'\D', '', raw)[-4:]}]"
        return raw

    text = _CARD.sub(card, text)
    text, found["email"] = _EMAIL.subn("[EMAIL]", text)
    text, found["national_id"] = _AADHAAR.subn("[ID]", text)
    text, found["phone"] = _PHONE.subn("[PHONE]", text)
    return text, {k: v for k, v in found.items() if v}


# ---------------- Prompt injection ----------------
_INJECTION = [
    r"ignore (all |any )?(the )?(previous|prior|above|earlier) (instructions|rules|prompts?)",
    r"disregard (all |any )?(the )?(previous|prior|above|your) (instructions|rules)",
    r"(reveal|show|print|repeat|leak) (me )?(your|the) (system )?(prompt|instructions|rules)",
    r"you are now\b", r"developer mode", r"\bjailbreak\b", r"\bDAN\b",
    r"pretend (you|to) (are|be)", r"bypass (the )?(guardrails?|safety|filters?)",
]


def detect_injection(text: str) -> dict:
    hits = [p for p in _INJECTION if re.search(p, text, re.I)]
    return {"flagged": bool(hits), "score": min(1.0, len(hits) / 2), "patterns": len(hits)}


# ---------------- Groundedness / hallucination ----------------
def _tokens(s: str) -> set[str]:
    return {w.rstrip("s") for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in STOP and len(w) > 2}


def groundedness(answer: str, evidence_texts: list[str], support_threshold: float = 0.6) -> dict:
    """Sentence-level lexical-support check: share of content tokens in each answer sentence
    that appear in the retrieved evidence. Cheap, deterministic stand-in for an NLI/LLM-judge."""
    ev = set().union(*[_tokens(t) for t in evidence_texts]) if evidence_texts else set()
    sents = [s for s in re.split(r"(?<=[.!?])\s+|\n", answer) if _tokens(s)]
    if not sents:
        return {"score": 0.0, "unsupported": []}
    scores, unsupported = [], []
    for s in sents:
        t = _tokens(s)
        sc = len(t & ev) / len(t)
        scores.append(sc)
        if sc < support_threshold:
            unsupported.append(s)
    return {"score": round(sum(scores) / len(scores), 3), "unsupported": unsupported}


# ---------------- Output safety ----------------
def output_safety(text: str) -> dict:
    leaked_card = any(luhn_ok(m.group(0)) for m in _CARD.finditer(text))
    leaked_secret = bool(re.search(r"(api[_-]?key|secret|password)\s*[:=]\s*\S+", text, re.I))
    return {"safe": not (leaked_card or leaked_secret), "leaked_card": leaked_card, "leaked_secret": leaked_secret}
