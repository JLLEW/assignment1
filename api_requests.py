import aiohttp

from typing import Any, Dict, List, Tuple, Optional

import utils


async def fetch_data(session: aiohttp.ClientSession, url: str, params: Dict[str, Any], retries: int = 5) -> Optional[Dict]:
    """
    Helper function to fetch data from an API with retry logic.

    Args:
        sesssion (aiohttp.ClientSession): Client sesssion.
        url (str): The API endpoint URL.
        params (Dict[str, Any]): Query parameters for the API request.
        retries (int): Number of retry attempts if the request fails.

    Returns:
        Optional[Dict]: The JSON response from the API, or None if the request fails.
    """
    for attempt in range(retries):
        try:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if "result" in data:
                        return data["result"]
                    else:
                        print(f"Unexpected response format: {data}")
                else:
                    print(f"Attempt {attempt + 1} failed with status {response.status}")
        except Exception as e:
            print(f"Attempt {attempt + 1} failed with exception: {e}")

    print(f"Failed to fetch data from {url} after {retries} retries")
    return None

async def get_strike_iv_price_dict(
        session: aiohttp.ClientSession,
        currency: str,
        expiry_code: str
) -> Tuple:
    """
    Fetch dictionary that maps strike price to their mark_iv and mark_price

    Args:
        sesssion (aiohttp.ClientSession): Client sesssion.
        currency (str): The currency for which to fetch the index price (e.g., 'BTC', 'ETH').
        expiry_code (str): The expiry code (e.g., '9MAY25').

    Returns:
        Tuple: Tuple of call and put strike - mark_iv, mark_price mappings as dicts.
    """

    url = "https://www.deribit.com/api/v2/public/get_book_summary_by_currency"
    params = {
        "currency": utils.map_currency(currency),
        "kind": "option"}

    try:
        data = await fetch_data(session, url, params)
    except Exception as e:
        print(f"Could not get strike iv dictionary for {currency}")
        return None
    
    # Filter and process the data
    filtered = []
    for item in data:
        if expiry_code in item["instrument_name"] and item["mark_iv"] is not None:
            filtered.append(
                {
                    "instrument_name": item["instrument_name"],
                    "mark_iv": item["mark_iv"] / 100,  # Convert percentage to decimal
                    'mark_price': item["mark_price"],
                    "strike": utils.process_strike(item["instrument_name"].split("-")[-2]),
                    "option_type": item["instrument_name"].split("-")[-1],  # C or P
                }
            )

    calls_dict = {}
    puts_dict = {}
    for option in filtered:
        strike = option["strike"]
        iv = option["mark_iv"]
        mark_price = round(option["mark_price"], 4)

        if option["option_type"] == "C":
            calls_dict[strike] = (iv, mark_price)
        else:
            puts_dict[strike] = (iv, mark_price)
    
    return calls_dict, puts_dict

async def get_existing_futures(session: aiohttp.ClientSession, currency: str) -> List:
    """
    Fetch list of existing futures for a given currency excluding perpetuals.

    Args:
        sesssion (aiohttp.ClientSession): Client sesssion.
        currency (str): The currency for which to fetch the index price (e.g., 'BTC', 'ETH').

    Returns:
        List: List of existing futures.
    """
    url = "https://www.deribit.com/api/v2/public/get_instruments"
    
    params={
        "currency": utils.map_currency(currency),
        "kind": "future"}
    
    data = await fetch_data(session, url, params)

    filtered = [item["instrument_name"] for item in data if currency in item["instrument_name"] if "PERP" not in item["instrument_name"]]

    return filtered

async def get_index_price(session: aiohttp.ClientSession, currency: str) -> Optional[float]:
    """
    Fetch the current index price for a given currency from Deribit.

    Args:
        sesssion (aiohttp.ClientSession): Client sesssion.
        currency (str): The currency for which to fetch the index price (e.g., 'BTC', 'ETH').

    Returns:
        Optional[float]: The current index price, or None if the request fails.
    """

    url = "https://www.deribit.com/api/v2/public/get_index_price"
    params = {"index_name": utils.map_index_name(currency)}
    data = await fetch_data(session, url, params)
    if data:
        return data.get("index_price")
    return None

async def get_underlying_price(session: aiohttp.ClientSession, currency: str, expiry_code: str) -> Optional[float]:
    """
    Fetch the current price of the underlying asset (BTC or ETH) from Deribit.

    Args:
        sesssion (aiohttp.ClientSession): Client sesssion.
        currency (str): The currency of the asset (e.g., 'BTC' or 'ETH').
        expiry_code (str): The expiry code (e.g., '9MAY25').

    Returns:
        Optional[float]: The current price of the underlying asset, or None if the request fails.
    """
    url = "https://www.deribit.com/api/v2/public/ticker"
    if currency.lower() not in ['eth', 'btc', 'paxg_usdc']:
        params = {"instrument_name": f"{currency}-PERPETUAL"}
    else:
        params = {"instrument_name": f"{currency}-{expiry_code}"}

    data = await fetch_data(session, url, params)
    if data:
        return data.get("mark_price")
    return None