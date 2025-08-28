# dietary.py
import pandas as pd

def _has_col(df, name):
    return name in df.columns

def filter_by_tag(df: pd.DataFrame, tag: str):
    if df.empty:
        return df

    tag_l = tag.lower()

    # 1) Prefer explicit product_diet_tags from your dataset
    if _has_col(df, "product_diet_tags"):
        mask = df["product_diet_tags"].fillna("").astype(str).str.lower().str.contains(tag_l)
        return df.loc[mask]

    # 2) Try generic variants if present
    for col in ["Dietary_Tags", "dietary_tags", "Tags", "tags"]:
        if _has_col(df, col):
            mask = df[col].fillna("").astype(str).str.lower().str.contains(tag_l)
            return df.loc[mask]

    # 3) Fallback: search by name/category
    mask = df.get("Product_Name", pd.Series([], dtype=str)).astype(str).str.lower().str.contains(tag_l)
    if "Category" in df.columns:
        mask = mask | df["Category"].astype(str).str.lower().str.contains(tag_l)
    return df.loc[mask]

def suggest_items_for_preferences(df: pd.DataFrame, prefs: dict, limit=20):
    if df.empty:
        return df

    out = df.copy()

    # remove items containing allergies (simple name match)
    allergies = [a.lower() for a in prefs.get("allergies", [])]
    if allergies:
        mask = out["Product_Name"].astype(str).str.lower().apply(lambda n: not any(a in n for a in allergies))
        out = out.loc[mask]

    # apply each preference (use keys that are True)
    for pref_key, val in prefs.items():
        if pref_key == "allergies" or not val:
            continue
        out = filter_by_tag(out, pref_key)
        if out.empty:
            break

    return out.head(limit) if not out.empty else pd.DataFrame(columns=df.columns)
