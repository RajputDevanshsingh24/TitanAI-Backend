# ============================================
# TITAN-AI TRADER — API Server FINAL
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

app = FastAPI(title="TITAN-AI TRADER API")
bot = None

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================
# IST MARKET CHECK
# ============================================
def is_market_open():
    try:
        ist     = timezone(timedelta(hours=5, minutes=30))
        now     = datetime.now(ist)
        weekday = now.weekday()
        if weekday >= 5:
            return False
        return dtime(9, 15) <= now.time() <= dtime(15, 30)
    except Exception as e:
        print(f"❌ Market check error: {e}")
        return False


def get_ist_time():
    ist = timezone(timedelta(hours=5, minutes=30))
    return datetime.now(ist).strftime("%H:%M:%S %d-%m-%Y")


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
            print(f"⏰ IST: {get_ist_time()}")

            # Data lo
            self.df = self.fetcher.get_best_data("NIFTY")

            # Angel One connect
            self.fetcher.connect()

            if self.df is not None:
                print(f"✅ Data: {len(self.df)} rows")
                loaded = self.model.load_model()
                if not loaded:
                    print("🤖 Training shuru...")
                    self.model.train(self.df)
            else:
                print("⚠️ Data nahi mila!")
                self.model.accuracy = 0.0

            self.order_mgr.fetcher = self.fetcher
            self.running = True
            print("✅ Bot Ready!")
            print(f"   Market: "
                  f"{'OPEN 🟢' if is_market_open() else 'CLOSED 🔴'}")
            print(f"   Data:   "
                  f"{len(self.df) if self.df is not None else 0} rows")
            print(f"   Model:  {self.model.accuracy:.1f}%")

        except Exception as e:
            print(f"❌ Init Error: {e}")
            import traceback
            traceback.print_exc()
            self.running = False


# ============================================
# AUTO TRADING
# ============================================
def bot_trade():
    try:
        if bot is None or not bot.running:
            return

        ist_time = get_ist_time()
        market   = is_market_open()
        print(f"⏰ IST: {ist_time} | "
              f"Market: {'OPEN 🟢' if market else 'CLOSED 🔴'}")

        if not market:
            return

        if bot.df is None:
            print("⚠️ Data nahi — skip")
            return

        if not bot.model.is_trained:
            print("⚠️ Model ready nahi — skip")
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

        print(f"🎯 Signal: {signal['signal']} "
              f"| Conf: {signal['confidence']:.1f}%")

        # Same signal skip
        if signal["value"] == bot.last_signal:
            print("⚠️ Same signal — skip")
            return

        # Min confidence 30%
        if signal["confidence"] < 30:
            print(f"⚠️ Low confidence — skip")
            return

        order_id = bot.order_mgr.execute_signal(
            signal, "NIFTY"
        )
        if order_id:
            bot.last_signal  = signal["value"]
            bot.trade_count += 1
            print(f"✅ Trade: {order_id}")

    except Exception as e:
        print(f"❌ Trade Error: {e}")
        import traceback
        traceback.print_exc()


# ============================================
# REFRESH DATA
# ============================================
def refresh_data():
    try:
        if bot:
            df = bot.fetcher.get_best_data("NIFTY")
            if df is not None:
                bot.df = df
                print(f"✅ Data refreshed: {len(df)} rows")
    except Exception as e:
        print(f"❌ Refresh Error: {e}")


# ============================================
# AUTO RETRAIN
# ============================================
def auto_retrain():
    try:
        print("\n🔄 Auto retraining...")
        if bot:
            df = bot.fetcher.get_best_data("NIFTY")
            if df is not None:
                bot.df = df
            if bot.df is not None:
                new_acc = bot.model.train(bot.df)
                print(f"✅ Retrain done: {new_acc:.2f}%")
    except Exception as e:
        print(f"❌ Retrain Error: {e}")


# ============================================
# DAILY RESET
# ============================================
def daily_reset():
    try:
        if bot:
            bot.order_mgr.risk.daily_loss   = 0
            bot.order_mgr.risk.daily_profit = 0
            bot.order_mgr.risk.trades_today = 0
            bot.order_mgr.risk.bot_active   = True
            bot.last_signal = None
            bot.trade_count = 0
            print("✅ Daily reset complete!")
    except Exception as e:
        print(f"❌ Reset Error: {e}")


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
    while True:
        try:
            schedule.run_pending()
        except Exception as e:
            print(f"❌ Scheduler Error: {e}")
        time.sleep(30)


# ============================================
# STARTUP
# ============================================
@app.on_event("startup")
async def startup():
    global bot
    print("🚀 TITAN-AI SERVER STARTING...")
    bot = BotState()
    threading.Thread(
        target=start_scheduler, daemon=True
    ).start()
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
@app.get("/")
async def root():
    return {
        "status"      : "running",
        "app"         : "TITAN-AI TRADER",
        "company"     : "TITAN-SURYA TECHNOLOGIES",
        "ist_time"    : get_ist_time(),
        "market_open" : is_market_open(),
        "bot_running" : bot.running if bot else False,
        "data_rows"   : len(bot.df)
                        if bot and bot.df is not None else 0,
        "accuracy"    : bot.model.accuracy if bot else 0,
    }


@app.get("/status")
async def get_status():
    try:
        risk = bot.order_mgr.risk
        net  = risk.daily_profit - risk.daily_loss
        try:
            nifty = bot.fetcher.get_live_price("NIFTY")
            bn    = bot.fetcher.get_live_price("BANKNIFTY")
        except:
            nifty, bn = 0, 0
        return {
            "status"        : "success",
            "bot_running"   : bot.running,
            "market_open"   : is_market_open(),
            "ist_time"      : get_ist_time(),
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
                              if bot.df is not None else 0,
            "last_signal"   : str(bot.last_signal),
            "trade_count"   : bot.trade_count,
            "timestamp"     : datetime.now().strftime(
                              "%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/signal")
async def get_signal():
    try:
        if bot.df is None:
            return {"status": "offline",
                    "message": "Data nahi mila!"}
        if not bot.model.is_trained:
            return {"status": "not_trained",
                    "message": "Model train nahi hua!"}
        signal = bot.model.predict(bot.df)
        if not signal:
            return {"status": "error",
                    "message": "Signal nahi mila!"}
        return {
            "status"       : "success",
            "ai_signal"    : signal["signal"],
            "ai_confidence": signal["confidence"],
            "rf_signal"    : signal["rf_signal"],
            "xgb_signal"   : signal["xgb_signal"],
            "market_open"  : is_market_open(),
            "ist_time"     : get_ist_time(),
            "timestamp"    : datetime.now().strftime(
                             "%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/prices")
async def get_prices():
    try:
        return {
            "status"   : "success",
            "nifty"    : bot.fetcher.get_live_price("NIFTY"),
            "banknifty": bot.fetcher.get_live_price("BANKNIFTY"),
            "ist_time" : get_ist_time(),
            "timestamp": datetime.now().strftime(
                         "%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/trade/execute")
async def execute_trade(req: TradeRequest):
    try:
        if not is_market_open():
            return {"status": "error",
                    "message": "Market band hai!"}
        if bot.df is None or not bot.model.is_trained:
            return {"status": "error",
                    "message": "Bot ready nahi!"}
        signal = bot.model.predict(bot.df)
        if not signal:
            return {"status": "error",
                    "message": "Signal nahi mila!"}
        order_id = bot.order_mgr.execute_signal(
            signal, req.symbol
        )
        if order_id:
            return {"status" : "success",
                    "order_id": order_id,
                    "signal"  : signal["signal"]}
        return {"status": "skipped",
                "message": "Conditions met nahi hui"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/trade/now")
async def trade_now():
    try:
        bot_trade()
        return {
            "status"     : "success",
            "market_open": is_market_open(),
            "ist_time"   : get_ist_time(),
            "trade_count": bot.trade_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/trade/exit/{order_id}")
async def exit_trade(order_id: str):
    try:
        result = bot.order_mgr.exit_trade(
            order_id, "MANUAL_EXIT"
        )
        return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/trades/active")
async def get_active_trades():
    try:
        trades = list(
            bot.order_mgr.risk.active_trades.values()
        )
        return {"status": "success",
                "count" : len(trades),
                "trades": trades}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/trades/history")
async def get_trade_history():
    try:
        history = bot.order_mgr.risk.trade_history
        return {"status" : "success",
                "count"  : len(history),
                "history": history[-20:]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/train")
async def manual_train():
    try:
        def train_bg():
            try:
                df = bot.fetcher.get_best_data("NIFTY")
                if df is not None:
                    bot.df = df
                if bot.df is not None:
                    acc = bot.model.train(bot.df)
                    print(f"✅ Training done: {acc:.2f}%")
            except Exception as e:
                print(f"❌ Train BG Error: {e}")

        threading.Thread(target=train_bg).start()
        return {"status" : "success",
                "message": "Training shuru!",
                "rows"   : len(bot.df)
                            if bot.df is not None else 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/settings")
async def update_settings(s: SettingsUpdate):
    try:
        bot.order_mgr.risk.stop_loss_pct = s.stop_loss
        bot.order_mgr.risk.target_pct    = s.target
        bot.order_mgr.risk.max_trades    = s.max_trades
        bot.order_mgr.risk.capital       = s.capital
        return {"status"  : "success",
                "message" : "Settings updated!",
                "settings": s.dict()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/emergency_stop")
async def emergency_stop():
    try:
        bot.order_mgr.risk.emergency_stop()
        bot.running = False
        return {"status" : "success",
                "message": "🔴 Emergency stop!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/training/history")
async def training_history():
    try:
        logs = bot.trainer.get_history()
        return {"status"       : "success",
                "best_accuracy": bot.trainer.best_acc,
                "logs"         : logs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/reconnect")
async def reconnect():
    try:
        def reconnect_bg():
            try:
                bot.fetcher.connect()
                df = bot.fetcher.get_best_data("NIFTY")
                if df is not None:
                    bot.df = df
                if bot.df is not None and \
                        not bot.model.is_trained:
                    bot.model.train(bot.df)
                bot.running = True
                print("✅ Reconnected!")
            except Exception as e:
                print(f"❌ Reconnect Error: {e}")

        threading.Thread(target=reconnect_bg).start()
        return {"status": "success",
                "message": "Reconnecting..."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(
        "api_server:app",
        host="0.0.0.0",
        port=8000,
        reload=False
    )