# shopping_list.py
import pandas as pd

def add_to_list(shopping_list: list, item: dict):
    """
    item: {"name","qty","unit","est_price","note"}
    """
    shopping_list.append(item)
    return shopping_list

def remove_from_list(shopping_list: list, index: int):
    if 0 <= index < len(shopping_list):
        shopping_list.pop(index)
    return shopping_list

def estimate_total(shopping_list: list):
    total = 0.0
    for it in shopping_list:
        price = float(it.get("est_price", 0) or 0)
        total += price
    return round(total, 2)

def as_dataframe(shopping_list: list):
    if not shopping_list:
        return pd.DataFrame(columns=["name","qty","unit","est_price","note"])
    df = pd.DataFrame(shopping_list)
    df["est_price"] = pd.to_numeric(df["est_price"], errors="coerce").fillna(0.0)
    return df
