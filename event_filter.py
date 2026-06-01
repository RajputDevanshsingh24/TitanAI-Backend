# ============================================
# TITAN-AI TRADER — Event Filter v1.0
# TITAN-SURYA TECHNOLOGIES
#
# Yeh file check karegi ki aaj trade karna
# safe hai ya nahi.
# High-impact events pe bot trade nahi karega.
# ============================================

import requests
from datetime import datetime, date
from config import TRADING


class EventFilter:

    def __init__(self):
        self.vix_threshold   = 20.0   # VIX > 20 → too volatile
        self.current_vix     = None
        self.no_trade_reason = None

        # ============================================
        # HIGH IMPACT DATES — manually update karo
        # Format: "YYYY-MM-DD"
        # ============================================
        self.high_impact_dates = [
            # RBI Policy 2026
            "2026-06-06",
            "2026-08-06",
            "2026-10-08",
            "2026-12-05",

            # Union Budget
            "2026-02-01",

            # US Fed Meetings 2026
            "2026-06-18",
            "2026-07-30",
            "2026-09-17",
            "2026-11-05",
            "2026-12-17",

            # NSE Special Holidays (add as needed)
        ]

        print("✅ Event Filter Ready!")
        print(f"   VIX Threshold:    {self.vix_threshold}")
        print(f"   High Impact Days: {len(self.high_impact_dates)}")

    # ============================================
    # MAIN CHECK — Yeh call karo trade se pehle
    # Returns: (True = safe to trade, False = no trade)
    # ============================================
    def is_safe_to_trade(self):
        today = date.today()

        # Check 1 — Expiry day (Every Thursday)
        if self._is_expiry_day(today):
            self.no_trade_reason = "⛔ Expiry Day — Options bahut volatile hain"
            print(f"\n{self.no_trade_reason}")
            return False

        # Check 2 — High impact event today
        if self._is_high_impact_day(today):
            self.no_trade_reason = "⛔ High Impact Event today — No Trade"
            print(f"\n{self.no_trade_reason}")
            return False

        # Check 3 — VIX too high
        vix_safe = self._check_vix()
        if not vix_safe:
            self.no_trade_reason = f"⛔ VIX too high: {self.current_vix:.1f} > {self.vix_threshold}"
            print(f"\n{self.no_trade_reason}")
            return False

        # Check 4 — Day before expiry (risky)
        if self._is_day_before_expiry(today):
            self.no_trade_reason = "⚠️ Expiry kal hai — Extra caution (allowed but risky)"
            print(f"\n{self.no_trade_reason}")
            # Warning deta hai but trade rok nahi raha
            # Confidence threshold zyada hoga — api_server handle karega

        self.no_trade_reason = None
        print(f"\n✅ Event Filter: Safe to trade!")
        print(f"   Date: {today.strftime('%d-%m-%Y')}")
        print(f"   VIX:  {self.current_vix if self.current_vix else 'N/A'}")
        return True

    # ============================================
    # EXPIRY DAY CHECK
    # NSE Weekly expiry = Every Thursday
    # Monthly expiry = Last Thursday of month
    # ============================================
    def _is_expiry_day(self, today):
        # Thursday = weekday 3
        if today.weekday() == 3:
            print(f"📅 Aaj Thursday hai — Expiry Day!")
            return True
        return False

    def _is_day_before_expiry(self, today):
        # Wednesday = weekday 2
        return today.weekday() == 2

    # ============================================
    # HIGH IMPACT DATE CHECK
    # ============================================
    def _is_high_impact_day(self, today):
        today_str = today.strftime("%Y-%m-%d")
        if today_str in self.high_impact_dates:
            print(f"📅 High impact event: {today_str}")
            return True
        return False

    # ============================================
    # VIX CHECK
    # India VIX = NSE ka fear index
    # > 20 → avoid trading
    # ============================================
    def _check_vix(self):
        try:
            vix = self._fetch_vix()
            if vix:
                self.current_vix = vix
                print(f"📊 India VIX: {vix:.2f}")
                if vix > self.vix_threshold:
                    return False
                return True
            else:
                # VIX fetch nahi hua — safe assume karo
                print("⚠️ VIX fetch failed — assuming safe")
                self.current_vix = None
                return True

        except Exception as e:
            print(f"⚠️ VIX check error: {e} — assuming safe")
            return True

    # ============================================
    # VIX FETCH — NSE se
    # ============================================
    def _fetch_vix(self):
        try:
            headers = {
                "User-Agent"  : "Mozilla/5.0",
                "Referer"     : "https://www.nseindia.com",
                "Accept"      : "application/json",
            }

            # NSE API
            session  = requests.Session()
            session.get("https://www.nseindia.com", headers=headers, timeout=5)
            response = session.get(
                "https://www.nseindia.com/api/allIndices",
                headers = headers,
                timeout = 10
            )

            if response.status_code == 200:
                data    = response.json()
                indices = data.get("data", [])
                for idx in indices:
                    if "INDIA VIX" in idx.get("index", ""):
                        vix = float(idx.get("last", 0))
                        return vix if vix > 0 else None

            return None

        except Exception as e:
            print(f"⚠️ VIX API error: {e}")
            return None

    # ============================================
    # NEXT EXPIRY DATE
    # ============================================
    def get_next_expiry(self):
        today  = date.today()
        days   = (3 - today.weekday()) % 7  # Next Thursday
        if days == 0:
            days = 7
        from datetime import timedelta
        expiry = today + timedelta(days=days)
        return expiry

    # ============================================
    # DAYS TO EXPIRY
    # ============================================
    def days_to_expiry(self):
        from datetime import timedelta
        expiry = self.get_next_expiry()
        today  = date.today()
        return (expiry - today).days

    # ============================================
    # STATUS — API ke liye
    # ============================================
    def get_status(self):
        today  = date.today()
        expiry = self.get_next_expiry()
        return {
            "today"            : today.strftime("%d-%m-%Y"),
            "is_expiry_day"    : self._is_expiry_day(today),
            "is_high_impact"   : self._is_high_impact_day(today),
            "days_to_expiry"   : self.days_to_expiry(),
            "next_expiry"      : expiry.strftime("%d-%m-%Y"),
            "current_vix"      : self.current_vix,
            "vix_threshold"    : self.vix_threshold,
            "safe_to_trade"    : self.no_trade_reason is None,
            "no_trade_reason"  : self.no_trade_reason,
        }

    # ============================================
    # MANUAL DATE ADD KARO
    # ============================================
    def add_event_date(self, date_str, reason="Custom Event"):
        """
        Usage: event_filter.add_event_date("2026-07-15", "Election Results")
        """
        if date_str not in self.high_impact_dates:
            self.high_impact_dates.append(date_str)
            print(f"✅ Event added: {date_str} — {reason}")
        else:
            print(f"⚠️ Already exists: {date_str}")