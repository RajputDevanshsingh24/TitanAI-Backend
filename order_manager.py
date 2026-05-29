# ============================================
# TITAN-AI TRADER — Order Manager FIXED v2.0
# TITAN-SURYA TECHNOLOGIES
#
# BUG FIX: can_trade() sirf ek baar check hoga execute_signal() mein.
# open_trade() ke andar second check hata diya.
# Signal value: 1=CALL, -1=PUT, 0=NO TRADE (ai_model ke saath sync)
# ============================================

import json
import os
from datetime import datetime, timedelta
from data_fetcher import DataFetcher
from risk_manager import RiskManager
from config import TRADING


class OrderManager:

    def __init__(self):
        self.fetcher     = DataFetcher()
        self.risk        = RiskManager()
        self.mode        = TRADING["mode"]
        self.orders      = []
        self.open_orders = {}
        self.logs_path   = "order_logs/"
        os.makedirs(self.logs_path, exist_ok=True)

        print(f"\n✅ Order Manager Ready!")
        print(f"   Mode: {'📄 PAPER TRADING' if self.mode == 'PAPER' else '💰 LIVE TRADING'}")

    def connect(self):
        return self.fetcher.connect()

    def get_option_symbol(self, index, strike, option_type, expiry=None):
        try:
            if not expiry:
                today       = datetime.now()
                days        = (3 - today.weekday()) % 7
                if days == 0:
                    days = 7
                expiry_date = today + timedelta(days=days)
                expiry      = expiry_date.strftime("%d%b%y").upper()

            symbol = f"{index}{expiry}{strike}{option_type}"
            return symbol

        except Exception as e:
            print(f"❌ Symbol Error: {e}")
            return None

    def get_best_strike(self, index, current_price, signal):
        try:
            round_to   = 50 if index == "NIFTY" else 100
            atm_strike = round(current_price / round_to) * round_to

            if signal == "BUY_CALL":
                otm_strike  = atm_strike + round_to
                recommended = atm_strike
            else:
                otm_strike  = atm_strike - round_to
                recommended = atm_strike

            print(f"\n🎯 STRIKE SELECTION:")
            print(f"   Current: ₹{current_price:,.2f}")
            print(f"   ATM:     {atm_strike}")
            print(f"   OTM:     {otm_strike}")
            print(f"   Using:   {recommended}")
            return recommended

        except Exception as e:
            print(f"❌ Strike Error: {e}")
            return None

    def _place_paper_order(self, symbol, order_type, quantity, price):
        order_id = f"PAPER_{datetime.now().strftime('%H%M%S%f')}"
        order = {
            "order_id"  : order_id,
            "symbol"    : symbol,
            "type"      : order_type,
            "quantity"  : quantity,
            "price"     : price,
            "status"    : "COMPLETE",
            "mode"      : "PAPER",
            "timestamp" : datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        self.orders.append(order)
        self._save_order_log(order)

        print(f"\n📄 PAPER ORDER:")
        print(f"   ID:     {order_id}")
        print(f"   Symbol: {symbol}")
        print(f"   Type:   {order_type}")
        print(f"   Qty:    {quantity}")
        print(f"   Price:  ₹{price:,.2f}")
        print(f"   Status: ✅ COMPLETE")
        return order_id

    def _place_real_order(self, symbol, order_type, quantity, price):
        try:
            if not self.fetcher.connected:
                self.fetcher.connect()

            order_params = {
                "variety"         : "NORMAL",
                "tradingsymbol"   : symbol,
                "symboltoken"     : "99926000",
                "transactiontype" : order_type,
                "exchange"        : "NFO",
                "ordertype"       : "MARKET",
                "producttype"     : "INTRADAY",
                "duration"        : "DAY",
                "quantity"        : str(quantity),
            }

            response = self.fetcher.api.placeOrder(order_params)

            if response["status"]:
                order_id = response["data"]["orderid"]
                order = {
                    "order_id"  : order_id,
                    "symbol"    : symbol,
                    "type"      : order_type,
                    "quantity"  : quantity,
                    "price"     : price,
                    "status"    : "PLACED",
                    "mode"      : "LIVE",
                    "timestamp" : datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
                self.orders.append(order)
                self._save_order_log(order)
                print(f"\n💰 LIVE ORDER PLACED! ID: {order_id}")
                return order_id
            else:
                print(f"❌ Order Failed: {response}")
                return None

        except Exception as e:
            print(f"❌ Real Order Error: {e}")
            return None

    def execute_signal(self, signal_data, index="NIFTY"):
        try:
            print(f"\n{'='*50}")
            print(f"🚀 SIGNAL EXECUTE HO RAHA HAI")
            print(f"{'='*50}")

            signal     = signal_data["value"]
            confidence = signal_data["confidence"]

            # NO TRADE check
            if signal == 0:
                print("🟡 NO TRADE signal — Skipping")
                return None

            # Risk check — SIRF EK BAAR YAHAN
            can, reasons = self.risk.can_trade()
            for r in reasons:
                print(r)
            if not can:
                return None

            # Live price lo
            price = self.fetcher.get_live_price(index)
            if not price:
                print("❌ Price nahi mila!")
                return None

            # Signal type set karo
            # value: 1 = BUY CALL, -1 = BUY PUT
            if signal == 1:
                signal_type = "BUY_CALL"
                option_type = "CE"
            else:
                signal_type = "BUY_PUT"
                option_type = "PE"

            # Strike price
            strike   = self.get_best_strike(index, price, signal_type)
            quantity = self.risk.get_position_size(price, confidence)
            symbol   = self.get_option_symbol(index, strike, option_type)

            print(f"\n📋 ORDER DETAILS:")
            print(f"   Index:    {index}")
            print(f"   Signal:   {signal_data['signal']}")
            print(f"   Strike:   {strike}")
            print(f"   Type:     {option_type}")
            print(f"   Symbol:   {symbol}")
            print(f"   Price:    ₹{price:,.2f}")
            print(f"   Qty:      {quantity}")
            print(f"   Conf:     {confidence:.1f}%")

            # Order place karo
            if self.mode == "PAPER":
                order_id = self._place_paper_order(symbol, "BUY", quantity, price)
            else:
                order_id = self._place_real_order(symbol, "BUY", quantity, price)

            if order_id:
                # Risk manager mein register karo
                # open_trade() mein trades_today++ hoga — ek baar
                trade_id = self.risk.open_trade(
                    symbol      = symbol,
                    signal      = signal_type,
                    entry_price = price,
                    quantity    = quantity,
                    confidence  = confidence,
                )
                if trade_id:
                    self.open_orders[order_id] = trade_id
                return order_id

            return None

        except Exception as e:
            print(f"❌ Execute Signal Error: {e}")
            return None

    def exit_trade(self, order_id, reason="MANUAL"):
        try:
            if order_id not in self.open_orders:
                print(f"❌ Order not found: {order_id}")
                return False

            trade_id = self.open_orders[order_id]
            price    = self.fetcher.get_live_price("NIFTY") or 0

            if self.mode == "PAPER":
                self._place_paper_order(trade_id, "SELL", 1, price)
            else:
                self._place_real_order(trade_id, "SELL", 1, price)

            self.risk.close_trade(trade_id, price, reason)
            del self.open_orders[order_id]
            return True

        except Exception as e:
            print(f"❌ Exit Error: {e}")
            return False

    def get_order_history(self):
        print(f"\n{'='*50}")
        print(f"📋 ORDER HISTORY")
        print(f"{'='*50}")
        print(f"{'Time':<22} {'Symbol':<20} {'Type':<6} {'Price':>10}")
        print("-"*60)
        for order in self.orders[-10:]:
            print(
                f"{order['timestamp']:<22} "
                f"{order['symbol']:<20} "
                f"{order['type']:<6} "
                f"₹{order['price']:>9,.2f}"
            )
        print(f"\nTotal Orders: {len(self.orders)}")
        self.risk.daily_summary()

    def _save_order_log(self, order):
        try:
            filename = f"{self.logs_path}orders_{datetime.now().strftime('%Y%m%d')}.json"
            logs     = []
            if os.path.exists(filename):
                with open(filename, "r") as f:
                    logs = json.load(f)
            logs.append(order)
            with open(filename, "w") as f:
                json.dump(logs, f, indent=2, default=str)
        except Exception as e:
            print(f"❌ Log Error: {e}")