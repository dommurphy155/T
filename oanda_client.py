import oandapyV20
import oandapyV20.endpoints.accounts as accounts
import oandapyV20.endpoints.orders as orders
import oandapyV20.endpoints.positions as positions
import oandapyV20.endpoints.trades as trades
import logging

# ERROR: 'close_trade_by_id', 'get_open_positions', and 'get_account_summary' are used as module-level functions in other files, but are not defined here. Implement these as module-level functions or update the imports in other files to use the OandaClient class methods.

class OandaClient:
    def __init__(self, access_token: str, account_id: str, environment: str = "practice"):
        self.client = oandapyV20.API(access_token=access_token, environment=environment)
        self.account_id = account_id

    def get_account_summary(self):
        try:
            r = accounts.AccountSummary(accountID=self.account_id)
            self.client.request(r)
            return r.response['account']
        except Exception as e:
            logging.error(f"Error getting account summary: {e}")
            return None

    def get_open_positions(self):
        try:
            r = positions.OpenPositions(accountID=self.account_id)
            self.client.request(r)
            return r.response['positions']
        except Exception as e:
            logging.error(f"Error getting open positions: {e}")
            return []

    def get_open_trades(self):
        try:
            r = trades.OpenTrades(accountID=self.account_id)
            self.client.request(r)
            return r.response['trades']
        except Exception as e:
            logging.error(f"Error getting open trades: {e}")
            return []

    def place_order(self, instrument: str, units: int, order_type: str = "MARKET", stop_loss: float = None, take_profit: float = None):
        try:
            order_data = {
                "order": {
                    "instrument": instrument,
                    "units": str(units),
                    "type": order_type,
                    "positionFill": "DEFAULT"
                }
            }

            if stop_loss:
                order_data["order"]["stopLossOnFill"] = {"price": str(stop_loss)}
            if take_profit:
                order_data["order"]["takeProfitOnFill"] = {"price": str(take_profit)}

            r = orders.OrderCreate(accountID=self.account_id, data=order_data)
            self.client.request(r)
            return r.response
        except Exception as e:
            logging.error(f"Error placing order: {e}")
            return None

    def close_trade(self, trade_id: str):
        try:
            r = trades.TradeClose(accountID=self.account_id, tradeID=trade_id)
            self.client.request(r)
            return r.response
        except Exception as e:
            logging.error(f"Error closing trade {trade_id}: {e}")
            return None
