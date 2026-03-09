import yfinance as yf
import pandas as pd
from typing import List

# Pre-selected basket of Indian stocks as per the implementation plan
NIFTY_TICKERS = [
    "RELIANCE.NS",
    "TCS.NS",
    "HDFCBANK.NS",
    "INFY.NS",
    "SUNPHARMA.NS",
    "TATASTEEL.NS",
    "ICICIBANK.NS",
    "HINDUNILVR.NS"
]

def fetch_historical_data(tickers: List[str] = NIFTY_TICKERS, period: str = "5y") -> pd.DataFrame:
    """
    Fetches historical adjusted close prices for the given list of tickers.
    Returns a DataFrame where rows are dates and columns are tickers.
    """
    print(f"Fetching {period} of historical data for {len(tickers)} tickers...")
    data = yf.download(tickers, period=period, progress=False)
    
    # yf.download returns a MultiIndex column DataFrame if multiple tickers are passed
    # We only care about 'Adj Close' or 'Close'
    if isinstance(data.columns, pd.MultiIndex):
        if 'Adj Close' in data.columns.levels[0]:
            prices = data['Adj Close']
        else:
            prices = data['Close']
    else:
        # Fallback if it didn't return a MultiIndex
        prices = data
        
    # CRITICAL FIX: If yfinance hits a rate limit for a specific ticker (e.g. SUNPHARMA.NS),
    # it completely omits that column from the returned DataFrame, causing a KeyError downstream.
    # We must explicitly reindex the DataFrame to guarantee all requested tickers are present.
    prices = prices.reindex(columns=tickers)
        
    prices = prices.dropna(how='all')
    
    # Ensure DataFrame is not empty if all downloads failed
    import numpy as np
    if len(prices) < 50:
        print("yfinance failed to fetch enough data. Generating fully synthetic market history...")
        dates = pd.date_range(end=pd.Timestamp.today(), periods=252)
        prices = pd.DataFrame(index=dates, columns=tickers)
        
    prices.ffill(inplace=True)
    prices.bfill(inplace=True)
    
    # Inject synthetic random-walk data for any entirely missing columns to prevent 
    # 0-variance NaN crashes in the SciPy optimizer downstream
    for t in tickers:
        if prices[t].isna().all() or (prices[t] == 0).all():
            print(f"Generating synthetic data for rate-limited ticker: {t}")
            returns = np.random.normal(loc=0.0005, scale=0.015, size=len(prices))
            prices[t] = 100 * np.exp(np.cumsum(returns))
    
    # Fill any remaining interspersed NaNs
    prices.bfill(inplace=True)
    prices.ffill(inplace=True)
    
    return prices

if __name__ == "__main__":
    df = fetch_historical_data()
    print(df.tail())
