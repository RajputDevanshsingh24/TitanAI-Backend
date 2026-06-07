# ============================================
# TITAN-AI TRADER — Order Manager
# TITAN-SURYA TECHNOLOGIES
# ============================================

from datetime import datetime
from risk_manager import RiskManager
from config import TRADING


class OrderManager:

    def __init__(self):
        self.risk    = RiskManager()
        self.fetcher = None
        self.mode    = TRADING["mode"]
        print(f"✅ Order Manager Ready! Mode: {self.mode}")

    def execute_signal(self, signal, symbol="NIFTY"):
        try:
            sig_val  = signal["value"]
            sig_text = signal["signal"]
            conf     = signal["confidence"]

            if sig_val == 0:
                print("🟡 NO TRADE signal — skip")
                return None

            sig_type = "BUY_CALL" if sig_val == 1 else "BUY_PUT"

            can, reasons = self.risk.can_trade()
            if not can:
                for r in reasons: print(r)
                return None

            # Live price lo
            price = None
            if self.fetcher and self.fetcher.connected:
                price = self.fetcher.get_live_price(symbol)

            if not price:
                print("❌ Price nahi mila!")
                return None

            # ATR for dynamic SL
            atr = None
            try:
                if self.fetcher:
                    from indicators import Indicators
                    df  = self.fetcher.get_best_data(symbol)
                    if df is not None:
                        ind = Indicators(df)
                        ind.add_atr()
                        atr = float(ind.df["ATR"].iloc[-1])
            except:
                pass

            quantity = self.risk.get_position_size(price, conf)
            trade_id = self.risk.open_trade(
                symbol, sig_type, price, quantity, conf, atr
            )

            if not trade_id:
                return None

            # Order place karo
            if self.mode == "LIVE" and self.fetcher and self.fetcher.connected:
                order_id = self._place_angel_order(
                    symbol, sig_type, quantity, price
                )
            else:
                order_id = f"PAPER_{datetime.now().strftime('%H%M%S%f')}"
                print(f"📋 PAPER ORDER: {sig_type} {quantity} {symbol} @ ₹{price:,.2f}")

            print(f"\n✅ Order executed! ID: {order_id}")
            return order_id

        except Exception as e:
            print(f"❌ Execute Signal Error: {e}")
            return None

    def _place_angel_order(self, symbol, signal_type, quantity, price):
        try:
            # Options order — ATM strike
            spot_price  = price
            strike      = round(spot_price / 50) * 50
            option_type = "CE" if signal_type == "BUY_CALL" else "PE"

            # Expiry — next Thursday
            from datetime import date, timedelta
            today   = date.today()
            days    = (3 - today.weekday()) % 7
            if days == 0: days = 7
            expiry  = today + timedelta(days=days)
            expiry_str = expiry.strftime("%d%b%Y").upper()

            trading_symbol = f"NIFTY{expiry_str}{strike}{option_type}"

            order_params = {
                "variety"          : "NORMAL",
                "tradingsymbol"    : trading_symbol,
                "symboltoken"      : "0",
                "transactiontype"  : "BUY",
                "exchange"         : "NFO",
                "ordertype"        : "MARKET",
                "producttype"      : "INTRADAY",
                "duration"         : "DAY",
                "price"            : "0",
                "squareoff"        : "0",
                "stoploss"         : "0",
                "quantity"         : str(quantity * 50),  # NIFTY lot size = 50
            }

            resp = self.fetcher.api.placeOrder(order_params)
            if resp["status"]:
                order_id = resp["data"]["orderid"]
                print(f"✅ Angel One order placed! ID: {order_id}")
                print(f"   Symbol: {trading_symbol}")
                print(f"   Qty:    {quantity * 50}")
                return order_id
            else:
                print(f"❌ Order failed: {resp.get('message')}")
                return None

        except Exception as e:
            print(f"❌ Angel Order Error: {e}")
            return None