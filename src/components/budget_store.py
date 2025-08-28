# src/components/budget_store.py
import pandas as pd
from pathlib import Path
from datetime import datetime

ART = Path("artifacts")
TXN_CSV = ART / "budget_txn.csv"
ART.mkdir(parents=True, exist_ok=True)

COLUMNS = ["date","item","qty","unit","amount_inr","note"]

def _ensure(df: pd.DataFrame) -> pd.DataFrame:
    for c in COLUMNS:
        if c not in df.columns:
            df[c] = pd.Series([None]*len(df))
    return df[COLUMNS]

def load_txns() -> pd.DataFrame:
    if TXN_CSV.exists():
        try:
            df = pd.read_csv(TXN_CSV)
            return _ensure(df)
        except Exception:
            pass
    return pd.DataFrame(columns=COLUMNS)

def add_txn(date: str, item: str, qty: float, unit: str, amount_inr: float, note: str = ""):
    df = load_txns()
    row = {"date": date, "item": item, "qty": qty, "unit": unit, "amount_inr": amount_inr, "note": note}
    out = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    out.to_csv(TXN_CSV, index=False)

def month_summary(month: int = None, year: int = None) -> dict:
    today = datetime.today()
    m = month or today.month
    y = year or today.year
    df = load_txns()
    if df.empty:
        return {"spent": 0.0, "n": 0}
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    mask = (df["date"].dt.month == m) & (df["date"].dt.year == y)
    sub = df[mask]
    spent = pd.to_numeric(sub["amount_inr"], errors="coerce").fillna(0).sum()
    return {"spent": float(spent), "n": int(len(sub))}