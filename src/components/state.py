# src/components/state.py
import pandas as pd
from pathlib import Path

_EXPECTED_COLS = [  # keep your full list here
    "User_ID","user_diet","preferred_cuisines","monthly_budget",
    "Product_ID","Product_Name","Brand","Category","unit","unit_price_inr",
    "quantity_on_hand","reorder_level","reorder_quantity","expiration_date",
    # ... include whatever you use in the app
]

def init_session_state(st, artifacts_dir="artifacts"):
    if "inventory" not in st.session_state:
        csv = Path(artifacts_dir) / "data.csv"
        if csv.exists():
            df = pd.read_csv(csv)
        else:
            # fallback to processed dataset if available
            alt = Path("notebook/processed_smart_grocery_dataset.csv")
            df = pd.read_csv(alt) if alt.exists() else pd.DataFrame(columns=_EXPECTED_COLS)
        st.session_state.inventory = df
