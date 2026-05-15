# ============================================
# TITAN-AI TRADER — API Server
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
app    = FastAPI(title="TITAN-AI TRADER API")
bot    = None

app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

# ============================================
# BOT CLASS
# ============================================
class BotState:
    def __init__(self):
        self.fetcher    = DataFetcher()
        self.model      = AIModel()
        self.order_mgr  = OrderManager()
        self.trainer    = AutoTrainer()
        self.df         = None
        self.running    = False
        self.last_signal= None
        self._init()

    def _init(self):
        self.fetcher.connect()
        self.df = self.fetcher.get_historical_data(
            "NIFTY", days=365
        )
        if not self.model.load_model():
            self.model.train(self.df)
        self.order_mgr.fetcher = self.fetcher
        self.running = True
        print("✅ Bot State Ready!")


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
# MODELS (Request/Response)
# ============================================
class TradeRequest(BaseModel):
    symbol    : str = "NIFTY"
    quantity  : int = 1

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
        "time"    : datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

# 2. Bot Status
@app.get("/status")
async def get_status():
    try:
        risk   = bot.order_mgr.risk
        price  = bot.fetcher.get_live_price("NIFTY")
        bnprice= bot.fetcher.get_live_price("BANKNIFTY")
        net    = risk.daily_profit - risk.daily_loss

        return {
            "status"        : "success",
            "bot_running"   : bot.running,
            "mode"          : TRADING["mode"],
            "capital"       : risk.capital,
            "daily_pnl"     : net,
            "daily_profit"  : risk.daily_profit,
            "daily_loss"    : risk.daily_loss,
            "trades_today"  : risk.trades_today,
            "max_trades"    : risk.max_trades,
            "ai_accuracy"   : bot.model.accuracy,
            "nifty_price"   : price,
            "banknifty"     : bnprice,
            "active_trades" : len(risk.active_trades),
            "timestamp"     : datetime.now().strftime(
                              "%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 3. Live Signal
@app.get("/signal")
async def get_signal():
    try:
        from indicators import Indicators
        ind    = Indicators(bot.df.copy())
        ind.add_rsi().add_macd().add_bollinger().add_ema()
        ind_signal = ind.get_signal()
        ai_signal  = bot.model.predict(bot.df)

        return {
            "status"          : "success",
            "ai_signal"       : ai_signal["signal"],
            "ai_confidence"   : ai_signal["confidence"],
            "indicator_signal": ind_signal["signal"],
            "indicator_score" : ind_signal["score"],
            "rsi"             : ind_signal["rsi"],
            "reasons"         : ind_signal["reasons"],
            "timestamp"       : datetime.now().strftime(
                                "%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 4. Live Prices
@app.get("/prices")
async def get_prices():
    try:
        nifty    = bot.fetcher.get_live_price("NIFTY")
        banknifty= bot.fetcher.get_live_price("BANKNIFTY")
        return {
            "status"    : "success",
            "nifty"     : nifty,
            "banknifty" : banknifty,
            "timestamp" : datetime.now().strftime(
                          "%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 5. Execute Trade
@app.post("/trade/execute")
async def execute_trade(req: TradeRequest):
    try:
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


# 6. Exit Trade
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


# 7. Active Trades
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


# 8. Trade History
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


# 9. Manual Train
@app.post("/train")
async def manual_train():
    try:
        def train_bg():
            bot.df = bot.fetcher.get_historical_data(
                "NIFTY", days=365
            )
            bot.model.train(bot.df)

        thread = threading.Thread(target=train_bg)
        thread.start()

        return {
            "status"  : "success",
            "message" : "Training shuru ho gayi! Background mein chalegi."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 10. Update Settings
@app.post("/settings")
async def update_settings(s: SettingsUpdate):
    try:
        bot.order_mgr.risk.stop_loss_pct  = s.stop_loss
        bot.order_mgr.risk.target_pct     = s.target
        bot.order_mgr.risk.max_trades     = s.max_trades
        bot.order_mgr.risk.capital        = s.capital

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


# 11. Emergency Stop
@app.post("/emergency_stop")
async def emergency_stop():
    try:
        bot.order_mgr.risk.emergency_stop()
        bot.running = False
        return {
            "status"  : "success",
            "message" : "🔴 Emergency stop activated!"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 12. Training History
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
# SERVER CHALAO
# ============================================
if __name__ == "__main__":
    print("🚀 TITAN-AI SERVER STARTING...")
    print("   URL: http://localhost:8000")
    print("   Docs: http://localhost:8000/docs")
    uvicorn.run(
        "api_server:app",
        host    = "0.0.0.0",
        port    = 8000,
        reload  = False
    )