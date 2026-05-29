# ============================================
# TITAN-AI TRADER — Risk Manager FIXED v2.0
# TITAN-SURYA TECHNOLOGIES
#
# BUG FIX: trades_today increment sirf open_trade() mein hoga.
# Pehle order_manager aur risk_manager dono mein can_trade() call
# hoti thi, aur open_trade() ke andar bhi — count double ho raha tha.
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
        print(f"   Max Daily Loss: ₹{self.max_daily_loss:,}")
        print(f"   Stop Loss:      {self.stop_loss_pct}%")
        print(f"   Target:         {self.target_pct}%")

    def can_trade(self):
        """Sirf check karta hai — koi increment nahi."""
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
        reasons.append(f"   Trades today: {self.trades_today}/{self.max_trades}")
        reasons.append(f"   Daily P&L: ₹{self.daily_profit - self.daily_loss:,.0f}")
        return True, reasons

    def get_position_size(self, price, signal_confidence=50):
        try:
            base_risk = self.capital * 0.02

            if signal_confidence >= 70:
                multiplier = 1.5
            elif signal_confidence >= 60:
                multiplier = 1.0
            else:
                multiplier = 0.5

            position_value = base_risk * multiplier
            quantity       = max(1, int(position_value / price))

            print(f"\n📊 POSITION SIZE:")
            print(f"   Price:       ₹{price:,.2f}")
            print(f"   Confidence:  {signal_confidence:.1f}%")
            print(f"   Risk Amount: ₹{position_value:,.0f}")
            print(f"   Quantity:    {quantity}")
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
            target_amount = entry_price * (self.target_pct    / 100)

        if signal_type == "BUY_CALL":
            sl     = entry_price - sl_amount
            target = entry_price + target_amount
        elif signal_type == "BUY_PUT":
            sl     = entry_price + sl_amount
            target = entry_price - target_amount
        else:
            sl     = entry_price * 0.98
            target = entry_price * 1.04

        print(f"\n🎯 SL & TARGET:")
        print(f"   Entry:  ₹{entry_price:,.2f}")
        print(f"   SL:     ₹{sl:,.2f}")
        print(f"   Target: ₹{target:,.2f}")
        print(f"   R:R     1:{target_amount/sl_amount:.1f}")
        return round(sl, 2), round(target, 2)

    def open_trade(self, symbol, signal, entry_price, quantity, confidence=50):
        """Trade record karo — can_trade() yahan call nahi hogi (OrderManager karta hai)."""
        try:
            sl, target = self.calculate_sl_target(entry_price, signal)
            trade_id   = f"{symbol}_{datetime.now().strftime('%H%M%S%f')}"

            trade = {
                "id"            : trade_id,
                "symbol"        : symbol,
                "signal"        : signal,
                "entry_price"   : entry_price,
                "quantity"      : quantity,
                "sl"            : sl,
                "target"        : target,
                "entry_time"    : datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status"        : "OPEN",
                "confidence"    : confidence,
                "highest_price" : entry_price,
                "lowest_price"  : entry_price,
            }

            self.active_trades[trade_id] = trade
            self.trades_today += 1  # Sirf ek baar, yahan hi

            print(f"\n✅ TRADE OPENED!")
            print(f"   ID:     {trade_id}")
            print(f"   Symbol: {symbol}")
            print(f"   Signal: {signal}")
            print(f"   Entry:  ₹{entry_price:,.2f}")
            print(f"   Qty:    {quantity}")
            print(f"   SL:     ₹{sl:,.2f}")
            print(f"   Target: ₹{target:,.2f}")
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
                if signal == "BUY_CALL":
                    if current_price > trade["highest_price"]:
                        trade["highest_price"] = current_price
                        new_sl = current_price * (1 - self.stop_loss_pct / 200)
                        if new_sl > trade["sl"]:
                            trade["sl"] = new_sl
                            sl          = new_sl
                elif signal == "BUY_PUT":
                    if current_price < trade["lowest_price"]:
                        trade["lowest_price"] = current_price
                        new_sl = current_price * (1 + self.stop_loss_pct / 200)
                        if new_sl < trade["sl"]:
                            trade["sl"] = new_sl
                            sl          = new_sl

            if signal == "BUY_CALL":
                pnl = (current_price - entry) * trade["quantity"]
                if current_price <= sl:
                    return self.close_trade(trade_id, current_price, "SL_HIT")
                if current_price >= target:
                    return self.close_trade(trade_id, current_price, "TARGET_HIT")
            elif signal == "BUY_PUT":
                pnl = (entry - current_price) * trade["quantity"]
                if current_price >= sl:
                    return self.close_trade(trade_id, current_price, "SL_HIT")
                if current_price <= target:
                    return self.close_trade(trade_id, current_price, "TARGET_HIT")
            else:
                pnl = 0

            denom   = entry * trade["quantity"]
            pnl_pct = (pnl / denom * 100) if denom > 0 else 0
            print(f"\r📊 {trade_id[:20]}: ₹{current_price:,.2f} | "
                  f"P&L: ₹{pnl:,.0f} ({pnl_pct:.1f}%) | SL: ₹{sl:,.2f}",
                  end="", flush=True)
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

            pnl = (exit_price - entry) * quantity if signal == "BUY_CALL" \
                  else (entry - exit_price) * quantity

            self.capital += pnl
            if pnl > 0: self.daily_profit += pnl
            else:        self.daily_loss   += abs(pnl)

            trade.update({
                "exit_price" : exit_price,
                "exit_time"  : datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "pnl"        : pnl,
                "reason"     : reason,
                "status"     : "CLOSED",
            })

            self.trade_history.append(trade)
            del self.active_trades[trade_id]

            emoji = "✅" if pnl > 0 else "❌"
            print(f"\n\n{emoji} TRADE CLOSED!")
            print(f"   Reason:  {reason}")
            print(f"   Entry:   ₹{entry:,.2f}  →  Exit: ₹{exit_price:,.2f}")
            print(f"   P&L:     ₹{pnl:,.0f}")
            print(f"   Capital: ₹{self.capital:,.0f}")

            self._save_trade_log(trade)
            return reason

        except Exception as e:
            print(f"❌ Close Trade Error: {e}")
            return "ERROR"

    def emergency_stop(self):
        print("\n🔴 EMERGENCY STOP ACTIVATED!")
        self.bot_active = False
        for trade_id in list(self.active_trades.keys()):
            self.close_trade(trade_id, 0, "EMERGENCY_STOP")
        print("✅ All trades closed!")

    def daily_reset(self):
        self.daily_loss   = 0.0
        self.daily_profit = 0.0
        self.trades_today = 0
        self.bot_active   = True
        print("✅ Risk Manager daily reset done!")

    def daily_summary(self):
        net = self.daily_profit - self.daily_loss
        e   = "✅" if net >= 0 else "❌"
        print(f"\n{'='*50}")
        print(f"📊 DAILY SUMMARY {e}")
        print(f"{'='*50}")
        print(f"   Capital:      ₹{self.capital:,.0f}")
        print(f"   Daily Profit: ₹{self.daily_profit:,.0f}")
        print(f"   Daily Loss:   ₹{self.daily_loss:,.0f}")
        print(f"   Net P&L:      ₹{net:,.0f}")
        print(f"   Trades:       {self.trades_today}")
        print(f"   Bot Active:   {self.bot_active}")
        print(f"{'='*50}")

    def _save_trade_log(self, trade):
        try:
            filename = f"{self.logs_path}trades_{datetime.now().strftime('%Y%m%d')}.json"
            logs     = []
            if os.path.exists(filename):
                with open(filename, "r") as f:
                    logs = json.load(f)
            logs.append(trade)
            with open(filename, "w") as f:
                json.dump(logs, f, indent=2, default=str)
        except Exception as e:
            print(f"❌ Log Error: {e}")