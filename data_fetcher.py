# ============================================
# TITAN-AI TRADER — Data Fetcher v3.0
# TITAN-SURYA TECHNOLOGIES
#
# FIX v3.0:
# - reconnect() method added
# - get_live_price() auto token refresh on AG8001
# - "string indices" error bhi handle hoga
# ============================================

import os
import time
import pyotp
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from SmartApi import SmartConnect
from config import ANGEL_ONE

# Symbols / Tokens
SYMBOL_TOKENS = {
    "NIFTY"      : "26000",
    "BANKNIFTY"  : "26009",
    "FINNIFTY"   : "26037",
    "SENSEX"     : "1",
}


class DataFetcher:

    def __init__(self):
        self.api       = None
        self.connected = False
        self.tokens    = SYMBOL_TOKENS
        print("✅ DataFetcher Ready!")

    # ============================================
    # ANGEL ONE RECONNECT (Token Refresh)
    # Call this daily at 9:05 AM to get fresh token
    # ============================================
    def reconnect(self):
        """Force fresh login — Angel One token daily expire hota hai"""
        print("\n🔄 Token refresh ho raha hai...")
        self.api       = None
        self.connected = False
        result = self.connect()
        if result:
            print("✅ Token refreshed! New session active.")
        else:
            print("❌ Token refresh failed! Credentials check karo.")
        return result

    # ============================================
    # ANGEL ONE CONNECT
    # ============================================
    def connect(self):
        try:
            api_key   = ANGEL_ONE["api_key"]
            client_id = ANGEL_ONE["client_id"]
            password  = ANGEL_ONE["password"]
            totp_key  = ANGEL_ONE["totp_key"]

            if not all([api_key, client_id, password, totp_key]):
                print("⚠️ Angel One credentials missing — Paper mode")
                self.connected = False
                return False

            print(f"\n🔌 Angel One connecting...")
            print(f"   Client: {client_id}")

            self.api = SmartConnect(api_key=api_key)
            totp     = pyotp.TOTP(totp_key).now()
            data     = self.api.generateSession(client_id, password, totp)

            if data["status"]:
                self.connected = True
                print(f"✅ Angel One connected!")
                return True
            else:
                print(f"❌ Login failed: {data.get('message', 'Unknown error')}")
                self.connected = False
                return False

        except Exception as e:
            print(f"❌ Connect Error: {e}")
            self.connected = False
            return False

    # ============================================
    # LIVE PRICE — Auto retry on token expire
    # ============================================
    def get_live_price(self, symbol="NIFTY"):
        try:
            if not self.connected:
                self.connect()

            token = self.tokens[symbol]
            data  = self.api.ltpData("NSE", symbol, token)

            # AG8001 = Invalid Token → auto reconnect karo
            if isinstance(data, dict) and not data.get("status", True):
                err_code = data.get("errorCode", "")
                if err_code == "AG8001" or "Invalid Token" in str(data.get("message", "")):
                    print("⚠️ Token expired! Auto-reconnecting...")
                    if self.reconnect():
                        # Retry once after fresh token
                        data = self.api.ltpData("NSE", symbol, token)
                    else:
                        print("❌ Reconnect failed!")
                        return None

            price = data["data"]["ltp"]
            print(f"📊 {symbol}: ₹{price:,.2f}")
            return price

        except Exception as e:
            print(f"❌ Live Price Error: {e}")
            # String indices error = bad response structure = likely token issue
            if "string indices" in str(e):
                print("⚠️ Token issue detected! Reconnecting...")
                if self.reconnect():
                    try:
                        token = self.tokens[symbol]
                        data  = self.api.ltpData("NSE", symbol, token)
                        price = data["data"]["ltp"]
                        print(f"📊 {symbol}: ₹{price:,.2f} (after reconnect)")
                        return price
                    except Exception as e2:
                        print(f"❌ Retry bhi fail: {e2}")
            return None

    # ============================================
    # BEST DATA — Historical + Today
    # ============================================
    def get_best_data(self, symbol="NIFTY"):
        """GitHub CSV + Angel One live data combine"""
        try:
            print(f"\n📦 Getting best data for {symbol}...")

            # Step 1: GitHub CSV (historical)
            df = self._load_github_csv()

            # Step 2: Angel One se today ke candles
            if self.connected:
                today_df = self.get_today_candles(symbol)
                if today_df is not None and len(today_df) > 0:
                    df = pd.concat([df, today_df])
                    df = df[~df.index.duplicated(keep="last")]
                    df = df.sort_index()
                    print(f"✅ Combined: {len(df)} rows")

            return df

        except Exception as e:
            print(f"❌ get_best_data error: {e}")
            return self._load_github_csv()

    # ============================================
    # GITHUB CSV LOAD
    # ============================================
    def _load_github_csv(self):
        try:
            # Local file pehle check karo
            local_paths = ["nifty_data.csv", "data/nifty_data.csv"]
            for path in local_paths:
                if os.path.exists(path):
                    df = pd.read_csv(path, index_col=0, parse_dates=True)
                    df.columns = [c.capitalize() for c in df.columns]
                    print(f"✅ Local CSV: {len(df)} rows")
                    return df

            # GitHub se download
            url = (
                "https://raw.githubusercontent.com/"
                "RajputDevanshsingh24/TitanAI-Backend/main/nifty_data.csv"
            )
            print("📥 Downloading from GitHub...")
            df = pd.read_csv(url, index_col=0, parse_dates=True)
            df.columns = [c.capitalize() for c in df.columns]
            print(f"✅ GitHub CSV: {len(df)} rows")
            return df

        except Exception as e:
            print(f"❌ CSV load error: {e}")
            return self._generate_dummy_data()

    # ============================================
    # TODAY'S 5-MIN CANDLES — Angel One
    # ============================================
    def get_today_candles(self, symbol="NIFTY"):
        try:
            if not self.connected:
                return None

            now   = datetime.now()
            from_  = now.replace(hour=9, minute=15, second=0).strftime("%Y-%m-%d %H:%M")
            to_    = now.strftime("%Y-%m-%d %H:%M")

            params = {
                "exchange"    : "NSE",
                "symboltoken" : self.tokens[symbol],
                "interval"    : "FIVE_MINUTE",
                "fromdate"    : from_,
                "todate"      : to_,
            }

            data = self.api.getCandleData(params)

            if not data["status"] or not data["data"]:
                return None

            df = pd.DataFrame(
                data["data"],
                columns=["Datetime", "Open", "High", "Low", "Close", "Volume"]
            )
            df["Datetime"] = pd.to_datetime(df["Datetime"])
            df.set_index("Datetime", inplace=True)
            df = df.astype(float)

            print(f"✅ Today candles: {len(df)} rows")
            return df

        except Exception as e:
            print(f"❌ Today candles error: {e}")
            return None

    # ============================================
    # VIX — India VIX from NSE
    # ============================================
    def get_vix(self):
        try:
            headers = {
                "User-Agent" : "Mozilla/5.0",
                "Referer"    : "https://www.nseindia.com",
                "Accept"     : "application/json",
            }
            session = requests.Session()
            session.get("https://www.nseindia.com", headers=headers, timeout=5)
            resp = session.get(
                "https://www.nseindia.com/api/allIndices",
                headers=headers, timeout=10
            )
            if resp.status_code == 200:
                for idx in resp.json().get("data", []):
                    if "INDIA VIX" in idx.get("index", ""):
                        vix = float(idx.get("last", 0))
                        if vix > 0:
                            print(f"📊 India VIX: {vix:.2f}")
                            return vix
            return None
        except Exception as e:
            print(f"⚠️ VIX fetch error: {e}")
            return None

    # ============================================
    # GIFT NIFTY — SGX/GIFT direction
    # ============================================
    def get_gift_nifty(self):
        try:
            # Yahoo Finance se SGX Nifty proxy
            import yfinance as yf
            ticker = yf.Ticker("^NSEI")
            hist   = ticker.history(period="2d", interval="1d")
            if len(hist) >= 2:
                prev  = hist["Close"].iloc[-2]
                curr  = hist["Close"].iloc[-1]
                pct   = (curr - prev) / prev * 100
                return {
                    "price"   : round(curr, 2),
                    "prev"    : round(prev, 2),
                    "pct"     : round(pct, 2),
                    "bullish" : pct > 0.3,
                    "bearish" : pct < -0.3,
                }
            return None
        except Exception as e:
            print(f"⚠️ Gift Nifty error: {e}")
            return None

    # ============================================
    # DUMMY DATA — Fallback
    # ============================================
    def _generate_dummy_data(self):
        print("⚠️ Generating dummy data...")
        dates  = pd.date_range("2024-01-01", periods=500, freq="5min")
        closes = 22000 + np.cumsum(np.random.randn(500) * 10)
        df = pd.DataFrame({
            "Open"   : closes * 0.999,
            "High"   : closes * 1.002,
            "Low"    : closes * 0.998,
            "Close"  : closes,
            "Volume" : np.random.randint(100000, 500000, 500),
        }, index=dates)
        print(f"✅ Dummy data: {len(df)} rows")
        return df