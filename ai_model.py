# ============================================
# TITAN-AI TRADER — AI Model
# TITAN-SURYA TECHNOLOGIES
# ============================================

import pandas as pd
import numpy as np
import pickle
import os
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import xgboost as xgb
import warnings
warnings.filterwarnings("ignore")

class AIModel:

    def __init__(self):
        self.rf_model    = None  # Random Forest
        self.xgb_model   = None  # XGBoost
        self.scaler      = StandardScaler()
        self.is_trained  = False
        self.accuracy    = 0
        self.model_path  = "models/"
        os.makedirs(self.model_path, exist_ok=True)

    # ============================================
    # FEATURES BANANA (Input for AI)
    # ============================================
    def prepare_features(self, df):
        from indicators import Indicators
        
        print("⚙️ Features prepare ho rahe hain...")
        
        # Indicators add karo
        ind = Indicators(df.copy())
        df  = ind.add_all()
        
        # Labels banao (Target)
        # Agar kal close > aaj close + 0.3% → BUY (1)
        # Agar kal close < aaj close - 0.3% → SELL (-1)
        # Warna → NO TRADE (0)
        
        df["Future_Close"] = df["Close"].shift(-1)
        df["Return"]       = (
            (df["Future_Close"] - df["Close"]) /
            df["Close"] * 100
        )
        
        df["Label"] = 0
        df.loc[df["Return"] >  0.3, "Label"] =  1  # BUY
        df.loc[df["Return"] < -0.3, "Label"] = -1  # SELL
        
        # Features select karo
        feature_cols = [
            "RSI", "MACD", "MACD_Sig", "MACD_Hist",
            "BB_Position", "BB_Width",
            "EMA_9", "EMA_20", "EMA_50",
            "ATR", "STOCH_K", "STOCH_D",
            "Change_1d", "Change_5d", "Change_20d",
            "Bullish", "Bearish", "Doji",
            "Hammer", "ShootingStar"
        ]
        
        # Sirf jo columns exist karte hain
        available = [c for c in feature_cols if c in df.columns]
        
        # Missing values hatao
        df = df.dropna()
        df = df[:-1]  # Last row hatao (future unknown)
        
        X = df[available]
        y = df["Label"]
        
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
        print("="*50)
        
        # Features prepare karo
        X, y = self.prepare_features(df)
        
        # Train/Test split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y,
            test_size    = 0.2,
            shuffle      = False  # Time series mein shuffle nahi!
        )
        
        print(f"\n📊 Training samples: {len(X_train)}")
        print(f"📊 Testing samples:  {len(X_test)}")
        
        # Scale karo
        X_train_sc = self.scaler.fit_transform(X_train)
        X_test_sc  = self.scaler.transform(X_test)
        
        # ---- MODEL 1: RANDOM FOREST ----
        print("\n🌲 Random Forest train ho raha hai...")
        self.rf_model = RandomForestClassifier(
            n_estimators = 200,
            max_depth    = 10,
            random_state = 42,
            n_jobs       = -1
        )
        self.rf_model.fit(X_train_sc, y_train)
        rf_pred = self.rf_model.predict(X_test_sc)
        rf_acc  = accuracy_score(y_test, rf_pred) * 100
        print(f"✅ Random Forest Accuracy: {rf_acc:.2f}%")
        
        # ---- MODEL 2: XGBOOST ----
        print("\n⚡ XGBoost train ho raha hai...")
        
        # XGBoost ke liye labels 0,1,2 chahiye
        y_train_xgb = y_train.map({-1: 0, 0: 1, 1: 2})
        y_test_xgb  = y_test.map({-1: 0, 0: 1, 1: 2})
        
        self.xgb_model = xgb.XGBClassifier(
            n_estimators    = 200,
            max_depth       = 6,
            learning_rate   = 0.1,
            random_state    = 42,
            eval_metric     = "mlogloss",
            verbosity       = 0
        )
        self.xgb_model.fit(
            X_train_sc, y_train_xgb,
            eval_set        = [(X_test_sc, y_test_xgb)],
            verbose         = False
        )
        xgb_pred     = self.xgb_model.predict(X_test_sc)
        xgb_pred_map = pd.Series(xgb_pred).map({0:-1, 1:0, 2:1})
        xgb_acc      = accuracy_score(y_test, xgb_pred_map) * 100
        print(f"✅ XGBoost Accuracy: {xgb_acc:.2f}%")
        
        # ---- ENSEMBLE ACCURACY ----
        ensemble_pred = []
        for i in range(len(rf_pred)):
            votes = [rf_pred[i], 
                     list(xgb_pred_map)[i]]
            # Majority vote
            from collections import Counter
            vote   = Counter(votes).most_common(1)[0][0]
            ensemble_pred.append(vote)
        
        ens_acc = accuracy_score(y_test, ensemble_pred) * 100
        
        print(f"\n{'='*50}")
        print(f"📊 FINAL RESULTS:")
        print(f"   Random Forest:  {rf_acc:.2f}%")
        print(f"   XGBoost:        {xgb_acc:.2f}%")
        print(f"   Ensemble:       {ens_acc:.2f}%")
        print(f"{'='*50}")
        
        self.accuracy   = ens_acc
        self.is_trained = True
        self.feature_cols = list(X.columns)
        
        # Model save karo
        self.save_model()
        
        return ens_acc

    # ============================================
    # PREDICT KARO (Live Trading)
    # ============================================
    def predict(self, df):
        try:
            if not self.is_trained:
                self.load_model()
            
            from indicators import Indicators
            ind = Indicators(df.copy())
            df  = ind.add_all()
            
            # Latest row lo
            latest = df.iloc[-1][self.feature_cols]
            latest = latest.fillna(0)
            X      = self.scaler.transform([latest])
            
            # Dono models se predict karo
            rf_pred  = self.rf_model.predict(X)[0]
            xgb_raw  = self.xgb_model.predict(X)[0]
            xgb_pred = {0:-1, 1:0, 2:1}[xgb_raw]
            
            # RF probability
            rf_prob  = self.rf_model.predict_proba(X)[0]
            rf_conf  = max(rf_prob) * 100
            
            # Ensemble vote
            from collections import Counter
            votes    = [rf_pred, xgb_pred]
            signal   = Counter(votes).most_common(1)[0][0]
            
            # Signal text
            if signal == 1:
                signal_text = "🟢 BUY CALL"
            elif signal == -1:
                signal_text = "🔴 BUY PUT"
            else:
                signal_text = "🟡 NO TRADE"
            
            result = {
                "signal"     : signal_text,
                "value"      : signal,
                "confidence" : rf_conf,
                "rf_signal"  : rf_pred,
                "xgb_signal" : xgb_pred,
                "timestamp"  : datetime.now().strftime(
                                "%Y-%m-%d %H:%M:%S")
            }
            
            return result
            
        except Exception as e:
            print(f"❌ Prediction Error: {e}")
            return None

    # ============================================
    # MODEL SAVE KARO
    # ============================================
    def save_model(self):
        try:
            pickle.dump(
                self.rf_model,
                open(f"{self.model_path}rf_model.pkl","wb")
            )
            pickle.dump(
                self.xgb_model,
                open(f"{self.model_path}xgb_model.pkl","wb")
            )
            pickle.dump(
                self.scaler,
                open(f"{self.model_path}scaler.pkl","wb")
            )
            pickle.dump(
                self.feature_cols,
                open(f"{self.model_path}features.pkl","wb")
            )
            # Accuracy save karo
            with open(f"{self.model_path}accuracy.txt","w") as f:
                f.write(str(self.accuracy))
            
            print(f"\n💾 Model saved!")
            print(f"   Path: {self.model_path}")
            print(f"   Accuracy: {self.accuracy:.2f}%")
            
        except Exception as e:
            print(f"❌ Save Error: {e}")

    # ============================================
    # MODEL LOAD KARO
    # ============================================
    def load_model(self):
        try:
            self.rf_model  = pickle.load(
                open(f"{self.model_path}rf_model.pkl","rb")
            )
            self.xgb_model = pickle.load(
                open(f"{self.model_path}xgb_model.pkl","rb")
            )
            self.scaler    = pickle.load(
                open(f"{self.model_path}scaler.pkl","rb")
            )
            self.feature_cols = pickle.load(
                open(f"{self.model_path}features.pkl","rb")
            )
            with open(f"{self.model_path}accuracy.txt","r") as f:
                self.accuracy = float(f.read())
            
            self.is_trained = True
            print(f"✅ Model loaded! Accuracy: {self.accuracy:.2f}%")
            return True
            
        except Exception as e:
            print(f"⚠️ Model load failed: {e}")
            print("   Pehle training karni hogi!")
            return False

    # ============================================
    # BACKTESTING
    # ============================================
    def backtest(self, df):
        print("\n" + "="*50)
        print("📊 BACKTESTING SHURU...")
        print("="*50)
        
        X, y = self.prepare_features(df)
        
        capital     = 50000
        start_cap   = capital
        trades      = []
        wins        = 0
        losses      = 0
        
        X_sc = self.scaler.transform(X)
        preds = self.rf_model.predict(X_sc)
        
        for i in range(len(preds)-1):
            signal      = preds[i]
            price_today = df["Close"].iloc[i]
            price_next  = df["Close"].iloc[i+1]
            
            if signal == 0:
                continue
            
            change = (price_next - price_today) / price_today
            
            if signal == 1:    # BUY CALL
                profit = capital * 0.02 * change * 10
            elif signal == -1: # BUY PUT
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
            "final_capital" : capital,
            "profit"        : total_profit,
            "returns"       : returns,
            "win_rate"      : win_rate,
            "total_trades"  : total_trades
        }


# ============================================
# TEST
# ============================================
if __name__ == "__main__":
    from data_fetcher import DataFetcher

    # Data lo
    print("📊 Data fetch ho raha hai...")
    fetcher = DataFetcher()
    fetcher.connect()
    df = fetcher.get_historical_data("NIFTY", days=365)

    # Model banao
    model = AIModel()

    # Train karo
    accuracy = model.train(df)

    # Backtest karo
    model.backtest(df)

    # Live prediction
    print("\n" + "="*50)
    print("🎯 LIVE PREDICTION:")
    print("="*50)
    result = model.predict(df)
    if result:
        print(f"\n Signal:     {result['signal']}")
        print(f" Confidence: {result['confidence']:.1f}%")
        print(f" RF Vote:    {result['rf_signal']}")
        print(f" XGB Vote:   {result['xgb_signal']}")
        print(f" Time:       {result['timestamp']}")