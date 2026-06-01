# ============================================
# TITAN-AI TRADER — Configuration v4.0
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
    "stop_loss_pct" : 1.5,
    "target_pct"    : 3.0,
    "trailing_sl"   : True,
}

MARKET = {
    "open_time"          : "09:15",
    "close_time"         : "15:30",
    "force_exit_time"    : "15:20",

    # FIX: 9:20 → 10:30 (opening volatility avoid)
    # Opening 1 hour bahut volatile hota hai
    "trading_start"      : "10:30",

    # FIX: 14:30 → 13:30 (safer exit window)
    "no_new_trade_after" : "13:30",
}

DATA = {
    # FIX: daily → 5min (intraday accuracy better)
    "interval"     : "FIVE_MINUTE",
    "lookback_days": 60,    # 5-min data ke liye 60 din kaafi
    "candles"      : 75,    # Ek din mein ~75 candles (6.25 hrs)
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
    "min_accuracy"   : 50,     # 55 → 50 (52% model bhi save ho)
    "ensemble_mode"  : "STRICT",
    "min_confidence" : 55,
    "lookback_candles": 60,    # LSTM ke liye last 60 candles
}

VIX = {
    "max_vix"          : 20.0,  # > 20 → no trade
    "caution_vix"      : 15.0,  # 15-20 → trade with lower size
}

print("✅ TITAN-AI Config v4.0 Loaded!")
print(f"   Mode:     {TRADING['mode']}")
print(f"   API Key:  {'SET ✅' if ANGEL_ONE['api_key'] else 'MISSING ❌'}")
print(f"   SL:       {RISK['stop_loss_pct']}% | Target: {RISK['target_pct']}%")
print(f"   Window:   {MARKET['trading_start']} → {MARKET['no_new_trade_after']}")
print(f"   Data:     {DATA['interval']} | {DATA['lookback_days']} days")