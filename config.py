# ============================================
# TITAN-AI TRADER — Configuration
# TITAN-SURYA TECHNOLOGIES
# ============================================

import os

ANGEL_ONE = {
    "api_key"   : os.environ.get("ANGEL_API_KEY",    ""),
    "secret_key": os.environ.get("ANGEL_SECRET_KEY", ""),
    "client_id" : os.environ.get("ANGEL_CLIENT_ID",  "AACG329697"),
    "password"  : os.environ.get("ANGEL_PASSWORD",   ""),
    "totp_key"  : os.environ.get("ANGEL_TOTP_KEY",   ""),
}

TRADING = {
    "mode"           : os.environ.get("TRADING_MODE", "PAPER"),
    "capital"        : 50000,
    "max_trades_day" : 3,
    "max_loss_day"   : 2500,
}

RISK = {
    "stop_loss_pct" : 20,
    "target_pct"    : 40,
    "trailing_sl"   : True,
}

WATCHLIST = ["NIFTY", "BANKNIFTY"]

SERVER = {
    "host": "0.0.0.0",
    "port": 8000,
}

TELEGRAM = {
    "token"  : os.environ.get("TELEGRAM_TOKEN",   ""),
    "chat_id": os.environ.get("TELEGRAM_CHAT_ID", ""),
}

AI = {
    "retrain_time" : "23:00",
    "min_accuracy" : 55,
    "lookback_days": 365,
    "ensemble_mode": "STRICT",
}

print("✅ TITAN-AI Config Loaded!")
print(f"   Mode:    {TRADING['mode']}")
print(f"   API Key: {'SET ✅' if ANGEL_ONE['api_key'] else 'MISSING ❌'}")
print(f"   Password:{'SET ✅' if ANGEL_ONE['password'] else 'MISSING ❌'}")
print(f"   TOTP:    {'SET ✅' if ANGEL_ONE['totp_key'] else 'MISSING ❌'}")