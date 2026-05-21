# ============================================
# TITAN-AI TRADER — API Server v4.0
# TITAN-SURYA TECHNOLOGIES
# ============================================

import threading
import schedule
import time
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, time as dtime
from data_fetcher import DataFetcher
from ai_model import AIModel
from order_manager import OrderManager
from trainer import AutoTrainer
from config import TRADING

# ============================================
# APP SETUP
# ============================================
app = FastAPI(title="TITAN-AI TRADER API")
bot = None

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Force redeploy 21-05-2026

# ============================================

# BOT STATE
# ============================================
class BotState:
    def __init__(self):
        self.fetcher = DataFetcher()
        self.model = AIModel()
        self.order_mgr = OrderManager()
        self.trainer = AutoTrainer()
        self.df = None
        self.running = False
        self.last_signal = None
        self.trade_count = 0
        self._init()

    # ============================================
    # UPDATED INIT FUNCTION
    # ============================================
    def _init(self):
        try:
            print("🔌 Bot initializing...")

            # Best data source se data lo
            self.df = self.fetcher.get_best_data("NIFTY")

            # Angel One connect karo (trading ke liye)
            self.fetcher.connect()

            # Model load ya train
            if self.df is not None:
                print(f"✅ Data: {len(self.df)} rows")
                loaded = self.model.load_model()

                if not loaded:
                    print("🤖 Training shuru...")
                    self.model.train(self.df)

            else:
                print("⚠️ Data nahi mila!")
                self.model.accuracy = 0

            self.order_mgr.fetcher = self.fetcher
            self.running = True

            print("✅ Bot Ready!")

        except Exception as e:
            print(f"⚠️ Init Error: {e}")
            self.running = False


# ============================================
# MARKET OPEN CHECK
# ============================================
def is_market_open():
    now = datetime.now()
    weekday = now.weekday()

    if weekday >= 5:
        return False

    market_open = dtime(9, 15)
    market_close = dtime(15, 30)

    return market_open <= now.time() <= market_close


# ============================================
# AUTO TRADING FUNCTION
# ============================================
def bot_trade():
    try:
        if bot is None or not bot.running:
            return

        # Market hours check
        if not is_market_open():
            print("🕐 Market band hai — skipping")
            return

        # Data check
        if bot.df is None:
            print("⚠️ Data nahi — reconnecting...")

            bot.fetcher.connect()

            self_df = bot.fetcher.get_best_data("NIFTY")

            if self_df is not None:
                bot.df = self_df

            return

        # Model check
        if not bot.model.is_trained:
            print("⚠️ Model trained nahi — skip")
            return

        # Risk check
        can, reasons = bot.order_mgr.risk.can_trade()

        if not can:
            for r in reasons:
                print(r)
            return

        # Signal lo
        signal = bot.model.predict(bot.df)

        if not signal:
            print("❌ Signal nahi mila")
            return

        print(f"\n🎯 Auto Trade Check:")
        print(f"   Signal:     {signal['signal']}")
        print(f"   Confidence: {signal['confidence']:.1f}%")

        # Same signal skip
        if signal["value"] == bot.last_signal:
            print("⚠️ Same signal — skip")
            return

        # Minimum confidence
        if signal["confidence"] < 45:
            print("⚠️ Low confidence — skip")
            return

        # NO TRADE signal
        if signal["value"] == 0:
            print("🟡 NO TRADE — waiting")
            return

        # Execute trade
        order_id = bot.order_mgr.execute_signal(
            signal,
            "NIFTY"
        )

        if order_id:
            bot.last_signal = signal["value"]
            bot.trade_count += 1

            print(f"✅ Trade executed: {order_id}")

        else:
            print("⚠️ Trade execute nahi hua")

    except Exception as e:
        print(f"❌ Auto Trading Error: {e}")


# ============================================
# DATA REFRESH
# ============================================
def refresh_data():
    try:
        if bot:
            df = bot.fetcher.get_best_data("NIFTY")

            if df is not None:
                bot.df = df
                print("✅ Data refreshed!")

    except Exception as e:
        print(f"❌ Data refresh error: {e}")


# ============================================
# AUTO RETRAIN
# ============================================
def auto_retrain():
    try:
        print("\n🔄 Auto retraining shuru...")

        if bot:
            df = bot.fetcher.get_best_data("NIFTY")

            if df is not None:
                bot.df = df

            if bot.df is not None:
                bot.trainer.train_once()
                print("✅ Auto retrain complete!")

    except Exception as e:
        print(f"❌ Auto retrain error: {e}")


# ============================================
# DAILY RESET
# ============================================
def daily_reset():
    if bot:
        bot.order_mgr.risk.daily_loss = 0
        bot.order_mgr.risk.daily_profit = 0
        bot.order_mgr.risk.trades_today = 0
        bot.order_mgr.risk.bot_active = True

        bot.last_signal = None
        bot.trade_count = 0

        print("✅ Daily reset complete!")


# ============================================
# BACKGROUND SCHEDULER
# ============================================
def start_scheduler():

    # Har 5 min trade
    schedule.every(5).minutes.do(bot_trade)

    # Har 1 ghante refresh
    schedule.every(1).hours.do(refresh_data)

    # 11 PM retrain
    schedule.every().day.at("23:00").do(auto_retrain)

    # 9:10 AM reset
    schedule.every().day.at("09:10").do(daily_reset)

    # Market summary
    schedule.every().day.at("15:35").do(
        lambda: bot.order_mgr.risk.daily_summary()
        if bot else None
    )

    print("⏰ Scheduler started!")

    while True:
        schedule.run_pending()
        time.sleep(30)


# ============================================
# STARTUP
# ============================================
@app.on_event("startup")
async def startup():

    global bot

    print("🚀 TITAN-AI SERVER STARTING...")

    bot = BotState()

    scheduler_thread = threading.Thread(
        target=start_scheduler,
        daemon=True
    )

    scheduler_thread.start()

    print("✅ Server + Auto Trading Ready!")

    print(
        f"   Market: {'OPEN 🟢' if is_market_open() else 'CLOSED 🔴'}"
    )

    print(
        f"   Data: {len(bot.df) if bot.df is not None else 0} rows"
    )

    print(
        f"   Model: {bot.model.accuracy:.1f}% accuracy"
    )


# ============================================
# REQUEST MODELS
# ============================================
class TradeRequest(BaseModel):
    symbol: str = "NIFTY"
    quantity: int = 1


class SettingsUpdate(BaseModel):
    stop_loss: float = 20.0
    target: float = 40.0
    max_trades: int = 3
    capital: float = 50000


# ============================================
# API ENDPOINTS
# ============================================

# 1. Health Check
@app.get("/")
async def root():

    return {
        "status": "running",
        "app": "TITAN-AI TRADER",
        "company": "TITAN-SURYA TECHNOLOGIES",
        "bot": bot.running if bot else False,
        "market_open": is_market_open(),
        "data_rows": len(bot.df) if bot and bot.df is not None else 0,
        "accuracy": bot.model.accuracy if bot else 0,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


# 2. Bot Status
@app.get("/status")
async def get_status():

    try:
        risk = bot.order_mgr.risk
        net = risk.daily_profit - risk.daily_loss

        try:
            nifty = bot.fetcher.get_live_price("NIFTY")
            bn = bot.fetcher.get_live_price("BANKNIFTY")

        except:
            nifty = 0
            bn = 0

        return {
            "status": "success",
            "bot_running": bot.running,
            "market_open": is_market_open(),
            "mode": TRADING["mode"],
            "capital": risk.capital,
            "daily_pnl": net,
            "daily_profit": risk.daily_profit,
            "daily_loss": risk.daily_loss,
            "trades_today": risk.trades_today,
            "max_trades": risk.max_trades,
            "ai_accuracy": bot.model.accuracy,
            "nifty_price": nifty,
            "banknifty": bn,
            "active_trades": len(risk.active_trades),
            "data_loaded": bot.df is not None,
            "data_rows": len(bot.df) if bot.df is not None else 0,
            "last_signal": str(bot.last_signal),
            "trade_count": bot.trade_count,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# SERVER
# ============================================
if __name__ == "__main__":

    print("🚀 TITAN-AI SERVER STARTING...")
    print("   URL: http://localhost:8000")

    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=False
    )