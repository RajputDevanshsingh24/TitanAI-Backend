# ============================================
# TITAN-AI TRADER — Indicators Engine v2.0
# TITAN-SURYA TECHNOLOGIES
#
# CHANGES v2.0:
# - 5-min candles support
# - VWAP session-based (intraday)
# - Opening Range Breakout (ORB)
# - Volume Profile
# - Supertrend
# - VIX filter feature
# - Session time features
# ============================================

import pandas as pd
import numpy as np


class Indicators:

    def __init__(self, df):
        self.df = df.copy()

    # ============================================
    # RSI
    # ============================================
    def add_rsi(self, period=14):
        delta = self.df["Close"].diff()
        gain  = delta.clip(lower=0)
        loss  = -delta.clip(upper=0)
        avg_g = gain.ewm(com=period - 1, min_periods=period).mean()
        avg_l = loss.ewm(com=period - 1, min_periods=period).mean()
        rs    = avg_g / avg_l
        self.df["RSI"] = 100 - (100 / (1 + rs))
        return self

    # ============================================
    # MACD
    # ============================================
    def add_macd(self, fast=12, slow=26, signal=9):
        ema_f                = self.df["Close"].ewm(span=fast).mean()
        ema_s                = self.df["Close"].ewm(span=slow).mean()
        self.df["MACD"]      = ema_f - ema_s
        self.df["MACD_Sig"]  = self.df["MACD"].ewm(span=signal).mean()
        self.df["MACD_Hist"] = self.df["MACD"] - self.df["MACD_Sig"]
        return self

    # ============================================
    # BOLLINGER BANDS
    # ============================================
    def add_bollinger(self, period=20, std=2):
        sma                    = self.df["Close"].rolling(period).mean()
        std_dev                = self.df["Close"].rolling(period).std()
        self.df["BB_Upper"]    = sma + std_dev * std
        self.df["BB_Lower"]    = sma - std_dev * std
        self.df["BB_Middle"]   = sma
        self.df["BB_Width"]    = self.df["BB_Upper"] - self.df["BB_Lower"]
        self.df["BB_Position"] = (
            (self.df["Close"] - self.df["BB_Lower"]) /
            self.df["BB_Width"].clip(lower=0.01)
        )
        return self

    # ============================================
    # EMA
    # ============================================
    def add_ema(self, periods=[9, 20, 50, 200]):
        for p in periods:
            self.df[f"EMA_{p}"] = self.df["Close"].ewm(span=p).mean()
        return self

    # ============================================
    # SMA
    # ============================================
    def add_sma(self, periods=[20, 50]):
        for p in periods:
            self.df[f"SMA_{p}"] = self.df["Close"].rolling(p).mean()
        return self

    # ============================================
    # ATR
    # ============================================
    def add_atr(self, period=14):
        high  = self.df["High"]
        low   = self.df["Low"]
        close = self.df["Close"].shift(1)
        tr    = pd.concat([
            high - low,
            (high - close).abs(),
            (low  - close).abs(),
        ], axis=1).max(axis=1)
        self.df["ATR"] = tr.rolling(period).mean()
        return self

    # ============================================
    # STOCHASTIC
    # ============================================
    def add_stochastic(self, period=14):
        low_min            = self.df["Low"].rolling(period).min()
        high_max           = self.df["High"].rolling(period).max()
        denom              = (high_max - low_min).clip(lower=0.01)
        self.df["STOCH_K"] = 100 * (self.df["Close"] - low_min) / denom
        self.df["STOCH_D"] = self.df["STOCH_K"].rolling(3).mean()
        return self

    # ============================================
    # VWAP — Session Based (5-min ke liye best)
    # Har din 9:15 pe reset hota hai
    # ============================================
    def add_vwap(self):
        try:
            typical = (
                self.df["High"] +
                self.df["Low"]  +
                self.df["Close"]
            ) / 3

            # Date group karke VWAP calculate karo
            # Taaki har din fresh start mile
            self.df["_typical"] = typical
            self.df["_tp_vol"]  = typical * self.df["Volume"]
            self.df["_date"]    = self.df.index.date

            # Cumulative per day
            self.df["_cum_tpvol"] = self.df.groupby("_date")["_tp_vol"].cumsum()
            self.df["_cum_vol"]   = self.df.groupby("_date")["Volume"].cumsum()

            self.df["VWAP"] = (
                self.df["_cum_tpvol"] /
                self.df["_cum_vol"].clip(lower=1)
            )

            # VWAP distance — price kitna door hai
            self.df["VWAP_Dist"] = (
                (self.df["Close"] - self.df["VWAP"]) /
                self.df["VWAP"].clip(lower=0.01) * 100
            )

            # VWAP position — above/below
            self.df["Above_VWAP"] = (
                self.df["Close"] > self.df["VWAP"]
            ).astype(int)

            # Cleanup
            self.df.drop(
                columns=["_typical", "_tp_vol", "_date",
                         "_cum_tpvol", "_cum_vol"],
                inplace=True
            )

        except Exception as e:
            print(f"⚠️ VWAP Error: {e}")
            self.df["VWAP"]       = self.df["Close"]
            self.df["VWAP_Dist"]  = 0.0
            self.df["Above_VWAP"] = 0

        return self

    # ============================================
    # SUPERTREND — Trend following (5-min best)
    # Green = Uptrend, Red = Downtrend
    # ============================================
    def add_supertrend(self, period=10, multiplier=3.0):
        try:
            high  = self.df["High"]
            low   = self.df["Low"]
            close = self.df["Close"]

            # ATR
            prev_close = close.shift(1)
            tr = pd.concat([
                high - low,
                (high - prev_close).abs(),
                (low  - prev_close).abs(),
            ], axis=1).max(axis=1)
            atr = tr.rolling(period).mean()

            # Basic bands
            hl_avg    = (high + low) / 2
            upper_band = hl_avg + multiplier * atr
            lower_band = hl_avg - multiplier * atr

            supertrend = pd.Series(index=self.df.index, dtype=float)
            direction  = pd.Series(index=self.df.index, dtype=int)

            for i in range(1, len(self.df)):
                # Upper band
                if upper_band.iloc[i] < upper_band.iloc[i-1] or \
                   close.iloc[i-1] > upper_band.iloc[i-1]:
                    upper_band.iloc[i] = upper_band.iloc[i]
                else:
                    upper_band.iloc[i] = upper_band.iloc[i-1]

                # Lower band
                if lower_band.iloc[i] > lower_band.iloc[i-1] or \
                   close.iloc[i-1] < lower_band.iloc[i-1]:
                    lower_band.iloc[i] = lower_band.iloc[i]
                else:
                    lower_band.iloc[i] = lower_band.iloc[i-1]

                # Direction
                if pd.isna(supertrend.iloc[i-1]):
                    direction.iloc[i] = 1
                elif supertrend.iloc[i-1] == upper_band.iloc[i-1]:
                    direction.iloc[i] = (
                        1 if close.iloc[i] > upper_band.iloc[i] else -1
                    )
                else:
                    direction.iloc[i] = (
                        -1 if close.iloc[i] < lower_band.iloc[i] else 1
                    )

                supertrend.iloc[i] = (
                    lower_band.iloc[i]
                    if direction.iloc[i] == 1
                    else upper_band.iloc[i]
                )

            self.df["Supertrend"]     = supertrend
            self.df["ST_Direction"]   = direction  # 1=up, -1=down
            self.df["ST_Bullish"]     = (direction == 1).astype(int)

        except Exception as e:
            print(f"⚠️ Supertrend Error: {e}")
            self.df["Supertrend"]   = self.df["Close"]
            self.df["ST_Direction"] = 0
            self.df["ST_Bullish"]   = 0

        return self

    # ============================================
    # OPENING RANGE BREAKOUT (ORB)
    # First 15 min (9:15-9:30) ka high/low
    # Breakout upar → Bullish
    # Breakout neeche → Bearish
    # ============================================
    def add_orb(self):
        try:
            self.df["_date"] = self.df.index.date
            self.df["_time"] = self.df.index.time

            import datetime as dt

            # Opening range = 9:15 to 9:30 (first 3 candles of 5-min)
            orb_end = dt.time(9, 30)

            orb_high = {}
            orb_low  = {}

            for date, group in self.df.groupby("_date"):
                opening = group[group["_time"] <= orb_end]
                if len(opening) > 0:
                    orb_high[date] = opening["High"].max()
                    orb_low[date]  = opening["Low"].min()

            self.df["ORB_High"] = self.df["_date"].map(orb_high)
            self.df["ORB_Low"]  = self.df["_date"].map(orb_low)

            # Breakout signals
            self.df["ORB_Breakout_Up"]   = (
                self.df["Close"] > self.df["ORB_High"]
            ).astype(int)
            self.df["ORB_Breakout_Down"] = (
                self.df["Close"] < self.df["ORB_Low"]
            ).astype(int)

            # Distance from ORB
            self.df["ORB_Dist_High"] = (
                (self.df["Close"] - self.df["ORB_High"]) /
                self.df["ORB_High"].clip(lower=0.01) * 100
            )
            self.df["ORB_Dist_Low"] = (
                (self.df["Close"] - self.df["ORB_Low"]) /
                self.df["ORB_Low"].clip(lower=0.01) * 100
            )

            self.df.drop(columns=["_date", "_time"], inplace=True)

        except Exception as e:
            print(f"⚠️ ORB Error: {e}")
            self.df["ORB_High"]          = self.df["High"]
            self.df["ORB_Low"]           = self.df["Low"]
            self.df["ORB_Breakout_Up"]   = 0
            self.df["ORB_Breakout_Down"] = 0
            self.df["ORB_Dist_High"]     = 0.0
            self.df["ORB_Dist_Low"]      = 0.0

        return self

    # ============================================
    # SESSION TIME FEATURES
    # Model ko pata rahe ki din ka konsa hissa hai
    # ============================================
    def add_session_features(self):
        try:
            import datetime as dt

            hour   = self.df.index.hour
            minute = self.df.index.minute

            # Time as number (9.25 = 9:15 AM)
            self.df["Time_Num"] = hour + minute / 60.0

            # Session bins
            # 0 = Opening (9:15-10:30)
            # 1 = Mid (10:30-14:00)
            # 2 = Closing (14:00-15:30)
            conditions = [
                (self.df["Time_Num"] < 10.5),
                (self.df["Time_Num"] >= 10.5) & (self.df["Time_Num"] < 14.0),
                (self.df["Time_Num"] >= 14.0),
            ]
            self.df["Session"] = np.select(conditions, [0, 1, 2], default=1)

            # Is opening session?
            self.df["Is_Opening"] = (self.df["Session"] == 0).astype(int)
            # Is mid session? (best for trading)
            self.df["Is_Mid"]     = (self.df["Session"] == 1).astype(int)
            # Is closing session?
            self.df["Is_Closing"] = (self.df["Session"] == 2).astype(int)

            # Day of week (Monday=0, Friday=4)
            self.df["Day_of_Week"] = self.df.index.dayofweek

            # Monday effect (gaps from weekend)
            self.df["Is_Monday"]   = (
                self.df.index.dayofweek == 0
            ).astype(int)

            # Friday (pre-weekend selling)
            self.df["Is_Friday"]   = (
                self.df.index.dayofweek == 4
            ).astype(int)

        except Exception as e:
            print(f"⚠️ Session Features Error: {e}")

        return self

    # ============================================
    # VOLUME FEATURES
    # ============================================
    def add_volume_features(self):
        try:
            vol = self.df["Volume"]

            # Rolling averages
            self.df["Vol_MA_10"]  = vol.rolling(10).mean()
            self.df["Vol_MA_20"]  = vol.rolling(20).mean()

            # Volume ratio — abhi kitna volume hai vs average
            self.df["Vol_Ratio"]  = (
                vol / self.df["Vol_MA_20"].clip(lower=1)
            )

            # High volume = institutional activity
            self.df["High_Volume"] = (
                self.df["Vol_Ratio"] > 1.5
            ).astype(int)

            # Volume trend
            self.df["Vol_Change"]  = vol.pct_change()
            self.df["Vol_Spike"]   = (
                self.df["Vol_Ratio"] > 2.0
            ).astype(int)

        except Exception as e:
            print(f"⚠️ Volume Features Error: {e}")

        return self

    # ============================================
    # PRICE ACTION FEATURES
    # ============================================
    def add_price_features(self):
        try:
            close = self.df["Close"]
            open_ = self.df["Open"]
            high  = self.df["High"]
            low   = self.df["Low"]

            # Returns
            self.df["Return_1"]  = close.pct_change(1)  * 100
            self.df["Return_3"]  = close.pct_change(3)  * 100
            self.df["Return_6"]  = close.pct_change(6)  * 100
            self.df["Return_12"] = close.pct_change(12) * 100

            # Candle ratios
            body   = (close - open_).abs()
            candle = (high - low).clip(lower=0.01)

            self.df["Body_Ratio"] = body / candle
            self.df["HL_Ratio"]   = candle / close.clip(lower=0.01)
            self.df["CO_Ratio"]   = (close - open_) / open_.clip(lower=0.01)

            # Momentum
            self.df["Mom_5"]  = close - close.shift(5)
            self.df["Mom_10"] = close - close.shift(10)
            self.df["Mom_20"] = close - close.shift(20)

            # Rolling stats
            self.df["Roll_Mean_10"] = close.rolling(10).mean()
            self.df["Roll_Std_10"]  = close.rolling(10).std()
            self.df["Roll_Mean_20"] = close.rolling(20).mean()
            self.df["Roll_Std_20"]  = close.rolling(20).std()

            # Z-score (mean reversion signal)
            self.df["Z_Score"] = (
                (close - self.df["Roll_Mean_20"]) /
                self.df["Roll_Std_20"].clip(lower=0.01)
            )

        except Exception as e:
            print(f"⚠️ Price Features Error: {e}")

        return self

    # ============================================
    # CANDLE PATTERNS
    # ============================================
    def add_candle_patterns(self):
        try:
            op = self.df["Open"]
            hi = self.df["High"]
            lo = self.df["Low"]
            cl = self.df["Close"]

            body   = (cl - op).abs()
            candle = (hi - lo).clip(lower=0.01)

            self.df["Doji"]    = (body <= candle * 0.1).astype(int)
            self.df["Bullish"] = (cl > op).astype(int)
            self.df["Bearish"] = (cl < op).astype(int)

            lower_wick        = op.where(cl > op, cl) - lo
            self.df["Hammer"] = (
                (lower_wick >= body * 2) & (cl > op)
            ).astype(int)

            upper_wick              = hi - cl.where(cl > op, op)
            self.df["ShootingStar"] = (
                (upper_wick >= body * 2) & (cl < op)
            ).astype(int)

            # Engulfing patterns
            prev_body  = body.shift(1)
            prev_bull  = self.df["Bullish"].shift(1)
            self.df["Bull_Engulf"] = (
                (cl > op) &
                (op < self.df["Close"].shift(1)) &
                (cl > self.df["Open"].shift(1)) &
                (body > prev_body)
            ).astype(int)

            self.df["Bear_Engulf"] = (
                (cl < op) &
                (op > self.df["Close"].shift(1)) &
                (cl < self.df["Open"].shift(1)) &
                (body > prev_body)
            ).astype(int)

        except Exception as e:
            print(f"⚠️ Candle Patterns Error: {e}")

        return self

    # ============================================
    # SUPPORT & RESISTANCE
    # ============================================
    def add_support_resistance(self, period=20):
        self.df["Support"]    = self.df["Low"].rolling(period).min()
        self.df["Resistance"] = self.df["High"].rolling(period).max()

        # Distance from S/R
        self.df["Dist_Support"] = (
            (self.df["Close"] - self.df["Support"]) /
            self.df["Support"].clip(lower=0.01) * 100
        )
        self.df["Dist_Resist"] = (
            (self.df["Resistance"] - self.df["Close"]) /
            self.df["Close"].clip(lower=0.01) * 100
        )
        return self

    # ============================================
    # QUICK SIGNAL — Simple rule-based
    # (AI signal ke saath compare karne ke liye)
    # ============================================
    def get_signal(self):
        latest  = self.df.iloc[-1]
        score   = 0
        reasons = []

        # RSI
        if "RSI" in self.df.columns:
            rsi = latest.get("RSI", 50)
            if rsi < 35:
                score += 2
                reasons.append(f"RSI Oversold: {rsi:.1f}")
            elif rsi > 65:
                score -= 2
                reasons.append(f"RSI Overbought: {rsi:.1f}")

        # MACD
        if "MACD" in self.df.columns:
            if latest.get("MACD", 0) > latest.get("MACD_Sig", 0):
                score += 2
                reasons.append("MACD Bullish")
            else:
                score -= 2
                reasons.append("MACD Bearish")

        # Supertrend
        if "ST_Bullish" in self.df.columns:
            if latest.get("ST_Bullish", 0) == 1:
                score += 2
                reasons.append("Supertrend Bullish")
            else:
                score -= 2
                reasons.append("Supertrend Bearish")

        # VWAP
        if "Above_VWAP" in self.df.columns:
            if latest.get("Above_VWAP", 0) == 1:
                score += 1
                reasons.append("Above VWAP")
            else:
                score -= 1
                reasons.append("Below VWAP")

        # ORB
        if "ORB_Breakout_Up" in self.df.columns:
            if latest.get("ORB_Breakout_Up", 0) == 1:
                score += 2
                reasons.append("ORB Bullish Breakout")
            elif latest.get("ORB_Breakout_Down", 0) == 1:
                score -= 2
                reasons.append("ORB Bearish Breakdown")

        if score >= 4:
            signal = "🟢 BUY CALL"
        elif score <= -4:
            signal = "🔴 BUY PUT"
        else:
            signal = "🟡 NO TRADE"

        return {
            "signal" : signal,
            "score"  : score,
            "reasons": reasons,
            "rsi"    : latest.get("RSI", 0),
            "macd"   : latest.get("MACD", 0),
        }

    # ============================================
    # ADD ALL — Ek baar mein sab lagao
    # ============================================
    def add_all(self):
        print("⚙️ Indicators calculating...")

        self.add_rsi()
        self.add_macd()
        self.add_bollinger()
        self.add_ema()
        self.add_sma()
        self.add_atr()
        self.add_stochastic()
        self.add_vwap()
        self.add_supertrend()
        self.add_orb()
        self.add_session_features()
        self.add_volume_features()
        self.add_price_features()
        self.add_candle_patterns()
        self.add_support_resistance()

        total = len(self.df.columns)
        print(f"✅ {total} features ready!")
        return self.df