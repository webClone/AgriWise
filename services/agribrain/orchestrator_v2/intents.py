from enum import Enum
from typing import Tuple
from datetime import datetime, timedelta
import re

class Intent(Enum):
    GREETING = "GREETING"
    GENERAL = "GENERAL"
    DATA_QUERY = "DATA_QUERY"
    DIAGNOSIS = "DIAGNOSIS"
    DECISION = "DECISION"
    PLANNING = "PLANNING"
    NUTRIENT = "NUTRIENT"
    EXECUTION_STATUS = "EXECUTION"
    SCENARIO = "SCENARIO"
    UNKNOWN = "UNKNOWN"

FIELD_OWNERSHIP_PATTERNS = [
    r"\bmy field\b", r"\bmy plot\b", r"\bmy farm\b", r"\bmy crop\b", r"\bmy land\b",
    r"\bthis field\b", r"\bthis plot\b", r"\bour field\b",
    r"\bplot id\b", r"\bfield id\b",
]
COORD_PATTERN = r"(-?\d{1,3}\.\d+)\s*,\s*(-?\d{1,3}\.\d+)"  # "36.7, 3.05"

def _has_field_context(q: str) -> bool:
    if re.search(COORD_PATTERN, q):
        return True
    return any(re.search(p, q) for p in FIELD_OWNERSHIP_PATTERNS)

def detect_intent(query: str, has_context: bool = False) -> Intent:
    q = (query or "").lower().strip()

    # 0) GREETING (early exit)
    if not q:
        return Intent.GREETING
    if re.fullmatch(r"[\W_]+", q):  # only punctuation/emojis
        return Intent.GREETING

    greeting_patterns = ["hi", "hello", "hey", "bonjour", "salut", "salam", "yo"]
    words = q.split()
    if len(words) <= 3 and any(g == q or f"{g} " in q or f" {g}" in q for g in greeting_patterns):
        return Intent.GREETING

    has_field = has_context or _has_field_context(q) or ("field" in q) or ("plot" in q)

    # 1) PLANNING (crop decision) - Highest priority to catch "can i plant" and "if i plant" before SCENARIO grabs "if i"
    planning_keywords = ["can i plant", "planting window", "what crop", "suitable", "best crop", "should i plant", "plant", "sow", "seed", "grow"]
    if any(k in q for k in planning_keywords):
        return Intent.PLANNING

    # 1.5) SCENARIO (what-if)
    if any(k in q for k in ["what if", "simulate", "scenario", "if i", "suppose"]):
        return Intent.SCENARIO

    # 2) EXECUTION (tasks)
    if any(k in q for k in ["did you do", "did it finish", "task status", "execution", "plan status", "completed"]):
        return Intent.EXECUTION_STATUS

    # 3) GENERAL (concept learning) — only if NOT about their field
    general_patterns = ["what is", "explain", "meaning of", "how does", "difference between", "define"]
    general_topics = ["ndvi", "sar", "vv", "vh", "et0", "gdd", "ph", "ec", "salinity", "nitrogen", "fungal", "irrigation"]
    if any(p in q for p in general_patterns) and any(t in q for t in general_topics) and not has_field:
        return Intent.GENERAL

    # 4.5) DECISION (actionable) — should we do X?
    decision_keywords = ["should i", "do i need", "recommend", "advice", "what should i do", "action plan"]
    decision_actions = ["irrigate", "spray", "harvest", "fertilize", "apply"]
    if any(k in q for k in decision_keywords) or (has_field and any(a in q for a in decision_actions)):
        # Nutrient decisions handled later by Nutrient intent
        if any(n in q for n in ["nitrogen", "phosphorus", "potassium", "fertilizer", "n-p-k", "urea"]):
            return Intent.NUTRIENT
        return Intent.DECISION

    # 5) DATA_QUERY (observations/metrics about their field)
    data_keywords = ["how much", "show me", "history", "graph", "trend", "last month", "this month", "last week", "yesterday"]
    data_metrics = ["rain", "temp", "weather", "precipitation", "ndvi", "moisture", "vv", "vh", "sar"]
    if any(k in q for k in data_keywords) and any(m in q for m in data_metrics):
        # only treat as DATA_QUERY if it is about their field (or implied field context)
        return Intent.DATA_QUERY if has_field or any(k in q for k in ["last month", "this month", "last week", "yesterday"]) else Intent.GENERAL

    # 6) DIAGNOSIS (health check)
    diag_keywords = ["problem", "issue", "risk", "stress", "health", "disease", "pest", "fungal", "yellow", "bug", "status", "how is my field"]
    if any(k in q for k in diag_keywords) or (len(words) <= 6 and has_field):
        return Intent.DIAGNOSIS

    # safer default
    return Intent.GENERAL if not has_field else Intent.DIAGNOSIS


def resolve_time_window(query: str, ref_date: datetime = None) -> Tuple[datetime, datetime]:
    if not ref_date:
        ref_date = datetime.now()
    q = (query or "").lower()

    if "last month" in q:
        first = ref_date.replace(day=1)
        prev_month_end = first - timedelta(days=1)
        start = prev_month_end.replace(day=1)
        return start, prev_month_end

    if "this month" in q:
        start = ref_date.replace(day=1)
        return start, ref_date

    if "last week" in q:
        return ref_date - timedelta(days=7), ref_date

    if "yesterday" in q:
        d = ref_date - timedelta(days=1)
        return d, d

    return ref_date - timedelta(days=14), ref_date
