
from enum import Enum
from typing import Tuple, Dict, Optional
from datetime import datetime, timedelta
import re
import calendar

class Intent(Enum):
    DATA_QUERY = "DATA_QUERY"       # "How much rain?" -> L1 only
    DIAGNOSIS = "DIAGNOSIS"         # "Is there stress?" -> L1+L2+L5
    DECISION = "DECISION"           # "Should I irrigate?" -> Full L3
    NUTRIENT = "NUTRIENT"           # "Nitrogen status?" -> L4
    EXECUTION_STATUS = "EXECUTION"  # "Did task X finish?" -> L6
    SCENARIO = "SCENARIO"           # "What if..." -> L7
    UNKNOWN = "UNKNOWN"             # Fallback -> Full Run or Clarification

def detect_intent(query: str) -> Intent:
    """
    Deterministic rule-based intent classification.
    """
    q = query.lower().strip()
    
    # 1. Data Query (Observational)
    # Keywords: how much, what is, show me, history, last month rain
    data_keywords = ["how much", "what is", "show me", "history", "graph", "plot"]
    data_metrics = ["rain", "temp", "weather", "precipitation", "ndvi", "moisture", "growth"]
    
    # Check if simple quantity query
    if any(k in q for k in data_keywords) and any(m in q for m in data_metrics):
        # Exclusion: "What is the problem?" -> Diagnosis
        if "problem" in q or "issue" in q or "risk" in q:
            return Intent.DIAGNOSIS
        return Intent.DATA_QUERY
        
    # 2. Diagnosis (Health Check)
    diag_keywords = ["problem", "issue", "risk", "stress", "health", "disease", "pest", "fungal", "yellow", "bug"]
    if any(k in q for k in diag_keywords):
        return Intent.DIAGNOSIS
        
    # 3. Decision (Actionable)
    decision_keywords = ["should i", "do i need", "recommend", "advice", "action", "irrigate", "spray", "harvest"]
    if any(k in q for k in decision_keywords):
        return Intent.DECISION
        
    # 4. Nutrient
    nutrient_keywords = ["nitrogen", "phosphorus", "fertilizer", "nutrient", "n-p-k", "urea"]
    if any(k in q for k in nutrient_keywords):
        return Intent.NUTRIENT
        
    # Default to DECISION (Safe default for "Help me") or UNKNOWN?
    # User requested deterministic. If unsure, maybe run Full Analysis (DECISION).
    return Intent.DECISION

def resolve_time_window(query: str, ref_date: datetime = None) -> Tuple[datetime, datetime]:
    """
    Parses natural language time range.
    Default: Last 14 days.
    """
    if not ref_date:
        ref_date = datetime.now()
        
    q = query.lower()
    
    # "Last Month"
    if "last month" in q:
        # First day of previous month
        # If current is March, prev is Feb.
        first = ref_date.replace(day=1)
        prev_month_end = first - timedelta(days=1)
        start = prev_month_end.replace(day=1)
        end = prev_month_end
        return start, end
        
    # "This Month"
    if "this month" in q:
        start = ref_date.replace(day=1)
        return start, ref_date

    # "Last Week"
    if "last week" in q:
        start = ref_date - timedelta(days=7)
        return start, ref_date
    
    # "Yesterday"
    if "yesterday" in q:
        d = ref_date - timedelta(days=1)
        return d, d

    # Default
    return ref_date - timedelta(days=14), ref_date
