# expiry_alert.py
from src.utils import expiring_soon, expired

def get_expiring_soon(df, days=7):
    return expiring_soon(df, days=days)

def get_expired(df):
    return expired(df)

