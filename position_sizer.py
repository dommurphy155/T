def calculate_position_size(*args, **kwargs):
    # Minimal stub for compatibility
    return 1

class PositionSizer:
    def __init__(self, risk_percentage: float, account_balance: float):
        """
        :param risk_percentage: Percentage of account balance to risk per trade (e.g., 1.0 for 1%)
        :param account_balance: Current account balance in GBP
        """
        self.risk_percentage = risk_percentage
        self.account_balance = account_balance

    def calculate_position_size(self, stop_loss_pips: float, pip_value: float = 0.0001, instrument: str = "GBP_USD") -> int:
        """
        Calculates position size based on risk and stop loss.
        
        :param stop_loss_pips: Distance from entry to stop loss in pips
        :param pip_value: Value of a pip for the pair (default 0.0001 for most major pairs)
        :param instrument: Currency pair, defaults to GBP_USD
        :return: Position size in units (rounded to nearest whole unit)
        """
        if stop_loss_pips <= 0:
            raise ValueError("Stop loss in pips must be greater than 0")

        # Total £ to risk per trade
        risk_amount = self.account_balance * (self.risk_percentage / 100.0)

        # Value per pip per unit of base currency
        # For GBP/USD, 1 pip = $0.0001, and 1 unit = 0.0001 USD
        # But we assume GBP account, so we convert pip_value to GBP
        # Approx conversion if needed can be added later
        pip_value_gbp = pip_value  # Assumes pip_value already in GBP

        # Calculate units to trade
        units = risk_amount / (stop_loss_pips * pip_value_gbp)

        return int(units)
