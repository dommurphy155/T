import asyncio
import json
import os
import logging
from collections import defaultdict
from datetime import datetime, timedelta

from oanda_client import OandaClient

logger = logging.getLogger("position_sizer")

STATE_FILE = "trade_state.json"

class PositionSizer:
    def __init__(self, oanda_client: OandaClient, min_risk=0.01, max_risk=0.03, max_open_trades=100):
        self.oanda_client = oanda_client
        self.min_risk = min_risk  # 1%
        self.max_risk = max_risk  # 3%
        self.max_open_trades = max_open_trades
        self.trade_cooldown_minutes = 0.1
        self.min_confidence = 0.5
        self.trade_state = {
            "last_trade_time": {},
            "open_trades": 0,
            "performance": defaultdict(lambda: {"wins": 0, "losses": 0, "confidence": 0.7}),
        }
        self._load_state()

    def _load_state(self):
        if os.path.isfile(STATE_FILE):
            try:
                with open(STATE_FILE, "r") as f:
                    data = json.load(f)
                    self.trade_state.update(data)
                    for inst, t_str in self.trade_state["last_trade_time"].items():
                        self.trade_state["last_trade_time"][inst] = datetime.fromisoformat(t_str)
                logger.info("Trade state loaded")
            except Exception as e:
                logger.warning(f"Failed to load trade state: {e}")

    def _save_state(self):
        try:
            data = self.trade_state.copy()
            data["last_trade_time"] = {
                k: v.isoformat() if isinstance(v, datetime) else v
                for k, v in self.trade_state["last_trade_time"].items()
            }
            with open(STATE_FILE, "w") as f:
                json.dump(data, f)
            logger.debug("Trade state saved")
        except Exception as e:
            logger.warning(f"Failed to save trade state: {e}")

    def update_performance(self, instrument: str, won: bool):
        perf = self.trade_state["performance"][instrument]
        if won:
            perf["wins"] += 1
            perf["confidence"] = min(1.0, perf["confidence"] + 0.05)
        else:
            perf["losses"] += 1
            perf["confidence"] = max(0.1, perf["confidence"] - 0.1)
        self._save_state()

    def get_confidence(self, instrument: str):
        return self.trade_state["performance"].get(instrument, {}).get("confidence", 0.5)

    def can_trade(self, instrument: str):
        last_time = self.trade_state["last_trade_time"].get(instrument)
        if last_time and datetime.utcnow() - last_time < timedelta(minutes=self.trade_cooldown_minutes):
            logger.info(f"Cooldown active for {instrument}, skipping trade")
            return False
        if self.trade_state["open_trades"] >= self.max_open_trades:
            logger.info(f"Max open trades reached ({self.max_open_trades}), skipping trade")
            return False
        return True

    def record_trade(self, instrument: str):
        self.trade_state["last_trade_time"][instrument] = datetime.utcnow()
        self.trade_state["open_trades"] += 1
        self._save_state()

    def close_trade(self, instrument: str):
        self.trade_state["open_trades"] = max(0, self.trade_state["open_trades"] - 1)
        self._save_state()

    async def calculate_units(self, instrument: str, stop_loss_pips: float):
        balance = await self.oanda_client.get_account_balance()
        if balance is None:
            logger.error("No account balance, cannot calculate units")
            return 0

        if not self.can_trade(instrument):
            return 0

        confidence = self.get_confidence(instrument)
        if confidence < self.min_confidence:
            logger.info(f"Confidence {confidence:.2f} below threshold {self.min_confidence}, skipping trade")
            return 0

        raw_risk = self.min_risk + (self.max_risk - self.min_risk) * confidence
        adjusted_risk = min(max(raw_risk, self.min_risk), self.max_risk)

        volatility_adjustment = 1.5 if confidence < 0.6 else 1.0
        adjusted_stop_loss = stop_loss_pips * volatility_adjustment

        if instrument.endswith("JPY"):
            pip_value = 0.01
        else:
            pip_value = 0.0001

        risk_amount = balance * adjusted_risk

        margin_available = await self.oanda_client.get_margin_available()
        if margin_available is None:
            logger.error("No margin info available, skipping trade")
            return 0

        units_by_risk = int(risk_amount / (adjusted_stop_loss * pip_value))

        price = await self.oanda_client.get_price(instrument)
        if price is None:
            logger.error(f"Price for {instrument} unavailable, skipping trade")
            return 0
        max_units_margin = int(margin_available / price)

        units = min(units_by_risk, max_units_margin)

        if units < 1:
            logger.warning(f"Units calculated less than 1 ({units}), no trade placed")
            return 0

        logger.info(
            f"PositionSizer: {instrument} units={units} | conf={confidence:.2f} | risk={adjusted_risk:.3f} | SL={adjusted_stop_loss}"
        )
        return units