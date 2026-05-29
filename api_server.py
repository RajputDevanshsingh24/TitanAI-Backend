# ============================================
# TITAN-AI TRADER — API Server FINAL v3.0
# TITAN-SURYA TECHNOLOGIES
#
# RAILWAY FIX: BotState ab background mein load hoga
# Server turant start hoga — Railway timeout nahi karega
# Bot ready hone se pehle endpoints "initializing" return karenge
# ============================================

import threading
import schedule
import time
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, time as dtime, timezone, timedelta
from data_fetcher import DataFetcher
from ai_model import AIModel
from order_manager import OrderManager
from trainer import AutoTrainer
from config import TRADING

app = FastAPI(title="TITAN-AI TRADER API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def is_market_open():
    try:
        ist     = timezone(timedelta(hours=5, minutes=30))
        now     = datetime.now(ist)
        if now.weekday() >= 5:
            return False
        return dtime(9, 15) <= now.time() <= dtime(15, 30)
    except:
        return False

def get_ist_time():
    ist = timezone(timedelta(hours=5, minutes=30))
    return datetime.now(ist).strftime("%H:%M:%S %d-%m-%Y")


class BotState:
    def __init__(self):
        self.fetcher          = None
        self.model            = None
        self.order_mgr        = None
        self.trainer          = None
        self.df               = None
        self.running          = False
        self.ready            = False   # Background init complete?
        self.last_signal      = None
        self.last_signal_time = None
        self.trade_count      = 0
        self.init_error       = None

    def init_background(self):
        """Yeh background thread mein chalega — Railway timeout nahi karega."""
        try:
            print("🔌 Bot background init shuru...")
            print(f"⏰ IST: {get_ist_time()}")

            self.fetcher   = DataFetcher()
            self.model     = AIModel()
            self.order_mgr = OrderManager()
            self.trainer   = AutoTrainer()

            self.df = self.fetcher.get_best_data("NIFTY")
            self.fetcher.connect()

            if self.df is not None:
                print(f"✅ Data: {len(self.df)} rows")
                if not self.model.load_model():
                    print("🤖 Training shuru...")
                    self.model.train(self.df)
            else:
                print("⚠️ Data nahi mila!")
                self.model.accuracy = 0.0

            self.order_mgr.fetcher = self.fetcher
            self.running           = True
            self.ready             = True

            print("✅ Bot Background Init Complete!")
            print(f"   Market: {'OPEN 🟢' if is_market_open() else 'CLOSED 🔴'}")
            print(f"   Data:   {len(self.df) if self.df is not None else 0} rows")
            print(f"   Model:  {self.model.accuracy:.1f}%")

        except Exception as e:
            self.init_error = str(e)
            print(f"❌ Background Init Error: {e}")
            import traceback; traceback.print_exc()


bot = BotState()


def run_scheduler():
    def trading_cycle():
        try:
            if not bot.ready or not is_market_open():
                return
            if bot.df is None:
                return
            can, reasons = bot.order_mgr.risk.can_trade()
            if not can:
                for r in reasons: print(r)
                return
            signal = bot.model.predict(bot.df)
            if not signal or signal["value"] == 0:
                return
            current_time = datetime.now()
            if (bot.last_signal == signal["value"] and
                    bot.last_signal_time is not None):
                mins = (current_time - bot.last_signal_time).seconds // 60
                if mins < 30:
                    return
            if signal["confidence"] < 55:
                return
            order_id = bot.order_mgr.execute_signal(signal, "NIFTY")
            if order_id:
                bot.last_signal      = signal["value"]
                bot.last_signal_time = current_time
                bot.trade_count     += 1
        except Exception as e:
            print(f"❌ Scheduler cycle error: {e}")

    def monitor_trades():
        try:
            if not bot.ready or not bot.order_mgr.risk.active_trades:
                return
            price = bot.fetcher.get_live_price("NIFTY")
            if not price:
                return
            for trade_id in list(bot.order_mgr.risk.active_trades.keys()):
                result = bot.order_mgr.risk.monitor_trade(trade_id, price)
                if result in ["SL_HIT", "TARGET_HIT"]:
                    bot.last_signal = None
        except Exception as e:
            print(f"❌ Monitor error: {e}")

    def refresh_data():
        try:
            if not bot.ready:
                return
            new_df = bot.fetcher.get_best_data("NIFTY")
            if new_df is not None:
                bot.df = new_df
                print(f"✅ Data refreshed: {len(bot.df)} rows")
        except Exception as e:
            print(f"❌ Refresh error: {e}")

    def daily_reset():
        if not bot.ready:
            return
        bot.order_mgr.risk.daily_summary()
        bot.order_mgr.risk.daily_reset()
        bot.last_signal      = None
        bot.last_signal_time = None
        bot.trade_count      = 0
        print("✅ Daily reset done!")

    schedule.every(5).minutes.do(trading_cycle)
    schedule.every(1).minutes.do(monitor_trades)
    schedule.every(30).minutes.do(refresh_data)
    schedule.every().day.at("09:10").do(daily_reset)
    schedule.every().day.at("15:35").do(
        lambda: bot.order_mgr.risk.daily_summary() if bot.ready else None
    )
    schedule.every().day.at("23:00").do(
        lambda: bot.trainer.train_once() if bot.ready else None
    )

    while True:
        try:
            schedule.run_pending()
        except Exception as e:
            print(f"❌ Scheduler error: {e}")
        time.sleep(30)


@app.on_event("startup")
async def startup():
    print("🚀 TITAN-AI SERVER STARTING...")
    print(f"⏰ IST: {get_ist_time()}")
    # Bot init aur scheduler — dono background mein
    threading.Thread(target=bot.init_background, daemon=True).start()
    threading.Thread(target=run_scheduler,        daemon=True).start()
    print("✅ Server Ready! Bot background mein load ho raha hai...")


@app.get("/")
def root():
    return {
        "status"     : "running",
        "bot"        : "TITAN-AI TRADER",
        "company"    : "TITAN-SURYA TECHNOLOGIES",
        "time_ist"   : get_ist_time(),
        "market"     : "OPEN" if is_market_open() else "CLOSED",
        "bot_ready"  : bot.ready,
        "init_error" : bot.init_error,
    }

@app.get("/health")
def health():
    return {"status": "ok", "time": get_ist_time()}

def _check_ready():
    if not bot.ready:
        raise HTTPException(
            status_code=503,
            detail="Bot abhi initialize ho raha hai, thoda wait karo..."
        )

@app.get("/status")
def get_status():
    if not bot.ready:
        return {
            "status"    : "initializing",
            "bot_ready" : False,
            "message"   : "Bot load ho raha hai...",
            "time_ist"  : get_ist_time(),
        }
    risk = bot.order_mgr.risk
    return {
        "status"       : "ok",
        "bot_ready"    : True,
        "market_open"  : is_market_open(),
        "bot_running"  : bot.running,
        "mode"         : TRADING["mode"],
        "capital"      : risk.capital,
        "daily_pnl"    : risk.daily_profit - risk.daily_loss,
        "daily_profit" : risk.daily_profit,
        "daily_loss"   : risk.daily_loss,
        "trades_today" : risk.trades_today,
        "max_trades"   : risk.max_trades,
        "ai_accuracy"  : round(bot.model.accuracy, 2),
        "data_rows"    : len(bot.df) if bot.df is not None else 0,
        "last_signal"  : bot.last_signal,
        "time_ist"     : get_ist_time(),
    }

@app.get("/signal")
def get_signal():
    _check_ready()
    try:
        if bot.df is None:
            raise HTTPException(status_code=503, detail="Data not loaded")
        if not bot.model.is_trained:
            raise HTTPException(status_code=503, detail="Model not trained")
        signal = bot.model.predict(bot.df)
        if not signal:
            raise HTTPException(status_code=500, detail="Signal generation failed")
        return {
            "status"     : "ok",
            "signal"     : signal["signal"],
            "value"      : signal["value"],
            "confidence" : round(signal["confidence"], 2),
            "rf_signal"  : signal["rf_signal"],
            "xgb_signal" : signal["xgb_signal"],
            "rf_conf"    : round(signal["rf_conf"],  2),
            "xgb_conf"   : round(signal["xgb_conf"], 2),
            "timestamp"  : signal["timestamp"],
            "market_open": is_market_open(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/trade")
def execute_trade():
    _check_ready()
    try:
        if not is_market_open():
            return {"status": "skipped", "reason": "Market closed"}
        can, reasons = bot.order_mgr.risk.can_trade()
        if not can:
            return {"status": "skipped", "reason": reasons[0]}
        signal = bot.model.predict(bot.df)
        if not signal:
            return {"status": "error", "reason": "Signal failed"}
        if signal["value"] == 0:
            return {"status": "skipped", "reason": "NO TRADE — models disagree"}
        if signal["confidence"] < 55:
            return {"status": "skipped", "reason": f"Low confidence: {signal['confidence']:.1f}%"}
        order_id = bot.order_mgr.execute_signal(signal, "NIFTY")
        if order_id:
            bot.last_signal      = signal["value"]
            bot.last_signal_time = datetime.now()
            bot.trade_count     += 1
            return {"status": "ok", "order_id": order_id, "signal": signal["signal"]}
        return {"status": "error", "reason": "Order failed"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/portfolio")
def get_portfolio():
    _check_ready()
    risk = bot.order_mgr.risk
    return {
        "status"        : "ok",
        "capital"       : risk.capital,
        "start_capital" : risk.start_capital,
        "total_return"  : round(
            (risk.capital - risk.start_capital) / risk.start_capital * 100, 2
        ),
        "daily_pnl"     : risk.daily_profit - risk.daily_loss,
        "active_trades" : len(risk.active_trades),
        "trade_history" : len(risk.trade_history),
        "trades_today"  : risk.trades_today,
        "bot_active"    : risk.bot_active,
    }

@app.get("/history")
def get_history():
    _check_ready()
    risk    = bot.order_mgr.risk
    history = risk.trade_history[-20:]
    return {
        "status" : "ok",
        "total"  : len(risk.trade_history),
        "trades" : [
            {
                "id"         : t.get("id"),
                "symbol"     : t.get("symbol"),
                "signal"     : t.get("signal"),
                "entry"      : t.get("entry_price"),
                "exit"       : t.get("exit_price"),
                "pnl"        : t.get("pnl"),
                "reason"     : t.get("reason"),
                "entry_time" : t.get("entry_time"),
                "exit_time"  : t.get("exit_time"),
            }
            for t in history
        ],
    }

@app.get("/train")
def trigger_training():
    _check_ready()
    try:
        if bot.df is None:
            raise HTTPException(status_code=503, detail="No data available")
        accuracy = bot.model.train(bot.df)
        return {"status": "ok", "accuracy": round(accuracy, 2), "message": "Training complete!"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/emergency-stop")
def emergency_stop():
    if bot.ready:
        bot.order_mgr.risk.emergency_stop()
    bot.running = False
    return {"status": "ok", "message": "Emergency stop activated!"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)