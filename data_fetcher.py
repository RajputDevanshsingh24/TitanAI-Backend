# ============================================
# TITAN-AI TRADER — Data Fetcher v6.0
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
        self.api       = None
        self.connected = False
        self.github_csv = (
            "https://raw.githubusercontent.com/"
            "RajputDevanshsingh24/TitanAI-Backend/"
            "main/nifty_data.csv"
        )

    def connect(self):
        try:
            print("🔌 Connecting to Angel One...")

            api_key  = os.environ.get("ANGEL_API_KEY",  "")
            client   = os.environ.get("ANGEL_CLIENT_ID","AACG329697")
            password = os.environ.get("ANGEL_PASSWORD", "")
            totp_key = os.environ.get("ANGEL_TOTP_KEY", "")

            print(f"   API Key:  {api_key[:4] if api_key else 'EMPTY'}****")
            print(f"   Client:   {client}")
            print(f"   Password: {'SET ✅' if password else 'EMPTY ❌'}")
            print(f"   TOTP Key: {'SET ✅' if totp_key else 'EMPTY ❌'}")

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

    def get_live_price(self, symbol="NIFTY"):
        try:
            if not self.connected:
                self.connect()

            symbols = {
                "NIFTY"    : {"token": "99926000", "exchange": "NSE"},
                "BANKNIFTY": {"token": "99926009", "exchange": "NSE"},
            }

            s     = symbols[symbol]
            data  = self.api.ltpData(s["exchange"], symbol, s["token"])
            price = data["data"]["ltp"]
            print(f"📊 {symbol}: ₹{price}")
            return price

        except Exception as e:
            print(f"❌ Live Price Error: {e}")
            return None

    def get_data_from_github(self):
        try:
            print("📊 GitHub CSV se data load ho raha hai...")
            response = requests.get(
                self.github_csv,
                timeout = 20,
                headers = {"User-Agent": "Mozilla/5.0"}
            )

            if response.status_code != 200:
                print(f"❌ GitHub HTTP Error: {response.status_code}")
                return None

            from io import StringIO
            content = response.text.strip()
            if len(content) < 100:
                print("❌ GitHub: Empty response!")
                return None

            df = pd.read_csv(StringIO(content), header=0)

            required = ['Date','Close','High','Low','Open','Volume']
            missing  = [c for c in required if c not in df.columns]
            if missing:
                print(f"❌ Missing columns: {missing}")
                return None

            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            df = df.dropna(subset=['Date'])
            df = df.set_index('Date')

            for col in ['Open','High','Low','Close','Volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')

            df = df.dropna()
            df = df.sort_index()
            df['Volume'] = df['Volume'].replace(0, 1)
            df = df[~df.index.duplicated(keep='last')]

            print(f"✅ GitHub CSV: {len(df)} rows!")
            print(f"   Start: {df.index[0].strftime('%Y-%m-%d')}")
            print(f"   End:   {df.index[-1].strftime('%Y-%m-%d')}")
            return df

        except Exception as e:
            print(f"❌ GitHub CSV Error: {e}")
            return None

    def _fetch_batch(self, token, from_date, to_date):
        try:
            params = {
                "exchange"    : "NSE",
                "symboltoken" : token,
                "interval"    : "ONE_DAY",
                "fromdate"    : from_date.strftime("%Y-%m-%d 09:00"),
                "todate"      : to_date.strftime("%Y-%m-%d 15:30"),
            }
            data = self.api.getCandleData(params)
            if data["status"] and data["data"]:
                return data["data"]
            return []
        except Exception as e:
            print(f"❌ Batch Error: {e}")
            return []

    def get_historical_data(self, symbol="NIFTY", days=365):
        try:
            if not self.connected:
                if not self.connect():
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
                current_start = current_end - timedelta(days=chunk_days)
                if current_start < start_date:
                    current_start = start_date

                batch = self._fetch_batch(token, current_start, current_end)
                if batch:
                    all_data = batch + all_data
                    print(f"   ✅ {len(batch)} rows")

                current_end = current_start - timedelta(days=1)
                time.sleep(0.5)

            if not all_data:
                print("❌ Angel One: Data nahi mila!")
                return None

            df = pd.DataFrame(
                all_data,
                columns=["Date","Open","High","Low","Close","Volume"]
            )
            df["Date"]   = pd.to_datetime(df["Date"])
            df           = df.sort_values("Date")
            df           = df.drop_duplicates(subset=["Date"])
            df.set_index("Date", inplace=True)
            df["Volume"] = df["Volume"].replace(0, 1)
            df           = df.dropna()

            print(f"✅ Angel One: {len(df)} rows!")
            return df

        except Exception as e:
            print(f"❌ Historical Data Error: {e}")
            return None

    def get_best_data(self, symbol="NIFTY"):
        print("\n" + "="*45)
        print("🔍 BEST DATA SOURCE DHUND RAHA HUN")
        print("="*45)

        print("\n[1/2] GitHub CSV try kar raha hun...")
        df = self.get_data_from_github()
        if df is not None and len(df) > 200:
            print(f"\n🏆 GitHub CSV selected! Rows: {len(df)}")
            return df

        print("\n[2/2] Angel One fallback...")
        if not self.connected:
            self.connect()
        df = self.get_historical_data(symbol, days=365)
        if df is not None:
            print(f"\n🏆 Angel One selected! Rows: {len(df)}")
            return df

        print("\n❌ Koi bhi source kaam nahi kar raha!")
        return None

    def get_intraday_data(self, symbol="NIFTY", days=5):
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
                "fromdate"    : start.strftime("%Y-%m-%d 09:00"),
                "todate"      : end.strftime("%Y-%m-%d 15:30"),
            }

            data = self.api.getCandleData(params)
            if data["status"] and data["data"]:
                df = pd.DataFrame(
                    data["data"],
                    columns=["Date","Open","High","Low","Close","Volume"]
                )
                df["Date"] = pd.to_datetime(df["Date"])
                df.set_index("Date", inplace=True)
                print(f"✅ Intraday: {len(df)} candles!")
                return df
            return None

        except Exception as e:
            print(f"❌ Intraday Error: {e}")
            return None