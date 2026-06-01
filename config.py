# ============================================
# TITAN-AI TRADER — Configuration FINAL v3.0
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
    # FIX: Pehle 20% tha — options ke liye 1.5% realistic hai
    # NIFTY ₹23,786 pe: SL = ₹356 neeche, Target = ₹713 upar
    "stop_loss_pct" : 1.5,
    "target_pct"    : 3.0,
    "trailing_sl"   : True,
}

MARKET = {
    "open_time"          : "09:15",
    "close_time"         : "15:30",
    "force_exit_time"    : "15:20",  # 10 min pehle sab close
    "trading_start"      : "09:20",  # First signal 9:20 ke baad
    "no_new_trade_after" : "14:30",  # Iske baad naya trade nahi
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
    "retrain_time"   : "23:00",
    "min_accuracy"   : 50,
    "lookback_days"  : 365,
    "ensemble_mode"  : "STRICT",
    "min_confidence" : 55,
}

print("✅ TITAN-AI Config Loaded!")
print(f"   Mode:    {TRADING['mode']}")
print(f"   API Key: {'SET ✅' if ANGEL_ONE['api_key'] else 'MISSING ❌'}")
print(f"   SL:      {RISK['stop_loss_pct']}% | Target: {RISK['target_pct']}%")
print(f"   Trading: {MARKET['trading_start']} → {MARKET['no_new_trade_after']}")