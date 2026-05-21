# ============================================
# TITAN-AI TRADER — Data Fetcher FINAL v6.0
# TITAN-SURYA TECHNOLOGIES
# ============================================

from SmartApi import SmartConnect
import pyotp
import pandas as pd
import requests
import os
import time
from datetime import datetime, timedelta

class DataFetcher:

    def __init__(self):
        self.api        = None
        self.connected  = False

        # GitHub CSV URL — 10 saal ka data
        self.github_csv = (
            "https://raw.githubusercontent.com/"
            "RajputDevanshsingh24/TitanAI-Backend/"
            "main/nifty_data.csv"
        )

    # ============================================
    # ANGEL ONE — CONNECT
    # ============================================
    def connect(self):
        try:
            print("🔌 Connecting to Angel One...")

            api_key  = os.environ.get("ANGEL_API_KEY",  "")
            client   = os.environ.get("ANGEL_CLIENT_ID","AACG329697")
            password = os.environ.get("ANGEL_PASSWORD", "")
            totp_key = os.environ.get("ANGEL_TOTP_KEY", "")

            print(f"   API Key:  "
                  f"{api_key[:4] if api_key else 'EMPTY'}****")
            print(f"   Client:   {client}")
            print(f"   Password: "
                  f"{'SET ✅' if password else 'EMPTY ❌'}")
            print(f"   TOTP Key: "
                  f"{'SET ✅' if totp_key else 'EMPTY ❌'}")

            if not api_key:
                print("❌ ANGEL_API_KEY missing!")
                return False
            if not password:
                print("❌ ANGEL_PASSWORD missing!")
                return False
            if not totp_key:
                print("❌ ANGEL_TOTP_KEY missing!")
                return False

            totp     = pyotp.TOTP(totp_key).now()
            print(f"   TOTP:     {totp}")

            self.api = SmartConnect(api_key=api_key)
            data     = self.api.generateSession(
                client, password, totp
            )

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
    # LIVE PRICE — ANGEL ONE
    # ============================================
    def get_live_price(self, symbol="NIFTY"):
        try:
            if not self.connected:
                self.connect()

            symbols = {
                "NIFTY"    : {
                    "token"   : "99926000",
                    "exchange": "NSE"
                },
                "BANKNIFTY": {
                    "token"   : "99926009",
                    "exchange": "NSE"
                },
            }

            s     = symbols[symbol]
            data  = self.api.ltpData(
                s["exchange"], symbol, s["token"]
            )
            price = data["data"]["ltp"]
            print(f"📊 {symbol}: ₹{price}")
            return price

        except Exception as e:
            print(f"❌ Live Price Error: {e}")
            return None

    # ============================================
    # METHOD 1: GITHUB CSV — PRIMARY (10 SAAL)
    # ============================================
    def get_data_from_github(self):
        try:
            print("📊 GitHub CSV se data load ho raha hai...")
            print(f"   URL: {self.github_csv}")

            response = requests.get(
                self.github_csv,
                timeout = 20,
                headers = {"User-Agent": "Mozilla/5.0"}
            )

            if response.status_code != 200:
                print(f"❌ GitHub HTTP Error: "
                      f"{response.status_code}")
                return None

            from io import StringIO
            content = response.text.strip()

            if len(content) < 100:
                print("❌ GitHub: Empty response!")
                return None

            # CSV parse karo
            # Format:
            # Date,Close,High,Low,Open,Volume
            # 2016-05-20,7749.7,7812.4,...
            df = pd.read_csv(
                StringIO(content),
                header = 0
            )

            # Columns verify karo
            required = ['Date','Close','High',
                       'Low','Open','Volume']
            missing  = [c for c in required
                       if c not in df.columns]

            if missing:
                print(f"❌ Missing columns: {missing}")
                print(f"   Available: {list(df.columns)}")
                return None

            # Date parse karo
            df['Date'] = pd.to_datetime(
                df['Date'], errors='coerce'
            )
            df = df.dropna(subset=['Date'])
            df = df.set_index('Date')
            df.index.name = 'Date'

            # Numeric convert karo
            for col in ['Open','High','Low',
                        'Close','Volume']:
                df[col] = pd.to_numeric(
                    df[col], errors='coerce'
                )

            # Clean karo
            df = df.dropna()
            df = df.sort_index()

            # Volume 0 fix
            df['Volume'] = df['Volume'].replace(0, 1)

            # Duplicate dates hatao
            df = df[~df.index.duplicated(keep='last')]

            row_count = len(df)
            print(f"✅ GitHub CSV: {row_count} din ka data!")
            print(f"   Start: "
                  f"{df.index[0].strftime('%Y-%m-%d')}")
            print(f"   End:   "
                  f"{df.index[-1].strftime('%Y-%m-%d')}")

            return df

        except Exception as e:
            print(f"❌ GitHub CSV Error: {e}")
            return None

    # ============================================
    # METHOD 2: ANGEL ONE — FALLBACK (1 SAAL)
    # ============================================
    def _fetch_batch(self, token, from_date, to_date):
        try:
            params = {
                "exchange"    : "NSE",
                "symboltoken" : token,
                "interval"    : "ONE_DAY",
                "fromdate"    : from_date.strftime(
                                "%Y-%m-%d 09:00"),
                "todate"      : to_date.strftime(
                                "%Y-%m-%d 15:30")
            }
            data = self.api.getCandleData(params)
            if data["status"] and data["data"]:
                return data["data"]
            return []
        except Exception as e:
            print(f"❌ Batch Error: {e}")
            return []

    def get_historical_data(self,
                             symbol="NIFTY",
                             days=365):
        try:
            if not self.connected:
                success = self.connect()
                if not success:
                    print("❌ Angel One connect fail!")
                    return None

            tokens = {
                "NIFTY"    : "99926000",
                "BANKNIFTY": "99926009",
            }

            token      = tokens[symbol]
            all_data   = []
            end_date   = datetime.now()
            start_date = end_date - timedelta(days=days)

            print(f"📅 Angel One se {days} din ka data...")

            chunk_days  = 90
            current_end = end_date

            while current_end > start_date:
                current_start = current_end - timedelta(
                    days=chunk_days
                )
                if current_start < start_date:
                    current_start = start_date

                batch = self._fetch_batch(
                    token, current_start, current_end
                )
                if batch:
                    all_data = batch + all_data
                    print(f"   ✅ {len(batch)} rows")

                current_end = current_start - timedelta(
                    days=1
                )
                time.sleep(0.5)

            if not all_data:
                print("❌ Angel One: Data nahi mila!")
                return None

            df = pd.DataFrame(
                all_data,
                columns=["Date","Open","High",
                         "Low","Close","Volume"]
            )

            df["Date"]   = pd.to_datetime(df["Date"])
            df           = df.sort_values("Date")
            df           = df.drop_duplicates(
                           subset=["Date"])
            df.set_index("Date", inplace=True)
            df["Volume"] = df["Volume"].replace(0, 1)
            df           = df.dropna()

            print(f"✅ Angel One: {len(df)} din ka data!")
            print(f"   Start: "
                  f"{df.index[0].strftime('%Y-%m-%d')}")
            print(f"   End:   "
                  f"{df.index[-1].strftime('%Y-%m-%d')}")

            return df

        except Exception as e:
            print(f"❌ Historical Data Error: {e}")
            return None

    # ============================================
    # MASTER — BEST DATA LO
    # ============================================
    def get_best_data(self, symbol="NIFTY"):
        """
        Priority:
        1. GitHub CSV  → 2464 rows (10 saal) ⭐
        2. Angel One   → 365 rows  (1 saal)
        """
        print("\n" + "="*45)
        print("🔍 BEST DATA SOURCE DHUND RAHA HUN")
        print("="*45)

        # Priority 1: GitHub CSV (10 saal)
        print("\n[1/2] GitHub CSV try kar raha hun...")
        df = self.get_data_from_github()

        if df is not None and len(df) > 200:
            print(f"\n🏆 GitHub CSV selected!")
            print(f"   Rows: {len(df)} ✅")
            return df

        # Priority 2: Angel One (1 saal)
        print("\n[2/2] Angel One fallback...")
        if not self.connected:
            self.connect()

        df = self.get_historical_data(symbol, days=365)

        if df is not None:
            print(f"\n🏆 Angel One selected!")
            print(f"   Rows: {len(df)} ✅")
            return df

        print("\n❌ Koi bhi source kaam nahi kar raha!")
        return None

    # ============================================
    # INTRADAY DATA
    # ============================================
    def get_intraday_data(self,
                           symbol="NIFTY",
                           days=5):
        try:
            if not self.connected:
                self.connect()

            tokens = {
                "NIFTY"    : "99926000",
                "BANKNIFTY": "99926009",
            }

            token = tokens[symbol]
            end   = datetime.now()
            start = end - timedelta(days=days)

            params = {
                "exchange"    : "NSE",
                "symboltoken" : token,
                "interval"    : "FIVE_MINUTE",
                "fromdate"    : start.strftime(
                                "%Y-%m-%d 09:00"),
                "todate"      : end.strftime(
                                "%Y-%m-%d 15:30")
            }

            data = self.api.getCandleData(params)

            if data["status"] and data["data"]:
                df = pd.DataFrame(
                    data["data"],
                    columns=["Date","Open","High",
                             "Low","Close","Volume"]
                )
                df["Date"] = pd.to_datetime(df["Date"])
                df.set_index("Date", inplace=True)
                print(f"✅ Intraday: {len(df)} candles!")
                return df

            return None

        except Exception as e:
            print(f"❌ Intraday Error: {e}")
            return None


# ============================================
# TEST
# ============================================
if __name__ == "__main__":
    print("=" * 50)
    print("🧪 DATA FETCHER FINAL TEST v6.0")
    print("=" * 50)

    # Local test ke liye credentials
    os.environ["ANGEL_API_KEY"]    = "mB3Hghfu"
    os.environ["ANGEL_SECRET_KEY"] = "36e27781-9351-4fbf-8143-973c0219b976"
    os.environ["ANGEL_CLIENT_ID"]  = "AACG329697"
    os.environ["ANGEL_PASSWORD"]   = "4160"
    os.environ["ANGEL_TOTP_KEY"]   = "APNA_TOTP_KEY_YAHAN"

    fetcher = DataFetcher()

    # Best data test
    print("\n--- Best Data Test ---")
    df = fetcher.get_best_data("NIFTY")

    if df is not None:
        print(f"\n✅ FINAL RESULT:")
        print(f"   Rows:    {len(df)}")
        print(f"   Columns: {list(df.columns)}")
        print(f"   Start:   {df.index[0].strftime('%Y-%m-%d')}")
        print(f"   End:     {df.index[-1].strftime('%Y-%m-%d')}")
        print(f"\n📋 Last 5 rows:")
        print(df.tail(5))
    else:
        print("❌ Data fetch failed!")

    # Angel One live price test
    print("\n--- Live Price Test ---")
    if fetcher.connect():
        fetcher.get_live_price("NIFTY")
        fetcher.get_live_price("BANKNIFTY")