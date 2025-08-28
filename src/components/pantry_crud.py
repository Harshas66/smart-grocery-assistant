# src/components/pantry_crud.py
import pandas as pd
from pathlib import Path
from datetime import datetime
import os

ART_DIR = Path("artifacts")
DATA_CSV = ART_DIR / "data.csv"
ART_DIR.mkdir(parents=True, exist_ok=True)

REQUIRED_COLS = [
    "User_ID","user_diet","preferred_cuisines","monthly_budget",
    "Product_ID","Product_Name","Brand","Category","unit","unit_price_inr",
    "quantity_on_hand","reorder_level","reorder_quantity","expiration_date"
]

def _ensure_schema(df: pd.DataFrame) -> pd.DataFrame:
    for c in REQUIRED_COLS:
        if c not in df.columns:
            df[c] = pd.Series([None] * len(df))
    return df[REQUIRED_COLS]

def load_inventory(fresh: bool = False) -> pd.DataFrame:
    """
    Load pantry inventory from artifacts/data.csv.
    - If fresh=True OR env FRESH_START=1, ignore any existing file and start empty.
    """
    if fresh or os.getenv("FRESH_START", "0") == "1":
        return pd.DataFrame(columns=REQUIRED_COLS)
    if DATA_CSV.exists():
        try:
            df = pd.read_csv(DATA_CSV)
            return _ensure_schema(df)
        except Exception:
            pass
    return pd.DataFrame(columns=REQUIRED_COLS)

def save_inventory(df: pd.DataFrame):
    df = _ensure_schema(df)
    df.to_csv(DATA_CSV, index=False)

def wipe_inventory() -> pd.DataFrame:
    """Delete the CSV file and return an empty inventory DataFrame."""
    try:
        DATA_CSV.unlink(missing_ok=True)
    except Exception:
        pass
    return pd.DataFrame(columns=REQUIRED_COLS)

def add_item(df: pd.DataFrame, item: dict) -> pd.DataFrame:
    if not item.get("Product_ID"):
        item["Product_ID"] = int(datetime.now().timestamp() * 1000)
    row = {c: item.get(c) for c in REQUIRED_COLS}
    out = pd.concat([_ensure_schema(df), pd.DataFrame([row])], ignore_index=True)
    return out

def update_qty(df: pd.DataFrame, product_id, new_qty) -> pd.DataFrame:
    out = _ensure_schema(df).copy()
    if "Product_ID" in out.columns:
        mask = out["Product_ID"] == product_id
        if not mask.any():
            try:
                mask = out["Product_ID"] == int(float(product_id))
            except Exception:
                pass
        if mask.any():
            out.loc[mask, "quantity_on_hand"] = new_qty
    return out

def delete_item(df: pd.DataFrame, product_id) -> pd.DataFrame:
    out = _ensure_schema(df).copy()
    if "Product_ID" in out.columns:
        try:
            pid = int(float(product_id))
            mask = out["Product_ID"] != pid
        except Exception:
            mask = out["Product_ID"] != product_id
        out = out[mask].reset_index(drop=True)
    return out