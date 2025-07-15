import logging
import os
import httpx
from typing import Optional

logger = logging.getLogger("oanda_client")
logger.info(f"[INIT] OandaClient loaded from: {__file__} | PID: {os.getpid()}")

class OandaClient:
    def __init__(self, api_key: str, account_id: str):
        self.api_key = api_key
        self.account_id = account_id
        self.base_url = "https://api-fxpractice.oanda.com/v3"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        self.client = httpx.AsyncClient(headers=self.headers)

    async def create_trade(self, instrument: str, units: int) -> tuple[bool, dict | str]:
        url = f"{self.base_url}/accounts/{self.account_id}/orders"
        order_data = {
            "order": {
                "units": str(units),
                "instrument": instrument,
                "timeInForce": "FOK",
                "type": "MARKET",
                "positionFill": "DEFAULT"
            }
        }
        try:
            response = await self.client.post(url, json=order_data)
            if response.status_code == 201:
                return True, response.json()
            return False, response.json()
        except Exception as e:
            return False, str(e)

    async def close_trade(self, trade_id: str) -> tuple[bool, dict | str]:
        url = f"{self.base_url}/accounts/{self.account_id}/trades/{trade_id}/close"
        try:
            response = await self.client.put(url)
            if response.status_code == 200:
                return True, response.json()
            return False, response.json()
        except Exception as e:
            return False, str(e)

    async def get_price(self, instrument: str) -> Optional[float]:
        url = f"{self.base_url}/accounts/{self.account_id}/pricing"
        params = {"instruments": instrument}
        try:
            response = await self.client.get(url, params=params)
            if response.status_code == 200:
                prices = response.json().get("prices")
                if prices:
                    bid = float(prices[0]["bids"][0]["price"])
                    ask = float(prices[0]["asks"][0]["price"])
                    return (bid + ask) / 2
        except Exception as e:
            logger.error(f"Exception getting price: {e}")
        return None

    async def get_account_balance(self) -> Optional[float]:
        url = f"{self.base_url}/accounts/{self.account_id}/summary"
        try:
            response = await self.client.get(url)
            if response.status_code == 200:
                return float(response.json()["account"]["balance"])
        except Exception as e:
            logger.error(f"Exception fetching balance: {e}")
        return None

    async def get_margin_available(self) -> Optional[float]:
        url = f"{self.base_url}/accounts/{self.account_id}/summary"
        try:
            response = await self.client.get(url)
            if response.status_code == 200:
                return float(response.json()["account"].get("marginAvailable", 0))
        except Exception as e:
            logger.error(f"Exception fetching margin: {e}")
        return None

    async def get_open_trades(self) -> list[dict]:
        url = f"{self.base_url}/accounts/{self.account_id}/openTrades"
        try:
            response = await self.client.get(url)
            if response.status_code == 200:
                return response.json().get("trades", [])
        except Exception as e:
            logger.error(f"Exception fetching trades: {e}")
        return []