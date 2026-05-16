# ============================================
# TITAN-AI TRADER — Data Fetcher v4.0
# TITAN-SURYA TECHNOLOGIES
# ============================================

from SmartApi import SmartConnect
import pyotp
import pandas as pd
import time
import os
from datetime import datetime, timedelta

class DataFetcher:

    def __init__(self):
        self.api       = None
        self.connected = False

    # ============================================
    # CONNECT
    # ============================================
    def connect(self):
        try:
            print("🔌 Connecting to Angel One...")

            # Seedha os.environ se lo
            api_key  = os.environ.get("ANGEL_API_KEY", "")
            client   = os.environ.get("ANGEL_CLIENT_ID", "AACG329697")
            password = os.environ.get("ANGEL_PASSWORD", "")
            totp_key = os.environ.get("ANGEL_TOTP_KEY", "")

            # Debug print
            print(f"   API Key:  {api_key[:4] if api_key else 'EMPTY'}****")
            print(f"   Client:   {client}")
            print(f"   Password: {'SET ✅' if password else 'EMPTY ❌'}")
            print(f"   TOTP Key: {'SET ✅' if totp_key else 'EMPTY ❌'}")

            # Validation
            if not api_key:
                print("❌ ANGEL_API_KEY missing in Railway!")
                return False
            if not password:
                print("❌ ANGEL_PASSWORD missing in Railway!")
                return False
            if not totp_key:
                print("❌ ANGEL_TOTP_KEY missing in Railway!")
                return False

            # TOTP generate
            totp = pyotp.TOTP(totp_key).now()
            print(f"   TOTP Code: {totp}")

            # Login
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
    # LIVE PRICE
    # ============================================
    def get_live_price(self, symbol="NIFTY"):
        try:
            if not self.connected:
                self.connect()

            symbols = {
                "NIFTY"    : {"token": "99926000", "exchange": "NSE"},
                "BANKNIFTY": {"token": "99926009", "exchange": "NSE"},
            }
            s     = symbols[symbol]
            data  = self.api.ltpData(
                s["exchange"], symbol, s["token"]
            )
            price = data["data"]["ltp"]
            print(f"📊 {symbol}: ₹{price}")
            return price

        except Exception as e:
            print(f"❌ Price Error: {e}")
            return None

    # ============================================
    # BATCH DATA
    # ============================================
    def _fetch_batch(self, token, from_date, to_date):
        try:
            params = {
                "exchange"    : "NSE",
                "symboltoken" : token,
                "interval"    : "ONE_DAY",
                "fromdate"    : from_date.strftime("%Y-%m-%d 09:00"),
                "todate"      : to_date.strftime("%Y-%m-%d 15:30")
            }
            data = self.api.getCandleData(params)
            if data["status"] and data["data"]:
                return data["data"]
            return []
        except Exception as e:
            print(f"❌ Batch Error: {e}")
            return []

    # ============================================
    # HISTORICAL DATA
    # ============================================
    def get_historical_data(self, symbol="NIFTY", days=365):
        try:
            if not self.connected:
                success = self.connect()
                if not success:
                    print("❌ Connect fail — data nahi milega!")
                    return None

            tokens = {
                "NIFTY"    : "99926000",
                "BANKNIFTY": "99926009",
            }
            token      = tokens[symbol]
            all_data   = []
            end_date   = datetime.now()
            start_date = end_date - timedelta(days=days)

            print(f"📅 {days} din ka data fetch ho raha hai...")

            chunk_days  = 90
            current_end = end_date

            while current_end > start_date:
                current_start = current_end - timedelta(days=chunk_days)
                if current_start < start_date:
                    current_start = start_date

                batch = self._fetch_batch(
                    token, current_start, current_end
                )
                if batch:
                    all_data = batch + all_data
                    print(f"   ✅ {len(batch)} rows fetched")

                current_end = current_start - timedelta(days=1)
                time.sleep(0.5)

            if not all_data:
                print("❌ Koi data nahi mila!")
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

            print(f"✅ Total {len(df)} din ka data ready!")
            return df

        except Exception as e:
            print(f"❌ Historical Data Error: {e}")
            return None

    # ============================================
    # INTRADAY DATA
    # ============================================
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
                "todate"      : end.strftime("%Y-%m-%d 15:30")
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
    # Local test ke liye hardcode
    os.environ["ANGEL_API_KEY"]    = "mB3Hghfu"
    os.environ["ANGEL_SECRET_KEY"] = "36e27781-9351-4fbf-8143-973c0219b976"
    os.environ["ANGEL_CLIENT_ID"]  = "AACG329697"
    os.environ["ANGEL_PASSWORD"]   = "4160"
    os.environ["ANGEL_TOTP_KEY"]   = "TOTP_KEY_YAHAN"

    fetcher = DataFetcher()
    if fetcher.connect():
        fetcher.get_live_price("NIFTY")
        df = fetcher.get_historical_data("NIFTY", days=100)
        if df is not None:
            print(df.tail())