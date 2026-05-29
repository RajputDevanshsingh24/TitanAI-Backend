# ============================================
# TITAN-AI TRADER — Indicators Engine
# TITAN-SURYA TECHNOLOGIES
# ============================================

import pandas as pd
import numpy as np

class Indicators:

    def __init__(self, df):
        self.df = df.copy()

    def add_rsi(self, period=14):
        delta  = self.df["Close"].diff()
        gain   = delta.clip(lower=0)
        loss   = -delta.clip(upper=0)
        avg_g  = gain.ewm(com=period-1, min_periods=period).mean()
        avg_l  = loss.ewm(com=period-1, min_periods=period).mean()
        rs     = avg_g / avg_l
        self.df["RSI"] = 100 - (100 / (1 + rs))
        return self

    def add_macd(self, fast=12, slow=26, signal=9):
        ema_fast             = self.df["Close"].ewm(span=fast).mean()
        ema_slow             = self.df["Close"].ewm(span=slow).mean()
        self.df["MACD"]      = ema_fast - ema_slow
        self.df["MACD_Sig"]  = self.df["MACD"].ewm(span=signal).mean()
        self.df["MACD_Hist"] = self.df["MACD"] - self.df["MACD_Sig"]
        return self

    def add_bollinger(self, period=20, std=2):
        sma                    = self.df["Close"].rolling(period).mean()
        std_dev                = self.df["Close"].rolling(period).std()
        self.df["BB_Upper"]    = sma + (std_dev * std)
        self.df["BB_Lower"]    = sma - (std_dev * std)
        self.df["BB_Middle"]   = sma
        self.df["BB_Width"]    = self.df["BB_Upper"] - self.df["BB_Lower"]
        self.df["BB_Position"] = (
            (self.df["Close"] - self.df["BB_Lower"]) /
            self.df["BB_Width"]
        )
        return self

    def add_ema(self, periods=[9, 20, 50, 200]):
        for p in periods:
            self.df[f"EMA_{p}"] = self.df["Close"].ewm(span=p).mean()
        return self

    def add_sma(self, periods=[20, 50]):
        for p in periods:
            self.df[f"SMA_{p}"] = self.df["Close"].rolling(p).mean()
        return self

    def add_atr(self, period=14):
        high  = self.df["High"]
        low   = self.df["Low"]
        close = self.df["Close"].shift(1)
        tr    = pd.concat([
            high - low,
            (high - close).abs(),
            (low  - close).abs()
        ], axis=1).max(axis=1)
        self.df["ATR"] = tr.rolling(period).mean()
        return self

    def add_stochastic(self, period=14):
        low_min            = self.df["Low"].rolling(period).min()
        high_max           = self.df["High"].rolling(period).max()
        self.df["STOCH_K"] = (
            100 * (self.df["Close"] - low_min) /
            (high_max - low_min)
        )
        self.df["STOCH_D"] = self.df["STOCH_K"].rolling(3).mean()
        return self

    def add_vwap(self):
        typical = (self.df["High"] + self.df["Low"] + self.df["Close"]) / 3
        self.df["VWAP"] = (
            (typical * self.df["Volume"]).cumsum() /
            self.df["Volume"].cumsum()
        )
        return self

    def add_support_resistance(self, period=20):
        self.df["Support"]    = self.df["Low"].rolling(period).min()
        self.df["Resistance"] = self.df["High"].rolling(period).max()
        return self

    def add_candle_patterns(self):
        op = self.df["Open"]
        hi = self.df["High"]
        lo = self.df["Low"]
        cl = self.df["Close"]

        body   = (cl - op).abs()
        candle = hi - lo

        self.df["Doji"]     = (body <= candle * 0.1).astype(int)
        self.df["Bullish"]  = (cl > op).astype(int)
        self.df["Bearish"]  = (cl < op).astype(int)

        lower_wick        = op.where(cl > op, cl) - lo
        self.df["Hammer"] = (
            (lower_wick >= body * 2) & (cl > op)
        ).astype(int)

        upper_wick               = hi - cl.where(cl > op, op)
        self.df["ShootingStar"]  = (
            (upper_wick >= body * 2) & (cl < op)
        ).astype(int)

        return self

    def add_price_change(self):
        self.df["Change_1d"]  = self.df["Close"].pct_change(1)  * 100
        self.df["Change_5d"]  = self.df["Close"].pct_change(5)  * 100
        self.df["Change_20d"] = self.df["Close"].pct_change(20) * 100
        return self

    def get_signal(self):
        latest  = self.df.iloc[-1]
        score   = 0
        reasons = []

        if "RSI" in self.df.columns:
            if latest["RSI"] < 35:
                score += 2
                reasons.append(f"RSI Oversold: {latest['RSI']:.1f}")
            elif latest["RSI"] > 65:
                score -= 2
                reasons.append(f"RSI Overbought: {latest['RSI']:.1f}")

        if "MACD" in self.df.columns:
            if latest["MACD"] > latest["MACD_Sig"]:
                score += 2
                reasons.append("MACD Bullish Crossover")
            else:
                score -= 2
                reasons.append("MACD Bearish Crossover")

        if "BB_Position" in self.df.columns:
            if latest["BB_Position"] < 0.2:
                score += 1
                reasons.append("Price near Lower BB")
            elif latest["BB_Position"] > 0.8:
                score -= 1
                reasons.append("Price near Upper BB")

        if "EMA_20" in self.df.columns and "EMA_50" in self.df.columns:
            if latest["EMA_20"] > latest["EMA_50"]:
                score += 1
                reasons.append("EMA Bullish Trend")
            else:
                score -= 1
                reasons.append("EMA Bearish Trend")

        if score >= 3:
            signal = "🟢 BUY CALL"
        elif score <= -3:
            signal = "🔴 BUY PUT"
        else:
            signal = "🟡 NO TRADE"

        return {
            "signal"  : signal,
            "score"   : score,
            "reasons" : reasons,
            "rsi"     : latest.get("RSI", 0),
            "macd"    : latest.get("MACD", 0),
        }

    def add_all(self):
        print("⚙️ Indicators calculating...")
        self.add_rsi()
        self.add_macd()
        self.add_bollinger()
        self.add_ema()
        self.add_sma()
        self.add_atr()
        self.add_stochastic()
        self.add_support_resistance()
        self.add_candle_patterns()
        self.add_price_change()
        print(f"✅ {len(self.df.columns)} columns ready!")
        return self.df