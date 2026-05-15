# ============================================
# TITAN-AI TRADER — Data Fetcher v2.0
# TITAN-SURYA TECHNOLOGIES
# ============================================

from SmartApi import SmartConnect
import pyotp
import pandas as pd
import time
from datetime import datetime, timedelta
from config import ANGEL_ONE

class DataFetcher:

    def __init__(self):
        self.api       = None
        self.connected = False

    # ============================================
    # ANGEL ONE SE CONNECT
    # ============================================
    def connect(self):
        try:
            print("🔌 Connecting to Angleone App...")
            totp     = pyotp.TOTP(ANGEL_ONE["totp_key"]).now()
            self.api = SmartConnect(api_key=ANGEL_ONE["api_key"])
            data     = self.api.generateSession(
                            ANGEL_ONE["client_id"],
                            ANGEL_ONE["password"],
                            totp)
            if data["status"]:
                self.connected = True
                print("✅ Angel One Connected!")
                return True
            else:
                print(f"❌ Login Failed: {data}")
                return False
        except Exception as e:
            print(f"❌ Connect Error: {e}")
            return False

    # ============================================
    # LIVE PRICE LO
    # ============================================
    def get_live_price(self, symbol="NIFTY"):
        try:
            symbols = {
                "NIFTY"     : {"token": "99926000", "exchange": "NSE"},
                "BANKNIFTY" : {"token": "99926009", "exchange": "NSE"},
            }
            s    = symbols[symbol]
            data = self.api.ltpData(s["exchange"], symbol, s["token"])
            price = data["data"]["ltp"]
            print(f"📊 {symbol}: ₹{price}")
            return price
        except Exception as e:
            print(f"❌ Live Price Error: {e}")
            return None

    # ============================================
    # EK BATCH KA DATA LO (Max 100 din)
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
    # HISTORICAL DATA LO (Chunks mein)
    # ============================================
    def get_historical_data(self, symbol="NIFTY", days=365):
        try:
            if not self.connected:
                self.connect()

            tokens = {
                "NIFTY"     : "99926000",
                "BANKNIFTY" : "99926009",
            }
            token    = tokens[symbol]
            all_data = []

            end_date   = datetime.now()
            start_date = end_date - timedelta(days=days)

            print(f"📅 {days} din ka data fetch ho raha hai...")
            print(f"   From: {start_date.strftime('%Y-%m-%d')}")
            print(f"   To:   {end_date.strftime('%Y-%m-%d')}")

            # 90 din ke chunks mein fetch karo
            chunk_days  = 90
            current_end = end_date

            while current_end > start_date:
                current_start = current_end - timedelta(days=chunk_days)
                if current_start < start_date:
                    current_start = start_date

                batch = self._fetch_batch(token, current_start, current_end)
                if batch:
                    all_data = batch + all_data
                    print(f"   ✅ {len(batch)} rows fetched "
                          f"({current_start.strftime('%Y-%m-%d')} to "
                          f"{current_end.strftime('%Y-%m-%d')})")

                current_end = current_start - timedelta(days=1)
                time.sleep(0.5)  # API rate limit

            if not all_data:
                print("❌ Koi data nahi mila!")
                return None

            # DataFrame banao
            df = pd.DataFrame(
                all_data,
                columns=["Date","Open","High","Low","Close","Volume"]
            )
            df["Date"]  = pd.to_datetime(df["Date"])
            df          = df.sort_values("Date")
            df          = df.drop_duplicates(subset=["Date"])
            df.set_index("Date", inplace=True)

            # Volume 0 fix (Index mein normal hai)
            df["Volume"] = df["Volume"].replace(0, 1)

            print(f"\n✅ Total {len(df)} din ka data ready!")
            print(f"   Start: {df.index[0].strftime('%Y-%m-%d')}")
            print(f"   End:   {df.index[-1].strftime('%Y-%m-%d')}")

            # CSV mein save karo
            filename = f"{symbol}_data.csv"
            df.to_csv(filename)
            print(f"💾 Data saved: {filename}")

            return df

        except Exception as e:
            print(f"❌ Historical Data Error: {e}")
            return None

    # ============================================
    # INTRADAY DATA (5 min candles)
    # ============================================
    def get_intraday_data(self, symbol="NIFTY", days=30):
        try:
            if not self.connected:
                self.connect()

            tokens = {
                "NIFTY"     : "99926000",
                "BANKNIFTY" : "99926009",
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
                    columns=["Date","Open","High","Low","Close","Volume"]
                )
                df["Date"] = pd.to_datetime(df["Date"])
                df.set_index("Date", inplace=True)
                print(f"✅ {symbol} intraday: {len(df)} candles!")
                return df
            return None

        except Exception as e:
            print(f"❌ Intraday Error: {e}")
            return None


# ============================================
# TEST
# ============================================
if __name__ == "__main__":
    fetcher = DataFetcher()

    # Connect
    if not fetcher.connect():
        print("❌ Connection failed! Check credentials.")
        exit()

    print("\n" + "="*50)
    print("📊 LIVE PRICES")
    print("="*50)
    fetcher.get_live_price("NIFTY")
    fetcher.get_live_price("BANKNIFTY")

    print("\n" + "="*50)
    print("📈 HISTORICAL DATA (365 din)")
    print("="*50)
    df = fetcher.get_historical_data("NIFTY", days=365)

    if df is not None:
        print("\n📋 Last 5 rows:")
        print(df.tail())
        print(f"\n📊 Data Shape: {df.shape}")
        print(f"📊 Columns: {list(df.columns)}")

    print("\n" + "="*50)
    print("⏱️ INTRADAY DATA (5 min)")
    print("="*50)
    df_intra = fetcher.get_intraday_data("NIFTY", days=5)
    if df_intra is not None:
        print(df_intra.tail())