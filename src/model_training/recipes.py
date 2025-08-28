# src/model_training/recipes.py
import pandas as pd
from src.model_training.model_trainer import recommend_from_pantry

def suggest_recipes_from_inventory(inventory_df: pd.DataFrame, top_k=10, diet=None):
    # pantry items as token names (product names)
    names = inventory_df.get("Product_Name", pd.Series(dtype=str)).dropna().tolist()
    return recommend_from_pantry(names, top_k=top_k, diet=diet)
