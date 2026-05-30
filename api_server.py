# ============================================
# TITAN-AI TRADER — API Server FINAL v4.0
# TITAN-SURYA TECHNOLOGIES
#
# FULL AUTO FLOW:
# 09:10 → Daily reset
# 09:20 → Trading window open
# Har 1 min → Monitor (SL/Target auto close)
# Har 5 min → Naya signal + trade
# 14:30 → Naya trade band
# 15:20 → Force exit sab open trades
# 15:35 → Daily summary (P&L result)
# 23:00 → AI retrain
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
from config import TRADING, MARKET, AI

app = FastAPI(title="TITAN-AI TRADER API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# TIME HELPERS
# ============================================
def get_ist_now():
    ist = timezone(timedelta(hours=5, minutes=30))
    return datetime.now(ist)

def get_ist_time():
    return get_ist_now().strftime("%H:%M:%S %d-%m-%Y")

def is_market_open():
    now = get_ist_now()
    if now.weekday() >= 5:
        return False
    return dtime(9, 15) <= now.time() <= dtime(15, 30)

def can_take_new_trade():
    """New trade sirf 9:20 AM se 2:30 PM ke beech."""
    now = get_ist_now()
    if now.weekday() >= 5:
        return False
    return dtime(9, 20) <= now.time() <= dtime(14, 30)

def is_force_exit_time():
    """3:20 PM ke baad force exit."""
    return get_ist_now().time() >= dtime(15, 20)


# ============================================
# BOT STATE
# ============================================
class BotState:
    def __init__(self):
        self.fetcher          = None
        self.model            = None
        self.order_mgr        = None
        self.trainer          = None
        self.df               = None
        self.running          = False
        self.ready            = False
        self.last_signal      = None
        self.last_signal_time = None
        self.last_signal_text = "None"
        self.trade_count      = 0
        self.init_error       = None
        self.force_exited     = False  # 3:20 PM force exit aaj hua?

    def init_background(self):
        """Railway timeout se bachne ke liye background mein init."""
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

            print(f"\n✅ Bot Ready!")
            print(f"   IST:       {get_ist_time()}")
            print(f"   Market:    {'OPEN 🟢' if is_market_open() else 'CLOSED 🔴'}")
            print(f"   Can Trade: {'YES ✅' if can_take_new_trade() else 'NO ❌'}")
            print(f"   Data:      {len(self.df) if self.df is not None else 0} rows")
            print(f"   Model:     {self.model.accuracy:.1f}%")

        except Exception as e:
            self.init_error = str(e)
            print(f"❌ Background Init Error: {e}")
            import traceback; traceback.print_exc()


bot = BotState()


# ============================================
# SCHEDULER JOBS
# ============================================

def job_daily_reset():
    """9:10 AM — nayi subah reset."""
    print(f"\n🌅 DAILY RESET | {get_ist_time()}")
    if bot.ready:
        bot.order_mgr.risk.daily_reset()
    bot.last_signal      = None
    bot.last_signal_time = None
    bot.last_signal_text = "None"
    bot.trade_count      = 0
    bot.force_exited     = False
    print("✅ Ready for today's trading!")


def job_refresh_data():
    """Har 30 min — latest data lo."""
    try:
        if not bot.ready:
            return
        new_df = bot.fetcher.get_best_data("NIFTY")
        if new_df is not None:
            bot.df = new_df
            print(f"\n✅ Data refreshed: {len(bot.df)} rows | {get_ist_time()}")
    except Exception as e:
        print(f"❌ Data refresh error: {e}")


def job_monitor_trades():
    """
    Har 1 min — open trades monitor karo.
    SL/Target hit → auto close.
    3:20 PM → force exit sab.
    """
    try:
        if not bot.ready:
            return

        # 3:20 PM force exit
        if is_force_exit_time() and not bot.force_exited:
            if bot.order_mgr.risk.active_trades:
                print(f"\n⏰ FORCE EXIT | {get_ist_time()}")
                bot.order_mgr.risk.market_close_exit(bot.fetcher)
            else:
                print(f"\n✅ 3:20 PM — No open trades.")
            bot.force_exited = True
            return

        # Normal monitoring
        if not bot.order_mgr.risk.active_trades:
            return

        price = bot.fetcher.get_live_price("NIFTY")
        if not price:
            return

        print(f"\n⏰ {get_ist_time()} | NIFTY: ₹{price:,.2f} | "
              f"Open: {len(bot.order_mgr.risk.active_trades)}")

        for trade_id in list(bot.order_mgr.risk.active_trades.keys()):
            result = bot.order_mgr.risk.monitor_trade(trade_id, price)
            if result in ["SL_HIT", "TARGET_HIT"]:
                print(f"\n🔔 Auto closed: {result}")
                bot.last_signal = None  # Next cycle mein fresh signal lo

    except Exception as e:
        print(f"❌ Monitor error: {e}")


def job_trading_cycle():
    """
    Har 5 min — signal dekho, trade lo.
    Sirf 9:20 AM – 2:30 PM ke beech.
    """
    try:
        if not bot.ready:
            return

        # Market open nahi
        if not is_market_open():
            return

        # Trading window check
        if not can_take_new_trade():
            print(f"⏰ Trading window closed | {get_ist_time()}")
            return

        # Risk check
        can, reasons = bot.order_mgr.risk.can_trade()
        if not can:
            for r in reasons:
                print(r)
            return

        # Data check
        if bot.df is None:
            print("❌ Data nahi hai!")
            return

        # Signal lo
        signal = bot.model.predict(bot.df)
        if not signal:
            print("❌ Signal nahi mila!")
            return

        sig_val  = signal["value"]
        sig_text = signal["signal"]
        conf     = signal["confidence"]

        print(f"\n{'='*40}")
        print(f"🎯 {sig_text}")
        print(f"   Conf: {conf:.1f}% | {get_ist_time()}")
        print(f"{'='*40}")

        # NO TRADE
        if sig_val == 0:
            print("🟡 Models disagree — Skip")
            return

        # Low confidence
        if conf < AI["min_confidence"]:
            print(f"⚠️ Confidence {conf:.1f}% < {AI['min_confidence']}% — Skip")
            return

        # Same signal 30-min window
        current_time = datetime.now()
        if (bot.last_signal == sig_val and bot.last_signal_time is not None):
            mins = (current_time - bot.last_signal_time).seconds // 60
            if mins < 30:
                print(f"⚠️ Same signal {mins} min pehle tha — Skip")
                return
            else:
                print(f"ℹ️ Same direction — {mins} min baad, allowing")

        # TRADE LO!
        order_id = bot.order_mgr.execute_signal(signal, "NIFTY")
        if order_id:
            bot.last_signal      = sig_val
            bot.last_signal_time = current_time
            bot.last_signal_text = sig_text
            bot.trade_count     += 1
            print(f"✅ Trade placed! {order_id}")
        else:
            print("❌ Order place nahi hua!")

    except Exception as e:
        print(f"❌ Trading cycle error: {e}")


def job_daily_summary():
    """3:35 PM — aaj ka final result."""
    if bot.ready:
        print(f"\n📊 END OF DAY | {get_ist_time()}")
        bot.order_mgr.risk.daily_summary()


def job_auto_train():
    """11 PM — agle din ke liye model retrain."""
    if bot.ready and bot.df is not None:
        print(f"\n🤖 AUTO TRAINING | {get_ist_time()}")
        bot.trainer.train_once()


# ============================================
# SCHEDULER RUNNER
# ============================================
def run_scheduler():
    # Daily fixed times
    schedule.every().day.at("09:10").do(job_daily_reset)
    schedule.every().day.at("15:35").do(job_daily_summary)
    schedule.every().day.at("23:00").do(job_auto_train)

    # Frequent jobs
    schedule.every(1).minutes.do(job_monitor_trades)
    schedule.every(5).minutes.do(job_trading_cycle)
    schedule.every(30).minutes.do(job_refresh_data)

    print("\n✅ Scheduler ready!")
    print("   09:10 → Daily reset")
    print("   09:20-14:30 → Trading window")
    print("   15:20 → Force exit all trades")
    print("   15:35 → Daily summary")
    print("   23:00 → AI retrain")
    print("   Har 1 min → Monitor trades")
    print("   Har 5 min → Signal + Trade")

    while True:
        try:
            schedule.run_pending()
        except Exception as e:
            print(f"❌ Scheduler error: {e}")
        time.sleep(30)


# ============================================
# FASTAPI STARTUP
# ============================================
@app.on_event("startup")
async def startup():
    print(f"🚀 TITAN-AI SERVER STARTING | {get_ist_time()}")
    threading.Thread(target=bot.init_background, daemon=True).start()
    threading.Thread(target=run_scheduler,        daemon=True).start()
    print("✅ Server started! Bot background mein load ho raha hai...")


# ============================================
# ENDPOINTS
# ============================================

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
    """Railway health check."""
    return {"status": "ok", "time": get_ist_time()}

def _check_ready():
    if not bot.ready:
        raise HTTPException(status_code=503,
            detail="Bot initialize ho raha hai, thoda wait karo...")

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
    net  = risk.daily_profit - risk.daily_loss

    return {
        "status"             : "ok",
        "bot_ready"          : True,
        "time_ist"           : get_ist_time(),
        "market_open"        : is_market_open(),
        "can_take_new_trade" : can_take_new_trade(),
        "force_exited_today" : bot.force_exited,
        "mode"               : TRADING["mode"],
        "capital"            : risk.capital,
        "daily_pnl"          : round(net, 2),
        "daily_profit"       : round(risk.daily_profit, 2),
        "daily_loss"         : round(risk.daily_loss, 2),
        "trades_today"       : risk.trades_today,
        "max_trades"         : risk.max_trades,
        "active_trades"      : len(risk.active_trades),
        "ai_accuracy"        : round(bot.model.accuracy, 2),
        "data_rows"          : len(bot.df) if bot.df is not None else 0,
        "last_signal"        : bot.last_signal_text,
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
            "status"           : "ok",
            "signal"           : signal["signal"],
            "value"            : signal["value"],
            "confidence"       : round(signal["confidence"], 2),
            "rf_signal"        : signal["rf_signal"],
            "xgb_signal"       : signal["xgb_signal"],
            "rf_conf"          : round(signal["rf_conf"],  2),
            "xgb_conf"         : round(signal["xgb_conf"], 2),
            "timestamp"        : signal["timestamp"],
            "market_open"      : is_market_open(),
            "can_trade_now"    : can_take_new_trade(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/trade")
def execute_trade():
    """Manual trade trigger."""
    _check_ready()
    try:
        if not is_market_open():
            return {"status": "skipped", "reason": "Market closed"}
        if not can_take_new_trade():
            return {"status": "skipped", "reason": "Trading window closed (after 14:30)"}

        can, reasons = bot.order_mgr.risk.can_trade()
        if not can:
            return {"status": "skipped", "reason": reasons[0]}

        signal = bot.model.predict(bot.df)
        if not signal:
            return {"status": "error", "reason": "Signal failed"}
        if signal["value"] == 0:
            return {"status": "skipped", "reason": "NO TRADE — models disagree"}
        if signal["confidence"] < AI["min_confidence"]:
            return {"status": "skipped",
                    "reason": f"Low confidence: {signal['confidence']:.1f}%"}

        order_id = bot.order_mgr.execute_signal(signal, "NIFTY")
        if order_id:
            bot.last_signal      = signal["value"]
            bot.last_signal_time = datetime.now()
            bot.last_signal_text = signal["signal"]
            bot.trade_count     += 1
            return {
                "status"   : "ok",
                "order_id" : order_id,
                "signal"   : signal["signal"],
                "conf"     : signal["confidence"],
            }
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
        "daily_pnl"     : round(risk.daily_profit - risk.daily_loss, 2),
        "active_trades" : len(risk.active_trades),
        "active_details": [
            {
                "id"        : t["id"][-16:],
                "symbol"    : t["symbol"],
                "signal"    : t["signal"],
                "entry"     : t["entry_price"],
                "sl"        : t["sl"],
                "target"    : t["target"],
                "entry_time": t["entry_time"],
            }
            for t in risk.active_trades.values()
        ],
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
                "id"        : t.get("id", "")[-16:],
                "symbol"    : t.get("symbol"),
                "signal"    : t.get("signal"),
                "entry"     : t.get("entry_price"),
                "exit"      : t.get("exit_price"),
                "pnl"       : t.get("pnl"),
                "reason"    : t.get("reason"),
                "entry_time": t.get("entry_time"),
                "exit_time" : t.get("exit_time"),
            }
            for t in history
        ],
    }

@app.get("/close-all")
def close_all_trades():
    """Manual force close — sab trades band karo."""
    _check_ready()
    count = len(bot.order_mgr.risk.active_trades)
    bot.order_mgr.risk.market_close_exit(bot.fetcher)
    bot.force_exited = True
    return {
        "status"  : "ok",
        "message" : f"{count} trade(s) closed!",
        "time"    : get_ist_time(),
    }

@app.get("/train")
def trigger_training():
    _check_ready()
    try:
        if bot.df is None:
            raise HTTPException(status_code=503, detail="No data available")
        accuracy = bot.model.train(bot.df)
        return {
            "status"   : "ok",
            "accuracy" : round(accuracy, 2),
            "message"  : "Training complete!",
        }
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