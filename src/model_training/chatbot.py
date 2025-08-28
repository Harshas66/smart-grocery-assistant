# chatbot.py
from datetime import date
import pandas as pd
from src.utils import low_stock as util_low_stock, expiring_soon as util_expiring_soon

def answer_query(q: str, session_state):
    ql = (q or "").lower()
    inv = session_state.get("inventory")
    b = session_state.get("budget", {"monthly_budget":0.0, "spent_this_month":0.0, "planned_spend":0.0})

    if inv is None or inv.empty:
        return "Your inventory looks empty. Upload a CSV or add products first."

    if "low stock" in ql or "reorder" in ql:
        ls = util_low_stock(inv)
        if ls.empty:
            return "No low stock items."
        rows = []
        for _, r in ls.iterrows():
            qty = r.get("quantity_on_hand", "")
            unit = r.get("unit", "")
            name = r.get("Product_Name", "")
            rows.append(f"- {name} ({qty} {unit})")
        return "Low stock items:\n" + "\n".join(rows)

    if "expiring" in ql:
        days = 7
        import re
        m = re.search(r"(\d+)\s*day", ql)
        if m:
            days = int(m.group(1))
        soon = util_expiring_soon(inv, days=days)
        if soon.empty:
            return f"No items expiring in next {days} days."
        return "Expiring items:\n" + "\n".join(
            [f"- {r.get('Product_Name','')} — {r.get('expiration_date','')}" for _, r in soon.iterrows()]
        )

    if "do we have" in ql or "in stock" in ql or "available" in ql:
        # naive extract: whatever user typed after the keyword
        name = ql.replace("do we have","").replace("in stock","").replace("available","").replace("?","").strip()
        if not name:
            return "Please mention the product name."
        row = inv[inv["Product_Name"].astype(str).str.lower() == name.lower()]
        if row.empty:
            # try contains
            row = inv[inv["Product_Name"].astype(str).str.lower().str.contains(name)]
        if row.empty:
            return f"I couldn't find '{name}' in inventory."
        qty = row["quantity_on_hand"].iloc[0] if "quantity_on_hand" in row.columns else ""
        unit = row["unit"].iloc[0] if "unit" in row.columns else ""
        return f"Yes — {row['Product_Name'].iloc[0]}: {qty} {unit}"

    if "budget" in ql:
        remaining = b["monthly_budget"] - (b["spent_this_month"] + b["planned_spend"])
        return f"Budget: ₹{b['monthly_budget']:.2f}. Spent: ₹{b['spent_this_month']:.2f}. Planned: ₹{b['planned_spend']:.2f}. Remaining: ₹{remaining:.2f}"

    if "today" in ql or "date" in ql:
        return f"Today is {date.today().isoformat()}."

    return "I can help with inventory (low stock, availability), expiry checks, and budget questions."
