from pathlib import Path
from xgboost import XGBRegressor
import json


# Find the project root
PROJECT_ROOT = Path(__file__).resolve().parents[2]

MODEL_DIR = PROJECT_ROOT / "src" / "models"


# Load trained model
model = XGBRegressor()
model.load_model(MODEL_DIR / "traffic_forecaster.json")


# Load feature order
with open(MODEL_DIR / "feature_columns.json", "r") as f:
    feature_columns = json.load(f)


print(f"Traffic model loaded successfully.")
print(f"Number of features: {len(feature_columns)}")