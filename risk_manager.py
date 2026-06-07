# ============================================
# TITAN-AI TRADER — Risk Manager v3.0
# TITAN-SURYA TECHNOLOGIES
# ============================================

import json
import os
from datetime import datetime
from config import TRADING, RISK


class RiskManager:

    def __init__(self):
        self.capital        = TRADING["capital"]
        self.start_capital  = TRADING["capital"]
        self.daily_loss     = 0.0
        self.daily_profit   = 0.0
        self.trades_today   = 0
        self.max_trades     = TRADING["max_trades_day"]
        self.max_daily_loss = TRADING["max_loss_day"]
        self.stop_loss_pct  = RISK["stop_loss_pct"]
        self.target_pct     = RISK["target_pct"]
        self.trailing_sl    = RISK["trailing_sl"]
        self.active_trades  = {}
        self.trade_history  = []
        self.bot_active     = True
        self.logs_path      = "risk_logs/"
        os.makedirs(self.logs_path, exist_ok=True)
        print("✅ Risk Manager Ready!")
        print(f"   Capital:        ₹{self.capital:,}")
        print(f"   Max Trades/Day: {self.max_trades}")
        print(f"   Stop Loss:      {self.stop_loss_pct}%")
        print(f"   Target:         {self.target_pct}%")

    def can_trade(self):
        reasons = []
        if not self.bot_active:
            reasons.append("❌ Bot manually stopped!")
            return False, reasons
        if self.trades_today >= self.max_trades:
            reasons.append(f"❌ Max trades reached: {self.trades_today}/{self.max_trades}")
            return False, reasons
        if self.daily_loss >= self.max_daily_loss:
            reasons.append(f"❌ Daily loss limit hit: ₹{self.daily_loss:,.0f}")
            self.bot_active = False
            return False, reasons
        if self.capital < self.start_capital * 0.5:
            reasons.append(f"❌ Capital 50% se kam: ₹{self.capital:,.0f}")
            self.bot_active = False
            return False, reasons
        reasons.append("✅ Trade allowed!")
        return True, reasons

    def get_position_size(self, price, signal_confidence=50):
        try:
            base_risk  = self.capital * 0.02
            multiplier = 1.5 if signal_confidence >= 70 else (1.0 if signal_confidence >= 60 else 0.5)
            position_value = base_risk * multiplier
            quantity       = max(1, int(position_value / price))
            print(f"\n📊 POSITION SIZE: Qty={quantity} | ₹{position_value:,.0f}")
            return quantity
        except Exception as e:
            print(f"❌ Position Size Error: {e}")
            return 1

    def calculate_sl_target(self, entry_price, signal_type, atr=None):
        if atr and atr > 0:
            sl_amount     = atr * 1.5
            target_amount = atr * 3.0
        else:
            sl_amount     = entry_price * (self.stop_loss_pct / 100)
            target_amount = entry_price * (self.target_pct / 100)

        if signal_type == "BUY_CALL":
            sl = entry_price - sl_amount; target = entry_price + target_amount
        else:
            sl = entry_price + sl_amount; target = entry_price - target_amount

        rr = target_amount / sl_amount if sl_amount > 0 else 0
        print(f"\n🎯 Entry:₹{entry_price:,.2f} | SL:₹{sl:,.2f} | Target:₹{target:,.2f} | R:R 1:{rr:.1f}")
        return round(sl, 2), round(target, 2)

    def open_trade(self, symbol, signal, entry_price, quantity, confidence=50, atr=None):
        try:
            sl, target = self.calculate_sl_target(entry_price, signal, atr)
            trade_id   = f"{symbol}_{datetime.now().strftime('%H%M%S%f')}"
            trade = {
                "id"           : trade_id,
                "symbol"       : symbol,
                "signal"       : signal,
                "entry_price"  : entry_price,
                "quantity"     : quantity,
                "sl"           : sl,
                "initial_sl"   : sl,
                "target"       : target,
                "entry_time"   : datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status"       : "OPEN",
                "confidence"   : confidence,
                "highest_price": entry_price,
                "lowest_price" : entry_price,
            }
            self.active_trades[trade_id] = trade
            self.trades_today += 1
            print(f"\n✅ TRADE OPENED! {symbol} {signal} ₹{entry_price:,.2f} Qty:{quantity}")
            return trade_id
        except Exception as e:
            print(f"❌ Open Trade Error: {e}")
            return None

    def monitor_trade(self, trade_id, current_price):
        try:
            if trade_id not in self.active_trades:
                return "NOT_FOUND"
            trade  = self.active_trades[trade_id]
            signal = trade["signal"]
            entry  = trade["entry_price"]
            sl     = trade["sl"]
            target = trade["target"]

            if self.trailing_sl:
                if signal == "BUY_CALL" and current_price > trade["highest_price"]:
                    trade["highest_price"] = current_price
                    sl_distance = entry - trade["initial_sl"]
                    new_sl = current_price - sl_distance
                    if new_sl > trade["sl"]:
                        trade["sl"] = round(new_sl, 2)
                        print(f"\n📈 Trailing SL → ₹{trade['sl']:,.2f}")
                elif signal == "BUY_PUT" and current_price < trade["lowest_price"]:
                    trade["lowest_price"] = current_price
                    sl_distance = trade["initial_sl"] - entry
                    new_sl = current_price + sl_distance
                    if new_sl < trade["sl"]:
                        trade["sl"] = round(new_sl, 2)
                        print(f"\n📉 Trailing SL → ₹{trade['sl']:,.2f}")

            sl = trade["sl"]
            if signal == "BUY_CALL":
                if current_price <= sl:     return self.close_trade(trade_id, current_price, "SL_HIT")
                if current_price >= target: return self.close_trade(trade_id, current_price, "TARGET_HIT")
            else:
                if current_price >= sl:     return self.close_trade(trade_id, current_price, "SL_HIT")
                if current_price <= target: return self.close_trade(trade_id, current_price, "TARGET_HIT")
            return "ACTIVE"
        except Exception as e:
            print(f"❌ Monitor Error: {e}")
            return "ERROR"

    def close_trade(self, trade_id, exit_price, reason):
        try:
            if trade_id not in self.active_trades:
                return "NOT_FOUND"
            trade    = self.active_trades[trade_id]
            entry    = trade["entry_price"]
            quantity = trade["quantity"]
            signal   = trade["signal"]
            pnl      = ((exit_price - entry) if signal == "BUY_CALL" else (entry - exit_price)) * quantity
            self.capital += pnl
            if pnl > 0: self.daily_profit += pnl
            else:        self.daily_loss   += abs(pnl)
            trade.update({
                "exit_price": exit_price,
                "exit_time" : datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "pnl"       : round(pnl, 2),
                "reason"    : reason,
                "status"    : "CLOSED",
            })
            self.trade_history.append(trade)
            del self.active_trades[trade_id]
            emoji = "✅ WIN" if pnl > 0 else "❌ LOSS"
            print(f"\n{emoji} | {reason} | P&L: ₹{pnl:+,.0f} | Capital: ₹{self.capital:,.0f}")
            self._save_trade_log(trade)
            return reason
        except Exception as e:
            print(f"❌ Close Trade Error: {e}")
            return "ERROR"

    def market_close_exit(self, fetcher):
        if not self.active_trades:
            print("✅ Market close: Koi open trade nahi.")
            return
        print(f"\n⏰ MARKET CLOSING — FORCE EXIT | {len(self.active_trades)} trades")
        try:
            price = fetcher.get_live_price("NIFTY")
        except:
            price = None
        for trade_id in list(self.active_trades.keys()):
            trade = self.active_trades[trade_id]
            self.close_trade(trade_id, price if price else trade["entry_price"], "MARKET_CLOSE")
        self.daily_summary()

    def emergency_stop(self):
        print("\n🔴 EMERGENCY STOP!")
        self.bot_active = False
        for trade_id in list(self.active_trades.keys()):
            trade = self.active_trades[trade_id]
            self.close_trade(trade_id, trade["entry_price"], "EMERGENCY_STOP")
        print("✅ All trades closed!")

    def daily_reset(self):
        self.daily_loss = 0.0; self.daily_profit = 0.0
        self.trades_today = 0; self.bot_active = True
        print(f"✅ Daily reset! [{datetime.now().strftime('%d-%m-%Y')}]")

    def daily_summary(self):
        net   = self.daily_profit - self.daily_loss
        today = datetime.now().strftime("%Y-%m-%d")
        today_trades = [t for t in self.trade_history if t.get("exit_time", "")[:10] == today]
        wins  = [t for t in today_trades if t.get("pnl", 0) > 0]
        total = len(today_trades)
        print(f"\n{'='*50}")
        print(f"📊 DAILY SUMMARY | {datetime.now().strftime('%d-%m-%Y')}")
        print(f"   Capital:  ₹{self.capital:,.0f}")
        print(f"   Net P&L:  ₹{net:+,.0f}")
        print(f"   Trades:   {total}")
        if total > 0:
            print(f"   Win Rate: {len(wins)/total*100:.0f}%")
        print(f"{'='*50}")

    def _save_trade_log(self, trade):
        try:
            filename = f"{self.logs_path}trades_{datetime.now().strftime('%Y%m%d')}.json"
            logs = []
            if os.path.exists(filename):
                with open(filename, "r") as f:
                    logs = json.load(f)
            logs.append(trade)
            with open(filename, "w") as f:
                json.dump(logs, f, indent=2, default=str)
        except Exception as e:
            print(f"❌ Log Error: {e}")