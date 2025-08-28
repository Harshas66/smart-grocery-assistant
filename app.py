# app.py
import os
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import pandas as pd
import streamlit as st
import requests

# ---------------- App Config ----------------
st.set_page_config(page_title="Smart Grocery Assistant", page_icon="🛒", layout="wide")
ART_DIR = Path(os.getenv("ARTIFACTS_DIR", "artifacts"))
ART_DIR.mkdir(parents=True, exist_ok=True)

# ---------------- Spoonacular KEY POOL (rotation) ----------------
# Prefer env var SPOON_KEYS as comma-separated keys; else use the provided keys.
_env_keys = (os.getenv("SPOON_KEYS") or "").strip()
if _env_keys:
    KEYS = [k.strip() for k in _env_keys.split(",") if k.strip()]
else:
    KEYS = [
        "b2ea4797723744c889f6fad85b347bcb",
        "2f2b0f15d12346048bd4383176acfaed",
    ]

st.session_state.setdefault("key_index", 0)

def current_key() -> str:
    if not KEYS:
        return ""
    return (KEYS[st.session_state.key_index] or "").strip()

def call_spoonacular(endpoint: str, params: dict, timeout: int = 12) -> Optional[requests.Response]:
    """
    Make a Spoonacular API call with the current key.
    If 401/402/429, rotate to next key and retry (up to number of KEYS).
    Returns Response or None if all keys fail.
    """
    n = max(1, len(KEYS))
    for _ in range(n):
        k = current_key()
        if not k:
            st.session_state.key_index = (st.session_state.key_index + 1) % n
            continue
        params = dict(params or {})
        params["apiKey"] = k
        try:
            r = requests.get(f"https://api.spoonacular.com{endpoint}", params=params, timeout=timeout)
            if r.status_code in (401, 402, 429):
                # rotate key and try next
                st.session_state.key_index = (st.session_state.key_index + 1) % n
                continue
            return r
        except Exception:
            # network/timeout; rotate and try next
            st.session_state.key_index = (st.session_state.key_index + 1) % n
            continue
    return None

# ---------------- Project Imports ----------------
from src.components.theme import set_background
from src.components.auth import login_ui, signup_ui
from src.components.budget_store import add_txn, month_summary
from src.components.pantry_crud import (
    load_inventory,
    save_inventory,
    add_item as pantry_add_item,
    update_qty as pantry_update_qty,
    delete_item as pantry_delete_item,
    wipe_inventory,
)
from src import utils as inv_mod
from src.model_training import shopping_list as sl_mod
from src.model_training import budget as budget_mod

# ---------------- Global Styles / Animations ----------------
def add_global_css():
    st.markdown(
        """
        <style>
        html, body, [class*="css"] { -webkit-font-smoothing: antialiased; }

        .section-title { font-weight: 800; font-size: 1.35rem; margin: .4rem 0 .75rem 0; }

        .soft-card {
          border-radius: 18px; background: rgba(255,255,255,.90);
          box-shadow: 0 10px 25px rgba(0,0,0,.08);
          padding: 1rem 1.1rem; transition: transform .2s ease, box-shadow .25s ease, background .2s ease;
          animation: fadeInUp .4s ease both;
        }
        .soft-card:hover { transform: translateY(-3px); box-shadow: 0 14px 34px rgba(0,0,0,.12); }

        /* Inventory grid + cards */
        .inv-grid {
          display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
          gap: 14px; align-items: stretch;
        }
        .inv-card {
          border-radius: 16px;
          background: #ffffff;
          box-shadow: 0 8px 20px rgba(0,0,0,.07);
          padding: 12px 14px; transition: transform .18s ease, box-shadow .2s ease;
          border: 1px solid rgba(0,0,0,.06); animation: fadeIn .35s ease both;
          color: #0f172a;
        }
        .inv-card * { color: #0f172a !important; }
        .inv-name { font-weight: 800; font-size: 1.02rem; margin-bottom: 4px; }
        .inv-meta { font-size: .9rem; color: #1f2937 !important; line-height: 1.25rem; }

        .pill { display: inline-block; padding: 3px 10px; border-radius: 999px;
          background: rgba(59,130,246,.12); color:#1f4ed8; font-size: .78rem; font-weight: 700; }
        .pill.warn { background: rgba(245,158,11,.18); color:#92400e; }
        .pill.danger { background: rgba(239,68,68,.18); color:#991b1b; }

        /* Animated progress bars */
        .bar-wrap { background: rgba(255,255,255,.15); border-radius: 999px; overflow: hidden; height: 12px; }
        .bar {
          height: 100%; width: 0%; border-radius: 999px;
          background: repeating-linear-gradient(
            45deg, rgba(59,130,246,.9) 0, rgba(59,130,246,.9) 10px, rgba(37,99,235,.9) 10px, rgba(37,99,235,.9) 20px
          );
          animation: growBar 1.1s ease forwards, barberpole 8s linear infinite;
        }
        .bar.alt {
          background: repeating-linear-gradient(
            45deg, rgba(16,185,129,.9) 0, rgba(16,185,129,.9) 10px, rgba(5,150,105,.9) 10px, rgba(5,150,105,.9) 20px
          );
        }
        @keyframes growBar { from { width: 0% } to { width: var(--pct, 0%) } }
        @keyframes barberpole { to { background-position: 100px 0; } }

        @keyframes fadeIn { from {opacity:0; transform: translateY(4px);} to {opacity:1; transform: translateY(0);} }
        @keyframes fadeInUp { from {opacity:0; transform: translateY(8px);} to {opacity:1; transform: translateY(0);} }
        </style>
        """,
        unsafe_allow_html=True,
    )
add_global_css()

# ---------------- Cache for recipes ----------------
CACHE_DIR = ART_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
LIST_CACHE = CACHE_DIR / "recipes_cache.json"
DETAILS_DIR = CACHE_DIR / "recipe_details"
DETAILS_DIR.mkdir(parents=True, exist_ok=True)
CACHE_TTL_DAYS = 3

def _read_json(path: Path, default):
    try:
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default

def _write_json(path: Path, data):
    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def _now_iso():
    return datetime.utcnow().isoformat()

def _is_fresh(iso_str: str, days: int = CACHE_TTL_DAYS) -> bool:
    try:
        ts = datetime.fromisoformat(iso_str.replace("Z",""))
        return datetime.utcnow() - ts <= timedelta(days=days)
    except Exception:
        return False

def _cache_key(ingredients: List[str], diet: str|None, number: int) -> str:
    norm = ",".join(sorted(x.strip().lower() for x in ingredients if x)).strip()
    d = (diet or "none").lower()
    return f"{norm}|{d}|{int(number or 10)}"

# ---- Offline/demo support ----
DEMO_RECIPES_FILE = ART_DIR / "demo_recipes.json"
DEMO_DETAILS_DIR = ART_DIR / "demo_recipe_details"
DEMO_DETAILS_DIR.mkdir(parents=True, exist_ok=True)

def _load_demo_recipes() -> list[dict]:
    demo = _read_json(DEMO_RECIPES_FILE, None)
    if isinstance(demo, list) and demo:
        return demo
    return [
        {"id": 910001, "title": "Masala Khichdi", "image": None, "usedIngredientCount": 4,
         "missedIngredientCount": 0, "readyInMinutes": 28, "servings": 2},
        {"id": 910002, "title": "Paneer Bhurji Wrap", "image": None, "usedIngredientCount": 5,
         "missedIngredientCount": 0, "readyInMinutes": 20, "servings": 2},
        {"id": 910003, "title": "Garlic Butter Pasta", "image": None, "usedIngredientCount": 3,
         "missedIngredientCount": 1, "readyInMinutes": 18, "servings": 2},
    ]

def _load_demo_details(recipe_id: int):
    p = DEMO_DETAILS_DIR / f"{recipe_id}.json"
    return _read_json(p, None)

# ---------------- Session State Init ----------------
def init_state():
    fresh = os.getenv("FRESH_START", "0") == "1"
    if "inventory" not in st.session_state:
        st.session_state.inventory = load_inventory(fresh=fresh)
    if "budget" not in st.session_state:
        st.session_state.budget = budget_mod.DEFAULT_BUDGET.copy()
    if "shopping_list" not in st.session_state:
        st.session_state.shopping_list = []
    st.session_state.setdefault("user_diet", "none")
    st.session_state.setdefault("preferred_cuisines", "Indian;Italian")
    st.session_state.setdefault("user", None)
    st.session_state.setdefault("recipes_cache", [])
    st.session_state.setdefault("selected_recipe_id", None)
    st.session_state.setdefault("extra_planned_inr", 0.0)
    st.session_state.setdefault("offline_mode", False)
init_state()

def inv_df() -> pd.DataFrame:
    df = st.session_state.get("inventory")
    if df is None:
        df = load_inventory(fresh=False)
        st.session_state.inventory = df
    return df

# ---------------- Global Auth Gate ----------------
def ensure_authenticated():
    if st.session_state.get("user"):
        return True
    try: set_background("dashboard.jpg", darken=0.35)
    except Exception: pass
    st.title("🛒 Smart Grocery Assistant")
    st.subheader("Welcome — please sign in")
    with st.expander("Login / Signup", expanded=True):
        tabs = st.tabs(["Login", "Signup"])
        with tabs[0]: login_ui()
        with tabs[1]: signup_ui()
    st.stop()

# ---------------- Helpers ----------------
def pantry_names(df: pd.DataFrame) -> List[str]:
    if df.empty or "Product_Name" not in df.columns:
        return []
    return [str(x).strip() for x in df["Product_Name"].dropna().tolist() if str(x).strip()]

def pantry_lookup(df: pd.DataFrame, name: str) -> Optional[Dict[str, Any]]:
    if df.empty or not name:
        return None
    m = df[df["Product_Name"].astype(str).str.lower() == name.lower()]
    return m.iloc[0].to_dict() if not m.empty else None

def get_pid_by_name(df: pd.DataFrame, name: str):
    if df.empty or "Product_Name" not in df.columns or "Product_ID" not in df.columns:
        return None
    m = df[df["Product_Name"].astype(str).str.lower() == str(name).lower()]
    return None if m.empty else m.iloc[0]["Product_ID"]

def _clean_text(val: Any) -> str:
    s = str(val) if val is not None else ""
    if s.lower() in ("nan", "none", "null"): return ""
    return s

def inv_card_html(name: str, qty, unit, expiry: str, brand: str = "", cat: str = "") -> str:
    badge = ""
    try:
        q = float(qty)
        if q <= 0: badge = '<span class="pill danger">Out</span>'
        elif q <= 1: badge = '<span class="pill warn">Low</span>'
    except Exception:
        pass
    name_html = f"{name} {badge}".strip()
    brand = _clean_text(brand); cat = _clean_text(cat)
    tail = " • ".join(x for x in [brand, cat] if x)
    tail = f" • {tail}" if tail else ""
    exp_str = expiry if expiry else "—"
    return (
        f"<div class='inv-card'>"
        f"<div class='inv-name'>{name_html}</div>"
        f"<div class='inv-meta'>Qty: <b>{qty}</b> {unit}</div>"
        f"<div class='inv-meta'>Expiry: <b>{exp_str}</b></div>"
        f"<div class='inv-meta' style='opacity:.8;'>{tail}</div>"
        f"</div>"
    )

def render_inventory_grid(df: pd.DataFrame, query: str = ""):
    if df.empty or "Product_Name" not in df.columns:
        st.info("No items yet. Add your first item in the **Add Item** tab.")
        return
    show = df
    if query:
        show = df[df["Product_Name"].astype(str).str.contains(query, case=False, na=False)]
    cards = []
    for _, row in show.iterrows():
        cards.append(
            inv_card_html(
                str(row.get("Product_Name","")),
                row.get("quantity_on_hand",""),
                row.get("unit",""),
                str(row.get("expiration_date","") or ""),
                row.get("Brand",""),
                row.get("Category",""),
            )
        )
    html = "<div class='inv-grid'>" + "".join(cards) + "</div>"
    st.markdown(html, unsafe_allow_html=True)

def quick_yes_no(df: pd.DataFrame, item: str) -> str:
    for n in pantry_names(df):
        if item.lower() in n.lower():
            return f"✅ Yes, you have **{n}**."
    return f"❌ No, **{item}** not found."

# ---------------- Image helpers ----------------
def _build_img_from_id(rid: Any, image_type: Optional[str]) -> Optional[str]:
    """Construct a Spoonacular CDN URL if we have id + imageType."""
    try:
        rid_int = int(rid)
    except Exception:
        return None
    if not image_type:
        return None
    return f"https://img.spoonacular.com/recipes/{rid_int}-556x370.{image_type}"

def _fix_image_url(val: Any, rid: Any = None, image_type: Optional[str] = None) -> Optional[str]:
    """
    Normalize/construct a usable image URL.
    Priority:
      1) Full http(s)/data URL provided by API
      2) Filename -> prefix CDN base path
      3) Fallback from (id + imageType)
    """
    if isinstance(val, str) and val.strip():
        v = val.strip()
        if v.startswith(("http://", "https://", "data:")):
            return v
        if v.endswith((".jpg", ".jpeg", ".png")) and "/" not in v:
            return f"https://img.spoonacular.com/recipes/{v}"
    built = _build_img_from_id(rid, image_type)
    if built:
        return built
    return None

def _render_safe_image(img_val: Any, rid: Any = None, image_type: Optional[str] = None):
    """Safely render recipe images (skip invalid ones)."""
    try:
        url = _fix_image_url(img_val, rid=rid, image_type=image_type)
        if url:
            st.image(url, use_container_width=False)
            return True
        return False
    except Exception:
        return False

# ---------------- Recipes (cache/offline + key rotation) ----------------
def spoonacular_recipes(include_ingredients: List[str], diet: str | None, number: int = 10, debug: bool = False) -> List[Dict[str, Any]]:
    # Offline mode: return cache or demo; skip network entirely
    if st.session_state.get("offline_mode", False):
        ingredients = [x.strip() for x in (include_ingredients or []) if x and x.strip()]
        diet_norm = (diet or "none").lower()
        key = _cache_key(ingredients, diet_norm, number)
        blob = _read_json(LIST_CACHE, {"items": {}, "meta": {}})
        entry = blob["items"].get(key)
        if entry and _is_fresh(entry.get("ts", "")):
            if debug: st.caption("Offline: serving cached results ✅")
            return entry.get("data", [])
        if debug: st.caption("Offline: serving demo recipes ✅")
        return _load_demo_recipes()

    diet_map = {"keto": "ketogenic", "gluten-free": "gluten free", "paleo": "paleolithic", "none": None, None: None}
    diet_norm = diet_map.get((diet or "").lower(), (diet or ""))

    ingredients = [x.strip() for x in (include_ingredients or []) if x and x.strip()]
    if not ingredients: ingredients = ["egg", "milk", "bread"]

    key = _cache_key(ingredients, diet_norm or "none", number)
    blob = _read_json(LIST_CACHE, {"items": {}, "meta": {}})
    entry = blob["items"].get(key)
    if entry and _is_fresh(entry.get("ts", "")):
        if debug: st.caption("Serving recipes from cache ✅")
        return entry.get("data", [])

    def _save_and_return(data_list: list[dict]):
        blob["items"][key] = {"ts": _now_iso(), "data": data_list}
        _write_json(LIST_CACHE, blob)
        return data_list

    # Attempt 1: complexSearch via key-rotating wrapper
    params = {
        "includeIngredients": ",".join(ingredients[:20]),
        "fillIngredients": "true",
        "addRecipeInformation": "true",
        "instructionsRequired": "true",
        "number": int(number or 10),
        "sort": "meta-score",
    }
    if diet_norm:
        params["diet"] = diet_norm

    try:
        r = call_spoonacular("/recipes/complexSearch", params)
        if debug and r is not None: st.caption(f"[complexSearch] status={r.status_code}")
        if r and r.status_code == 200:
            results = (r.json() or {}).get("results", []) or []
            summaries = []
            for rec in results:
                rid = rec.get("id")
                img = _fix_image_url(rec.get("image"), rid=rid, image_type=rec.get("imageType"))
                summaries.append({
                    "id": rid,
                    "title": rec.get("title"),
                    "image": img,
                    "usedIngredientCount": rec.get("usedIngredientCount"),
                    "missedIngredientCount": rec.get("missedIngredientCount"),
                    "sourceUrl": rec.get("sourceUrl") or rec.get("spoonacularSourceUrl"),
                    "readyInMinutes": rec.get("readyInMinutes"),
                    "servings": rec.get("servings"),
                    "imageType": rec.get("imageType"),
                })
            if summaries: return _save_and_return(summaries)
        elif r is None:
            # all keys failed → cache/demo
            return entry.get("data", []) if entry else _load_demo_recipes()
    except Exception as e:
        if debug: st.caption(f"complexSearch failed: {e}")

    # Attempt 2: findByIngredients (fallback)
    try:
        params2 = {
            "ingredients": ",".join(ingredients[:20]),
            "number": int(number or 10),
            "ranking": 1,
            "ignorePantry": "true",
        }
        r2 = call_spoonacular("/recipes/findByIngredients", params2)
        if debug and r2 is not None: st.caption(f"[findByIngredients] status={r2.status_code}")
        if r2 and r2.status_code == 200:
            arr = r2.json() or []
            out = []
            for rec in arr:
                rid = rec.get("id")
                img = _fix_image_url(rec.get("image"), rid=rid, image_type=rec.get("imageType"))
                out.append({
                    "id": rid,
                    "title": rec.get("title"),
                    "image": img,
                    "usedIngredientCount": rec.get("usedIngredientCount") or 0,
                    "missedIngredientCount": rec.get("missedIngredientCount") or 0,
                    "sourceUrl": None,
                    "readyInMinutes": None,
                    "servings": None,
                    "imageType": rec.get("imageType"),
                })
            if out: return _save_and_return(out)
        elif r2 is None:
            return entry.get("data", []) if entry else _load_demo_recipes()
    except Exception as e:
        if debug: st.caption(f"findByIngredients failed: {e}")

    # If everything failed
    return entry.get("data", []) if entry else _load_demo_recipes()

def spoonacular_recipe_details(recipe_id: int) -> Optional[Dict[str, Any]]:
    if not recipe_id: return None

    # 1) cache
    detail_path = DETAILS_DIR / f"{recipe_id}.json"
    cached = _read_json(detail_path, None)
    if cached: return cached

    # 2) demo local details
    demo = _load_demo_details(recipe_id)
    if demo: return demo

    # 3) API (rotating keys)
    params = {"includeNutrition": "false"}
    try:
        r = call_spoonacular(f"/recipes/{int(recipe_id)}/information", params)
        if not r or r.status_code != 200:
            return None
        data = r.json()
        details = {
            "id": data.get("id"),
            "title": data.get("title"),
            "image": _fix_image_url(data.get("image"), rid=data.get("id"), image_type=data.get("imageType")),
            "readyInMinutes": data.get("readyInMinutes"),
            "servings": data.get("servings"),
            "sourceUrl": data.get("sourceUrl") or data.get("spoonacularSourceUrl"),
            "ingredients": [
                {"name": ing.get("name"), "amount": ing.get("amount"), "unit": ing.get("unit"), "original": ing.get("original")}
                for ing in (data.get("extendedIngredients") or [])
            ],
            "steps": [
                step.get("step")
                for inst in (data.get("analyzedInstructions") or [])
                for step in (inst.get("steps") or [])
                if step.get("step")
            ] or ([data.get("instructions")] if data.get("instructions") else []),
        }
        _write_json(detail_path, details)
        return details
    except Exception:
        return None

def render_recipe_card(summary: Dict[str, Any], expanded: bool = False):
    rid = summary["id"]
    with st.container():
        st.markdown('<div class="soft-card">', unsafe_allow_html=True)
        st.markdown(
            f"**{summary.get('title','(No title)')}**  |  ⏱️ {summary.get('readyInMinutes','?')} min • "
            f"🍽️ {summary.get('servings','?')} servings"
        )

        # Safe image display (after normalization, with id fallback)
        _render_safe_image(summary.get("image"), rid=rid, image_type=summary.get("imageType"))

        st.write(
            f"Used: {summary.get('usedIngredientCount', 0) or 0} • "
            f"Missing: {summary.get('missedIngredientCount', 0) or 0}"
        )
        colA, colB = st.columns(2)
        with colA:
            if st.button("View here", key=f"view_{rid}"):
                st.session_state.selected_recipe_id = rid
        with colB:
            if summary.get("sourceUrl"):
                st.link_button("Open original", summary["sourceUrl"])

        if expanded or st.session_state.get("selected_recipe_id") == rid:
            details = spoonacular_recipe_details(rid)
            if not details:
                st.info("Couldn’t load details.")
            else:
                st.markdown("**Ingredients**")
                if details["ingredients"]:
                    for ing in details["ingredients"]:
                        txt = ing.get("original") or f"{ing.get('amount','')} {ing.get('unit','')} {ing.get('name','')}"
                        st.write(f"• {txt}")
                else:
                    st.write("_No ingredients listed_")
                st.markdown("**Steps**")
                if details["steps"]:
                    for i, step in enumerate(details["steps"], start=1):
                        st.write(f"{i}. {step}")
                else:
                    st.write("_No step-by-step instructions provided_")
        st.markdown('</div>', unsafe_allow_html=True)

def progress_bar(percent: float, alt: bool = False):
    pct = max(0.0, min(100.0, percent))
    klass = "bar alt" if alt else "bar"
    st.markdown(f'<div class="bar-wrap"><div class="{klass}" style="--pct:{pct:.2f}%;"></div></div>', unsafe_allow_html=True)

# ---------------- Gate app until login ----------------
ensure_authenticated()

# ---------------- Sidebar ----------------
with st.sidebar:
    st.title("🛠️ Menu")
    menu = st.radio("Go to", ["Dashboard", "Inventory", "Recipes", "Shopping List", "Budget", "Assistant"], index=0)

    st.divider()
    st.caption(f"Signed in as {st.session_state['user']['username']}")
    if st.button("Log out"):
        st.session_state.user = None
        st.rerun()

    st.divider()
    st.markdown("### ➕ Quick Add")
    qa_name = st.text_input("Item name", key="qa_name")
    qa_qty = st.number_input("Qty", 0.0, 1e6, 1.0, key="qa_qty")
    qa_unit = st.text_input("Unit", "pcs", key="qa_unit")
    qa_brand = st.text_input("Brand", "", key="qa_brand")
    qa_cat = st.text_input("Category", "", key="qa_cat")
    qa_price = st.number_input("Unit price (₹)", 0.0, 1e7, 0.0, key="qa_price")
    qa_reorder = st.number_input("Reorder level", 0.0, 1e6, 1.0, key="qa_reorder")
    qa_req = st.number_input("Reorder qty", 0.0, 1e6, 1.0, key="qa_req")
    qa_exp = st.date_input("Expiry", value=datetime.today(), key="qa_exp")
    if st.button("Add", type="primary", use_container_width=True):
        df = inv_df()
        new_row = {
            "User_ID": 1, "user_diet": st.session_state.get("user_diet", "none"),
            "preferred_cuisines": st.session_state.get("preferred_cuisines", "Indian;Italian"),
            "monthly_budget": st.session_state.get("budget", {}).get("monthly_budget", 0.0),
            "Product_ID": None, "Product_Name": qa_name, "Brand": qa_brand, "Category": qa_cat,
            "unit": qa_unit, "unit_price_inr": qa_price, "quantity_on_hand": qa_qty,
            "reorder_level": qa_reorder, "reorder_quantity": qa_req, "expiration_date": str(qa_exp),
        }
        st.session_state.inventory = pantry_add_item(df, new_row)
        save_inventory(st.session_state.inventory)
        st.success(f"Added {qa_name}")
        st.rerun()

    st.divider()
    st.markdown("### 🔎 Quick Check")
    qc_term = st.text_input("Do I have…?")
    if st.button("Check"):
        st.write(quick_yes_no(inv_df(), qc_term))

# ---------------- Pages ----------------
st.title("🛒 Smart Grocery Assistant")

# Dashboard
if menu == "Dashboard":
    set_background("dashboard.jpg", darken=0.25)
    st.markdown('<div class="section-title">Overview</div>', unsafe_allow_html=True)
    df = inv_df()
    soon = inv_mod.expiring_soon(df, days=7)
    low  = inv_mod.low_stock(df)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="soft-card">', unsafe_allow_html=True)
        st.markdown("#### Expiring soon (7 days)")
        names = pantry_names(soon)[:10]
        if names: st.write("• " + "\n• ".join(names))
        else: st.success("No items expiring this week 🎉")
        st.markdown('</div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="soft-card">', unsafe_allow_html=True)
        st.markdown("#### Low stock")
        ln = pantry_names(low)[:10]
        if ln: st.write("• " + "\n• ".join(ln))
        else: st.success("No low-stock items right now")
        st.markdown('</div>', unsafe_allow_html=True)

# Inventory
elif menu == "Inventory":
    set_background("inventory.jpg", darken=0.2)
    st.markdown('<div class="section-title">Inventory</div>', unsafe_allow_html=True)

    inv_tabs = st.tabs(["Browse", "Add Item", "Edit / Delete", "Danger Zone"])

    # Browse
    with inv_tabs[0]:
        st.markdown("#### Your pantry")
        df = inv_df()
        q = st.text_input("Search by name", key="inv_search")
        render_inventory_grid(df, q)

    # Add
    with inv_tabs[1]:
        st.markdown('<div class="soft-card">', unsafe_allow_html=True)
        st.markdown("#### Add a new item")
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1: p_name = st.text_input("Product name")
        with c2: qty = st.number_input("Quantity", 0.0, 1e6, 1.0)
        with c3: unit = st.text_input("Unit", "pcs")
        brand = st.text_input("Brand")
        cat = st.text_input("Category")
        price = st.number_input("Unit price (₹)", 0.0, 1e7, 0.0)
        reorder_level = st.number_input("Reorder level", 0.0, 1e7, 1.0)
        reorder_qty = st.number_input("Reorder qty", 0.0, 1e7, 1.0)
        expiry = st.date_input("Expiry date", value=datetime.today())
        if st.button("Add to pantry"):
            df = inv_df()
            new_row = {
                "User_ID": 1, "user_diet": st.session_state.get("user_diet", "none"),
                "preferred_cuisines": st.session_state.get("preferred_cuisines", "Indian;Italian"),
                "monthly_budget": st.session_state.get("budget", {}).get("monthly_budget", 0.0),
                "Product_ID": None, "Product_Name": p_name, "Brand": brand, "Category": cat, "unit": unit,
                "unit_price_inr": price, "quantity_on_hand": qty, "reorder_level": reorder_level,
                "reorder_quantity": reorder_qty, "expiration_date": str(expiry),
            }
            st.session_state.inventory = pantry_add_item(df, new_row)
            save_inventory(st.session_state.inventory)
            st.success(f"Added {p_name}")
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    # Edit/Delete
    with inv_tabs[2]:
        st.markdown('<div class="soft-card">', unsafe_allow_html=True)
        st.markdown("#### Quick edit / delete")
        df = inv_df()
        names_list = pantry_names(df)
        if names_list:
            sel_name = st.selectbox("Pick item", options=names_list)
            if sel_name:
                pid = get_pid_by_name(df, sel_name)
                current = pantry_lookup(df, sel_name) or {}
                st.caption(f"Current: {current.get('quantity_on_hand','?')} {current.get('unit','')}")
                new_q = st.number_input("New quantity", 0.0, 1e9, float(current.get("quantity_on_hand", 1) or 1), key="edit_qty")
                cA, cB = st.columns(2)
                if cA.button("Update"):
                    st.session_state.inventory = pantry_update_qty(df, pid, new_q); save_inventory(st.session_state.inventory)
                    st.success("Updated."); st.rerun()
                if cB.button("Delete"):
                    st.session_state.inventory = pantry_delete_item(df, pid); save_inventory(st.session_state.inventory)
                    st.warning("Deleted."); st.rerun()
        else:
            st.caption("Add items to enable quick edit/delete.")
        st.markdown('</div>', unsafe_allow_html=True)

    # Danger
    with inv_tabs[3]:
        st.markdown('<div class="soft-card">', unsafe_allow_html=True)
        st.warning("Reset inventory will delete ALL items you currently see.")
        if st.button("Reset inventory (wipe all items)"):
            empty = wipe_inventory(); save_inventory(empty)
            st.session_state.inventory = empty
            st.success("Inventory cleared."); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# Recipes
elif menu == "Recipes":
    set_background("recipes.jpg", darken=0.2)
    st.markdown('<div class="section-title">Recipes</div>', unsafe_allow_html=True)

    r_tabs = st.tabs(["Find", "Results"])
    with r_tabs[0]:
        st.markdown('<div class="soft-card">', unsafe_allow_html=True)
        all_items = pantry_names(inv_df())
        selected = st.multiselect("Select ingredients to include", options=all_items, default=all_items[:5])
        diet = st.selectbox("Diet", ["none", "vegan", "keto", "gluten-free", "paleo"])
        number = st.slider("How many recipes?", 5, 30, 10)
        debug = st.checkbox("Show API debug", value=False)
        offline = st.checkbox("Offline mode (use cache/demo only)", value=st.session_state.offline_mode)
        st.session_state.offline_mode = offline
        st.caption("Tip: results are cached for 3 days so repeated searches don’t use API quota.")
        c1, c2 = st.columns([1,1])
        with c1:
            if st.button("Get recipes", type="primary"):
                include = selected if selected else all_items
                recs = spoonacular_recipes(include, None if diet == "none" else diet, number, debug=debug)
                st.session_state.recipes_cache = recs
                st.session_state.selected_recipe_id = recs[0]["id"] if recs else None
        with c2:
            if st.button("Clear results"):
                st.session_state.recipes_cache = []; st.session_state.selected_recipe_id = None
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with r_tabs[1]:
        recs = st.session_state.get("recipes_cache", [])
        if not recs:
            st.info("No recipes yet. Use the **Find** tab to search.")
        else:
            for r in recs:
                render_recipe_card(r, expanded=(st.session_state.selected_recipe_id == r["id"]))

# Shopping List
elif menu == "Shopping List":
    set_background("inventory.jpg", darken=0.18)
    st.markdown('<div class="section-title">Shopping List</div>', unsafe_allow_html=True)

    sl_tabs = st.tabs(["Add Item", "List"])
    with sl_tabs[0]:
        st.markdown('<div class="soft-card">', unsafe_allow_html=True)
        name = st.text_input("Item")
        qty = st.number_input("Qty", 0.0, 1e6, 1.0)
        unit = st.text_input("Unit", "pcs")
        est_price = st.number_input("Est. price (₹)", 0.0, 1e7, 0.0)
        note = st.text_input("Note", "")
        if st.button("Add to list"):
            sl_mod.add_to_list(st.session_state.shopping_list, {"name": name, "qty": qty, "unit": unit, "est_price": est_price, "note": note})
            st.success("Added to list."); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with sl_tabs[1]:
        st.markdown('<div class="soft-card">', unsafe_allow_html=True)
        if st.session_state.shopping_list:
            st.markdown("#### Items")
            for i, it in enumerate(st.session_state.shopping_list, start=1):
                st.write(f"{i}. {it['name']} — {it['qty']} {it['unit']} @ ₹{it['est_price']}")
            st.info(f"Estimated total: ₹ {sl_mod.estimate_total(st.session_state.shopping_list):,.2f}")
        else:
            st.caption("List is empty.")
        st.markdown('</div>', unsafe_allow_html=True)

# Budget
elif menu == "Budget":
    set_background("budget.jpg", darken=0.25)
    st.markdown('<div class="section-title">Budget</div>', unsafe_allow_html=True)

    b = st.session_state.budget
    b_tabs = st.tabs(["Plan & Track", "Add Purchase", "Monthly Summary"])

    with b_tabs[0]:
        st.markdown('<div class="soft-card">', unsafe_allow_html=True)
        st.markdown("#### Monthly cap")
        new_budget = st.number_input("Monthly budget (₹)", 0.0, 1e9, float(b.get("monthly_budget", 0.0)))
        if st.button("Save budget"):
            budget_mod.set_budget(b, new_budget); st.success("Budget updated.")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown('<div class="soft-card">', unsafe_allow_html=True)
        st.markdown("#### Planned & Spent")
        planned_from_list = 0.0
        for it in st.session_state.shopping_list:
            planned_from_list += float(it.get("est_price", 0)) * float(it.get("qty", 0))
        extra_plan = st.number_input("Additional planned (₹)", 0.0, 1e9, float(st.session_state.get("extra_planned_inr", 0.0)))
        st.session_state.extra_planned_inr = extra_plan
        total_planned = planned_from_list + extra_plan
        budget_mod.set_planned(b, total_planned)

        ms = month_summary()
        spent = float(ms["spent"])
        budget_mod.record_spend(b, 0.0)

        cap = max(float(b.get("monthly_budget", 0.0)), 1.0)
        st.caption("Spent vs Budget"); progress_bar((spent / cap) * 100.0)
        st.caption("Spent + Planned vs Budget"); progress_bar(((spent + total_planned) / cap) * 100.0, alt=True)

        status = budget_mod.check_budget_status(b)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Budget (₹)", f"{status['monthly_budget']:,.0f}")
        c2.metric("Spent MTD (₹)", f"{spent:,.0f}")
        c3.metric("Planned (₹)", f"{total_planned:,.0f}")   # <-- fixed
        c4.metric("Remaining (₹)", f"{status['remaining']:,.0f}")

        if status["status"] == "over":
            st.error("You’re over budget when including planned purchases.")
        elif status["status"] == "warning":
            st.warning("You’re close to your monthly budget.")
        st.markdown('</div>', unsafe_allow_html=True)

    with b_tabs[1]:
        st.markdown('<div class="soft-card">', unsafe_allow_html=True)
        st.markdown("#### Add a purchase")
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1: item = st.text_input("Item")
        with c2: qty = st.number_input("Qty", 0.0, 1e6, 1.0)
        with c3: unit = st.text_input("Unit", "pcs")
        amt = st.number_input("Amount paid (₹)", 0.0, 1e9, 0.0)
        note = st.text_input("Note", "")
        date = st.date_input("Date", value=datetime.today())
        if st.button("Add purchase"):
            add_txn(str(date), item, qty, unit, amt, note)
            st.success("Recorded."); st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with b_tabs[2]:
        st.markdown('<div class="soft-card">', unsafe_allow_html=True)
        st.markdown("#### This month")
        ms = month_summary()
        st.write(f"Total purchases: **{ms['n']}**")
        st.write(f"Spent this month: **₹ {ms['spent']:,.2f}**")
        st.markdown('</div>', unsafe_allow_html=True)

# Assistant
elif menu == "Assistant":
    set_background("assistant.jpg", darken=0.25)
    st.markdown('<div class="section-title">Assistant</div>', unsafe_allow_html=True)
    st.caption("Try: 'do I have milk?', 'add 2 kg sugar', 'expiring in 3 days', 'low stock', 'vegan recipes with pasta'")

    q = st.text_input("Type your request")
    if st.button("Ask"):
        text = (q or "").strip().lower()
        df = inv_df()

        if "do i have" in text or text.startswith("have "):
            term = text.replace("do i have", "").replace("have", "").strip()
            st.write(quick_yes_no(df, term))

        elif text.startswith("add "):
            parts = text.split()
            qty = 1.0; unit = "pcs"; name = None
            try:
                if len(parts) >= 4 and parts[1].replace(".", "", 1).isdigit():
                    qty = float(parts[1]); unit = parts[2]; name = " ".join(parts[3:])
                else:
                    name = " ".join(parts[1:])
                if name:
                    new_row = {
                        "User_ID": 1, "user_diet": st.session_state.get("user_diet", "none"),
                        "preferred_cuisines": st.session_state.get("preferred_cuisines", "Indian;Italian"),
                        "monthly_budget": st.session_state.get("budget", {}).get("monthly_budget", 0.0),
                        "Product_ID": None, "Product_Name": name.title(), "Brand": "", "Category": "",
                        "unit": unit, "unit_price_inr": 0.0, "quantity_on_hand": qty,
                        "reorder_level": 1.0, "reorder_quantity": 1.0, "expiration_date": "",
                    }
                    st.session_state.inventory = pantry_add_item(df, new_row); save_inventory(st.session_state.inventory)
                    st.success(f"Added {qty} {unit} {name}"); st.rerun()
                else:
                    st.write("Tell me what to add, e.g., 'add 2 kg sugar'.")
            except Exception as e:
                st.write(f"Couldn't add item: {e}")

        elif "low stock" in text:
            low = inv_mod.low_stock(df); names = pantry_names(low)
            st.write("Low stock: " + (", ".join(names) if names else "None 🎉"))

        elif "expir" in text:
            import re
            m = re.search(r"(\d+)\s*day", text); days = int(m.group(1)) if m else 7
            soon = inv_mod.expiring_soon(df, days=days); names = pantry_names(soon)
            st.write(f"Expiring in {days} days: " + (", ".join(names) if names else "None 🎉"))

        elif "recipe" in text or "cook" in text or "make with" in text:
            diet = None
            for d in ["vegan", "keto", "gluten-free", "paleo"]:
                if d in text: diet = d
            include = pantry_names(df)
            if "with" in text:
                tail = text.split("with", 1)[1].strip()
                if tail:
                    include = list(set(include + [w.strip() for w in tail.split() if w.strip()]))
            recs = spoonacular_recipes(include, diet, 5)
            if not recs:
                st.write("No recipes found (cache/demo used if available).")
            else:
                st.session_state.recipes_cache = recs
                st.session_state.selected_recipe_id = recs[0]["id"]
                for i, r in enumerate(recs):
                    render_recipe_card(r, expanded=(i == 0))
        else:
            st.write("I can help with: do I have X, add items, low stock, expiring items, budget, and recipe suggestions.")

# ---------------- Footer ----------------
st.caption("FreshGro • Real-time pantry • No preloaded datasets")
