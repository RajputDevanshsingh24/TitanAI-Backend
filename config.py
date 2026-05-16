import os

ANGEL_ONE = {
    "api_key"   : os.getenv("mB3Hghfu", ""),
    "secret_key": os.getenv("36e27781-9351-4fbf-8143-973c0219b976", ""),
    "client_id" : os.getenv("ANGEL_CLIENT_ID", "AACG329697"),
    "password"  : os.getenv("4160", ""),
    "totp_key"  : os.getenv("D3CT3WCEA5AQCQ74P2D2ZSOY4E", "")
}


TRADING = {
    "mode"          : os.getenv("TRADING_MODE", "PAPER"),
    "capital"       : 50000,
    "max_trades_day": 3,
    "max_loss_day"  : 2500,
}


RISK = {
    "stop_loss_pct": 20,
    "target_pct"   : 40,
    "trailing_sl"  : True,
}

print("✅ TITAN-AI Config Loaded!")
