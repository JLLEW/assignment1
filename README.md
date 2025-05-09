### How to run

Run script to generate data in real-time

available currencies
```
["BTC", "ETH", "SOL_USDC", "XRP_USDC", "BNB_USDC", "PAXG_USDC"]
```

```
python main.py --currency BTC --expiry_code 30MAY25 --t1 10 --t2 5 --strikes 91000 92000 94000 --output-file btc_test.py
```

visualisation

```
python visualizer.py --input-file btc_test.py
```

**Each file needs to be deleted if name is being reused, otherwise new prices will be appended to the file. Still works with visualizer and displays as a separate timestamp tab**


### Asumptions made
1. Mark prices should be returned in crypto.
2. All options (BTC, ETH, PAXG, BNB, SOL, XRP) should be handled, based on Deribit availability.
3. REST API is used instead of WebSockets due to acceptable latency and simplicity.
4. T1 means total script runtime, and T2 is the interval at which mark prices should be recalculated.
5. I can save data in a chosen form at each interval as the format was not specified

### Key Challenges
1. Time synchronization and API delay: There was a ~1s delay between fetching data and computing results, causing mismatches with Deribit mark prices. I resolved this by fetching the mark price and order book in a single API call.
2. API rate limits: Deribit blocked my IP for a moment due to too many requests. Solved by batching mark_iv requests across strikes and using a global aiohttp session.
3. IV Interpolation Errors: I tried different interpolation methods for interpolating IV for non-standard strikes. Quadratic interpolation caused incorrect prices for non-standard strikes, especially deep OTM puts. Interpolated IVs where not reasonable. Switched to cubic spline interpolation, which solved the problem.
4. Deciding how to price options with standard strikes:
    - Idea 1: Use the mark price based on the order book at some mid-level depth (like depth 5), taking market pressure into account. Pros: Reacts well to actual supply and demand. Cons: Can be easily manipulated, especially when the book is illiquid or heavily skewed to one side. I noticed that at depth 5, the prices already differ quite a bit from Deribit’s mark prices. Even though the assignment says I should not match Deribit exactly, this shows that order book pricing doesn’t work well for illiquid instruments. For example, I looked at the BTC-9MAY25-91000-C order book and saw low liquidity, with waiting orders only deeper in the book and far from the mark price. This confirms the concern about how easy it is to skew the price in such cases. I’ve left this method in the code anyway, in case you want to check it.
    - Idea 2: Use the Black-76 model to calculate the mark price, using the mark_iv from standard strike prices. Pros: Based on solid theory, more stable, and reflects the theoretical value using key option components like time to expiry, strike, and underlying price. Cons: Black-76 gives a theoretical value, but it doesn’t account for actual supply/demand or liquidity at the moment.
    Due to noticed problems in Idea 1 I decided to use Black 76
5. Black-Scholes vs Black 76: Initially used Black-Scholes instead of Black 76. Black-Scholes was underpicing puts and overpricing calls.
6. Time to expiry calculation: Used .seconds() instead of .total_seconds(), which led to incorrect time to expiry for longer-term options. Fixed the issue.
7. Conversion issue: Initially used underlying price instead of index price to normalize option values to crypto.
8. I noticed that some options are priced using synthethic forward price that cannot be fetched from deribit API. I read in this doc: https://statics.deribit.com/files/DeribitInstitutionalSetupGuide.pdf that the synthetic futures price is obtained via linear inter/extrapolation between existing futures mark prices. I had to implement my own synthetics pricing based on that. Synthetic interpolation does not work well for extrapolation -> If the expiry date is not between any of the futures. Perhaps some better interpolation method should fix it, however I run out of time to work on it.
9. Multiple currencies: I firstly implemented my solution for BTC only, when I started scaling it to all available options it challenged me to understand which underlyings are used: future, index, synthetic. Then I was challenged by mess in my code which arose due to all of the changes. Eventually, I had to rewrite everything for clarity.

### Solution design
1. Standard strikes pricing:
    - Mark price is computed using the Black 76 model with mark_iv from Deribit.
    - Mark price in crypto is normalized using index price
    - I compared this with mid-market order book-based pricing, but rejected it due to poor reliability in low-liquidity conditions.
    - Chose theoretical Black 76 because it yields stable results and reflects consistent pricing logic.
2. Non-Standard strikes pricing:
    - Priced using the Black 76 model.
    - Since mark_iv isn’t directly available, I used cubic spline interpolation across standard strikes' IVs.
    - Earlier attempts (linear and quadratic interpolation) failed to interpolate IV's correctly.
3. Design Tradeoffs:
    - REST API chosen over WebSockets for simplicity and control over request timing.
    - Emphasized asynchronous handling of multiple HTTP requests to stay within T2 intervals and reduce latency.
4. Error Handling
    - Implemented exception catching and retry mechanisms in case of timeouts or API failures.
    - Designed system to run iteratively every T2 seconds without breaching T1 total time constraint.
5. Visualizer Implementation:
    - Implemented simple visualizer using Tkinter to better see how options are priced than checking output file manually.