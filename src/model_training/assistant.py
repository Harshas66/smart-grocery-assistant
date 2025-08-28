# src/model_training/assistant.py
import re
import pandas as pd
from src import utils as inv_mod
from src.model_training.recipes import suggest_recipes_from_inventory

def _search(df: pd.DataFrame, q: str) -> pd.DataFrame:
    ql = q.lower().strip()
    obj_cols = [c for c in df.columns if df[c].dtype == "object"]
    if not obj_cols:
        return pd.DataFrame()
    mask = False
    for c in obj_cols:
        mask = mask | df[c].astype(str).str.lower().str.contains(ql, na=False)
    return df[mask]

def answer(query: str, state) -> str | pd.DataFrame:
    q = query.strip().lower()

    # 1) low stock
    if "low stock" in q or "reorder" in q:
        df = state.inventory
        out = inv_mod.low_stock(df)
        return out if len(out) else "No items are at or below reorder level."

    # 2) expiring in N days
    m = re.search(r"expir\w+.*(\d+)\s*day", q)
    if "expiring" in q or "expire" in q or m:
        days = int(m.group(1)) if m else 7
        df = state.inventory
        out = inv_mod.expiring_soon(df, days=days)
        return out if len(out) else f"No items expiring in the next {days} days."

    # 3) budget status
    if "budget" in q or "spent" in q:
        b = state.get("budget", {"monthly_budget":0.0, "spent_this_month":0.0, "planned_spend":0.0})
        return f"Monthly budget ₹{b.get('monthly_budget',0):,.0f}, spent ₹{b.get('spent_this_month',0):,.0f}, planned ₹{b.get('planned_spend',0):,.0f}"

    # 4) do I have X? / search X
    m2 = re.search(r"(have|search|find)\s+(.*)", q)
    if m2:
        term = m2.group(2)
        df = state.inventory
        res = _search(df, term)
        if len(res):
            return res
        return f"Couldn't find '{term}' in your pantry."

    # 5) suggest recipes
    if "recipe" in q or "cook" in q or "make with" in q:
        diet = None
        if "vegan" in q: diet = "vegan"
        if "keto" in q: diet = "keto"
        if "gluten" in q: diet = "gluten-free"
        if "paleo" in q: diet = "paleo"
        df = state.inventory
        try:
            recs = suggest_recipes_from_inventory(df, top_k=10, diet=diet)
            return recs if len(recs) else "No matching recipes found."
        except Exception:
            return "Recipe model not trained yet. Train it first."

    return "I can help with: low stock, expiring items, budget status, quick search (e.g., 'do I have milk?'), and recipe suggestions."
