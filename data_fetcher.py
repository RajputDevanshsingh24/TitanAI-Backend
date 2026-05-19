# ============================================
# TITAN-AI TRADER — Data Fetcher v5.0
# TITAN-SURYA TECHNOLOGIES
# ============================================

from SmartApi import SmartConnect
import pyotp
import pandas as pd
import time
import os
import yfinance as yf
from datetime import datetime, timedelta

class DataFetcher:

    def __init__(self):
        self.api       = None
        self.connected = False

    # ============================================
    # ANGEL ONE CONNECT
    # ============================================
    def connect(self):
        try:
            print("🔌 Connecting to Angel One...")

            api_key  = os.environ.get("ANGEL_API_KEY", "")
            client   = os.environ.get("ANGEL_CLIENT_ID", "AACG329697")
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
            print(f"❌ Live Price Error: {e}")
            return None

    # ============================================
    # HISTORICAL DATA — YFINANCE (5 SAAL) ⭐
    # ============================================
    def get_historical_data_yfinance(self, 
                                      symbol="NIFTY", 
                                      years=5):
        try:
            # NSE Symbols
            symbols = {
                "NIFTY"    : "^NSEI",
                "BANKNIFTY": "^NSEBANK"
            }

            ticker = symbols.get(symbol, "^NSEI")

            print(f"📊 yfinance se {years} saal ka "
                  f"data fetch ho raha hai...")
            print(f"   Symbol: {ticker}")

            # Data download karo
            df = yf.download(
                ticker,
                period   = f"{years}y",
                progress = False,
                auto_adjust = True
            )

            if df.empty:
                print("❌ yfinance se data nahi mila!")
                return None

            # Column names fix karo
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [col[0] for col in df.columns]

            # Sirf OHLCV rakho
            df = df[["Open", "High", "Low", 
                     "Close", "Volume"]]
            df = df.dropna()
            df = df.sort_index()

            # Volume 0 fix
            df["Volume"] = df["Volume"].replace(0, 1)

            print(f"✅ yfinance: {len(df)} din ka data ready!")
            print(f"   Start: {df.index[0].strftime('%Y-%m-%d')}")
            print(f"   End:   {df.index[-1].strftime('%Y-%m-%d')}")

            # CSV save
            try:
                df.to_csv(f"{symbol}_yfinance.csv")
                print(f"💾 Saved: {symbol}_yfinance.csv")
            except:
                pass

            return df

        except Exception as e:
            print(f"❌ yfinance Error: {e}")
            return None

    # ============================================
    # HISTORICAL DATA — ANGEL ONE (Backup)
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
                    print("❌ Connect fail!")
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

                current_end = current_start - timedelta(days=1)
                time.sleep(0.5)

            if not all_data:
                print("❌ Koi data nahi mila!")
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

            print(f"✅ Angel One: {len(df)} din ka data!")
            return df

        except Exception as e:
            print(f"❌ Historical Data Error: {e}")
            return None

    # ============================================
    # SMART DATA FETCH (yfinance + Angel One)
    # ============================================
    def get_best_data(self, symbol="NIFTY", years=5):
        """
        Pehle yfinance try karo (5 saal)
        Fail hone pe Angel One se lo (1 saal)
        """
        print(f"🔍 Best data fetch kar raha hun...")

        # Try 1: yfinance (5 saal)
        df = self.get_historical_data_yfinance(
            symbol, years
        )

        if df is not None and len(df) > 100:
            print(f"✅ yfinance data use kar raha hun "
                  f"({len(df)} rows)")
            return df

        # Try 2: Angel One (1 saal)
        print("⚠️ yfinance failed — Angel One try kar raha hun...")
        if not self.connected:
            self.connect()

        df = self.get_historical_data(symbol, days=365)

        if df is not None:
            print(f"✅ Angel One data use kar raha hun "
                  f"({len(df)} rows)")
            return df

        print("❌ Dono sources fail ho gaye!")
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
    print("="*50)
    print("🧪 DATA FETCHER TEST v5.0")
    print("="*50)

    # Local test credentials
    os.environ["ANGEL_API_KEY"]    = "mB3Hghfu"
    os.environ["ANGEL_SECRET_KEY"] = "36e27781-9351-4fbf-8143-973c0219b976"
    os.environ["ANGEL_CLIENT_ID"]  = "AACG329697"
    os.environ["ANGEL_PASSWORD"]   = "4160"
    os.environ["ANGEL_TOTP_KEY"]   = "TOTP_KEY_YAHAN"

    fetcher = DataFetcher()

    # yfinance test
    print("\n--- yfinance Test ---")
    df = fetcher.get_historical_data_yfinance(
        "NIFTY", years=5
    )
    if df is not None:
        print(f"Rows: {len(df)}")
        print(df.tail(3))

    # Angel One test
    print("\n--- Angel One Test ---")
    if fetcher.connect():
        fetcher.get_live_price("NIFTY")
        fetcher.get_live_price("BANKNIFTY")