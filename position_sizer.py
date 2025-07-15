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
    def __init__(self, oanda_client: OandaClient, max_risk=0.015, max_open_trades=50):
        self.oanda_client = oanda_client
        self.max_risk = max_risk  # 1.5% max risk per trade
        self.max_open_trades = max_open_trades  # 50 max open trades
        self.trade_cooldown_minutes = 0.1  # 6 seconds
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
                    # Convert performance dict back to defaultdict
                    if "performance" in data:
                        perf_dict = defaultdict(lambda: {"wins": 0, "losses": 0, "confidence": 0.7})
                        for k, v in data["performance"].items():
                            perf_dict[k] = v
                        self.trade_state["performance"] = perf_dict
                    
                    # Convert timestamp strings back to datetime objects
                    for inst, t_str in self.trade_state["last_trade_time"].items():
                        if isinstance(t_str, str):
                            self.trade_state["last_trade_time"][inst] = datetime.fromisoformat(t_str)
                logger.info("Trade state loaded")
            except Exception as e:
                logger.warning(f"Failed to load trade state: {e}")

    def _save_state(self):
        try:
            data = self.trade_state.copy()
            # Convert datetime objects to strings for JSON serialization
            data["last_trade_time"] = {
                k: v.isoformat() if isinstance(v, datetime) else v
                for k, v in self.trade_state["last_trade_time"].items()
            }
            # Convert defaultdict to regular dict for JSON serialization
            data["performance