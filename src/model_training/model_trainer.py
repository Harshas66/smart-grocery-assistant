# src/model_training/model_trainer.py
import os
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel
import joblib
from pathlib import Path

ART_DIR = Path("artifacts")
ART_DIR.mkdir(parents=True, exist_ok=True)
VECT_PATH = ART_DIR / "recipe_tfidf_vectorizer.joblib"
MATRIX_PATH = ART_DIR / "recipe_tfidf_matrix.joblib"
RECIPES_MAP = ART_DIR / "recipes_index.csv"

def _prep_text_list(x):
    # Expect "ingredients" to be a list-like string or list; normalize to "a b c"
    if isinstance(x, list): 
        return " ".join(str(i).lower().strip().replace(" ", "_") for i in x)
    if isinstance(x, str):
        # try comma or semicolon separated
        parts = [p.strip().lower().replace(" ", "_") for p in x.replace(";", ",").split(",") if p.strip()]
        return " ".join(parts)
    return ""

def train_recipe_model(recipes_csv: str, text_col="ingredients", id_col="recipe_id", title_col="title"):
    """
    Train TF-IDF on recipe ingredients and persist artifacts to artifacts/.
    recipes_csv must contain at least: recipe_id, title, ingredients, diet_tag(optional)
    """
    df = pd.read_csv(recipes_csv)
    if text_col not in df.columns:
        raise ValueError(f"{text_col} column not found in {recipes_csv}")
    df["__txt__"] = df[text_col].apply(_prep_text_list)

    vec = TfidfVectorizer(min_df=2, ngram_range=(1,2))
    mat = vec.fit_transform(df["__txt__"])

    joblib.dump(vec, VECT_PATH)
    joblib.dump(mat, MATRIX_PATH)
    df[[id_col, title_col, text_col] + ([c for c in ["diet_tag"] if c in df.columns])].to_csv(RECIPES_MAP, index=False)
    return {"n_recipes": len(df), "vocab_size": len(vec.vocabulary_)}

def recommend_from_pantry(pantry_items, top_k=10, diet=None):
    """
    pantry_items: list of ingredient names (strings)
    diet: optional diet_tag to filter ('vegan','keto','gluten-free','paleo', etc.)
    """
    if not os.path.exists(VECT_PATH) or not os.path.exists(MATRIX_PATH) or not os.path.exists(RECIPES_MAP):
        raise RuntimeError("Model not trained. Run train_recipe_model(...) first.")

    vec = joblib.load(VECT_PATH)
    mat = joblib.load(MATRIX_PATH)
    rec_map = pd.read_csv(RECIPES_MAP)

    pantry_query = " ".join(str(i).lower().strip().replace(" ", "_") for i in pantry_items if str(i).strip())
    if not pantry_query:
        return rec_map.head(top_k).assign(score=0.0)

    qv = vec.transform([pantry_query])
    # cosine similarity (linear kernel on L2-normalized tf-idf)
    sims = linear_kernel(qv, mat).ravel()
    rec_map = rec_map.copy()
    rec_map["score"] = sims

    if diet and "diet_tag" in rec_map.columns:
        rec_map = rec_map[rec_map["diet_tag"].str.lower() == diet.lower()]

    out = rec_map.sort_values("score", ascending=False).head(top_k)
    return out.reset_index(drop=True)
