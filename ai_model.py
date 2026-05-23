# ============================================
# TITAN-AI TRADER — AI Model UPGRADED v2.0
# TITAN-SURYA TECHNOLOGIES
# ============================================

import pandas as pd
import numpy as np
import pickle
import os
from datetime import datetime
from sklearn.ensemble import (
    RandomForestClassifier,
    GradientBoostingClassifier,
    VotingClassifier
)
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
from sklearn.utils.class_weight import compute_class_weight
import xgboost as xgb
import warnings
warnings.filterwarnings("ignore")


class AIModel:

    def __init__(self):
        self.rf_model    = None
        self.xgb_model   = None
        self.gb_model    = None
        self.scaler      = StandardScaler()
        self.is_trained  = False
        self.accuracy    = 0
        self.model_path  = "models/"
        self.feature_cols = []
        os.makedirs(self.model_path, exist_ok=True)

    # ============================================
    # FEATURES PREPARE KARO
    # ============================================
    def prepare_features(self, df):
        from indicators import Indicators

        print("⚙️ Features prepare ho rahe hain...")

        ind = Indicators(df.copy())
        df  = ind.add_all()

        # Labels banana
        df["Future_Close"] = df["Close"].shift(-1)
        df["Return"]       = (
            (df["Future_Close"] - df["Close"]) /
            df["Close"] * 100
        )

        # 0.3% threshold
        df["Label"] = 0
        df.loc[df["Return"] > 0, "Label"] = 1  # UP

        # Extra features add karo
        df["Price_Change"]  = df["Close"].pct_change()
        df["High_Low_Ratio"] = (df["High"] - df["Low"]) / df["Close"]
        df["Close_Open_Ratio"] = (df["Close"] - df["Open"]) / df["Open"]

        # Rolling features
        df["Rolling_Mean_5"]  = df["Close"].rolling(5).mean()
        df["Rolling_Std_5"]   = df["Close"].rolling(5).std()
        df["Rolling_Mean_10"] = df["Close"].rolling(10).mean()
        df["Rolling_Std_10"]  = df["Close"].rolling(10).std()

        # Momentum
        df["Momentum_5"]  = df["Close"] - df["Close"].shift(5)
        df["Momentum_10"] = df["Close"] - df["Close"].shift(10)

        # Volume change
        df["Volume_Change"] = df["Volume"].pct_change()

        feature_cols = [
            # Core indicators
            "RSI", "MACD", "MACD_Sig", "MACD_Hist",
            "BB_Position", "BB_Width",
            "EMA_9", "EMA_20", "EMA_50",
            "ATR", "STOCH_K", "STOCH_D",
            "Change_1d", "Change_5d", "Change_20d",
            "Bullish", "Bearish", "Doji",
            "Hammer", "ShootingStar",
            # Extra features
            "Price_Change",
            "High_Low_Ratio",
            "Close_Open_Ratio",
            "Rolling_Mean_5",
            "Rolling_Std_5",
            "Rolling_Mean_10",
            "Rolling_Std_10",
            "Momentum_5",
            "Momentum_10",
            "Volume_Change",
        ]

        available = [c for c in feature_cols
                     if c in df.columns]

        df = df.dropna()
        df = df[:-1]  # Last row remove

        X = df[available]
        y = df["Label"]

        # Infinite values remove karo
        X = X.replace([np.inf, -np.inf], np.nan)
        X = X.fillna(0)

        print(f"✅ Features ready: {len(available)} columns")
        print(f"✅ Total samples: {len(X)}")
        print(f"   BUY signals:    {(y==1).sum()}")
        print(f"   SELL signals:   {(y==-1).sum()}")
        print(f"   NO TRADE:       {(y==0).sum()}")

        return X, y

    # ============================================
    # MODEL TRAIN KARO
    # ============================================
    def train(self, df):
        print("\n" + "="*50)
        print("🤖 AI MODEL TRAINING SHURU!")
        print(f"   Data rows: {len(df)}")
        print("="*50)

        # Features
        X, y = self.prepare_features(df)

        # Train/Test split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y,
            test_size    = 0.2,
            shuffle      = False
        )

        print(f"\n📊 Training samples: {len(X_train)}")
        print(f"📊 Testing samples:  {len(X_test)}")

        # Scale karo
        X_train_sc = self.scaler.fit_transform(X_train)
        X_test_sc  = self.scaler.transform(X_test)

        # Class weights (balanced)
        classes     = np.unique(y_train)
        class_wts   = compute_class_weight(
            'balanced', classes=classes, y=y_train
        )
        class_weight_dict = dict(zip(classes, class_wts))

        # ---- MODEL 1: RANDOM FOREST ----
        print("\n🌲 Random Forest training...")
        self.rf_model = RandomForestClassifier(
            n_estimators      = 500,
            max_depth         = 15,
            min_samples_split = 5,
            min_samples_leaf  = 2,
            max_features      = 'sqrt',
            class_weight      = class_weight_dict,
            random_state      = 42,
            n_jobs            = -1
        )
        self.rf_model.fit(X_train_sc, y_train)
        rf_pred = self.rf_model.predict(X_test_sc)
        rf_acc  = accuracy_score(y_test, rf_pred) * 100
        print(f"✅ Random Forest: {rf_acc:.2f}%")

        # ---- MODEL 2: XGBOOST ----
        print("\n⚡ XGBoost training...")

        # XGBoost labels: 0,1,2
        y_train_xgb = y_train.map({-1: 0, 0: 1, 1: 2})
        y_test_xgb  = y_test.map({-1: 0, 0: 1, 1: 2})

        scale_pos = len(y_train[y_train==0]) / max(
            len(y_train[y_train==1]), 1
        )

        self.xgb_model = xgb.XGBClassifier(
            n_estimators     = 500,
            max_depth        = 8,
            learning_rate    = 0.05,
            subsample        = 0.8,
            colsample_bytree = 0.8,
            min_child_weight = 3,
            gamma            = 0.1,
            reg_alpha        = 0.1,
            reg_lambda       = 1.0,
            random_state     = 42,
            eval_metric      = "mlogloss",
            verbosity        = 0
        )
        self.xgb_model.fit(
            X_train_sc, y_train_xgb,
            eval_set  = [(X_test_sc, y_test_xgb)],
            verbose   = False
        )
        xgb_raw      = self.xgb_model.predict(X_test_sc)
        xgb_pred_map = pd.Series(xgb_raw).map(
            {0: -1, 1: 0, 2: 1}
        )
        xgb_acc = accuracy_score(
            y_test, xgb_pred_map
        ) * 100
        print(f"✅ XGBoost: {xgb_acc:.2f}%")

        # ---- MODEL 3: GRADIENT BOOSTING ----
        print("\n🚀 Gradient Boosting training...")
        self.gb_model = GradientBoostingClassifier(
            n_estimators  = 300,
            max_depth     = 6,
            learning_rate = 0.05,
            subsample     = 0.8,
            random_state  = 42
        )
        self.gb_model.fit(X_train_sc, y_train)
        gb_pred = self.gb_model.predict(X_test_sc)
        gb_acc  = accuracy_score(y_test, gb_pred) * 100
        print(f"✅ Gradient Boosting: {gb_acc:.2f}%")

        # ---- ENSEMBLE VOTING ----
        from collections import Counter
        ensemble_pred = []
        xgb_list = list(xgb_pred_map)

        for i in range(len(rf_pred)):
            votes = [
                rf_pred[i],
                xgb_list[i],
                gb_pred[i]
            ]
            vote = Counter(votes).most_common(1)[0][0]
            ensemble_pred.append(vote)

        ens_acc = accuracy_score(
            y_test, ensemble_pred
        ) * 100

        print(f"\n{'='*50}")
        print(f"📊 FINAL RESULTS:")
        print(f"   Random Forest:     {rf_acc:.2f}%")
        print(f"   XGBoost:           {xgb_acc:.2f}%")
        print(f"   Gradient Boosting: {gb_acc:.2f}%")
        print(f"   Ensemble:          {ens_acc:.2f}%")
        print(f"{'='*50}")

        self.accuracy     = ens_acc
        self.is_trained   = True
        self.feature_cols = list(X.columns)

        # Save karo
        self.save_model()
        return ens_acc

    # ============================================
    # PREDICT KARO
    # ============================================
    def predict(self, df):
        try:
            if not self.is_trained:
                self.load_model()

            from indicators import Indicators
            ind = Indicators(df.copy())
            df  = ind.add_all()

            # Extra features
            df["Price_Change"]     = df["Close"].pct_change()
            df["High_Low_Ratio"]   = (
                (df["High"] - df["Low"]) / df["Close"]
            )
            df["Close_Open_Ratio"] = (
                (df["Close"] - df["Open"]) / df["Open"]
            )
            df["Rolling_Mean_5"]   = df["Close"].rolling(5).mean()
            df["Rolling_Std_5"]    = df["Close"].rolling(5).std()
            df["Rolling_Mean_10"]  = df["Close"].rolling(10).mean()
            df["Rolling_Std_10"]   = df["Close"].rolling(10).std()
            df["Momentum_5"]       = df["Close"] - df["Close"].shift(5)
            df["Momentum_10"]      = df["Close"] - df["Close"].shift(10)
            df["Volume_Change"]    = df["Volume"].pct_change()

            latest = df.iloc[-1][self.feature_cols]
            latest = latest.fillna(0)
            latest = latest.replace([np.inf, -np.inf], 0)

            X = self.scaler.transform([latest])

            # RF predict
            rf_pred  = self.rf_model.predict(X)[0]
            rf_prob  = self.rf_model.predict_proba(X)[0]
            rf_conf  = max(rf_prob) * 100

            # XGB predict
            xgb_raw  = self.xgb_model.predict(X)[0]
            xgb_pred = {0: -1, 1: 0, 2: 1}[xgb_raw]
            xgb_prob = self.xgb_model.predict_proba(X)[0]
            xgb_conf = max(xgb_prob) * 100

            # GB predict
            gb_pred  = self.gb_model.predict(X)[0]
            gb_prob  = self.gb_model.predict_proba(X)[0]
            gb_conf  = max(gb_prob) * 100

            # Ensemble vote
            from collections import Counter
            votes    = [rf_pred, xgb_pred, gb_pred]
            signal   = Counter(votes).most_common(1)[0][0]

            # Average confidence
            avg_conf = (rf_conf + xgb_conf + gb_conf) / 3

            # Signal text
            if signal == 1:
                signal_text = "🟢 BUY CALL"
            else :
                signal_text = "🔴 BUY PUT"
            

            result = {
                "signal"     : signal_text,
                "value"      : signal,
                "confidence" : avg_conf,
                "rf_signal"  : rf_pred,
                "xgb_signal" : xgb_pred,
                "gb_signal"  : gb_pred,
                "rf_conf"    : rf_conf,
                "xgb_conf"   : xgb_conf,
                "gb_conf"    : gb_conf,
                "timestamp"  : datetime.now().strftime(
                               "%Y-%m-%d %H:%M:%S")
            }

            print(f"🎯 Prediction:")
            print(f"   Signal:     {signal_text}")
            print(f"   Confidence: {avg_conf:.1f}%")
            print(f"   RF:  {rf_pred} ({rf_conf:.1f}%)")
            print(f"   XGB: {xgb_pred} ({xgb_conf:.1f}%)")
            print(f"   GB:  {gb_pred} ({gb_conf:.1f}%)")

            return result

        except Exception as e:
            print(f"❌ Prediction Error: {e}")
            return None

    # ============================================
    # MODEL SAVE
    # ============================================
    def save_model(self):
        try:
            pickle.dump(
                self.rf_model,
                open(f"{self.model_path}rf_model.pkl", "wb")
            )
            pickle.dump(
                self.xgb_model,
                open(f"{self.model_path}xgb_model.pkl", "wb")
            )
            pickle.dump(
                self.gb_model,
                open(f"{self.model_path}gb_model.pkl", "wb")
            )
            pickle.dump(
                self.scaler,
                open(f"{self.model_path}scaler.pkl", "wb")
            )
            pickle.dump(
                self.feature_cols,
                open(f"{self.model_path}features.pkl", "wb")
            )
            with open(f"{self.model_path}accuracy.txt", "w") as f:
                f.write(str(self.accuracy))

            print(f"\n💾 Model saved!")
            print(f"   Accuracy: {self.accuracy:.2f}%")

        except Exception as e:
            print(f"❌ Save Error: {e}")

    # ============================================
    # MODEL LOAD
    # ============================================
    def load_model(self):
        try:
            self.rf_model = pickle.load(
                open(f"{self.model_path}rf_model.pkl", "rb")
            )
            self.xgb_model = pickle.load(
                open(f"{self.model_path}xgb_model.pkl", "rb")
            )
            self.scaler = pickle.load(
                open(f"{self.model_path}scaler.pkl", "rb")
            )
            self.feature_cols = pickle.load(
                open(f"{self.model_path}features.pkl", "rb")
            )

            # GB model (optional — purane model mein nahi hoga)
            try:
                self.gb_model = pickle.load(
                    open(f"{self.model_path}gb_model.pkl", "rb")
                )
            except:
                self.gb_model = None
                print("⚠️ GB model nahi mila — 2 model use honge")

            with open(f"{self.model_path}accuracy.txt", "r") as f:
                self.accuracy = float(f.read())

            self.is_trained = True
            print(f"✅ Model loaded! Accuracy: {self.accuracy:.2f}%")
            return True

        except Exception as e:
            print(f"⚠️ Model load failed: {e}")
            return False

    # ============================================
    # BACKTESTING
    # ============================================
    def backtest(self, df):
        print("\n" + "="*50)
        print("📊 BACKTESTING SHURU...")
        print("="*50)

        X, y = self.prepare_features(df)
        capital   = 50000
        start_cap = capital
        trades    = []
        wins      = 0
        losses    = 0

        X_sc  = self.scaler.transform(X)
        preds = self.rf_model.predict(X_sc)

        for i in range(len(preds)-1):
            signal      = preds[i]
            price_today = df["Close"].iloc[i]
            price_next  = df["Close"].iloc[i+1]

            if signal == 0:
                continue

            change = (price_next - price_today) / price_today

            if signal == 1:
                profit = capital * 0.02 * change * 10
            elif signal == -1:
                profit = capital * 0.02 * (-change) * 10

            capital += profit
            trades.append(profit)

            if profit > 0:
                wins += 1
            else:
                losses += 1

        total_trades = wins + losses
        win_rate     = (wins/total_trades*100) if total_trades > 0 else 0
        total_profit = capital - start_cap
        returns      = (total_profit/start_cap*100)

        print(f"\n💰 BACKTEST RESULTS:")
        print(f"   Starting Capital: ₹{start_cap:,.0f}")
        print(f"   Final Capital:    ₹{capital:,.0f}")
        print(f"   Total Profit:     ₹{total_profit:,.0f}")
        print(f"   Returns:          {returns:.2f}%")
        print(f"   Total Trades:     {total_trades}")
        print(f"   Wins:             {wins}")
        print(f"   Losses:           {losses}")
        print(f"   Win Rate:         {win_rate:.2f}%")
        print(f"   Model Accuracy:   {self.accuracy:.2f}%")

        return {
            "final_capital": capital,
            "profit"       : total_profit,
            "returns"      : returns,
            "win_rate"     : win_rate,
            "total_trades" : total_trades
        }


# ============================================
# TEST
# ============================================
if __name__ == "__main__":
    from data_fetcher import DataFetcher
    import os

    os.environ["ANGEL_API_KEY"]    = "mB3Hghfu"
    os.environ["ANGEL_CLIENT_ID"]  = "AACG329697"
    os.environ["ANGEL_PASSWORD"]   = "4160"
    os.environ["ANGEL_TOTP_KEY"]   = "TOTP_KEY_YAHAN"

    print("📊 Data fetch ho raha hai...")
    fetcher = DataFetcher()
    df = fetcher.get_best_data("NIFTY")

    if df is not None:
        print(f"✅ Data: {len(df)} rows")

        model    = AIModel()
        accuracy = model.train(df)
        model.backtest(df)

        print("\n🎯 LIVE PREDICTION:")
        result = model.predict(df)
        if result:
            print(f"Signal:     {result['signal']}")
            print(f"Confidence: {result['confidence']:.1f}%")
    else:
        print("❌ Data fetch failed!")