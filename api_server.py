# ============================================
# TITAN-AI TRADER — API Server v5.0
# TITAN-SURYA TECHNOLOGIES
# ============================================

import threading
import schedule
import time
import uvicorn
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, time as dtime, timezone, timedelta
from data_fetcher import DataFetcher
from ai_model import AIModel
from order_manager import OrderManager
from trainer import AutoTrainer
from event_filter import EventFilter
from config import TRADING, MARKET, AI, VIX

app = FastAPI(title="TITAN-AI TRADER API v5.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
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
    if now.weekday() >= 5: return False
    return dtime(9, 15) <= now.time() <= dtime(15, 30)

def can_take_new_trade():
    now = get_ist_now()
    if now.weekday() >= 5: return False
    return dtime(10, 30) <= now.time() <= dtime(13, 30)

def is_force_exit_time():
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
        self.event_filter     = None
        self.df               = None
        self.running          = False
        self.ready            = False
        self.last_signal      = None
        self.last_signal_time = None
        self.last_signal_text = "None"
        self.trade_count      = 0
        self.init_error       = None
        self.force_exited     = False
        self.gift_nifty       = None
        self.current_vix      = None

    def init_background(self):
        try:
            print("🔌 Bot background init shuru...")
            self.fetcher      = DataFetcher()
            self.model        = AIModel()
            self.order_mgr    = OrderManager()
            self.trainer      = AutoTrainer()
            self.event_filter = EventFilter()

            self.df = self.fetcher.get_best_data("NIFTY")
            self.fetcher.connect()
            self.current_vix = self.fetcher.get_vix()
            self.gift_nifty  = self.fetcher.get_gift_nifty()

            if self.df is not None:
                print(f"✅ Data: {len(self.df)} rows")
                if not self.model.load_model():
                    print("🤖 Training shuru...")
                    self.model.train(self.df)
            else:
                print("⚠️ Data nahi mila!")
                self.model.accuracy = 0.0

            self.order_mgr.fetcher = self.fetcher
            self.running = True
            self.ready   = True
            print(f"\n✅ Bot Ready! | {get_ist_time()}")
            print(f"   Market: {'OPEN 🟢' if is_market_open() else 'CLOSED 🔴'}")
            print(f"   Model:  {self.model.accuracy:.1f}%")

        except Exception as e:
            self.init_error = str(e)
            print(f"❌ Background Init Error: {e}")
            import traceback; traceback.print_exc()


bot = BotState()


# ============================================
# SCHEDULER JOBS
# ============================================
def job_token_refresh():
    """9:05 AM — Angel One token refresh"""
    print(f"\n🔄 TOKEN REFRESH | {get_ist_time()}")
    if bot.ready and bot.fetcher:
        result = bot.fetcher.reconnect()
        if result:
            print("✅ Token refreshed!")
        else:
            print("❌ Token refresh failed!")

def job_daily_reset():
    print(f"\n🌅 DAILY RESET | {get_ist_time()}")
    if bot.ready:
        bot.order_mgr.risk.daily_reset()
    bot.last_signal = None; bot.last_signal_time = None
    bot.last_signal_text = "None"; bot.trade_count = 0
    bot.force_exited = False
    print("✅ Ready for today's trading!")

def job_morning_fetch():
    try:
        if not bot.ready: return
        print(f"\n🌅 MORNING FETCH | {get_ist_time()}")
        bot.gift_nifty  = bot.fetcher.get_gift_nifty()
        bot.current_vix = bot.fetcher.get_vix()
        if bot.event_filter:
            bot.event_filter.current_vix = bot.current_vix
    except Exception as e:
        print(f"❌ Morning fetch error: {e}")

def job_refresh_data():
    try:
        if not bot.ready: return
        print(f"\n🔄 Data refresh | {get_ist_time()}")
        today_df = bot.fetcher.get_today_candles("NIFTY")
        if today_df is not None and bot.df is not None:
            combined = pd.concat([bot.df, today_df])
            combined = combined[~combined.index.duplicated(keep="last")]
            bot.df   = combined.sort_index()
            print(f"✅ Data: {len(bot.df)} rows")
    except Exception as e:
        print(f"❌ Data refresh error: {e}")

def job_monitor_trades():
    try:
        if not bot.ready: return
        if is_force_exit_time() and not bot.force_exited:
            if bot.order_mgr.risk.active_trades:
                print(f"\n⏰ FORCE EXIT | {get_ist_time()}")
                bot.order_mgr.risk.market_close_exit(bot.fetcher)
            bot.force_exited = True
            return
        if not bot.order_mgr.risk.active_trades: return
        price = bot.fetcher.get_live_price("NIFTY")
        if not price: return
        for trade_id in list(bot.order_mgr.risk.active_trades.keys()):
            result = bot.order_mgr.risk.monitor_trade(trade_id, price)
            if result in ["SL_HIT", "TARGET_HIT"]:
                bot.last_signal = None
    except Exception as e:
        print(f"❌ Monitor error: {e}")

def job_trading_cycle():
    try:
        if not bot.ready: return
        if not is_market_open(): return
        if not can_take_new_trade():
            print(f"⏰ Window closed | {get_ist_time()}")
            return
        if bot.event_filter and not bot.event_filter.is_safe_to_trade():
            print(f"⛔ {bot.event_filter.no_trade_reason}")
            return
        can, reasons = bot.order_mgr.risk.can_trade()
        if not can:
            for r in reasons: print(r)
            return
        if bot.df is None or len(bot.df) < 100:
            print("❌ Data insufficient!"); return
        signal = bot.model.predict(bot.df)
        if not signal:
            print("❌ Signal nahi mila!"); return

        sig_val = signal["value"]
        conf    = signal["confidence"]
        print(f"\n🎯 {signal['signal']} | Conf:{conf:.1f}% | {get_ist_time()}")

        if sig_val == 0: return
        if conf < AI["min_confidence"]:
            print(f"⚠️ Low conf {conf:.1f}% — Skip"); return

        now = datetime.now()
        if bot.last_signal == sig_val and bot.last_signal_time:
            mins = (now - bot.last_signal_time).seconds // 60
            if mins < 30:
                print(f"⚠️ Same signal {mins}min ago — Skip"); return

        order_id = bot.order_mgr.execute_signal(signal, "NIFTY")
        if order_id:
            bot.last_signal      = sig_val
            bot.last_signal_time = now
            bot.last_signal_text = signal["signal"]
            bot.trade_count     += 1
            print(f"✅ Trade placed! {order_id}")
        else:
            print("❌ Order place nahi hua!")

    except Exception as e:
        print(f"❌ Trading cycle error: {e}")

def job_daily_summary():
    if bot.ready:
        bot.order_mgr.risk.daily_summary()

def job_auto_train():
    if bot.ready and bot.df is not None:
        print(f"\n🤖 AUTO TRAINING | {get_ist_time()}")
        full_df = bot.fetcher.get_best_data("NIFTY")
        if full_df is not None:
            bot.df = full_df
            bot.trainer.train_once()

def run_scheduler():
    schedule.every().day.at("09:00").do(job_morning_fetch)
    schedule.every().day.at("09:05").do(job_token_refresh)    # ✅ FIX
    schedule.every().day.at("09:10").do(job_daily_reset)
    schedule.every().day.at("15:35").do(job_daily_summary)
    schedule.every().day.at("23:00").do(job_auto_train)
    schedule.every(1).minutes.do(job_monitor_trades)
    schedule.every(5).minutes.do(job_trading_cycle)
    schedule.every(30).minutes.do(job_refresh_data)
    print("\n✅ Scheduler ready!")
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
    print(f"🚀 TITAN-AI SERVER v5.0 | {get_ist_time()}")
    job_daily_reset()
    threading.Thread(target=bot.init_background, daemon=True).start()
    threading.Thread(target=run_scheduler, daemon=True).start()
    print("✅ Server started!")


# ============================================
# ENDPOINTS
# ============================================
@app.get("/")
def root():
    return {
        "status"   : "running",
        "bot"      : "TITAN-AI TRADER",
        "version"  : "5.0",
        "company"  : "TITAN-SURYA TECHNOLOGIES",
        "time_ist" : get_ist_time(),
        "market"   : "OPEN" if is_market_open() else "CLOSED",
        "bot_ready": bot.ready,
        "init_error": bot.init_error,
    }

@app.get("/health")
def health():
    return {"status": "ok", "time": get_ist_time()}

def _check_ready():
    if not bot.ready:
        raise HTTPException(status_code=503, detail="Bot initialize ho raha hai...")

@app.get("/status")
def get_status():
    if not bot.ready:
        return {"status": "initializing", "bot_ready": False,
                "message": "Bot load ho raha hai...", "time_ist": get_ist_time()}
    risk = bot.order_mgr.risk
    net  = risk.daily_profit - risk.daily_loss
    return {
        "status"            : "ok",
        "version"           : "5.0",
        "bot_ready"         : True,
        "time_ist"          : get_ist_time(),
        "market_open"       : is_market_open(),
        "can_take_new_trade": can_take_new_trade(),
        "force_exited_today": bot.force_exited,
        "mode"              : TRADING["mode"],
        "capital"           : risk.capital,
        "daily_pnl"         : round(net, 2),
        "daily_profit"      : round(risk.daily_profit, 2),
        "daily_loss"        : round(risk.daily_loss, 2),
        "trades_today"      : risk.trades_today,
        "max_trades"        : risk.max_trades,
        "active_trades"     : len(risk.active_trades),
        "ai_accuracy"       : round(bot.model.accuracy, 2),
        "data_rows"         : len(bot.df) if bot.df is not None else 0,
        "last_signal"       : bot.last_signal_text,
        "vix"               : bot.current_vix,
        "vix_safe"          : (bot.current_vix < VIX["max_vix"] if bot.current_vix else True),
        "gift_nifty"        : bot.gift_nifty,
        "event_filter"      : bot.event_filter.get_status() if bot.event_filter else {},
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
        event_safe = True; event_reason = None
        if bot.event_filter:
            event_safe   = bot.event_filter.is_safe_to_trade()
            event_reason = bot.event_filter.no_trade_reason
        return {
            "status"       : "ok",
            "signal"       : signal["signal"],
            "value"        : signal["value"],
            "confidence"   : round(signal["confidence"], 2),
            "rf_signal"    : signal["rf_signal"],
            "rf_conf"      : round(signal["rf_conf"], 2),
            "xgb_signal"   : signal["xgb_signal"],
            "xgb_conf"     : round(signal["xgb_conf"], 2),
            "lstm_signal"  : signal.get("lstm_signal"),
            "lstm_conf"    : round(signal.get("lstm_conf", 0), 2),
            "timestamp"    : signal["timestamp"],
            "market_open"  : is_market_open(),
            "can_trade_now": can_take_new_trade(),
            "event_safe"   : event_safe,
            "event_reason" : event_reason,
            "vix"          : bot.current_vix,
        }
    except HTTPException: raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/trade")
def execute_trade():
    _check_ready()
    try:
        if not is_market_open():
            return {"status": "skipped", "reason": "Market closed"}
        if not can_take_new_trade():
            return {"status": "skipped", "reason": "Window closed (10:30-13:30 only)"}
        if bot.event_filter and not bot.event_filter.is_safe_to_trade():
            return {"status": "skipped", "reason": bot.event_filter.no_trade_reason}
        can, reasons = bot.order_mgr.risk.can_trade()
        if not can:
            return {"status": "skipped", "reason": reasons[0]}
        signal = bot.model.predict(bot.df)
        if not signal:
            return {"status": "error", "reason": "Signal failed"}
        if signal["value"] == 0:
            return {"status": "skipped", "reason": "NO TRADE — models disagree"}
        if signal["confidence"] < AI["min_confidence"]:
            return {"status": "skipped", "reason": f"Low conf: {signal['confidence']:.1f}%"}
        order_id = bot.order_mgr.execute_signal(signal, "NIFTY")
        if order_id:
            bot.last_signal = signal["value"]
            bot.last_signal_time = datetime.now()
            bot.last_signal_text = signal["signal"]
            bot.trade_count += 1
            return {"status": "ok", "order_id": order_id,
                    "signal": signal["signal"], "conf": signal["confidence"]}
        return {"status": "error", "reason": "Order failed"}
    except HTTPException: raise
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
        "total_return"  : round((risk.capital - risk.start_capital) / risk.start_capital * 100, 2),
        "daily_pnl"     : round(risk.daily_profit - risk.daily_loss, 2),
        "active_trades" : len(risk.active_trades),
        "active_details": [
            {"id": t["id"][-16:], "symbol": t["symbol"], "signal": t["signal"],
             "entry": t["entry_price"], "sl": t["sl"], "target": t["target"],
             "entry_time": t["entry_time"]}
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
        "status": "ok",
        "total" : len(risk.trade_history),
        "trades": [
            {"id": t.get("id", "")[-16:], "symbol": t.get("symbol"),
             "signal": t.get("signal"), "entry": t.get("entry_price"),
             "exit": t.get("exit_price"), "pnl": t.get("pnl"),
             "reason": t.get("reason"), "entry_time": t.get("entry_time"),
             "exit_time": t.get("exit_time")}
            for t in history
        ],
    }

@app.get("/events")
def get_events():
    _check_ready()
    if not bot.event_filter:
        return {"status": "error", "reason": "Event filter not initialized"}
    safe = bot.event_filter.is_safe_to_trade()
    return {
        "status"         : "ok",
        "safe_to_trade"  : safe,
        "no_trade_reason": bot.event_filter.no_trade_reason,
        "details"        : bot.event_filter.get_status(),
        "vix"            : bot.current_vix,
        "gift_nifty"     : bot.gift_nifty,
    }

@app.get("/close-all")
def close_all():
    _check_ready()
    count = len(bot.order_mgr.risk.active_trades)
    bot.order_mgr.risk.market_close_exit(bot.fetcher)
    bot.force_exited = True
    return {"status": "ok", "message": f"{count} trade(s) closed!", "time": get_ist_time()}

@app.get("/train")
def trigger_train():
    _check_ready()
    try:
        if bot.df is None:
            raise HTTPException(status_code=503, detail="No data")
        acc = bot.model.train(bot.df)
        return {"status": "ok", "accuracy": round(acc, 2), "message": "Training complete!"}
    except HTTPException: raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/emergency-stop")
def emergency_stop():
    if bot.ready:
        bot.order_mgr.risk.emergency_stop()
    bot.running = False
    return {"status": "ok", "message": "Emergency stop!"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)