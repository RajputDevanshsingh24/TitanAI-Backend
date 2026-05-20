# ============================================
# TITAN-AI TRADER — Data Fetcher FINAL
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
        
        # GitHub raw CSV URL
        self.github_csv = (
            "https://raw.githubusercontent.com/"
            "RajputDevanshsingh24/TitanAI-Backend/"
            "main/nifty_data.csv"
        )

    # ============================================
    # CONNECT — ANGEL ONE
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

            if not api_key or not password or not totp_key:
                print("❌ Credentials missing!")
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
    # METHOD 1: GITHUB CSV (PRIMARY — 10 SAAL)
    # ============================================
    def get_data_from_github(self):
        try:
            print("📊 GitHub CSV se data load ho raha hai...")
            print(f"   URL: {self.github_csv}")

            response = requests.get(
                self.github_csv,
                timeout=15
            )

            if response.status_code != 200:
                print(f"❌ GitHub error: {response.status_code}")
                return None

            from io import StringIO
            df = pd.read_csv(StringIO(response.text))

            # Column names normalize karo
            df.columns = [c.strip().title() 
                         for c in df.columns]

            # Date column find karo
            date_col = None
            for col in df.columns:
                if 'date' in col.lower():
                    date_col = col
                    break

            if date_col is None:
                print("❌ Date column nahi mila!")
                return None

            df[date_col] = pd.to_datetime(
                df[date_col], dayfirst=True
            )
            df.set_index(date_col, inplace=True)
            df.index.name = "Date"

            # OHLCV columns find karo
            col_map = {}
            for col in df.columns:
                cl = col.lower()
                if 'open' in cl:
                    col_map[col] = 'Open'
                elif 'high' in cl:
                    col_map[col] = 'High'
                elif 'low' in cl:
                    col_map[col] = 'Low'
                elif 'close' in cl:
                    col_map[col] = 'Close'
                elif 'volume' in cl:
                    col_map[col] = 'Volume'

            df = df.rename(columns=col_map)

            # Volume nahi hai toh add karo
            if 'Volume' not in df.columns:
                df['Volume'] = 1

            # Sirf OHLCV rakho
            available = [c for c in 
                        ['Open','High','Low','Close','Volume']
                        if c in df.columns]
            df = df[available]

            # Commas hatao numbers se
            for col in df.columns:
                if df[col].dtype == object:
                    df[col] = df[col].astype(str)\
                              .str.replace(',', '')\
                              .str.replace(' ', '')
                    df[col] = pd.to_numeric(
                        df[col], errors='coerce'
                    )

            df = df.dropna()
            df = df.sort_index()

            print(f"✅ GitHub CSV: {len(df)} din ka data!")
            print(f"   Start: {df.index[0].strftime('%Y-%m-%d')}")
            print(f"   End:   {df.index[-1].strftime('%Y-%m-%d')}")

            return df

        except Exception as e:
            print(f"❌ GitHub CSV Error: {e}")
            return None

    # ============================================
    # METHOD 2: STOOQ (BACKUP — AUTO)
    # ============================================
    def get_data_from_stooq(self, years=5):
        try:
            print("📊 Stooq se data fetch ho raha hai...")

            from datetime import datetime, timedelta
            end   = datetime.now()
            start = end - timedelta(days=years*365)

            url = (
                f"https://stooq.com/q/d/l/"
                f"?s=%5Ensep"
                f"&d1={start.strftime('%Y%m%d')}"
                f"&d2={end.strftime('%Y%m%d')}"
                f"&i=d"
            )

            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(
                url, headers=headers, timeout=15
            )

            if response.status_code != 200:
                print(f"❌ Stooq error: {response.status_code}")
                return None

            from io import StringIO
            df = pd.read_csv(StringIO(response.text))

            if df.empty or len(df) < 100:
                print("❌ Stooq: Kafi data nahi mila!")
                return None

            df['Date'] = pd.to_datetime(df['Date'])
            df.set_index('Date', inplace=True)

            # Rename columns
            df = df.rename(columns={
                'Open' : 'Open',
                'High' : 'High',
                'Low'  : 'Low',
                'Close': 'Close',
            })

            if 'Volume' not in df.columns:
                df['Volume'] = 1

            df = df[['Open','High','Low','Close','Volume']]
            df = df.dropna()
            df = df.sort_index()

            print(f"✅ Stooq: {len(df)} din ka data!")
            print(f"   Start: {df.index[0].strftime('%Y-%m-%d')}")
            print(f"   End:   {df.index[-1].strftime('%Y-%m-%d')}")

            return df

        except Exception as e:
            print(f"❌ Stooq Error: {e}")
            return None

    # ============================================
    # METHOD 3: ANGEL ONE (FALLBACK — 1 SAAL)
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

            print(f"✅ Angel One: {len(df)} din ka data!")
            return df

        except Exception as e:
            print(f"❌ Historical Data Error: {e}")
            return None

    # ============================================
    # MASTER FUNCTION — BEST DATA LO
    # ============================================
    def get_best_data(self, symbol="NIFTY"):
        """
        Priority order:
        1. GitHub CSV (10 saal — manually uploaded)
        2. Stooq (5 saal — auto)
        3. Angel One (1 saal — fallback)
        """
        print("\n" + "="*45)
        print("🔍 BEST DATA SOURCE DHUND RAHA HUN")
        print("="*45)

        # Priority 1: GitHub CSV
        df = self.get_data_from_github()
        if df is not None and len(df) > 500:
            print(f"🏆 GitHub CSV use kar raha hun!")
            print(f"   Rows: {len(df)} ✅")
            return df

        # Priority 2: Stooq
        print("⚠️ GitHub failed — Stooq try...")
        df = self.get_data_from_stooq(years=5)
        if df is not None and len(df) > 500:
            print(f"🏆 Stooq use kar raha hun!")
            print(f"   Rows: {len(df)} ✅")
            return df

        # Priority 3: Angel One
        print("⚠️ Stooq failed — Angel One fallback...")
        if not self.connected:
            self.connect()
        df = self.get_historical_data(symbol, days=365)
        if df is not None:
            print(f"🏆 Angel One use kar raha hun!")
            print(f"   Rows: {len(df)} ✅")
            return df

        print("❌ Koi bhi source kaam nahi kar raha!")
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
    print("="*50)
    print("🧪 DATA FETCHER FINAL TEST")
    print("="*50)

    fetcher = DataFetcher()

    # Best data test
    df = fetcher.get_best_data("NIFTY")
    if df is not None:
        print(f"\n✅ Final Result:")
        print(f"   Rows:  {len(df)}")
        print(f"   Start: {df.index[0].strftime('%Y-%m-%d')}")
        print(f"   End:   {df.index[-1].strftime('%Y-%m-%d')}")
        print(df.tail(3))