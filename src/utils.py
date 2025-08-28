# src/utils.py
import pandas as pd

def low_stock(inventory: pd.DataFrame, threshold_col: str = "reorder_level") -> pd.DataFrame:
    if inventory is None or inventory.empty:
        return pd.DataFrame(columns=inventory.columns if inventory is not None else [])
    cols = inventory.columns
    if "quantity_on_hand" not in cols or threshold_col not in cols:
        return pd.DataFrame(columns=cols)
    inv = inventory.copy()
    inv["quantity_on_hand"] = pd.to_numeric(inv["quantity_on_hand"], errors="coerce")
    inv[threshold_col] = pd.to_numeric(inv[threshold_col], errors="coerce")
    return inv[inv["quantity_on_hand"] <= inv[threshold_col]].fillna("")

def expiring_soon(inventory: pd.DataFrame, days: int = 7) -> pd.DataFrame:
    if inventory is None or inventory.empty or "expiration_date" not in inventory.columns:
        return pd.DataFrame(columns=inventory.columns if inventory is not None else [])
    inv = inventory.copy()
    inv["expiration_date"] = pd.to_datetime(inv["expiration_date"], errors="coerce")
    today = pd.Timestamp.today().normalize()
    mask = (inv["expiration_date"] >= today) & ((inv["expiration_date"] - today).dt.days <= int(days))
    return inv[mask].sort_values("expiration_date", na_position="last").fillna("")