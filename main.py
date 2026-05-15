# ============================================
# TITAN-AI TRADER — Main Bot Engine
# TITAN-SURYA TECHNOLOGIES
# ============================================

import time
import schedule
import threading
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

        self.fetcher      = DataFetcher()
        self.model        = AIModel()
        self.order_mgr    = OrderManager()
        self.trainer      = AutoTrainer()
        self.is_running   = False
        self.mode         = TRADING["mode"]
        self.df           = None
        self.last_signal  = None
        self.trade_count  = 0

        print(f"\n✅ Bot Initialized!")
        print(f"   Mode: {'📄 PAPER' if self.mode == 'PAPER' else '💰 LIVE'}")
        print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # ============================================
    # MARKET OPEN HAI?
    # ============================================
    def is_market_open(self):
        now      = datetime.now()
        weekday  = now.weekday()

        # Weekend check
        if weekday >= 5:
            return False

        # Market hours: 9:15 AM - 3:30 PM
        market_open  = dtime(9, 15)
        market_close = dtime(15, 30)
        current_time = now.time()

        return market_open <= current_time <= market_close

    # ============================================
    # DATA REFRESH KARO
    # ============================================
    def refresh_data(self):
        try:
            print(f"\n📊 Data refresh ho raha hai...")
            self.df = self.fetcher.get_historical_data(
                "NIFTY", days=365
            )
            if self.df is not None:
                print(f"✅ Data ready: {len(self.df)} rows")
                return True
            return False
        except Exception as e:
            print(f"❌ Data refresh error: {e}")
            return False

    # ============================================
    # AI SIGNAL LO
    # ============================================
    def get_signal(self):
        try:
            if self.df is None:
                self.refresh_data()

            # Model load karo (agar nahi hai)
            if not self.model.is_trained:
                loaded = self.model.load_model()
                if not loaded:
                    print("⚠️ Model nahi mila! Training...")
                    self.model.train(self.df)

            # Signal lo
            signal = self.model.predict(self.df)
            return signal

        except Exception as e:
            print(f"❌ Signal Error: {e}")
            return None

    # ============================================
    # EK TRADING CYCLE
    # ============================================
    def trading_cycle(self):
        try:
            now = datetime.now().strftime("%H:%M:%S")
            print(f"\n{'='*50}")
            print(f"🔄 TRADING CYCLE | {now}")
            print(f"{'='*50}")

            # Market open check
            if not self.is_market_open():
                print("🕐 Market band hai — Waiting...")
                return

            # Risk check
            can, reasons = self.order_mgr.risk.can_trade()
            if not can:
                for r in reasons:
                    print(r)
                return

            # Signal lo
            signal = self.get_signal()
            if not signal:
                print("❌ Signal nahi mila!")
                return

            print(f"\n🎯 Signal: {signal['signal']}")
            print(f"   Confidence: {signal['confidence']:.1f}%")

            # Same signal dobara mat lo
            if signal["value"] == self.last_signal:
                print("⚠️ Same signal — Skipping duplicate")
                return

            # Minimum confidence check
            if signal["confidence"] < 55:
                print(f"⚠️ Low confidence ({signal['confidence']:.1f}%) — Skipping")
                return

            # NO TRADE signal
            if signal["value"] == 0:
                print("🟡 NO TRADE — Waiting for better signal")
                return

            # Order execute karo
            order_id = self.order_mgr.execute_signal(
                signal, "NIFTY"
            )

            if order_id:
                self.last_signal = signal["value"]
                self.trade_count += 1
                print(f"\n✅ Order placed: {order_id}")
                print(f"   Total trades today: {self.trade_count}")

        except Exception as e:
            print(f"❌ Trading Cycle Error: {e}")

    # ============================================
    # MONITOR OPEN TRADES
    # ============================================
    def monitor_trades(self):
        try:
            open_trades = self.order_mgr.risk.active_trades
            if not open_trades:
                return

            price = self.fetcher.get_live_price("NIFTY")
            if not price:
                return

            for trade_id in list(open_trades.keys()):
                result = self.order_mgr.risk.monitor_trade(
                    trade_id, price
                )
                if result in ["SL_HIT", "TARGET_HIT"]:
                    print(f"\n🔔 Trade closed: {result}")

        except Exception as e:
            print(f"❌ Monitor Error: {e}")

    # ============================================
    # DAILY RESET
    # ============================================
    def daily_reset(self):
        print(f"\n{'='*50}")
        print(f"🌅 DAILY RESET - {datetime.now().strftime('%Y-%m-%d')}")
        print(f"{'='*50}")

        # Summary dikhao
        self.order_mgr.risk.daily_summary()

        # Reset karo
        self.order_mgr.risk.daily_loss   = 0
        self.order_mgr.risk.daily_profit = 0
        self.order_mgr.risk.trades_today = 0
        self.order_mgr.risk.bot_active   = True
        self.last_signal = None
        self.trade_count = 0

        print("✅ Daily reset complete!")

    # ============================================
    # STATUS DIKHAO
    # ============================================
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

    # ============================================
    # BOT SHURU KARO
    # ============================================
    def start(self):
        print(f"\n🚀 BOT STARTING!")

        # Connect karo
        if not self.fetcher.connect():
            print("❌ Connection failed!")
            return

        self.order_mgr.fetcher = self.fetcher
        self.is_running        = True

        # Fresh data lo
        self.refresh_data()

        # Model load karo
        if not self.model.load_model():
            print("⚠️ Model nahi mila, training shuru...")
            self.model.train(self.df)

        # Schedule setup
        # Har 5 min mein trading cycle
        schedule.every(5).minutes.do(self.trading_cycle)

        # Har 1 min mein trades monitor
        schedule.every(1).minutes.do(self.monitor_trades)

        # Har 30 min mein data refresh
        schedule.every(30).minutes.do(self.refresh_data)

        # Roz 9:10 AM reset
        schedule.every().day.at("09:10").do(self.daily_reset)

        # Roz 3:35 PM summary
        schedule.every().day.at("15:35").do(
            self.order_mgr.risk.daily_summary
        )

        # Roz 11 PM auto train
        schedule.every().day.at("23:00").do(
            self.trainer.train_once
        )

        print(f"\n✅ Bot Running!")
        print(f"   Trading cycle: Har 5 min")
        print(f"   Auto train:    Raat 11 PM")
        print(f"   Press Ctrl+C to stop\n")

        # Status dikhao
        self.show_status()

        # Main loop
        try:
            while self.is_running:
                schedule.run_pending()
                time.sleep(30)

                # Har 10 min status print
                if datetime.now().minute % 10 == 0:
                    self.show_status()

        except KeyboardInterrupt:
            self.stop()

    # ============================================
    # BOT BAND KARO
    # ============================================
    def stop(self):
        print(f"\n\n🔴 BOT STOPPING...")
        self.is_running = False

        # Sab trades close karo
        for order_id in list(
            self.order_mgr.open_orders.keys()
        ):
            self.order_mgr.exit_trade(order_id, "BOT_STOPPED")

        # Final summary
        self.order_mgr.risk.daily_summary()
        self.order_mgr.get_order_history()

        print("✅ Bot stopped safely!")


# ============================================
# MENU
# ============================================
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

    elif choice == "4":
        bot.fetcher.connect()
        bot.refresh_data()
        bot.model.train(bot.df)

    elif choice == "5":
        bot.order_mgr.get_order_history()

    elif choice == "6":
        bot.order_mgr.risk.emergency_stop()

    else:
        print("❌ Invalid choice!")


if __name__ == "__main__":
    main()