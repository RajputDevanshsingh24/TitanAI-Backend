# ============================================
# TITAN-AI TRADER — Event Filter v1.0
# TITAN-SURYA TECHNOLOGIES
# ============================================

import requests
from datetime import datetime, date
from config import TRADING


class EventFilter:

    def __init__(self):
        self.vix_threshold   = 20.0
        self.current_vix     = None
        self.no_trade_reason = None

        self.high_impact_dates = [
            "2026-06-06", "2026-08-06", "2026-10-08", "2026-12-05",
            "2026-02-01",
            "2026-06-18", "2026-07-30", "2026-09-17",
            "2026-11-05", "2026-12-17",
        ]
        print("✅ Event Filter Ready!")

    def is_safe_to_trade(self):
        today = date.today()
        if self._is_expiry_day(today):
            self.no_trade_reason = "⛔ Expiry Day — Options bahut volatile hain"
            print(f"\n{self.no_trade_reason}")
            return False
        if self._is_high_impact_day(today):
            self.no_trade_reason = "⛔ High Impact Event today — No Trade"
            print(f"\n{self.no_trade_reason}")
            return False
        if not self._check_vix():
            self.no_trade_reason = f"⛔ VIX too high: {self.current_vix:.1f} > {self.vix_threshold}"
            print(f"\n{self.no_trade_reason}")
            return False
        if self._is_day_before_expiry(today):
            print("\n⚠️ Expiry kal hai — Extra caution")
        self.no_trade_reason = None
        print(f"\n✅ Safe to trade! VIX: {self.current_vix}")
        return True

    def _is_expiry_day(self, today):
        return today.weekday() == 3

    def _is_day_before_expiry(self, today):
        return today.weekday() == 2

    def _is_high_impact_day(self, today):
        return today.strftime("%Y-%m-%d") in self.high_impact_dates

    def _check_vix(self):
        try:
            vix = self._fetch_vix()
            if vix:
                self.current_vix = vix
                return vix <= self.vix_threshold
            return True
        except:
            return True

    def _fetch_vix(self):
        try:
            headers = {"User-Agent": "Mozilla/5.0",
                       "Referer": "https://www.nseindia.com",
                       "Accept": "application/json"}
            session = requests.Session()
            session.get("https://www.nseindia.com", headers=headers, timeout=5)
            resp = session.get("https://www.nseindia.com/api/allIndices",
                               headers=headers, timeout=10)
            if resp.status_code == 200:
                for idx in resp.json().get("data", []):
                    if "INDIA VIX" in idx.get("index", ""):
                        vix = float(idx.get("last", 0))
                        return vix if vix > 0 else None
            return None
        except:
            return None

    def get_next_expiry(self):
        today = date.today()
        from datetime import timedelta
        days   = (3 - today.weekday()) % 7
        if days == 0: days = 7
        return today + timedelta(days=days)

    def days_to_expiry(self):
        return (self.get_next_expiry() - date.today()).days

    def get_status(self):
        today = date.today()
        return {
            "today"          : today.strftime("%d-%m-%Y"),
            "is_expiry_day"  : self._is_expiry_day(today),
            "is_high_impact" : self._is_high_impact_day(today),
            "days_to_expiry" : self.days_to_expiry(),
            "next_expiry"    : self.get_next_expiry().strftime("%d-%m-%Y"),
            "current_vix"    : self.current_vix,
            "safe_to_trade"  : self.no_trade_reason is None,
            "no_trade_reason": self.no_trade_reason,
        }

    def add_event_date(self, date_str, reason="Custom Event"):
        if date_str not in self.high_impact_dates:
            self.high_impact_dates.append(date_str)
            print(f"✅ Event added: {date_str} — {reason}")