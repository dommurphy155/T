import asyncio

from logger import log_trade_action
from oanda_client import OandaClient


async def close_all_trades(manual_override=False):
    client = OandaClient()
    open_positions = client.get_open_positions()
    if not open_positions:
        return "No open positions to close."

    results = []
    for position in open_positions:
        for side in ["long", "short"]:
            units = int(position[side]["units"])
            if units != 0:
                trade_id = position[side]["tradeIDs"][0]
                result = client.close_trade(trade_id)
                results.append(
                    f"Closed {side.upper()} {position['instrument']} - "
                    f"{units} units: {result}"
                )
                await log_trade_action(
                    f"Closed trade {trade_id} on {position['instrument']} "
                    f"({side}) - {result}"
                )

                # Sleep to respect rate limits
                await asyncio.sleep(0.5)

    return "\n".join(results)
