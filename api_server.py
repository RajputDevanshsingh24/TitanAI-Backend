# ============================================
# TITAN-AI TRADER — API Server FINAL v5.0
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
from datetime import timezone, timedelta
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
    allow_origins  = ["*"],
    allow_methods  = ["*"],
    allow_headers  = ["*"],
)


# ============================================
# MARKET OPEN CHECK — IST TIMEZONE
# ============================================
def is_market_open():
    try:
        # IST = UTC + 5:30 (No pytz needed!)
        ist     = timezone(timedelta(hours=5, minutes=30))
        now     = datetime.now(ist)
        weekday = now.weekday()

        print(f"⏰ IST: {now.strftime('%H:%M:%S %d-%m-%Y')} "
              f"| Day: {weekday}")

        # Weekend check (5=Saturday, 6=Sunday)
        if weekday >= 5:
            print("📅 Weekend — Market band!")
            return False

        # Market hours: 9:15 AM - 3:30 PM IST
        market_open  = dtime(9, 15)
        market_close = dtime(15, 30)
        current_time = now.time()

        is_open = market_open <= current_time <= market_close
        print(f"🕐 Market: "
              f"{'OPEN 🟢' if is_open else 'CLOSED 🔴'}")
        return is_open

    except Exception as e:
        print(f"❌ Market check error: {e}")
        return False


# ============================================
# BOT STATE
# ============================================
class BotState:
    def __init__(self):
        self.fetcher     = DataFetcher()
        self.model       = AIModel()
        self.order_mgr   = OrderManager()
        self.trainer     = AutoTrainer()
        self.df          = None
        self.running     = False
        self.last_signal = None
        self.trade_count = 0
        self._init()

    def _init(self):
        try:
            print("🔌 Bot initializing...")

            # Step 1: Best data source se data lo
            self.df = self.fetcher.get_best_data("NIFTY")

            # Step 2: Angel One connect karo
            self.fetcher.connect()

            # Step 3: Model train ya load
            if self.df is not None:
                print(f"✅ Data: {len(self.df)} rows")

                loaded = self.model.load_model()

                # 2464 rows available — force retrain!
                if loaded and len(self.df) > 500:
                    print(f"🔄 {len(self.df)} rows mila — "
                          f"Force retraining!")
                    self.model.train(self.df)
                elif not loaded:
                    print("🤖 Model nahi mila — training...")
                    self.model.train(self.df)
            else:
                print("⚠️ Data nahi mila!")
                self.model.accuracy = 0

            self.order_mgr.fetcher = self.fetcher
            self.running = True
            print("✅ Bot Ready!")
            print(f"   Market: "
                  f"{'OPEN 🟢' if is_market_open() else 'CLOSED 🔴'}")
            print(f"   Data:   "
                  f"{len(self.df) if self.df is not None else 0} rows")
            print(f"   Model:  {self.model.accuracy:.1f}%")

        except Exception as e:
            print(f"⚠️ Init Error: {e}")
            self.running = False


# ============================================
# AUTO TRADING
# ============================================
def bot_trade():
    try:
        if bot is None or not bot.running:
            return

        if not is_market_open():
            return

        if bot.df is None:
            print("⚠️ Data nahi — reconnecting...")
            bot.fetcher.connect()
            bot.df = bot.fetcher.get_best_data("NIFTY")
            return

        if not bot.model.is_trained:
            print("⚠️ Model trained nahi — skip")
            return

        can, reasons = bot.order_mgr.risk.can_trade()
        if not can:
            for r in reasons:
                print(r)
            return

        signal = bot.model.predict(bot.df)
        if not signal:
            print("❌ Signal nahi mila")
            return

        print(f"\n🎯 Auto Trade Check:")
        print(f"   Signal:     {signal['signal']}")
        print(f"   Confidence: {signal['confidence']:.1f}%")

        if signal["value"] == bot.last_signal:
            print("⚠️ Same signal — skip")
            return

        if signal["confidence"] < 30:
            print(f"⚠️ Low confidence — skip")
            return

        if signal["value"] == 0:
            print("🟡 NO TRADE — waiting")
            return

        order_id = bot.order_mgr.execute_signal(
            signal, "NIFTY"
        )

        if order_id:
            bot.last_signal  = signal["value"]
            bot.trade_count += 1
            print(f"✅ Trade: {order_id}")

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
                print(f"✅ Data refreshed: {len(df)} rows")
    except Exception as e:
        print(f"❌ Refresh error: {e}")


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
        bot.order_mgr.risk.daily_loss   = 0
        bot.order_mgr.risk.daily_profit = 0
        bot.order_mgr.risk.trades_today = 0
        bot.order_mgr.risk.bot_active   = True
        bot.last_signal = None
        bot.trade_count = 0
        print("✅ Daily reset complete!")


# ============================================
# SCHEDULER
# ============================================
def start_scheduler():
    schedule.every(5).minutes.do(bot_trade)
    schedule.every(1).hours.do(refresh_data)
    schedule.every().day.at("23:00").do(auto_retrain)
    schedule.every().day.at("09:10").do(daily_reset)
    schedule.every().day.at("15:35").do(
        lambda: bot.order_mgr.risk.daily_summary()
        if bot else None
    )

    print("⏰ Scheduler started!")
    print("   → Trade: Har 5 min")
    print("   → Refresh: Har 1 ghanta")
    print("   → Retrain: Raat 11 PM")
    print("   → Reset: 9:10 AM")

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


# ============================================
# REQUEST MODELS
# ============================================
class TradeRequest(BaseModel):
    symbol   : str = "NIFTY"
    quantity : int = 1

class SettingsUpdate(BaseModel):
    stop_loss  : float = 20.0
    target     : float = 40.0
    max_trades : int   = 3
    capital    : float = 50000


# ============================================
# ENDPOINTS
# ============================================

# 1. Root
@app.get("/")
async def root():
    return {
        "status"      : "running",
        "app"         : "TITAN-AI TRADER",
        "company"     : "TITAN-SURYA TECHNOLOGIES",
        "bot"         : bot.running if bot else False,
        "market_open" : is_market_open(),
        "data_rows"   : len(bot.df)
                        if bot and bot.df is not None
                        else 0,
        "accuracy"    : bot.model.accuracy if bot else 0,
        "time"        : datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S")
    }


# 2. Status
@app.get("/status")
async def get_status():
    try:
        risk = bot.order_mgr.risk
        net  = risk.daily_profit - risk.daily_loss

        try:
            nifty = bot.fetcher.get_live_price("NIFTY")
            bn    = bot.fetcher.get_live_price("BANKNIFTY")
        except:
            nifty = 0
            bn    = 0

        return {
            "status"        : "success",
            "bot_running"   : bot.running,
            "market_open"   : is_market_open(),
            "mode"          : TRADING["mode"],
            "capital"       : risk.capital,
            "daily_pnl"     : net,
            "daily_profit"  : risk.daily_profit,
            "daily_loss"    : risk.daily_loss,
            "trades_today"  : risk.trades_today,
            "max_trades"    : risk.max_trades,
            "ai_accuracy"   : bot.model.accuracy,
            "nifty_price"   : nifty,
            "banknifty"     : bn,
            "active_trades" : len(risk.active_trades),
            "data_loaded"   : bot.df is not None,
            "data_rows"     : len(bot.df)
                              if bot.df is not None
                              else 0,
            "last_signal"   : str(bot.last_signal),
            "trade_count"   : bot.trade_count,
            "timestamp"     : datetime.now().strftime(
                              "%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=str(e)
        )


# 3. Signal
@app.get("/signal")
async def get_signal():
    try:
        if bot.df is None:
            return {
                "status"  : "offline",
                "message" : "Data nahi mila!"
            }

        from indicators import Indicators
        ind        = Indicators(bot.df.copy())
        ind.add_rsi().add_macd().add_bollinger().add_ema()
        ind_signal = ind.get_signal()

        if bot.model.is_trained:
            ai_signal = bot.model.predict(bot.df)
        else:
            ai_signal = {
                "signal"    : "🟡 NO TRADE",
                "confidence": 0
            }

        return {
            "status"           : "success",
            "ai_signal"        : ai_signal["signal"],
            "ai_confidence"    : ai_signal["confidence"],
            "indicator_signal" : ind_signal["signal"],
            "indicator_score"  : ind_signal["score"],
            "rsi"              : ind_signal["rsi"],
            "reasons"          : ind_signal["reasons"],
            "market_open"      : is_market_open(),
            "timestamp"        : datetime.now().strftime(
                                 "%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=str(e)
        )


# 4. Prices
@app.get("/prices")
async def get_prices():
    try:
        nifty = bot.fetcher.get_live_price("NIFTY")
        bn    = bot.fetcher.get_live_price("BANKNIFTY")
        return {
            "status"    : "success",
            "nifty"     : nifty,
            "banknifty" : bn,
            "timestamp" : datetime.now().strftime(
                          "%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=str(e)
        )


# 5. Reconnect
@app.post("/reconnect")
async def reconnect():
    try:
        def reconnect_bg():
            connected = bot.fetcher.connect()
            if connected:
                df = bot.fetcher.get_best_data("NIFTY")
                if df is not None:
                    bot.df = df
                if (bot.df is not None and
                        not bot.model.is_trained):
                    bot.model.train(bot.df)
                bot.running = True
                print("✅ Reconnected!")

        thread = threading.Thread(target=reconnect_bg)
        thread.start()

        return {
            "status"  : "success",
            "message" : "Reconnecting..."
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=str(e)
        )


# 6. Execute Trade
@app.post("/trade/execute")
async def execute_trade(req: TradeRequest):
    try:
        if bot.df is None:
            return {
                "status" : "error",
                "message": "Bot offline!"
            }

        if not is_market_open():
            return {
                "status" : "error",
                "message": "Market band hai!"
            }

        signal = bot.model.predict(bot.df)
        if not signal:
            raise HTTPException(
                status_code=400,
                detail="Signal nahi mila!"
            )

        order_id = bot.order_mgr.execute_signal(
            signal, req.symbol
        )

        if order_id:
            return {
                "status"   : "success",
                "order_id" : order_id,
                "signal"   : signal["signal"],
                "message"  : "Trade executed!"
            }
        else:
            return {
                "status"  : "skipped",
                "message" : "Conditions met nahi hui"
            }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=str(e)
        )


# 7. Trade Now
@app.post("/trade/now")
async def trade_now():
    try:
        bot_trade()
        return {
            "status"      : "success",
            "message"     : "Trade cycle executed!",
            "trade_count" : bot.trade_count,
            "market_open" : is_market_open()
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=str(e)
        )


# 8. Exit Trade
@app.post("/trade/exit/{order_id}")
async def exit_trade(order_id: str):
    try:
        result = bot.order_mgr.exit_trade(
            order_id, "MANUAL_EXIT"
        )
        return {
            "status"  : "success",
            "result"  : result,
            "message" : "Trade closed!"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=str(e)
        )


# 9. Active Trades
@app.get("/trades/active")
async def get_active_trades():
    try:
        trades = list(
            bot.order_mgr.risk.active_trades.values()
        )
        return {
            "status" : "success",
            "count"  : len(trades),
            "trades" : trades
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=str(e)
        )


# 10. Trade History
@app.get("/trades/history")
async def get_trade_history():
    try:
        history = bot.order_mgr.risk.trade_history
        return {
            "status"  : "success",
            "count"   : len(history),
            "history" : history[-20:]
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=str(e)
        )


# 11. Train
@app.post("/train")
async def manual_train():
    try:
        def train_bg():
            df = bot.fetcher.get_best_data("NIFTY")
            if df is not None:
                bot.df = df
            if bot.df is not None:
                bot.model.train(bot.df)
                print("✅ Training complete! "
                      f"Accuracy: {bot.model.accuracy:.2f}%")

        thread = threading.Thread(target=train_bg)
        thread.start()

        return {
            "status"  : "success",
            "message" : f"Training shuru! "
                        f"{len(bot.df) if bot.df is not None else 0}"
                        f" rows se."
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=str(e)
        )


# 12. Settings
@app.post("/settings")
async def update_settings(s: SettingsUpdate):
    try:
        bot.order_mgr.risk.stop_loss_pct = s.stop_loss
        bot.order_mgr.risk.target_pct    = s.target
        bot.order_mgr.risk.max_trades    = s.max_trades
        bot.order_mgr.risk.capital       = s.capital

        return {
            "status"  : "success",
            "message" : "Settings updated!",
            "settings": {
                "stop_loss"  : s.stop_loss,
                "target"     : s.target,
                "max_trades" : s.max_trades,
                "capital"    : s.capital,
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=str(e)
        )


# 13. Emergency Stop
@app.post("/emergency_stop")
async def emergency_stop():
    try:
        bot.order_mgr.risk.emergency_stop()
        bot.running = False
        return {
            "status"  : "success",
            "message" : "🔴 Emergency stop!"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=str(e)
        )


# 14. Training History
@app.get("/training/history")
async def training_history():
    try:
        logs = bot.trainer.get_history()
        return {
            "status"       : "success",
            "best_accuracy": bot.trainer.best_acc,
            "logs"         : logs
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=str(e)
        )


# ============================================
# SERVER
# ============================================
if __name__ == "__main__":
    print("🚀 TITAN-AI SERVER STARTING...")
    print("   URL: http://localhost:8000")
    uvicorn.run(
        "api_server:app",
        host   = "0.0.0.0",
        port   = 8000,
        reload = False
    )