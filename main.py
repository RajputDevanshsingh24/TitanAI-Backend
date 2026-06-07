# ============================================
# TITAN-AI TRADER — Main Bot v3.0
# TITAN-SURYA TECHNOLOGIES
#
# FIX v3.0:
# - refresh_token() method added
# - Daily 9:05 AM auto token refresh scheduled
# ============================================

import schedule
import time
import threading
from datetime import datetime, timezone, timedelta
from data_fetcher import DataFetcher
from ai_model import AIModel
from order_manager import OrderManager
from trainer import AutoTrainer
from event_filter import EventFilter
from config import TRADING, MARKET, AI

# ============================================
# IST TIME HELPERS
# ============================================
def get_ist_now():
    ist = timezone(timedelta(hours=5, minutes=30))
    return datetime.now(ist)

def get_ist_time():
    return get_ist_now().strftime("%H:%M:%S %d-%m-%Y")

def is_market_open():
    from datetime import time as dtime
    now = get_ist_now()
    if now.weekday() >= 5:
        return False
    return dtime(9, 15) <= now.time() <= dtime(15, 30)

def can_take_new_trade():
    from datetime import time as dtime
    now = get_ist_now()
    if now.weekday() >= 5:
        return False
    return dtime(10, 30) <= now.time() <= dtime(13, 30)

def is_force_exit_time():
    from datetime import time as dtime
    return get_ist_now().time() >= dtime(15, 20)


# ============================================
# MAIN BOT CLASS
# ============================================
class TitanBot:

    def __init__(self):
        print("\n" + "="*50)
        print("🤖 TITAN-AI TRADER v3.0")
        print("   TITAN-SURYA TECHNOLOGIES")
        print("="*50)

        self.fetcher      = DataFetcher()
        self.model        = AIModel()
        self.order_mgr    = OrderManager()
        self.trainer      = AutoTrainer()
        self.event_filter = EventFilter()
        self.df           = None
        self.running      = False
        self.force_exited = False
        self.last_signal  = None
        self.last_signal_time = None

    # ============================================
    # REFRESH TOKEN — Daily 9:05 AM
    # ============================================
    def refresh_token(self):
        """Daily 9:05 AM — Angel One token refresh"""
        print("\n" + "="*50)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print("🔄 TOKEN REFRESH — " + now_str)
        print("="*50)
        result = self.fetcher.reconnect()
        if result:
            print("✅ Token refreshed! Trading ready.")
        else:
            print("❌ Token refresh failed! Angel One credentials check karo.")
        return result

    # ============================================
    # DAILY RESET — 9:10 AM
    # ============================================
    def daily_reset(self):
        print(f"\n🌅 DAILY RESET | {get_ist_time()}")
        self.order_mgr.risk.daily_reset()
        self.last_signal      = None
        self.last_signal_time = None
        self.force_exited     = False
        print("✅ Ready for today's trading!")

    # ============================================
    # STATUS
    # ============================================
    def show_status(self):
        risk = self.order_mgr.risk
        net  = risk.daily_profit - risk.daily_loss
        print(f"\n{'='*50}")
        print(f"📊 BOT STATUS | {get_ist_time()}")
        print(f"{'='*50}")
        print(f"   Market:       {'OPEN 🟢' if is_market_open() else 'CLOSED 🔴'}")
        print(f"   Can Trade:    {'YES ✅' if can_take_new_trade() else 'NO ❌'}")
        print(f"   Capital:      ₹{risk.capital:,.0f}")
        print(f"   Daily P&L:    ₹{net:+,.0f}")
        print(f"   Trades Today: {risk.trades_today}/{risk.max_trades}")
        print(f"   Active:       {len(risk.active_trades)}")
        print(f"   AI Accuracy:  {self.model.accuracy:.1f}%")
        print(f"   Data Rows:    {len(self.df) if self.df is not None else 0}")
        print(f"{'='*50}")

    # ============================================
    # DATA REFRESH — Har 30 min
    # ============================================
    def refresh_data(self):
        try:
            print(f"\n📊 Data refresh ho raha hai...")
            today_df = self.fetcher.get_today_candles("NIFTY")
            if today_df is not None and self.df is not None:
                import pandas as pd
                combined  = pd.concat([self.df, today_df])
                combined  = combined[~combined.index.duplicated(keep="last")]
                self.df   = combined.sort_index()
                print(f"✅ Data updated: {len(self.df)} rows")
        except Exception as e:
            print(f"❌ Data refresh error: {e}")

    # ============================================
    # TRADING CYCLE — Har 5 min
    # ============================================
    def trading_cycle(self):
        try:
            if not is_market_open():
                return
            if not can_take_new_trade():
                print(f"⏰ Trading window closed | {get_ist_time()}")
                return

            # Event filter
            if not self.event_filter.is_safe_to_trade():
                print(f"⛔ Event filter: {self.event_filter.no_trade_reason}")
                return

            # Risk check
            can, reasons = self.order_mgr.risk.can_trade()
            if not can:
                for r in reasons: print(r)
                return

            if self.df is None or len(self.df) < 100:
                print("❌ Data insufficient!")
                return

            # Signal
            signal = self.model.predict(self.df)
            if not signal:
                print("❌ Signal nahi mila!")
                return

            sig_val = signal["value"]
            conf    = signal["confidence"]

            print(f"\n{'='*40}")
            print(f"🎯 {signal['signal']}")
            print(f"   Conf: {conf:.1f}% | Time: {get_ist_time()}")
            print(f"{'='*40}")

            if sig_val == 0:
                print("🟡 Models disagree — Skip")
                return

            if conf < AI["min_confidence"]:
                print(f"⚠️ Low confidence {conf:.1f}% — Skip")
                return

            # Duplicate signal check (30-min window)
            now = datetime.now()
            if self.last_signal == sig_val and self.last_signal_time:
                mins = (now - self.last_signal_time).seconds // 60
                if mins < 30:
                    print(f"⚠️ Same signal {mins} min pehle — Skip")
                    return

            # Trade execute!
            order_id = self.order_mgr.execute_signal(signal, "NIFTY")
            if order_id:
                self.last_signal      = sig_val
                self.last_signal_time = now
                print(f"✅ Trade placed! {order_id}")
            else:
                print("❌ Order place nahi hua!")

        except Exception as e:
            print(f"❌ Trading cycle error: {e}")

    # ============================================
    # MONITOR TRADES — Har 1 min
    # ============================================
    def monitor_trades(self):
        try:
            # Force exit 3:20 PM
            if is_force_exit_time() and not self.force_exited:
                if self.order_mgr.risk.active_trades:
                    print(f"\n⏰ FORCE EXIT | {get_ist_time()}")
                    self.order_mgr.risk.market_close_exit(self.fetcher)
                self.force_exited = True
                return

            if not self.order_mgr.risk.active_trades:
                return

            price = self.fetcher.get_live_price("NIFTY")
            if not price:
                return

            for trade_id in list(self.order_mgr.risk.active_trades.keys()):
                result = self.order_mgr.risk.monitor_trade(trade_id, price)
                if result in ["SL_HIT", "TARGET_HIT"]:
                    self.last_signal = None

        except Exception as e:
            print(f"❌ Monitor error: {e}")

    # ============================================
    # START
    # ============================================
    def start(self):
        print(f"\n🚀 BOT STARTING!")

        if not self.fetcher.connect():
            print("❌ Connection failed!")
            print("⚠️ Paper mode mein start ho raha hai...")

        self.order_mgr.fetcher = self.fetcher
        self.df = self.fetcher.get_best_data("NIFTY")

        if self.df is not None:
            print(f"✅ Data: {len(self.df)} rows")
            if not self.model.load_model():
                print("🤖 Training shuru karta hun...")
                self.model.train(self.df)
        else:
            print("⚠️ Data nahi mila!")

        self.show_status()

        # ============================================
        # SCHEDULER
        # ============================================
        schedule.every().day.at("09:05").do(self.refresh_token)   # ✅ FIX: Daily token refresh
        schedule.every().day.at("09:10").do(self.daily_reset)
        schedule.every().day.at("15:35").do(self.order_mgr.risk.daily_summary)
        schedule.every().day.at("23:00").do(self.trainer.train_once)

        schedule.every(5).minutes.do(self.trading_cycle)
        schedule.every(1).minutes.do(self.monitor_trades)
        schedule.every(30).minutes.do(self.refresh_data)

        print("\n✅ Scheduler ready!")
        print("   09:05 → Token refresh")
        print("   09:10 → Daily reset")
        print("   10:30-13:30 → Trading window")
        print("   15:20 → Force exit")
        print("   23:00 → AI retrain")
        print("   Har 5 min → Signal + Trade")
        print("   Har 1 min → Monitor")

        self.running = True

        while self.running:
            try:
                schedule.run_pending()
                time.sleep(30)
            except KeyboardInterrupt:
                print("\n\n🛑 Bot stopped by user!")
                self.order_mgr.risk.emergency_stop()
                break
            except Exception as e:
                print(f"❌ Main loop error: {e}")
                time.sleep(60)


# ============================================
# ENTRY POINT
# ============================================
if __name__ == "__main__":
    bot = TitanBot()
    bot.start()