from typing import Callable, Dict, List, Optional
from scipy.interpolate import PchipInterpolator
from scipy.stats import norm
import aiohttp
import asyncio
import api_requests
import utils
import numpy as np

async def iv_interpolator(strike_iv: Dict[float, float]) -> Callable:
    """
    Creates cubic spline interpolator.
    Args:
        strike_iv (Dict): Dictionary that maps strike prices to implied vols.
    Returns:
        Callable: Interpolation function
    """

    # Sort the dictionary by strike prices
    sorted_strikes_ivs = sorted(strike_iv.items())

    # Extract strikes and IVs
    strikes = [strike for strike, _ in sorted_strikes_ivs]
    implied_vols = [iv for _, (iv, _) in sorted_strikes_ivs]
    return PchipInterpolator(strikes, implied_vols, extrapolate=True)

async def normalize_usd_price_to_currency(price: float, index_price: float):
    """
    Normalize the price to a index_price.
    Args:
        price (float): The price to be normalized.
        index_price (float): Index price in USD.
    Returns:
        float: The normalized price.
    """
    if price is None or index_price is None:
        return None
    return round(price/index_price, 4)

async def price_option(
        session: aiohttp.ClientSession,
        currency: str,
        expiry_code: str,
        strike: float,
        option_type: str,
        iv: float,
        existing_futures: List) -> Optional[float]:
    """
    Calculate the price of an option using the Black-76 model.

    Args:
        session (aiohttp.ClientSession): Client session.
        currency (str): The currency of the option (e.g., "BTC").
        expiry_code (str): The expiry code (e.g., "9MAY25").
        strike (float): The strike price of the option.
        option_type (str): The type of the option ("call" or "put").
        iv (float): The implied volatility of the option.
        existing_futures (List): List of existing futures on Deribit for a given currency.

    Returns:
        Optional[float]: The price of the option.
    """
    try:
        if option_type not in ["call", "put"]:
            raise ValueError("Invalid option_type. Must be 'call' or 'put'.")

        time_to_expiry = utils.convert_expiration_to_years(expiry_code)

        if currency.lower() not in ['eth', 'btc', 'paxg_usdc']:
            future_name = f"{currency}-PERPETUAL"
        else:
            future_name = f"{currency}-{expiry_code}"

        if future_name not in existing_futures and currency.lower() in ['eth', 'btc', 'paxg_usdc']:
            future_price = await create_synthetic_future_price(session, currency, expiry_code, existing_futures)
        else:
            future_price = await api_requests.get_underlying_price(session, currency, expiry_code)
        if future_price is None:
            raise ValueError(f"Failed to fetch future price for {currency} and expiry_code: {expiry_code}")

        return await price_black_76(future_price, strike, time_to_expiry, iv, option_type)
    except Exception as e:
        print(f"Error in price_option for {currency}, {expiry_code}, {strike}, {option_type}: {e}")
        return None

async def create_synthetic_future_price(
        session: aiohttp.ClientSession,
        currency: str,
        expiry_code: str,
        existing_futures: List) -> float:
    """
    Creates synthetic future based on the existing futures interpolation/extrapolation.

    Args:
        sesssion (aiohttp.ClientSession): Client sesssion.
        currency (str): The currency of the option (e.g., "BTC").
        expiry_code (str): The expiry code (e.g., "9MAY25").
        existing_futures (List): List of existing futures on Deribit for a given currency.

    Returns:
        float: Synthethic future price
    """
    
    # find sorouding futures
    target_future = f"{currency}-{expiry_code}"

    # Convert all existing futures expiration dates to datetime objects
    existing_dates = [(future, utils.convert_future_name_to_date(future)) for future in existing_futures]

    # Convert the target future expiration date
    target_date = utils.convert_future_name_to_date(target_future)

    # Sort the existing futures by expiration date
    existing_dates.sort(key=lambda x: x[1])

    # Find the two surrounding futures for the target future
    for i in range(1, len(existing_dates)):
        if target_date < existing_dates[0][1]:
            # Extrapolate before first known future
            prev_expiry_code = existing_dates[0][0].split('-')[-1]
            next_expiry_code = existing_dates[1][0].split('-')[-1]
            prev_expiry_date = existing_dates[0][1]
            next_expiry_date = existing_dates[1][1]
            break
        elif target_date > existing_dates[-1][1]:
            # Extrapolate after last known future
            prev_expiry_code = existing_dates[-2][0].split('-')[-1]
            next_expiry_code = existing_dates[-1][0].split('-')[-1]
            prev_expiry_date = existing_dates[-2][1]
            next_expiry_date = existing_dates[-1][1]
            break
        elif existing_dates[i][1] > target_date:
            # Interpolate between two known futures
            prev_expiry_code = existing_dates[i - 1][0].split('-')[-1]
            next_expiry_code = existing_dates[i][0].split('-')[-1]
            prev_expiry_date = existing_dates[i - 1][1]
            next_expiry_date = existing_dates[i][1]
            break
    
    prev_future_task = api_requests.get_underlying_price(session, currency, prev_expiry_code)
    next_future_task = api_requests.get_underlying_price(session, currency, next_expiry_code)

    prev_future_price, next_future_price = await asyncio.gather(prev_future_task, next_future_task)
    # Calculate the time differences in days
    time_diff_target_prev = (target_date - prev_expiry_date).days
    time_diff_next_prev = (next_expiry_date - prev_expiry_date).days
    
    # Apply the linear interpolation formula
    interpolated_price = prev_future_price + (time_diff_target_prev / time_diff_next_prev) * (next_future_price - prev_future_price)
    
    return interpolated_price

async def price_black_76(F: float, K: float, T: float, iv: float, option_type: str) -> Optional[float]:
    """
    Calculate the price of an option using the Black-76 model.

    Args:
        F (float): The current underlying price.
        K (float): The strike price of the option.
        T (float): The time to expiration in years.
        iv (float): The implied volatility of the option.
        option_type (str): The type of the option ("call" or "put").

    Returns:
        Optional[float]: The price of the option.
    """

    try:
        if option_type not in ["call", "put"]:
            raise ValueError("Invalid option_type. Must be 'call' or 'put'.")

        d1 = (np.log(F / K) + 0.5 * iv ** 2 * T) / (iv * np.sqrt(T))
        d2 = d1 - iv * np.sqrt(T)

        if option_type == "call":
            price = np.exp(-0 * T) * (F * norm.cdf(d1) - K * norm.cdf(d2))
        elif option_type == "put":
            price = np.exp(-0 * T) * (K * norm.cdf(-d2) - F * norm.cdf(-d1))
        else:
            raise ValueError("option_type must be 'call' or 'put'")

        return price
    except Exception as e:
        print(f"Error in price_black_76: {e}")
        return None