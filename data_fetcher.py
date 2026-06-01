# ============================================
# TITAN-AI TRADER — Data Fetcher v7.0
# TITAN-SURYA TECHNOLOGIES
#
# CHANGES v7.0:
# - 5-min intraday data PRIMARY source
# - Gift Nifty morning fetch added
# - VIX data fetch added
# - get_best_data() → 5-min data return karta hai
# ============================================

from SmartApi import SmartConnect
import pyotp
import pandas as pd
import requests
import os
import time
from datetime import datetime, timedelta
from io import StringIO
from config import ANGEL_ONE, DATA


class DataFetcher:

    def __init__(self):
        self.api        = None
        self.connected  = False
        self.github_csv = (
            "https://raw.githubusercontent.com/"
            "RajputDevanshsingh24/TitanAI-Backend/"
            "main/nifty_data.csv"
        )

        # Angel One token map
        self.tokens = {
            "NIFTY"    : "99926000",
            "BANKNIFTY": "99926009",
        }

    # ============================================
    # ANGEL ONE CONNECT
    # ============================================
    def connect(self):
        try:
            print("🔌 Connecting to Angel One...")

            api_key  = ANGEL_ONE["api_key"]
            client   = ANGEL_ONE["client_id"]
            password = ANGEL_ONE["password"]
            totp_key = ANGEL_ONE["totp_key"]

            print(f"   API Key:  {api_key[:4] if api_key else 'EMPTY'}****")
            print(f"   Client:   {client}")
            print(f"   Password: {'SET ✅' if password else 'EMPTY ❌'}")
            print(f"   TOTP Key: {'SET ✅' if totp_key else 'EMPTY ❌'}")

            if not api_key or not password or not totp_key:
                print("❌ Credentials missing!")
                return False

            totp     = pyotp.TOTP(totp_key).now()
            self.api = SmartConnect(api_key=api_key)
            data     = self.api.generateSession(client, password, totp)

            if data["status"]:
                self.connected = True
                print("✅ Angel One Connected!")
                return True
            else:
                print(f"❌ Login Failed: {data['message']}")
                return False

        except Exception as e:
            print(f"❌ Connect Error: {e}")
            return False

    # ============================================
    # LIVE PRICE
    # ============================================
    def get_live_price(self, symbol="NIFTY"):
        try:
            if not self.connected:
                self.connect()

            token    = self.tokens[symbol]
            data     = self.api.ltpData("NSE", symbol, token)
            price    = data["data"]["ltp"]
            print(f"📊 {symbol}: ₹{price:,.2f}")
            return price

        except Exception as e:
            print(f"❌ Live Price Error: {e}")
            return None

    # ============================================
    # 5-MIN INTRADAY DATA — PRIMARY SOURCE
    # Angel One se fetch karta hai
    # ============================================
    def get_intraday_5min(self, symbol="NIFTY", days=60):
        try:
            if not self.connected:
                if not self.connect():
                    return None

            token    = self.tokens[symbol]
            all_data = []
            end_date = datetime.now()

            print(f"\n📊 5-min data fetch ho raha hai...")
            print(f"   Symbol: {symbol} | Days: {days}")

            # Angel One ek baar mein max 30 din deta hai
            # Isliye chunks mein fetch karo
            chunk_days  = 25
            current_end = end_date

            while current_end > end_date - timedelta(days=days):
                current_start = current_end - timedelta(days=chunk_days)
                if current_start < end_date - timedelta(days=days):
                    current_start = end_date - timedelta(days=days)

                try:
                    params = {
                        "exchange"    : "NSE",
                        "symboltoken" : token,
                        "interval"    : "FIVE_MINUTE",
                        "fromdate"    : current_start.strftime("%Y-%m-%d 09:00"),
                        "todate"      : current_end.strftime("%Y-%m-%d 15:30"),
                    }

                    resp = self.api.getCandleData(params)

                    if resp["status"] and resp["data"]:
                        batch = resp["data"]
                        all_data = batch + all_data
                        print(f"   ✅ {current_start.strftime('%d-%m')} → "
                              f"{current_end.strftime('%d-%m')}: "
                              f"{len(batch)} candles")

                except Exception as e:
                    print(f"   ⚠️ Chunk error: {e}")

                current_end = current_start - timedelta(days=1)
                time.sleep(0.3)  # Rate limit

            if not all_data:
                print("❌ 5-min data nahi mila!")
                return None

            # DataFrame banao
            df = pd.DataFrame(
                all_data,
                columns=["Date", "Open", "High", "Low", "Close", "Volume"]
            )
            df["Date"]   = pd.to_datetime(df["Date"])
            df           = df.sort_values("Date")
            df           = df.drop_duplicates(subset=["Date"])
            df.set_index("Date", inplace=True)

            for col in ["Open", "High", "Low", "Close", "Volume"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")

            df["Volume"] = df["Volume"].replace(0, 1)
            df           = df.dropna()

            # Sirf market hours (9:15 - 15:30)
            df = df.between_time("09:15", "15:30")

            print(f"\n✅ 5-min data ready!")
            print(f"   Total candles: {len(df)}")
            print(f"   Start: {df.index[0].strftime('%d-%m-%Y %H:%M')}")
            print(f"   End:   {df.index[-1].strftime('%d-%m-%Y %H:%M')}")
            return df

        except Exception as e:
            print(f"❌ 5-min fetch error: {e}")
            import traceback; traceback.print_exc()
            return None

    # ============================================
    # DAILY DATA — Training ke liye (backup)
    # GitHub CSV se load karta hai
    # ============================================
    def get_daily_data_github(self):
        try:
            print("📊 GitHub CSV (daily) load ho raha hai...")
            response = requests.get(
                self.github_csv,
                timeout = 20,
                headers = {"User-Agent": "Mozilla/5.0"}
            )

            if response.status_code != 200:
                print(f"❌ GitHub HTTP {response.status_code}")
                return None

            content = response.text.strip()
            if len(content) < 100:
                print("❌ GitHub: Empty!")
                return None

            df = pd.read_csv(StringIO(content), header=0)

            required = ["Date", "Close", "High", "Low", "Open", "Volume"]
            missing  = [c for c in required if c not in df.columns]
            if missing:
                print(f"❌ Missing columns: {missing}")
                return None

            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
            df         = df.dropna(subset=["Date"])
            df         = df.set_index("Date")

            for col in ["Open", "High", "Low", "Close", "Volume"]:
                df[col] = pd.to_numeric(df[col], errors="coerce")

            df           = df.dropna()
            df           = df.sort_index()
            df["Volume"] = df["Volume"].replace(0, 1)
            df           = df[~df.index.duplicated(keep="last")]

            print(f"✅ Daily data: {len(df)} rows")
            print(f"   {df.index[0].strftime('%Y-%m-%d')} → "
                  f"{df.index[-1].strftime('%Y-%m-%d')}")
            return df

        except Exception as e:
            print(f"❌ GitHub CSV Error: {e}")
            return None

    # ============================================
    # ANGEL ONE DAILY DATA (fallback)
    # ============================================
    def get_daily_data_angel(self, symbol="NIFTY", days=365):
        try:
            if not self.connected:
                if not self.connect():
                    return None

            token      = self.tokens[symbol]
            all_data   = []
            end_date   = datetime.now()
            start_date = end_date - timedelta(days=days)

            chunk_days  = 90
            current_end = end_date

            print(f"📅 Angel One daily data ({days} din)...")

            while current_end > start_date:
                current_start = current_end - timedelta(days=chunk_days)
                if current_start < start_date:
                    current_start = start_date

                try:
                    params = {
                        "exchange"    : "NSE",
                        "symboltoken" : token,
                        "interval"    : "ONE_DAY",
                        "fromdate"    : current_start.strftime("%Y-%m-%d 09:00"),
                        "todate"      : current_end.strftime("%Y-%m-%d 15:30"),
                    }
                    resp = self.api.getCandleData(params)
                    if resp["status"] and resp["data"]:
                        all_data = resp["data"] + all_data
                except Exception as e:
                    print(f"   ⚠️ Chunk error: {e}")

                current_end = current_start - timedelta(days=1)
                time.sleep(0.5)

            if not all_data:
                return None

            df = pd.DataFrame(
                all_data,
                columns=["Date", "Open", "High", "Low", "Close", "Volume"]
            )
            df["Date"] = pd.to_datetime(df["Date"])
            df         = df.sort_values("Date").drop_duplicates("Date")
            df.set_index("Date", inplace=True)
            df["Volume"] = df["Volume"].replace(0, 1)
            df           = df.dropna()

            print(f"✅ Angel One daily: {len(df)} rows")
            return df

        except Exception as e:
            print(f"❌ Angel Daily Error: {e}")
            return None

    # ============================================
    # GET BEST DATA — 5-min PRIMARY
    # Hierarchy:
    # 1. Angel One 5-min (best)
    # 2. Angel One daily (fallback)
    # 3. GitHub CSV daily (last resort)
    # ============================================
    def get_best_data(self, symbol="NIFTY"):
        print("\n" + "="*45)
        print("🔍 BEST DATA SOURCE DHUND RAHA HUN")
        print("="*45)

        # [1] Angel One 5-min — best for intraday AI
        print("\n[1/3] Angel One 5-min try kar raha hun...")
        if self.connected or self.connect():
            df = self.get_intraday_5min(symbol, days=DATA["lookback_days"])
            if df is not None and len(df) > 500:
                print(f"\n🏆 5-min data selected! Candles: {len(df)}")
                return df

        # [2] Angel One daily
        print("\n[2/3] Angel One daily fallback...")
        df = self.get_daily_data_angel(symbol, days=365)
        if df is not None and len(df) > 200:
            print(f"\n🏆 Angel One daily selected! Rows: {len(df)}")
            return df

        # [3] GitHub CSV
        print("\n[3/3] GitHub CSV last resort...")
        df = self.get_daily_data_github()
        if df is not None:
            print(f"\n🏆 GitHub CSV selected! Rows: {len(df)}")
            return df

        print("\n❌ Koi bhi source kaam nahi kar raha!")
        return None

    # ============================================
    # GIFT NIFTY — Morning direction hint
    # Market open se pehle fetch karo (9:00 AM)
    # ============================================
    def get_gift_nifty(self):
        try:
            print("🌏 Gift Nifty fetch ho raha hai...")

            headers = {
                "User-Agent": "Mozilla/5.0",
                "Referer"   : "https://www.nseindia.com",
            }

            session  = requests.Session()
            session.get("https://www.nseindia.com", headers=headers, timeout=5)
            response = session.get(
                "https://www.nseindia.com/api/allIndices",
                headers = headers,
                timeout = 10
            )

            if response.status_code == 200:
                data    = response.json()
                indices = data.get("data", [])
                for idx in indices:
                    name = idx.get("index", "")
                    if "GIFT" in name or "SGX" in name:
                        price  = float(idx.get("last",   0))
                        change = float(idx.get("change", 0))
                        pct    = float(idx.get("percentChange", 0))
                        print(f"✅ Gift Nifty: ₹{price:,.2f} | "
                              f"Change: {change:+.2f} ({pct:+.2f}%)")
                        return {
                            "price"   : price,
                            "change"  : change,
                            "pct"     : pct,
                            "bullish" : pct > 0.3,
                            "bearish" : pct < -0.3,
                        }

            print("⚠️ Gift Nifty nahi mila")
            return None

        except Exception as e:
            print(f"⚠️ Gift Nifty Error: {e}")
            return None

    # ============================================
    # INDIA VIX
    # ============================================
    def get_vix(self):
        try:
            headers = {
                "User-Agent": "Mozilla/5.0",
                "Referer"   : "https://www.nseindia.com",
            }

            session  = requests.Session()
            session.get("https://www.nseindia.com", headers=headers, timeout=5)
            response = session.get(
                "https://www.nseindia.com/api/allIndices",
                headers = headers,
                timeout = 10
            )

            if response.status_code == 200:
                data    = response.json()
                indices = data.get("data", [])
                for idx in indices:
                    if "INDIA VIX" in idx.get("index", ""):
                        vix = float(idx.get("last", 0))
                        print(f"📊 India VIX: {vix:.2f}")
                        return vix

            return None

        except Exception as e:
            print(f"⚠️ VIX Error: {e}")
            return None

    # ============================================
    # TODAY KI 5-MIN CANDLES (live trading ke liye)
    # ============================================
    def get_today_candles(self, symbol="NIFTY"):
        try:
            if not self.connected:
                self.connect()

            token = self.tokens[symbol]
            today = datetime.now()

            params = {
                "exchange"    : "NSE",
                "symboltoken" : token,
                "interval"    : "FIVE_MINUTE",
                "fromdate"    : today.strftime("%Y-%m-%d 09:00"),
                "todate"      : today.strftime("%Y-%m-%d 15:30"),
            }

            resp = self.api.getCandleData(params)

            if resp["status"] and resp["data"]:
                df = pd.DataFrame(
                    resp["data"],
                    columns=["Date", "Open", "High", "Low", "Close", "Volume"]
                )
                df["Date"] = pd.to_datetime(df["Date"])
                df.set_index("Date", inplace=True)
                df = df.between_time("09:15", "15:30")
                print(f"✅ Today candles: {len(df)}")
                return df

            return None

        except Exception as e:
            print(f"❌ Today Candles Error: {e}")
            return None