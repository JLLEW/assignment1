from datetime import datetime, timezone
from typing import Dict, Optional
import pandas as pd
import re

def map_currency(currency: str) -> str:
    """
    Map currency pairs like PAXG_USDC to currency in which contract is settled.

    Args:
        currency (str): currency

    Returns:
        str: settlment currency
    """
    if "USDC" in currency:
        return "USDC"
    return currency

def map_index_name(currency: str) -> str:
    """
    Map currency to its index name.

    Args:
        currency (str): currency

    Returns:
        str: index name
    """
    if currency.lower() in ["btc", "eth"]:
        return f"{currency.lower()}_usd"
    return currency.lower()

def process_strike(strike: str) -> float:
    """
    Processes strike if strikes includes 'd'(used to indicate a decimal eg. XRP)

    Args:
        strike (str): strike string

    Returns:
        float: processed strike.
    """
    return float(strike.replace('d', '.'))

def save(output_dict: Dict, output_file: str) -> None:
    """
    Save the output dictionary to a CSV file in a structured format.

    Args:
        output_dict (Dict): Dictionary with output data.
        output_file (str): Output file path
    """
    # Convert the output dictionary to a list of rows
    rows = []
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for strike, data in sorted(output_dict.items()):
        rows.append({
            "timestamp": timestamp,
            "strike_price": strike,
            "option_type": "call",
            "deribit_mark_price": data["deribit_call_mark_price"],
            "computed_mark_price": data["call_mark_price"]
        })
        rows.append({
            "timestamp": timestamp,
            "strike_price": strike,
            "option_type": "put",
            "deribit_mark_price": data["deribit_put_mark_price"],
            "computed_mark_price": data["put_mark_price"]
        })

    # Convert rows to a DataFrame
    df = pd.DataFrame(rows)

    # Save to a CSV file (append if the file already exists)
    try:
        # If the file exists, append without writing the header again
        with open(output_file, "a") as f:
            df.to_csv(f, index=False, header=f.tell() == 0)
    except Exception as e:
        print(f"Error saving data: {e}")

    print(f"Data saved to {output_file}")

def convert_expiration_to_years(expiration: str) -> Optional[float]:
    """
    Convert an expiration date to the time to expiration in years.

    Args:
        expiration (str): The expiration date in the format "DDMMMYY" (e.g., "9MAY25").

    Returns:
        Optional[float]: The time to expiration in years.
    """
    try:
        match = re.match(r"(\d{1,2})([A-Z]{3})(\d{2})", expiration.upper())
        if not match:
            raise ValueError(f"Invalid expiration format: {expiration}")
        day, month, year = match.groups()
        normalized_date = f"{int(day):02d}{month}{year}"

        # Create a datetime object for the expiration date
        expiration_date = datetime.strptime(normalized_date, "%d%b%y")
        expiration_date = expiration_date.replace(hour=8, tzinfo=timezone.utc)

        # Ensure current_date is also UTC-aware
        current_date = datetime.now(timezone.utc)

        # Calculate total time difference in seconds
        delta_seconds = (expiration_date - current_date).total_seconds()
        if delta_seconds < 0:
            raise ValueError(f"Expiration date {expiration_date} is in the past.")

        # Convert seconds to years
        return delta_seconds / (365 * 24 * 3600)
    except Exception as e:
        print(f"Error in convert_expiration_to_years: {e}")
        return None
    
def convert_future_name_to_date(future_str: str) -> datetime:
    # Extract the expiration part from the future string
    expiration_str = future_str.split(('-'))[-1]
    # Convert expiration to a date using datetime.strptime
    output = datetime.strptime(expiration_str, "%d%b%y")
    return output