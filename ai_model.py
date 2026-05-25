# ============================================
# TITAN-AI TRADER — AI Model FINAL
# TITAN-SURYA TECHNOLOGIES
# ============================================

import pandas as pd
import numpy as np
import pickle
import os
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import xgboost as xgb
import warnings
warnings.filterwarnings("ignore")


class AIModel:

    def __init__(self):
        self.rf_model     = None
        self.xgb_model    = None
        self.scaler       = StandardScaler()
        self.is_trained   = False
        self.accuracy     = 0.0
        self.model_path   = "models/"
        self.feature_cols = []
        os.makedirs(self.model_path, exist_ok=True)

    # ============================================
    # FEATURES
    # ============================================
    def _get_features(self, df):
        from indicators import Indicators

        data = df.copy()
        ind  = Indicators(data)
        data = ind.add_all()

        # Extra features
        data["Price_Change"]  = data["Close"].pct_change()
        data["HL_Ratio"]      = (
            (data["High"] - data["Low"]) /
            data["Close"].clip(lower=0.01)
        )
        data["CO_Ratio"]      = (
            (data["Close"] - data["Open"]) /
            data["Open"].clip(lower=0.01)
        )
        data["Roll_Mean_5"]   = data["Close"].rolling(5).mean()
        data["Roll_Std_5"]    = data["Close"].rolling(5).std()
        data["Roll_Mean_10"]  = data["Close"].rolling(10).mean()
        data["Roll_Std_10"]   = data["Close"].rolling(10).std()
        data["Mom_5"]         = data["Close"] - data["Close"].shift(5)
        data["Mom_10"]        = data["Close"] - data["Close"].shift(10)
        data["Vol_Change"]    = data["Volume"].pct_change()

        cols = [
            "RSI", "MACD", "MACD_Sig", "MACD_Hist",
            "BB_Position", "BB_Width",
            "EMA_9", "EMA_20", "EMA_50",
            "ATR", "STOCH_K", "STOCH_D",
            "Change_1d", "Change_5d", "Change_20d",
            "Bullish", "Bearish", "Doji",
            "Hammer", "ShootingStar",
            "Price_Change", "HL_Ratio", "CO_Ratio",
            "Roll_Mean_5", "Roll_Std_5",
            "Roll_Mean_10", "Roll_Std_10",
            "Mom_5", "Mom_10", "Vol_Change",
        ]

        available = [c for c in cols if c in data.columns]
        data      = data.dropna().iloc[:-1]

        X = data[available].copy()
        X = X.replace([np.inf, -np.inf], np.nan).fillna(0)

        return X, available

    # ============================================
    # LABELS
    # ============================================
    def _get_labels(self, df):
        data             = df.copy()
        data["Next"]     = data["Close"].shift(-1)
        data["Return"]   = (data["Next"] - data["Close"]) / data["Close"]
        data             = data.dropna().iloc[:-1]
        labels           = (data["Return"] > 0).astype(int)
        return labels

    # ============================================
    # TRAIN
    # ============================================
    def train(self, df):
        print("\n" + "="*50)
        print("🤖 AI MODEL TRAINING SHURU!")
        print(f"   Data: {len(df)} rows")
        print("="*50)

        try:
            X, self.feature_cols = self._get_features(df)
            y                    = self._get_labels(df)

            # Align lengths
            min_len = min(len(X), len(y))
            X       = X.iloc[:min_len]
            y       = y.iloc[:min_len]

            print(f"\n✅ Samples: {len(X)}")
            print(f"   UP:   {y.sum()} ({y.mean()*100:.1f}%)")
            print(f"   DOWN: {(y==0).sum()} ({(1-y.mean())*100:.1f}%)")

            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, shuffle=False
            )

            X_tr = self.scaler.fit_transform(X_train)
            X_te = self.scaler.transform(X_test)

            # ---- RANDOM FOREST ----
            print("\n🌲 Random Forest...")
            self.rf_model = RandomForestClassifier(
                n_estimators      = 300,
                max_depth         = 10,
                min_samples_split = 10,
                min_samples_leaf  = 5,
                max_features      = 'sqrt',
                class_weight      = 'balanced',
                random_state      = 42,
                n_jobs            = -1
            )
            self.rf_model.fit(X_tr, y_train)
            rf_pred = self.rf_model.predict(X_te)
            rf_acc  = accuracy_score(y_test, rf_pred) * 100
            print(f"✅ RF: {rf_acc:.2f}%")

            # ---- XGBOOST ----
            print("\n⚡ XGBoost...")
            self.xgb_model = xgb.XGBClassifier(
                n_estimators     = 300,
                max_depth        = 6,
                learning_rate    = 0.05,
                subsample        = 0.8,
                colsample_bytree = 0.8,
                min_child_weight = 5,
                random_state     = 42,
                eval_metric      = "logloss",
                verbosity        = 0
            )
            self.xgb_model.fit(
                X_tr, y_train,
                eval_set        = [(X_te, y_test)],
                verbose         = False
            )
            xgb_pred = self.xgb_model.predict(X_te)
            xgb_acc  = accuracy_score(y_test, xgb_pred) * 100
            print(f"✅ XGB: {xgb_acc:.2f}%")

            # ---- ENSEMBLE ----
            ens_pred = []
            for i in range(len(rf_pred)):
                votes = [int(rf_pred[i]), int(xgb_pred[i])]
                ens_pred.append(
                    1 if votes.count(1) > votes.count(0) else 0
                )

            ens_acc = accuracy_score(y_test, ens_pred) * 100

            print(f"\n{'='*50}")
            print(f"📊 RESULTS:")
            print(f"   RF:       {rf_acc:.2f}%")
            print(f"   XGBoost:  {xgb_acc:.2f}%")
            print(f"   Ensemble: {ens_acc:.2f}%")
            print(f"{'='*50}")

            self.accuracy   = ens_acc
            self.is_trained = True
            self._save()
            return ens_acc

        except Exception as e:
            print(f"❌ Training Error: {e}")
            import traceback
            traceback.print_exc()
            return 0.0

    # ============================================
    # PREDICT
    # ============================================
    def predict(self, df):
        try:
            if not self.is_trained:
                if not self._load():
                    return None

            X, _ = self._get_features(df)

            # Available features only
            available = [c for c in self.feature_cols
                        if c in X.columns]
            if not available:
                print("❌ Features mismatch!")
                return None

            row = X[available].iloc[-1].copy()
            row = row.fillna(0).replace(
                [np.inf, -np.inf], 0
            )

            X_pred = self.scaler.transform(
                row.values.reshape(1, -1)
            )

            rf_pred  = int(self.rf_model.predict(X_pred)[0])
            rf_prob  = self.rf_model.predict_proba(X_pred)[0]
            rf_conf  = float(max(rf_prob) * 100)

            xgb_pred = int(self.xgb_model.predict(X_pred)[0])
            xgb_prob = self.xgb_model.predict_proba(X_pred)[0]
            xgb_conf = float(max(xgb_prob) * 100)

            # Ensemble
            signal   = 1 if (rf_pred + xgb_pred) >= 1 else 0
            avg_conf = (rf_conf + xgb_conf) / 2

            signal_text = (
                "🟢 BUY CALL" if signal == 1
                else "🔴 BUY PUT"
            )

            print(f"🎯 {signal_text} | "
                  f"Conf: {avg_conf:.1f}% | "
                  f"RF:{rf_pred} XGB:{xgb_pred}")

            return {
                "signal"     : signal_text,
                "value"      : signal,
                "confidence" : avg_conf,
                "rf_signal"  : rf_pred,
                "xgb_signal" : xgb_pred,
                "rf_conf"    : rf_conf,
                "xgb_conf"   : xgb_conf,
                "timestamp"  : datetime.now().strftime(
                               "%Y-%m-%d %H:%M:%S")
            }

        except Exception as e:
            print(f"❌ Predict Error: {e}")
            import traceback
            traceback.print_exc()
            return None

    # ============================================
    # SAVE / LOAD
    # ============================================
    def _save(self):
        try:
            p = self.model_path
            pickle.dump(self.rf_model,
                open(f"{p}rf_model.pkl",   "wb"))
            pickle.dump(self.xgb_model,
                open(f"{p}xgb_model.pkl",  "wb"))
            pickle.dump(self.scaler,
                open(f"{p}scaler.pkl",     "wb"))
            pickle.dump(self.feature_cols,
                open(f"{p}features.pkl",   "wb"))
            with open(f"{p}accuracy.txt", "w") as f:
                f.write(str(self.accuracy))
            print(f"💾 Model saved! ({self.accuracy:.2f}%)")
        except Exception as e:
            print(f"❌ Save Error: {e}")

    def _load(self):
        try:
            p = self.model_path
            self.rf_model = pickle.load(
                open(f"{p}rf_model.pkl",  "rb"))
            self.xgb_model = pickle.load(
                open(f"{p}xgb_model.pkl", "rb"))
            self.scaler = pickle.load(
                open(f"{p}scaler.pkl",    "rb"))
            self.feature_cols = pickle.load(
                open(f"{p}features.pkl",  "rb"))
            with open(f"{p}accuracy.txt", "r") as f:
                self.accuracy = float(f.read())
            self.is_trained = True
            print(f"✅ Model loaded! ({self.accuracy:.2f}%)")
            return True
        except Exception as e:
            print(f"⚠️ Load failed: {e}")
            return False

    # Backward compatibility
    def save_model(self): self._save()
    def load_model(self): return self._load()

    # ============================================
    # BACKTEST
    # ============================================
    def backtest(self, df):
        try:
            print("\n📊 BACKTESTING...")
            X, _  = self._get_features(df)
            y     = self._get_labels(df)
            min_l = min(len(X), len(y))
            X, y  = X.iloc[:min_l], y.iloc[:min_l]

            X_sc  = self.scaler.transform(X)
            preds = self.rf_model.predict(X_sc)

            capital = 50000
            start   = capital
            wins    = 0
            losses  = 0
            closes  = df["Close"].values

            for i in range(min(len(preds)-1, len(closes)-2)):
                sig    = int(preds[i])
                change = (closes[i+1] - closes[i]) / closes[i]
                profit = capital * 0.02 * (
                    change if sig == 1 else -change
                ) * 10
                capital += profit
                if profit > 0: wins += 1
                else: losses += 1

            total    = wins + losses
            win_rate = wins/total*100 if total > 0 else 0

            print(f"   Capital: ₹{start:,.0f} → ₹{capital:,.0f}")
            print(f"   Profit:  ₹{capital-start:,.0f}")
            print(f"   Win Rate: {win_rate:.1f}%")
            return {"capital": capital, "win_rate": win_rate}

        except Exception as e:
            print(f"❌ Backtest Error: {e}")
            return None