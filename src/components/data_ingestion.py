# src/components/data_ingestion.py
import os
import sys
import logging
from pathlib import Path
import pandas as pd
from sklearn.model_selection import train_test_split

# -------------------------------
# Configure logging
# -------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_LOG = PROJECT_ROOT / "artifacts" / "data_ingestion.log"

# Ensure artifacts folder exists
(ARTIFACT_LOG.parent).mkdir(parents=True, exist_ok=True)

# Remove previous handlers to ensure logging updates in repeated runs
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(ARTIFACT_LOG, mode='w')  # overwrite log each run
    ]
)

# -------------------------------
# Data Ingestion Class
# -------------------------------
class DataIngestion:
    def __init__(self, ingestion_config):
        self.ingestion_config = ingestion_config

    def initiate_data_ingestion(self):
        logging.info("Entered the data ingestion method")
        try:
            # Dataset path
            dataset_path = PROJECT_ROOT / "notebook" / "processed_smart_grocery_dataset.csv"
            if not dataset_path.exists():
                raise FileNotFoundError(f"Dataset not found at {dataset_path}")
            logging.info(f"Dataset found at {dataset_path}")

            # Read dataset
            df = pd.read_csv(dataset_path)
            logging.info("Read the dataset as dataframe")

            # Column mapping
            COLUMN_MAP = {
                "User_ID": "user_id",
                "Product_ID": "Product_ID",
                "Product_Name": "Product_Name",
                "Category": "Category",
                "Subcategory": "Subcategory",
                "unit": "Unit",
                "unit_price_inr": "unit_price_inr",
                "quantity_purchased": "quantity_purchased",
                "discount_applied": "discount_applied",
                "total_spent": "total_spent",
                "storage_type": "storage_type",
                "expiration_date": "Expiry_Date",
                "days_to_expiry": "days_to_expiry",
                "quantity_on_hand": "quantity_on_hand",
                "reorder_level": "reorder_level",
                "reorder_quantity": "reorder_quantity",
                "payment_method": "payment_method",
                "store_type": "store_type",
                "calories": "calories",
                "protein_g": "protein_g",
                "fat_g": "fat_g",
                "carbs_g": "carbs_g",
                "fiber_g": "fiber_g",
                "sugar_g": "sugar_g",
                "sodium_mg": "sodium_mg",
                "product_diet_tags": "product_diet_tags",
                "recipe_id": "recipe_id",
                "recipe_name": "recipe_name",
                "recipe_cuisine": "recipe_cuisine",
                "recipe_cook_time": "recipe_cook_time",
                "ingredient_product_ids": "ingredient_product_ids",
                "ingredient_qtys": "ingredient_qtys",
                "recipe_instructions": "recipe_instructions",
                "user_monthly_spend": "user_monthly_spend",
                "category_spend_share": "category_spend_share"
            }
            df.rename(columns={k: v for k, v in COLUMN_MAP.items() if k in df.columns}, inplace=True)

            # Convert date columns
            for col in df.columns:
                if "date" in col.lower():
                    df[col] = pd.to_datetime(df[col], errors="coerce")

            # Ensure numeric fields
            num_cols = [
                "unit_price_inr", "quantity_purchased", "discount_applied", "total_spent",
                "quantity_on_hand", "reorder_level", "reorder_quantity",
                "calories", "protein_g", "fat_g", "carbs_g", "fiber_g", "sugar_g", "sodium_mg",
                "user_monthly_spend", "category_spend_share"
            ]
            for col in num_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

            # Ensure diet tags column exists
            if "product_diet_tags" not in df.columns:
                df["product_diet_tags"] = ""

            # -------------------------------
            # Save raw dataset
            # -------------------------------
            raw_path = Path(self.ingestion_config.raw_data_path)
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(raw_path, index=False, header=True)
            logging.info(f"Saved cleaned dataset to {raw_path}")

            # -------------------------------
            # Train-test split
            # -------------------------------
            logging.info("Train-test split initiated")
            train_set, test_set = train_test_split(df, test_size=0.2, random_state=42)

            # Save train/test datasets
            train_path = Path(self.ingestion_config.train_data_path)
            test_path = Path(self.ingestion_config.test_data_path)
            train_path.parent.mkdir(parents=True, exist_ok=True)
            test_path.parent.mkdir(parents=True, exist_ok=True)

            train_set.to_csv(train_path, index=False, header=True)
            test_set.to_csv(test_path, index=False, header=True)
            logging.info(f"Train dataset saved to {train_path}")
            logging.info(f"Test dataset saved to {test_path}")

            logging.info("Data ingestion completed successfully")
            return train_path, test_path

        except Exception as e:
            logging.error(f"Error in data ingestion: {e}")
            raise e

class IngestionConfig:
    raw_data_path = "artifacts/data.csv"
    train_data_path = "artifacts/train.csv"
    test_data_path = "artifacts/test.csv"

ingestion_config = IngestionConfig()
ingestor = DataIngestion(ingestion_config)
train_path, test_path = ingestor.initiate_data_ingestion()
