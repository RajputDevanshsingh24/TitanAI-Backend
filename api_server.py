# ============================================
# TITAN-AI TRADER — API Server v2.0
# TITAN-SURYA TECHNOLOGIES
# ============================================

import threading
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
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
# BOT CLASS
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
        self._init()

    def _init(self):
        try:
            print("🔌 Bot initializing...")

            # Connect karo
            connected = self.fetcher.connect()

            if connected:
                print("✅ Connected! Data fetch ho raha hai...")
                self.df = self.fetcher.get_historical_data(
                    "NIFTY", days=365
                )
            else:
                print("⚠️ Connection failed — offline mode!")
                self.df = None

            # Model load ya train karo
            if self.df is not None:
                loaded = self.model.load_model()
                if not loaded:
                    print("🤖 Training shuru ho rahi hai...")
                    self.model.train(self.df)
            else:
                print("⚠️ Data nahi mila — model skip!")
                self.model.accuracy = 0

            self.order_mgr.fetcher = self.fetcher
            self.running = True
            print("✅ Bot State Ready!")

        except Exception as e:
            print(f"⚠️ Init Error: {e}")
            self.running = False


# ============================================
# STARTUP
# ============================================
@app.on_event("startup")
async def startup():
    global bot
    print("🚀 TITAN-AI SERVER STARTING...")
    bot = BotState()
    print("✅ Server Ready!")


# ============================================
# MODELS
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

# 1. Health Check
@app.get("/")
async def root():
    return {
        "status"  : "running",
        "app"     : "TITAN-AI TRADER",
        "company" : "TITAN-SURYA TECHNOLOGIES",
        "bot"     : bot.running if bot else False,
        "time"    : datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

# 2. Bot Status
@app.get("/status")
async def get_status():
    try:
        risk    = bot.order_mgr.risk
        net     = risk.daily_profit - risk.daily_loss
        
        # Live prices
        try:
            nifty  = bot.fetcher.get_live_price("NIFTY")
            bn     = bot.fetcher.get_live_price("BANKNIFTY")
        except:
            nifty  = 0
            bn     = 0

        return {
            "status"       : "success",
            "bot_running"  : bot.running,
            "mode"         : TRADING["mode"],
            "capital"      : risk.capital,
            "daily_pnl"    : net,
            "daily_profit" : risk.daily_profit,
            "daily_loss"   : risk.daily_loss,
            "trades_today" : risk.trades_today,
            "max_trades"   : risk.max_trades,
            "ai_accuracy"  : bot.model.accuracy,
            "nifty_price"  : nifty,
            "banknifty"    : bn,
            "active_trades": len(risk.active_trades),
            "data_loaded"  : bot.df is not None,
            "timestamp"    : datetime.now().strftime(
                             "%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 3. Live Signal
@app.get("/signal")
async def get_signal():
    try:
        if bot.df is None:
            return {
                "status"  : "offline",
                "message" : "Data nahi mila — reconnecting..."
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
            "timestamp"        : datetime.now().strftime(
                                 "%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 4. Live Prices
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
        raise HTTPException(status_code=500, detail=str(e))


# 5. Reconnect
@app.post("/reconnect")
async def reconnect():
    try:
        def reconnect_bg():
            connected = bot.fetcher.connect()
            if connected:
                bot.df = bot.fetcher.get_historical_data(
                    "NIFTY", days=365
                )
                if bot.df is not None:
                    if not bot.model.is_trained:
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
        raise HTTPException(status_code=500, detail=str(e))


# 6. Execute Trade
@app.post("/trade/execute")
async def execute_trade(req: TradeRequest):
    try:
        if bot.df is None:
            return {
                "status"  : "error",
                "message" : "Bot offline hai!"
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
                "message" : "Trade conditions met nahi hui"
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 7. Exit Trade
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
        raise HTTPException(status_code=500, detail=str(e))


# 8. Active Trades
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
        raise HTTPException(status_code=500, detail=str(e))


# 9. Trade History
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
        raise HTTPException(status_code=500, detail=str(e))


# 10. Manual Train
@app.post("/train")
async def manual_train():
    try:
        def train_bg():
            if bot.fetcher.connected:
                bot.df = bot.fetcher.get_historical_data(
                    "NIFTY", days=365
                )
            if bot.df is not None:
                bot.model.train(bot.df)
                print("✅ Training complete!")
            else:
                print("❌ Data nahi mila!")

        thread = threading.Thread(target=train_bg)
        thread.start()

        return {
            "status"  : "success",
            "message" : "Training shuru!"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 11. Update Settings
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
        raise HTTPException(status_code=500, detail=str(e))


# 12. Emergency Stop
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
        raise HTTPException(status_code=500, detail=str(e))


# 13. Training History
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
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# SERVER
# ============================================
if __name__ == "__main__":
    print("🚀 TITAN-AI SERVER STARTING...")
    print("   URL: http://localhost:8000")
    print("   Docs: http://localhost:8000/docs")
    uvicorn.run(
        "api_server:app",
        host   = "0.0.0.0",
        port   = 8000,
        reload = False
    )