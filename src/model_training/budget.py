# src/model_training/budget.py
"""
Lightweight in-memory budget helpers for the Smart Grocery Assistant.

This module intentionally keeps state in a simple dict so it can be
stored in Streamlit's st.session_state, e.g.:

    b = st.session_state.setdefault("budget", DEFAULT_BUDGET.copy())
    set_budget(b, 20000)
    record_spend(b, 1299)
    add_planned(b, 800)
    status = check_budget_status(b)

If you need persistent transaction history, use src/components/budget_store.py.
"""

from __future__ import annotations
from typing import Dict, Any

DEFAULT_BUDGET: Dict[str, float] = {
    "monthly_budget": 0.0,
    "spent_this_month": 0.0,
    "planned_spend": 0.0,
}

def _ensure(state: Dict[str, Any]) -> Dict[str, float]:
    """Guarantee required keys exist; coerce to floats."""
    if state is None:
        state = {}
    for k, v in DEFAULT_BUDGET.items():
        state.setdefault(k, v)
        try:
            state[k] = float(state[k])
        except (TypeError, ValueError):
            state[k] = v
    return state  # mutated in place

def set_budget(state: Dict[str, Any], amount_inr: float) -> Dict[str, float]:
    """Set the monthly budget (₹)."""
    s = _ensure(state)
    s["monthly_budget"] = max(0.0, float(amount_inr or 0.0))
    return s

def record_spend(state: Dict[str, Any], amount_inr: float) -> Dict[str, float]:
    """Increase 'spent_this_month' by amount (₹)."""
    s = _ensure(state)
    inc = max(0.0, float(amount_inr or 0.0))
    s["spent_this_month"] += inc
    return s

def add_planned(state: Dict[str, Any], amount_inr: float) -> Dict[str, float]:
    """Increase 'planned_spend' by amount (₹)."""
    s = _ensure(state)
    inc = max(0.0, float(amount_inr or 0.0))
    s["planned_spend"] += inc
    return s

def set_planned(state: Dict[str, Any], amount_inr: float) -> Dict[str, float]:
    """Overwrite 'planned_spend' with amount (₹)."""
    s = _ensure(state)
    s["planned_spend"] = max(0.0, float(amount_inr or 0.0))
    return s

def clear_planned(state: Dict[str, Any]) -> Dict[str, float]:
    """Zero out 'planned_spend'."""
    s = _ensure(state)
    s["planned_spend"] = 0.0
    return s

def reset_month(state: Dict[str, Any]) -> Dict[str, float]:
    """Start a new month: clear spend and planned; keep the budget cap."""
    s = _ensure(state)
    s["spent_this_month"] = 0.0
    s["planned_spend"] = 0.0
    return s

def remaining_amount(state: Dict[str, Any]) -> float:
    """Budget remaining after spent + planned (can be negative)."""
    s = _ensure(state)
    return float(s["monthly_budget"] - s["spent_this_month"] - s["planned_spend"])

def check_budget_status(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return a summary dict with status classification.
    Status:
      - "over"    : remaining < 0
      - "warning" : remaining <= 10% of budget (and budget > 0)
      - "ok"      : otherwise
    """
    s = _ensure(state)
    rem = remaining_amount(s)
    budget = s["monthly_budget"]
    if rem < 0:
        status = "over"
    elif budget > 0 and rem <= 0.10 * budget:
        status = "warning"
    else:
        status = "ok"
    return {
        "monthly_budget": round(budget, 2),
        "spent_this_month": round(s["spent_this_month"], 2),
        "planned_spend": round(s["planned_spend"], 2),
        "remaining": round(rem, 2),
        "status": status,
    }

# Optional convenience alias (used in some older snippets)
check_status = check_budget_status