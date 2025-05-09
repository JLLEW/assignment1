import argparse
import asyncio
import aiohttp
import time
from typing import Callable, Dict, List

import api_requests
import utils
import pricing


async def process_strike(
        session: aiohttp.ClientSession,
        currency: str,
        strike: float,
        expiry_code: str,
        standard_strikes: List,
        output_dict: Dict,
        call_iv_fn: Callable,
        put_iv_fn: Callable,
        calls_strike_iv: Dict,
        puts_strike_iv: Dict,
        index_price: float,
        existing_futures: List):
    """
    Process a single strike asynchronously, including call and put pricing.
    """
    if strike in standard_strikes:
        # Use Mark IV
        call_iv = calls_strike_iv[strike][0]
        put_iv = puts_strike_iv[strike][0]
        call_mark_price_act = calls_strike_iv[strike][1]
        put_mark_price_act = puts_strike_iv[strike][1]
    else:
        # Interpolate IV
        call_iv = call_iv_fn(strike)
        put_iv = put_iv_fn(strike)
        call_mark_price_act = None
        put_mark_price_act = None

    # price the options using Black 76
    call_task = pricing.price_option(session, currency, expiry_code, strike, "call", call_iv, existing_futures)
    put_task = pricing.price_option(session, currency, expiry_code, strike, "put", put_iv, existing_futures)

    call_mark_price_pred, put_mark_price_pred = await asyncio.gather(call_task, put_task)

    # Normalize price to currency in which option is settled
    if currency.lower() in ['eth', 'btc']:
        call_mark_price_pred = await pricing.normalize_usd_price_to_currency(call_mark_price_pred, index_price)
        put_mark_price_pred = await pricing.normalize_usd_price_to_currency(put_mark_price_pred, index_price)
    else:
        call_mark_price_pred = round(call_mark_price_pred, 4)
        put_mark_price_pred = round(put_mark_price_pred, 4)

    output_dict[strike] = {
        "call_mark_price": call_mark_price_pred,
        "deribit_call_mark_price": call_mark_price_act,
        "put_mark_price": put_mark_price_pred,
        "deribit_put_mark_price": put_mark_price_act,
    }

async def main_loop(
        currency: str,
        expiry_code: str,
        t1: int,
        t2: int,
        strikes: List[float],
        output_file_path: str
) -> None: 
    # Create aiohttp Client Session
    async with aiohttp.ClientSession() as session:
        # get standard strikes
        strike_iv_price_dicts = await api_requests.get_strike_iv_price_dict(session, currency, expiry_code)
        call_strike_iv_price_dict, _ = strike_iv_price_dicts
        standard_strikes = call_strike_iv_price_dict.keys()

        # Get existing futures since those might be needed to create synthetic underlyings
        existing_futures = await api_requests.get_existing_futures(session, currency)
        
        number_of_iterations = int(t1 / t2)
        iv_interpolation_needed = False

        # Check if there are any non-standard strikes
        if set(strikes) - set(standard_strikes):
            iv_interpolation_needed = True

        for _ in range(number_of_iterations):
            start_time = time.time()
            # Get implied volatilities for all strikes across the option chain
            strike_iv_price_dicts = await api_requests.get_strike_iv_price_dict(session, currency, expiry_code)
            call_strike_iv_price_dict, put_strike_iv_price_dict = strike_iv_price_dicts

            # Get index price
            index_price = await api_requests.get_index_price(session, currency)
            
            # Create the interpolation function only if needed
            call_iv_fn = None
            put_iv_fn = None
            if iv_interpolation_needed:
                call_iv_fn = await pricing.iv_interpolator(call_strike_iv_price_dict)
                put_iv_fn = await pricing.iv_interpolator(put_strike_iv_price_dict)

            output_dict = {}
            # Create tasks for all strikes
            tasks = [
                process_strike(
                    session,
                    currency,
                    strike,
                    expiry_code,
                    standard_strikes,
                    output_dict,
                    call_iv_fn,
                    put_iv_fn,
                    call_strike_iv_price_dict,
                    put_strike_iv_price_dict,
                    index_price,
                    existing_futures) for strike in strikes
            ]

            # Run all tasks concurrently
            await asyncio.gather(*tasks)

            utils.save(output_dict, output_file_path)

            execution_time = time.time() - start_time
            print(f"Execution time: {execution_time} seconds")

            sleep_time = t2 - execution_time
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)







if __name__ == "__main__":
    # Set up argument parser
    parser = argparse.ArgumentParser(description="Run the option pricing main loop.")
    parser.add_argument("--currency", type=str, required=True, help="Currency to use (e.g., BTC, ETH).")
    parser.add_argument("--expiry-code", type=str, required=True, help="Expiry code (e.g., 9MAY25).")
    parser.add_argument("--t1", type=int, required=True, help="Total runtime in seconds.")
    parser.add_argument("--t2", type=int, required=True, help="Interval in seconds for recalculating mark prices.")
    parser.add_argument("--strikes", type=float, nargs="+", required=True, help="List of strike prices.")
    parser.add_argument("--output-file", type=str, default="output.csv", help="Path to the output CSV file where data will be saved")

    # Parse arguments
    args = parser.parse_args()

    if args.currency.upper() not in ["BTC", "ETH", "SOL_USDC", "XRP_USDC", "BNB_USDC", "PAXG_USDC"]:
        parser.error("Invalid currency. Supported currencies are: BTC, ETH, SOL_USDC, XRP_USDC, BNB_USDC, PAXG_USDC.")

     # Run the main loop with parsed arguments
    asyncio.run(main_loop(args.currency, args.expiry_code, args.t1, args.t2, args.strikes, args.output_file))