# ============================================
# TITAN-AI TRADER — Main Bot Engine FIXED v2.0
# TITAN-SURYA TECHNOLOGIES
#
# BUG FIX: last_signal ab (value, direction) dono store karta hai
# Pehle sirf value compare hoti thi — same direction ke naye
# valid signals bhi skip ho jaate the
# ============================================

import time
import schedule
from datetime import datetime, time as dtime
from data_fetcher import DataFetcher
from ai_model import AIModel
from order_manager import OrderManager
from trainer import AutoTrainer
from config import TRADING


class TitanAIBot:

    def __init__(self):
        print("\n" + "="*50)
        print("🚀 TITAN-AI TRADER STARTING...")
        print("   TITAN-SURYA TECHNOLOGIES")
        print("="*50)

        self.fetcher     = DataFetcher()
        self.model       = AIModel()
        self.order_mgr   = OrderManager()
        self.trainer     = AutoTrainer()
        self.is_running  = False
        self.mode        = TRADING["mode"]
        self.df          = None
        self.last_signal = None   # Last executed signal value
        self.last_signal_time = None  # Uski timestamp
        self.trade_count = 0

        print(f"\n✅ Bot Initialized!")
        print(f"   Mode: {'📄 PAPER' if self.mode == 'PAPER' else '💰 LIVE'}")
        print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    def is_market_open(self):
        now     = datetime.now()
        weekday = now.weekday()
        if weekday >= 5:
            return False
        market_open  = dtime(9, 15)
        market_close = dtime(15, 30)
        return market_open <= now.time() <= market_close

    def refresh_data(self):
        try:
            print(f"\n📊 Data refresh ho raha hai...")
            # BUG FIX: get_best_data() use karo — GitHub CSV primary, Angel One fallback
            self.df = self.fetcher.get_best_data("NIFTY")
            if self.df is not None:
                print(f"✅ Data ready: {len(self.df)} rows")
                return True
            return False
        except Exception as e:
            print(f"❌ Data refresh error: {e}")
            return False

    def get_signal(self):
        try:
            if self.df is None:
                self.refresh_data()

            if not self.model.is_trained:
                loaded = self.model.load_model()
                if not loaded:
                    print("⚠️ Model nahi mila! Training...")
                    if self.df is not None:
                        self.model.train(self.df)
                    else:
                        return None

            return self.model.predict(self.df)

        except Exception as e:
            print(f"❌ Signal Error: {e}")
            return None

    def trading_cycle(self):
        try:
            now = datetime.now().strftime("%H:%M:%S")
            print(f"\n{'='*50}")
            print(f"🔄 TRADING CYCLE | {now}")
            print(f"{'='*50}")

            if not self.is_market_open():
                print("🕐 Market band hai — Waiting...")
                return

            can, reasons = self.order_mgr.risk.can_trade()
            if not can:
                for r in reasons:
                    print(r)
                return

            signal = self.get_signal()
            if not signal:
                print("❌ Signal nahi mila!")
                return

            print(f"\n🎯 Signal: {signal['signal']}")
            print(f"   Confidence: {signal['confidence']:.1f}%")

            # NO TRADE skip
            if signal["value"] == 0:
                print("🟡 NO TRADE — Models disagree, waiting...")
                return

            # BUG FIX: last_signal check improved
            # Pehle: signal["value"] == self.last_signal — sirf value compare
            # Problem: agar pichla trade CALL tha aur naya bhi CALL hai
            # toh skip hota tha — chahe 30 min baad naya valid signal ho
            # Fix: 30 min baad same direction pe bhi trade allow karo
            current_time = datetime.now()
            if (self.last_signal == signal["value"] and
                self.last_signal_time is not None):
                mins_elapsed = (current_time - self.last_signal_time).seconds // 60
                if mins_elapsed < 30:
                    print(f"⚠️ Same signal ({signal['signal']}) — {mins_elapsed} min ago, skipping")
                    return
                else:
                    print(f"ℹ️ Same direction but {mins_elapsed} min baad — allowing")

            # Low confidence skip
            if signal["confidence"] < 55:
                print(f"⚠️ Low confidence ({signal['confidence']:.1f}%) — Skipping")
                return

            order_id = self.order_mgr.execute_signal(signal, "NIFTY")

            if order_id:
                self.last_signal      = signal["value"]
                self.last_signal_time = current_time
                self.trade_count     += 1
                print(f"\n✅ Order placed: {order_id}")
                print(f"   Total trades today: {self.trade_count}")

        except Exception as e:
            print(f"❌ Trading Cycle Error: {e}")

    def monitor_trades(self):
        try:
            open_trades = self.order_mgr.risk.active_trades
            if not open_trades:
                return

            price = self.fetcher.get_live_price("NIFTY")
            if not price:
                return

            for trade_id in list(open_trades.keys()):
                result = self.order_mgr.risk.monitor_trade(trade_id, price)
                if result in ["SL_HIT", "TARGET_HIT"]:
                    print(f"\n🔔 Trade closed: {result}")
                    # Reset last_signal taaki next signal fresh ho
                    self.last_signal = None

        except Exception as e:
            print(f"❌ Monitor Error: {e}")

    def daily_reset(self):
        print(f"\n{'='*50}")
        print(f"🌅 DAILY RESET - {datetime.now().strftime('%Y-%m-%d')}")
        print(f"{'='*50}")

        self.order_mgr.risk.daily_summary()
        self.order_mgr.risk.daily_reset()

        self.last_signal      = None
        self.last_signal_time = None
        self.trade_count      = 0

        print("✅ Daily reset complete!")

    def show_status(self):
        risk   = self.order_mgr.risk
        now    = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        net    = risk.daily_profit - risk.daily_loss
        market = "🟢 OPEN" if self.is_market_open() else "🔴 CLOSED"

        print(f"\n{'='*50}")
        print(f"📊 BOT STATUS | {now}")
        print(f"{'='*50}")
        print(f"   Market:      {market}")
        print(f"   Bot:         {'🟢 RUNNING' if self.is_running else '🔴 STOPPED'}")
        print(f"   Mode:        {'📄 PAPER' if self.mode == 'PAPER' else '💰 LIVE'}")
        print(f"   Capital:     ₹{risk.capital:,.0f}")
        print(f"   Today P&L:   ₹{net:,.0f}")
        print(f"   Trades:      {risk.trades_today}/{risk.max_trades}")
        print(f"   AI Accuracy: {self.model.accuracy:.1f}%")
        print(f"   Last Signal: {self.last_signal}")
        print(f"{'='*50}")

    def start(self):
        print(f"\n🚀 BOT STARTING!")

        if not self.fetcher.connect():
            print("❌ Connection failed!")
            return

        self.order_mgr.fetcher = self.fetcher
        self.is_running        = True

        self.refresh_data()

        if self.df is not None and not self.model.load_model():
            print("⚠️ Model nahi mila, training shuru...")
            self.model.train(self.df)

        schedule.every(5).minutes.do(self.trading_cycle)
        schedule.every(1).minutes.do(self.monitor_trades)
        schedule.every(30).minutes.do(self.refresh_data)
        schedule.every().day.at("09:10").do(self.daily_reset)
        schedule.every().day.at("15:35").do(self.order_mgr.risk.daily_summary)
        schedule.every().day.at("23:00").do(self.trainer.train_once)

        print(f"\n✅ Bot Running!")
        print(f"   Trading cycle: Har 5 min")
        print(f"   Auto train:    Raat 11 PM")
        print(f"   Press Ctrl+C to stop\n")

        self.show_status()

        try:
            while self.is_running:
                schedule.run_pending()
                time.sleep(30)
                if datetime.now().minute % 10 == 0:
                    self.show_status()
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        print(f"\n\n🔴 BOT STOPPING...")
        self.is_running = False

        for order_id in list(self.order_mgr.open_orders.keys()):
            self.order_mgr.exit_trade(order_id, "BOT_STOPPED")

        self.order_mgr.risk.daily_summary()
        self.order_mgr.get_order_history()
        print("✅ Bot stopped safely!")


def main():
    bot = TitanAIBot()

    print("\n" + "="*50)
    print("TITAN-AI TRADER — MENU")
    print("="*50)
    print("1. Bot shuru karo (Auto trading)")
    print("2. Status dekho")
    print("3. Ek baar signal dekho")
    print("4. Model train karo")
    print("5. Order history dekho")
    print("6. Emergency stop")
    print("="*50)

    choice = input("Choice (1-6): ").strip()

    if choice == "1":
        bot.start()

    elif choice == "2":
        bot.fetcher.connect()
        bot.model.load_model()
        bot.show_status()

    elif choice == "3":
        bot.fetcher.connect()
        bot.refresh_data()
        signal = bot.get_signal()
        if signal:
            print(f"\n🎯 Signal:     {signal['signal']}")
            print(f"   Confidence: {signal['confidence']:.1f}%")
            print(f"   RF Vote:    {signal['rf_signal']}")
            print(f"   XGB Vote:   {signal['xgb_signal']}")
        else:
            print("❌ Signal nahi mila!")

    elif choice == "4":
        bot.fetcher.connect()
        bot.refresh_data()
        if bot.df is not None:
            bot.model.train(bot.df)
        else:
            print("❌ Data nahi mila, training nahi ho sakti!")

    elif choice == "5":
        bot.order_mgr.get_order_history()

    elif choice == "6":
        bot.order_mgr.risk.emergency_stop()

    else:
        print("❌ Invalid choice!")


if __name__ == "__main__":
    main()