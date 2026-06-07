# ============================================
# TITAN-AI TRADER — Config
# TITAN-SURYA TECHNOLOGIES
# ============================================

import os

# ============================================
# ANGEL ONE CREDENTIALS
# Railway environment variables se aayenge
# ============================================
ANGEL_ONE = {
    "api_key"   : os.environ.get("ANGEL_API_KEY",    ""),
    "client_id" : os.environ.get("ANGEL_CLIENT_ID",  ""),
    "password"  : os.environ.get("ANGEL_PASSWORD",   ""),
    "totp_key"  : os.environ.get("ANGEL_TOTP_KEY",   ""),
}

# ============================================
# TRADING SETTINGS
# ============================================
TRADING = {
    "mode"           : os.environ.get("TRADING_MODE", "PAPER"),  # PAPER / LIVE
    "capital"        : 50000,
    "max_trades_day" : 3,
    "max_loss_day"   : 2000,
}

# ============================================
# MARKET TIMINGS (IST)
# ============================================
MARKET = {
    "open"        : "09:15",
    "close"       : "15:30",
    "trade_start" : "10:30",
    "trade_end"   : "13:30",
    "force_exit"  : "15:20",
}

# ============================================
# AI SETTINGS
# ============================================
AI = {
    "min_confidence" : 60.0,
    "min_accuracy"   : 50.0,
}

# ============================================
# RISK SETTINGS
# ============================================
RISK = {
    "stop_loss_pct" : 1.5,
    "target_pct"    : 3.0,
    "trailing_sl"   : True,
}

# ============================================
# VIX SETTINGS
# ============================================
VIX = {
    "max_vix"     : 20.0,
    "caution_vix" : 15.0,
}