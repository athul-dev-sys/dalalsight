from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import pandas as pd
import numpy as np

from data_ingestion import fetch_historical_data, NIFTY_TICKERS
from allocator import ModernPortfolioTheoryAllocator

app = FastAPI(title="DalalSight ML Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AllocationRequest(BaseModel):
    risk_capacity: str
    selected_industries: List[str]

# Mocking expected returns since real-time training of BiLSTM/ARIMA is too slow for synchronous API
MOCK_EXPECTED_RETURNS = {
    "RELIANCE.NS": 0.12,
    "TCS.NS": 0.15,
    "HDFCBANK.NS": 0.14,
    "INFY.NS": 0.11,
    "SUNPHARMA.NS": 0.18,
    "TATASTEEL.NS": 0.08,
    "ICICIBANK.NS": 0.13,
    "HINDUNILVR.NS": 0.09
}

print("Loading historical data for Covariance matrix calculation...")
# Fetch 1 year of data to compute covariance matrix quickly
HISTORICAL_PRICES = fetch_historical_data(tickers=NIFTY_TICKERS, period="1y")
print("Startup complete.")

# Map industries back to tickers
INDUSTRY_MAP = {
    "IT": ["TCS.NS", "INFY.NS"],
    "Finance": ["HDFCBANK.NS", "ICICIBANK.NS"],
    "Energy": ["RELIANCE.NS"],
    "Healthcare": ["SUNPHARMA.NS"],
    "Manufacturing": ["TATASTEEL.NS"],
    "FMCG": ["HINDUNILVR.NS"]
}

@app.get("/health")
def health_check():
    return {"status": "ML Engine is running"}

@app.post("/allocate")
def allocate_portfolio(req: AllocationRequest):
    # Determine the pool of tickers based on user's selected industries
    selected_tickers = []
    if not req.selected_industries:
        # Fallback to all if none selected
        selected_tickers = list(MOCK_EXPECTED_RETURNS.keys())
    else:
        for industry in req.selected_industries:
            if industry in INDUSTRY_MAP:
                selected_tickers.extend(INDUSTRY_MAP[industry])
                
    # Further fallback if industries didn't match anything
    if not selected_tickers:
        selected_tickers = list(MOCK_EXPECTED_RETURNS.keys())
        
    # Filter constraints to only the selected pool
    filtered_returns = {k: MOCK_EXPECTED_RETURNS[k] for k in selected_tickers if k in MOCK_EXPECTED_RETURNS}
    filtered_prices = HISTORICAL_PRICES[selected_tickers]
    
    # Initialize the allocator with ONLY the filtered pool
    allocator = ModernPortfolioTheoryAllocator(
        expected_returns=filtered_returns, 
        historical_prices=filtered_prices,
        risk_free_rate=0.07
    )
    
    # Run the Markowitz optimizer
    allocation_weights = allocator.allocate(risk_capacity=req.risk_capacity)
    
    # Filter out near-zero weights
    cleaned_allocation = {k: round(v, 4) for k, v in allocation_weights.items() if v > 0.001}
    
    return {
        "risk_capacity": req.risk_capacity,
        "allocation": cleaned_allocation,
        "expected_portfolio_return": sum(MOCK_EXPECTED_RETURNS[k] * v for k, v in cleaned_allocation.items()),
    }
