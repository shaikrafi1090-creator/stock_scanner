import pandas as pd
import streamlit as st
import yfinance as yf
import numpy as np

st.set_page_config(
    page_title="Pro NSE Screener", page_icon="🚀", layout="wide"
)

st.title("🚀 Advanced NSE Stock Screener")
st.write(
    "Combine Technical Analysis, Fundamentals, and Relative Strength in one scan."
)

@st.cache_data(ttl=86400)
def get_nse_tickers():
  url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
  headers = {"User-Agent": "Mozilla/5.0"}
  try:
    df = pd.read_csv(url, storage_options=headers)
    return df["SYMBOL"].str.strip().tolist()
  except Exception:
    return ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "ITC", "SBIN", "BHARTIARTL", "LICI"]

all_nse_symbols = get_nse_tickers()

# ==========================================
# 1. SIDEBAR: CORE & FUNDAMENTAL FILTERS
# ==========================================
st.sidebar.header("1. Fundamental Filters")
max_stocks_to_scan = st.sidebar.slider("Stocks to Scan (Limits API load)", 5, 500, 30, 5)
selected_symbols = st.sidebar.multiselect("Select Specific Stocks", all_nse_symbols, default=all_nse_symbols[:15])

max_price = st.sidebar.number_input("Max Price (₹)", value=5000)
min_mcap_cr = st.sidebar.number_input("Min Market Cap (₹ Crores)", value=1000)
max_pe = st.sidebar.number_input("Max P/E Ratio", value=100)

yfinance_sectors = ["All", "Basic Materials", "Communication Services", "Consumer Cyclical", "Consumer Defensive", "Energy", "Financial Services", "Healthcare", "Industrials", "Technology", "Utilities"]
selected_sectors = st.sidebar.multiselect("Filter by Sector", yfinance_sectors, default=["All"])

# ==========================================
# 2. SIDEBAR: TECHNICAL FILTERS
# ==========================================
st.sidebar.header("2. Technical Filters")
above_50ma = st.sidebar.checkbox("📈 Price > 50-Day MA (Uptrend)")
above_200ma = st.sidebar.checkbox("🚀 Price > 200-Day MA (Long Trend)")
near_52w_high = st.sidebar.checkbox("🔥 Within 10% of 52-Week High")

# ==========================================
# 3. SIDEBAR: PERFORMANCE FILTERS
# ==========================================
st.sidebar.header("3. Relative Performance")
timeframe_options = {"1 Month": "1mo", "3 Months": "3mo", "6 Months": "6mo"}
selected_timeframe = st.sidebar.selectbox("Comparison Timeframe", list(timeframe_options.keys()), index=1)
timeframe_val = timeframe_options[selected_timeframe]

stock_outperform_sector = st.sidebar.checkbox(f"Stock > Sector Return")


# ==========================================
# DATA FETCHING ENGINE
# ==========================================
@st.cache_data(ttl=3600)
def fetch_advanced_data(tickers, timeframe):
  data_list = []
  formatted_tickers = [f"{t}.NS" for t in tickers]
  
  # Fetch historical prices for returns calculation
  try:
    hist = yf.download(formatted_tickers, period=timeframe, progress=False)
    hist_close = hist["Close"] if "Close" in hist else hist
        
    returns = {}
    for col in hist_close.columns:
        valid_prices = hist_close[col].dropna()
        if len(valid_prices) >= 2:
            returns[col] = (valid_prices.iloc[-1] - valid_prices.iloc[0]) / valid_prices.iloc[0] * 100
        else:
            returns[col] = 0
  except Exception:
    returns = {}

  # Fetch fundamental & technical data
  for ticker, f_ticker in zip(tickers, formatted_tickers):
    try:
      stock = yf.Ticker(f_ticker)
      info = stock.info
      
      # Handle potential None values from Yahoo Finance
      price = info.get("currentPrice", info.get("regularMarketPrice", 0)) or 0
      mcap = info.get("marketCap", 0) or 0
      pe = info.get("trailingPE", 0) or 0
      div_yield = info.get("dividendYield", 0) or 0
      ma50 = info.get("fiftyDayAverage", 0) or 0
      ma200 = info.get("twoHundredDayAverage", 0) or 0
      high52 = info.get("fiftyTwoWeekHigh", 0) or 0

      data_list.append({
          "Ticker": ticker,
          "Sector": info.get("sector", "Unknown"),
          "Price (₹)": round(price, 2),
          "Return (%)": round(returns.get(f_ticker, 0), 2),
          "Market Cap (₹ Cr)": round(mcap / 10000000, 2), # Convert to Crores
          "P/E Ratio": round(pe, 2),
          "Div Yield (%)": round(div_yield * 100, 2),
          "50-Day MA": round(ma50, 2),
          "200-Day MA": round(ma200, 2),
          "52W High (₹)": round(high52, 2)
      })
    except Exception:
      continue
      
  return pd.DataFrame(data_list)

# ==========================================
# EXECUTION & FILTERING LOGIC
# ==========================================
target_tickers = selected_symbols if selected_symbols else all_nse_symbols[:max_stocks_to_scan]

if target_tickers:
  if st.button("Run Advanced Screener", type="primary"):
    
    # Progress bar UI
    progress_text = "Scanning market data..."
    my_bar = st.progress(0, text=progress_text)
    
    df = fetch_advanced_data(target_tickers, timeframe_val)
    my_bar.progress(100, text="Scan Complete!")

    if not df.empty:
      # Calculate Dynamic Sector Average Returns
      df["Sector Return (%)"] = round(df.groupby("Sector")["Return (%)"].transform("mean"), 2)
      
      # 1. Apply Core Filters
      f_df = df[
          (df["Price (₹)"] <= max_price) & 
          (df["Market Cap (₹ Cr)"] >= min_mcap_cr)
      ]
      
      # Filter P/E Ratio (ignoring 0 which means unprofitable/no data)
      f_df = f_df[(f_df["P/E Ratio"] <= max_pe) | (f_df["P/E Ratio"] == 0)]
      
      if "All" not in selected_sectors and len(selected_sectors) > 0:
          f_df = f_df[f_df["Sector"].isin(selected_sectors)]
          
      # 2. Apply Technical Filters
      if above_50ma:
          f_df = f_df[f_df["Price (₹)"] > f_df["50-Day MA"]]
      if above_200ma:
          f_df = f_df[f_df["Price (₹)"] > f_df["200-Day MA"]]
      if near_52w_high:
          # Price is greater than 90% of the 52-week high
          f_df = f_df[f_df["Price (₹)"] >= (f_df["52W High (₹)"] * 0.90)]

      # 3. Apply Performance Filter
      if stock_outperform_sector:
          f_df = f_df[f_df["Return (%)"] > f_df["Sector Return (%)"]]

      # Formatting the final display table
      display_cols = ["Ticker", "Sector", "Price (₹)", "Return (%)", "Sector Return (%)", "Market Cap (₹ Cr)", "P/E Ratio", "Div Yield (%)", "52W High (₹)"]
      f_df = f_df[[c for c in display_cols if c in f_df.columns]]

      st.success(f"Found {len(f_df)} stocks matching your advanced criteria.")
      
      # Display as an interactive dataframe
      st.dataframe(
          f_df, 
          use_container_width=True,
          hide_index=True
      )
      
      # Export
      csv = f_df.to_csv(index=False).encode("utf-8")
      st.download_button("Download Final List as CSV", data=csv, file_name="pro_nse_screener.csv", mime="text/csv")
      
    else:
      st.warning("No data retrieved. Try adjusting your limits.")
else:
  st.info("Select symbols from the sidebar to begin.")
