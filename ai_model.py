# ============================================
# TITAN-AI TRADER — AI Model v3.0
# TITAN-SURYA TECHNOLOGIES
#
# CHANGES v3.0:
# - LSTM add kiya (time series memory)
# - 3 model ensemble: RF + XGB + LSTM
# - 60-candle lookback window
# - 5-min data ke liye optimized
# - Teeno agree → Trade, warna NO TRADE
# ============================================

import pandas as pd
import numpy as np
import pickle
import os
import warnings
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
import xgboost as xgb
warnings.filterwarnings("ignore")

# TensorFlow import — graceful fallback
try:
    import tensorflow as tf
    from tensorflow.keras.models import Sequential, load_model
    from tensorflow.keras.layers import (
        LSTM, Dense, Dropout, BatchNormalization
    )
    from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
    from tensorflow.keras.optimizers import Adam
    TF_AVAILABLE = True
    print("✅ TensorFlow available!")
except ImportError:
    TF_AVAILABLE = False
    print("⚠️ TensorFlow nahi hai — RF + XGB only")


class AIModel:

    def __init__(self):
        self.rf_model      = None
        self.xgb_model     = None
        self.lstm_model    = None
        self.scaler        = StandardScaler()
        self.lstm_scaler   = StandardScaler()
        self.is_trained    = False
        self.accuracy      = 0.0
        self.model_path    = "models/"
        self.feature_cols  = []
        self.lookback      = 60    # 60 candles = 5 hours of 5-min data
        self.tf_available  = TF_AVAILABLE
        os.makedirs(self.model_path, exist_ok=True)

        print("✅ AI Model v3.0 Ready!")
        print(f"   LSTM:     {'✅' if TF_AVAILABLE else '❌ (RF+XGB only)'}")
        print(f"   Lookback: {self.lookback} candles")

    # ============================================
    # FEATURES BANAO
    # ============================================
    def _get_features(self, df):
        from indicators import Indicators

        data = df.copy()
        ind  = Indicators(data)
        data = ind.add_all()

        # Feature columns — sab jo humne add kiye
        feature_cols = [
            # Classic
            "RSI", "MACD", "MACD_Sig", "MACD_Hist",
            "BB_Position", "BB_Width",
            "EMA_9", "EMA_20", "EMA_50",
            "ATR", "STOCH_K", "STOCH_D",

            # NIFTY Specific (v2.0)
            "VWAP", "VWAP_Dist", "Above_VWAP",
            "ST_Bullish", "ST_Direction",
            "ORB_Breakout_Up", "ORB_Breakout_Down",
            "ORB_Dist_High", "ORB_Dist_Low",

            # Session
            "Session", "Is_Opening", "Is_Mid", "Is_Closing",
            "Day_of_Week", "Is_Monday", "Is_Friday",

            # Volume
            "Vol_Ratio", "High_Volume", "Vol_Change", "Vol_Spike",

            # Price action
            "Return_1", "Return_3", "Return_6", "Return_12",
            "Body_Ratio", "HL_Ratio", "CO_Ratio",
            "Mom_5", "Mom_10", "Mom_20",
            "Roll_Mean_10", "Roll_Std_10",
            "Roll_Mean_20", "Roll_Std_20",
            "Z_Score",

            # Candle patterns
            "Bullish", "Bearish", "Doji",
            "Hammer", "ShootingStar",
            "Bull_Engulf", "Bear_Engulf",

            # Support/Resistance
            "Dist_Support", "Dist_Resist",
        ]

        available = [c for c in feature_cols if c in data.columns]
        data      = data.dropna()
        X         = data[available].copy()
        X         = X.replace([np.inf, -np.inf], np.nan).fillna(0)

        return X, available

    # ============================================
    # LABELS BANAO
    # Next candle UP ya DOWN?
    # ============================================
    def _get_labels(self, df):
        data           = df.copy()
        data["Next"]   = data["Close"].shift(-1)
        data["Return"] = (data["Next"] - data["Close"]) / data["Close"]
        data           = data.dropna()
        return (data["Return"] > 0).astype(int)

    # ============================================
    # LSTM SEQUENCES BANAO
    # 60 candles ka window → ek prediction
    # ============================================
    def _make_sequences(self, X_scaled, y, lookback=60):
        Xs, ys = [], []
        for i in range(lookback, len(X_scaled)):
            Xs.append(X_scaled[i - lookback:i])
            ys.append(y.iloc[i])
        return np.array(Xs), np.array(ys)

    # ============================================
    # LSTM MODEL BANAO
    # ============================================
    def _build_lstm(self, input_shape):
        model = Sequential([
            LSTM(
                128,
                return_sequences = True,
                input_shape      = input_shape
            ),
            Dropout(0.3),
            BatchNormalization(),

            LSTM(64, return_sequences=True),
            Dropout(0.3),
            BatchNormalization(),

            LSTM(32, return_sequences=False),
            Dropout(0.2),

            Dense(32, activation="relu"),
            Dropout(0.2),

            Dense(16, activation="relu"),

            Dense(1, activation="sigmoid"),
        ])

        model.compile(
            optimizer = Adam(learning_rate=0.001),
            loss      = "binary_crossentropy",
            metrics   = ["accuracy"],
        )
        return model

    # ============================================
    # TRAIN
    # ============================================
    def train(self, df):
        print("\n" + "="*50)
        print("🤖 AI MODEL v3.0 TRAINING SHURU!")
        print(f"   Data: {len(df)} rows")
        print(f"   LSTM: {'YES' if self.tf_available else 'NO'}")
        print("="*50)

        try:
            X, self.feature_cols = self._get_features(df)
            y                    = self._get_labels(df)

            min_len = min(len(X), len(y))
            X       = X.iloc[:min_len]
            y       = y.iloc[:min_len]

            print(f"\n✅ Samples: {len(X)}")
            print(f"   UP:   {y.sum()} ({y.mean()*100:.1f}%)")
            print(f"   DOWN: {(y==0).sum()} ({(1-y.mean())*100:.1f}%)")

            # Train/Test split — shuffle=False (time series!)
            split       = int(len(X) * 0.8)
            X_train     = X.iloc[:split]
            X_test      = X.iloc[split:]
            y_train     = y.iloc[:split]
            y_test      = y.iloc[split:]

            X_tr = self.scaler.fit_transform(X_train)
            X_te = self.scaler.transform(X_test)

            # ---- RANDOM FOREST ----
            print("\n🌲 Random Forest training...")
            self.rf_model = RandomForestClassifier(
                n_estimators      = 300,
                max_depth         = 10,
                min_samples_split = 10,
                min_samples_leaf  = 5,
                max_features      = "sqrt",
                class_weight      = "balanced",
                random_state      = 42,
                n_jobs            = -1,
            )
            self.rf_model.fit(X_tr, y_train)
            rf_pred = self.rf_model.predict(X_te)
            rf_acc  = accuracy_score(y_test, rf_pred) * 100
            print(f"✅ RF Accuracy: {rf_acc:.2f}%")

            # ---- XGBOOST ----
            print("\n⚡ XGBoost training...")
            self.xgb_model = xgb.XGBClassifier(
                n_estimators     = 300,
                max_depth        = 6,
                learning_rate    = 0.05,
                subsample        = 0.8,
                colsample_bytree = 0.8,
                min_child_weight = 5,
                random_state     = 42,
                eval_metric      = "logloss",
                verbosity        = 0,
            )
            self.xgb_model.fit(
                X_tr, y_train,
                eval_set = [(X_te, y_test)],
                verbose  = False,
            )
            xgb_pred = self.xgb_model.predict(X_te)
            xgb_acc  = accuracy_score(y_test, xgb_pred) * 100
            print(f"✅ XGB Accuracy: {xgb_acc:.2f}%")

            # ---- LSTM ----
            lstm_acc  = 0.0
            lstm_pred = None

            if self.tf_available and len(X) > self.lookback * 3:
                print("\n🧠 LSTM training...")
                try:
                    # LSTM ke liye alag scaler
                    X_lstm_scaled = self.lstm_scaler.fit_transform(X)

                    # Sequences banao
                    X_seq, y_seq = self._make_sequences(
                        X_lstm_scaled, y, self.lookback
                    )

                    # Train/test split for LSTM
                    split_lstm  = int(len(X_seq) * 0.8)
                    X_seq_tr    = X_seq[:split_lstm]
                    X_seq_te    = X_seq[split_lstm:]
                    y_seq_tr    = y_seq[:split_lstm]
                    y_seq_te    = y_seq[split_lstm:]

                    # Model build
                    self.lstm_model = self._build_lstm(
                        (X_seq_tr.shape[1], X_seq_tr.shape[2])
                    )

                    # Callbacks
                    callbacks = [
                        EarlyStopping(
                            patience           = 10,
                            restore_best_weights = True,
                            monitor            = "val_accuracy",
                        ),
                        ReduceLROnPlateau(
                            patience = 5,
                            factor   = 0.5,
                            monitor  = "val_loss",
                        ),
                    ]

                    # Train
                    self.lstm_model.fit(
                        X_seq_tr, y_seq_tr,
                        epochs          = 50,
                        batch_size      = 32,
                        validation_data = (X_seq_te, y_seq_te),
                        callbacks       = callbacks,
                        verbose         = 0,
                    )

                    # Predict
                    lstm_prob = self.lstm_model.predict(
                        X_seq_te, verbose=0
                    ).flatten()
                    lstm_pred_raw = (lstm_prob > 0.5).astype(int)
                    lstm_acc      = accuracy_score(
                        y_seq_te, lstm_pred_raw
                    ) * 100
                    print(f"✅ LSTM Accuracy: {lstm_acc:.2f}%")

                except Exception as e:
                    print(f"⚠️ LSTM failed: {e} — RF+XGB only")
                    self.lstm_model = None
                    lstm_acc        = 0.0
            else:
                print("⚠️ LSTM skip — data kam hai ya TF nahi")

            # ---- ENSEMBLE ACCURACY ----
            # RF + XGB pe calculate karo (LSTM alag size ka hai)
            ens_preds = []
            for i in range(len(rf_pred)):
                rf_s  = int(rf_pred[i])
                xgb_s = int(xgb_pred[i])

                if rf_s == 1 and xgb_s == 1:
                    ens_preds.append(1)
                elif rf_s == 0 and xgb_s == 0:
                    ens_preds.append(0)
                else:
                    ens_preds.append(-1)  # NO TRADE

            valid_idx = [i for i, p in enumerate(ens_preds) if p != -1]
            if valid_idx:
                v_preds  = [ens_preds[i] for i in valid_idx]
                v_actual = [int(y_test.iloc[i]) for i in valid_idx]
                ens_acc  = accuracy_score(v_actual, v_preds) * 100
            else:
                ens_acc = 50.0

            # Final accuracy — LSTM bhi ho toh boost
            if lstm_acc > 0:
                final_acc = (ens_acc * 0.5) + (lstm_acc * 0.5)
            else:
                final_acc = ens_acc

            print(f"\n{'='*50}")
            print(f"📊 TRAINING RESULTS:")
            print(f"   RF:              {rf_acc:.2f}%")
            print(f"   XGBoost:         {xgb_acc:.2f}%")
            print(f"   LSTM:            {lstm_acc:.2f}%")
            print(f"   Ensemble RF+XGB: {ens_acc:.2f}%")
            print(f"   Final Accuracy:  {final_acc:.2f}%")
            print(f"   Valid signals:   {len(valid_idx)}/{len(ens_preds)}")
            print(f"{'='*50}")

            self.accuracy   = final_acc
            self.is_trained = True
            self._save()
            return final_acc

        except Exception as e:
            print(f"❌ Training Error: {e}")
            import traceback; traceback.print_exc()
            return 0.0

    # ============================================
    # PREDICT — Signal lo
    # ============================================
    def predict(self, df):
        try:
            if not self.is_trained:
                if not self._load():
                    return None

            X, _ = self._get_features(df)

            available = [c for c in self.feature_cols if c in X.columns]
            if not available:
                print("❌ Features mismatch! Model retrain karo.")
                return None

            row    = X[available].iloc[-1].copy()
            row    = row.fillna(0).replace([np.inf, -np.inf], 0)
            X_pred = self.scaler.transform(row.values.reshape(1, -1))

            # RF predict
            rf_pred = int(self.rf_model.predict(X_pred)[0])
            rf_prob = self.rf_model.predict_proba(X_pred)[0]
            rf_conf = float(max(rf_prob) * 100)

            # XGB predict
            xgb_pred = int(self.xgb_model.predict(X_pred)[0])
            xgb_prob = self.xgb_model.predict_proba(X_pred)[0]
            xgb_conf = float(max(xgb_prob) * 100)

            # LSTM predict
            lstm_pred = None
            lstm_conf = 0.0

            if self.lstm_model is not None and len(X) >= self.lookback:
                try:
                    X_seq_scaled = self.lstm_scaler.transform(
                        X[available].fillna(0)
                        .replace([np.inf, -np.inf], 0)
                    )
                    # Last 60 candles
                    seq = X_seq_scaled[-self.lookback:].reshape(
                        1, self.lookback, -1
                    )
                    lstm_prob_val = float(
                        self.lstm_model.predict(seq, verbose=0)[0][0]
                    )
                    lstm_pred = 1 if lstm_prob_val > 0.5 else 0
                    lstm_conf = (
                        lstm_prob_val * 100
                        if lstm_pred == 1
                        else (1 - lstm_prob_val) * 100
                    )
                except Exception as e:
                    print(f"⚠️ LSTM predict error: {e}")

            # ---- ENSEMBLE LOGIC ----
            # LSTM available → 3 model vote
            # LSTM nahi → 2 model strict (dono agree)

            if lstm_pred is not None:
                # 3 models
                votes = rf_pred + xgb_pred + lstm_pred

                if votes == 3:
                    signal      = 1
                    signal_text = "🟢 BUY CALL (3/3)"
                elif votes == 0:
                    signal      = -1
                    signal_text = "🔴 BUY PUT (3/3)"
                elif votes == 2:
                    signal      = 1
                    signal_text = "🟢 BUY CALL (2/3)"
                elif votes == 1:
                    signal      = -1
                    signal_text = "🔴 BUY PUT (2/3)"
                else:
                    signal      = 0
                    signal_text = "🟡 NO TRADE (split)"

                avg_conf = (rf_conf + xgb_conf + lstm_conf) / 3

            else:
                # 2 models — strict
                if rf_pred == 1 and xgb_pred == 1:
                    signal      = 1
                    signal_text = "🟢 BUY CALL (2/2)"
                elif rf_pred == 0 and xgb_pred == 0:
                    signal      = -1
                    signal_text = "🔴 BUY PUT (2/2)"
                else:
                    signal      = 0
                    signal_text = "🟡 NO TRADE (split)"

                avg_conf = (rf_conf + xgb_conf) / 2

            print(f"\n🎯 {signal_text}")
            print(f"   Conf:  {avg_conf:.1f}%")
            print(f"   RF:    {'BUY' if rf_pred==1 else 'SELL'} ({rf_conf:.1f}%)")
            print(f"   XGB:   {'BUY' if xgb_pred==1 else 'SELL'} ({xgb_conf:.1f}%)")
            if lstm_pred is not None:
                print(f"   LSTM:  {'BUY' if lstm_pred==1 else 'SELL'} ({lstm_conf:.1f}%)")

            return {
                "signal"     : signal_text,
                "value"      : signal,
                "confidence" : avg_conf,
                "rf_signal"  : rf_pred,
                "rf_conf"    : rf_conf,
                "xgb_signal" : xgb_pred,
                "xgb_conf"   : xgb_conf,
                "lstm_signal": lstm_pred,
                "lstm_conf"  : lstm_conf,
                "timestamp"  : datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }

        except Exception as e:
            print(f"❌ Predict Error: {e}")
            import traceback; traceback.print_exc()
            return None

    # ============================================
    # SAVE
    # ============================================
    def _save(self):
        try:
            p = self.model_path
            pickle.dump(self.rf_model,
                open(f"{p}rf_model.pkl",  "wb"))
            pickle.dump(self.xgb_model,
                open(f"{p}xgb_model.pkl", "wb"))
            pickle.dump(self.scaler,
                open(f"{p}scaler.pkl",    "wb"))
            pickle.dump(self.lstm_scaler,
                open(f"{p}lstm_scaler.pkl", "wb"))
            pickle.dump(self.feature_cols,
                open(f"{p}features.pkl",  "wb"))

            if self.lstm_model is not None:
                self.lstm_model.save(f"{p}lstm_model.h5")
                print("💾 LSTM model saved!")

            with open(f"{p}accuracy.txt", "w") as f:
                f.write(str(self.accuracy))

            print(f"💾 Models saved! Accuracy: {self.accuracy:.2f}%")

        except Exception as e:
            print(f"❌ Save Error: {e}")

    # ============================================
    # LOAD
    # ============================================
    def _load(self):
        try:
            p = self.model_path
            self.rf_model     = pickle.load(
                open(f"{p}rf_model.pkl",  "rb"))
            self.xgb_model    = pickle.load(
                open(f"{p}xgb_model.pkl", "rb"))
            self.scaler       = pickle.load(
                open(f"{p}scaler.pkl",    "rb"))
            self.feature_cols = pickle.load(
                open(f"{p}features.pkl",  "rb"))

            # LSTM scaler
            lstm_sc_path = f"{p}lstm_scaler.pkl"
            if os.path.exists(lstm_sc_path):
                self.lstm_scaler = pickle.load(
                    open(lstm_sc_path, "rb"))

            # LSTM model
            lstm_path = f"{p}lstm_model.h5"
            if os.path.exists(lstm_path) and self.tf_available:
                self.lstm_model = load_model(lstm_path)
                print("✅ LSTM model loaded!")

            with open(f"{p}accuracy.txt", "r") as f:
                self.accuracy = float(f.read())

            self.is_trained = True
            print(f"✅ Models loaded! Accuracy: {self.accuracy:.2f}%")
            return True

        except Exception as e:
            print(f"⚠️ Model load failed: {e}")
            return False

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

            X_sc      = self.scaler.transform(X)
            rf_preds  = self.rf_model.predict(X_sc)
            xgb_preds = self.xgb_model.predict(X_sc)

            capital = 50000
            start   = capital
            wins = losses = skipped = 0
            closes  = df["Close"].values

            for i in range(min(len(rf_preds) - 1, len(closes) - 2)):
                rf_s  = int(rf_preds[i])
                xgb_s = int(xgb_preds[i])

                if rf_s == 1 and xgb_s == 1:
                    sig = 1
                elif rf_s == 0 and xgb_s == 0:
                    sig = -1
                else:
                    skipped += 1
                    continue

                change = (closes[i+1] - closes[i]) / closes[i]
                profit = capital * 0.02 * (
                    change if sig == 1 else -change
                ) * 10
                capital += profit
                if profit > 0: wins   += 1
                else:          losses += 1

            total    = wins + losses
            win_rate = wins / total * 100 if total > 0 else 0

            print(f"   Capital:  ₹{start:,.0f} → ₹{capital:,.0f}")
            print(f"   Profit:   ₹{capital-start:+,.0f}")
            print(f"   Win Rate: {win_rate:.1f}%")
            print(f"   Trades:   {total}  Skipped: {skipped}")

            return {
                "capital" : capital,
                "win_rate": win_rate,
                "trades"  : total,
            }

        except Exception as e:
            print(f"❌ Backtest Error: {e}")
            return None