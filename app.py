import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(
    page_title="NSE Stock Screener", page_icon="📈", layout="wide"
)

st.title("🇮🇳 NSE Listed Stock Screener (Performance Edition)")
st.write(
    "Screen live data and relative strength across NSE-listed equities using Python."
)

@st.cache_data(ttl=86400)
def get_nse_tickers():
  url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
  headers = {"User-Agent": "Mozilla/5.0"}
  try:
    df = pd.read_csv(url, storage_options=headers)
    symbols = df["SYMBOL"].str.strip().tolist()
    return symbols
  except Exception as root_err:
    st.warning("Could not download live NSE master list. Using fallback list.")
    return ["RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "ITC", "SBIN", "BHARTIARTL", "LICI"]

all_nse_symbols = get_nse_tickers()

# ==========================================
# 1. SIDEBAR FILTERS (CORE & PERFORMANCE)
# ==========================================
st.sidebar.header("1. Core Filters")
max_stocks_to_scan = st.sidebar.slider("Max Stocks to Scan", 5, len(all_nse_symbols), 20, 5)
selected_symbols = st.sidebar.multiselect("Select Specific Stocks", all_nse_symbols, default=all_nse_symbols[:10])
max_price = st.sidebar.slider("Maximum Price (₹)", 10, 10000, 5000, 50)

yfinance_sectors = [
    "All", "Basic Materials", "Communication Services", "Consumer Cyclical",
    "Consumer Defensive", "Energy", "Financial Services", "Healthcare",
    "Industrials", "Real Estate", "Technology", "Utilities"
]
selected_sectors = st.sidebar.multiselect("Filter by Sector", yfinance_sectors, default=["All"])

st.sidebar.header("2. Performance Filters")
timeframe_options = {"1 Month": "1mo", "3 Months": "3mo", "6 Months": "6mo", "1 Year": "1y"}
selected_timeframe = st.sidebar.selectbox("Comparison Timeframe", list(timeframe_options.keys()), index=1)
timeframe_val = timeframe_options[selected_timeframe]

# New Checkboxes for Relative Strength
sector_outperform_nifty = st.sidebar.checkbox(f"Sector > NIFTY 50 ({selected_timeframe})")
stock_outperform_sector = st.sidebar.checkbox(f"Stock > Sector ({selected_timeframe})")

# ==========================================
# 2. DATA FETCHING FUNCTION
# ==========================================
@st.cache_data(ttl=3600)
def fetch_stock_data(tickers, timeframe):
  data_list = []
  formatted_tickers = [f"{t}.NS" for t in tickers]
  
  # Add NIFTY 50 index (^NSEI) to calculate benchmark performance
  all_tickers = formatted_tickers + ["^NSEI"]  

  # Fetch historical prices for returns calculation
  try:
    hist = yf.download(all_tickers, period=timeframe, progress=False)
    # yfinance returns multi-index columns for multiple tickers
    if "Close" in hist:
        hist_close = hist["Close"]
    else:
        hist_close = hist
        
    returns = {}
    for col in hist_close.columns:
        valid_prices = hist_close[col].dropna()
        if len(valid_prices) >= 2:
            # (Latest Price - Past Price) / Past Price * 100
            returns[col] = (valid_prices.iloc[-1] - valid_prices.iloc[0]) / valid_prices.iloc[0] * 100
        else:
            returns[col] = 0
            
    nifty_return = returns.get("^NSEI", 0)
  except Exception:
    returns = {}
    nifty_return = 0

  # Fetch fundamental data
  for ticker, f_ticker in zip(tickers, formatted_tickers):
    try:
      stock = yf.Ticker(f_ticker)
      info = stock.info
      data_list.append({
          "Ticker": ticker,
          "Company Name": info.get("shortName", ticker),
          "Sector": info.get("sector", "Unknown"),
          "Price (₹)": info.get("currentPrice", info.get("regularMarketPrice", 0)),
          "Return (%)": round(returns.get(f_ticker, 0), 2),
          "Market Cap (₹)": info.get("marketCap", 0),
          "P/E Ratio": info.get("trailingPE", 0)
      })
    except Exception:
      continue
      
  return pd.DataFrame(data_list), round(nifty_return, 2)

# ==========================================
# 3. EXECUTION & FILTERING LOGIC
# ==========================================
target_tickers = selected_symbols if selected_symbols else all_nse_symbols[:max_stocks_to_scan]

if target_tickers:
  if st.button("Run Screener"):
    with st.spinner(f"Fetching {selected_timeframe} performance data for {len(target_tickers)} stocks..."):
      df, nifty_return = fetch_stock_data(target_tickers, timeframe_val)

    if not df.empty:
      # Step 1: Calculate Dynamic Sector Average Returns
      df["Sector Return (%)"] = round(df.groupby("Sector")["Return (%)"].transform("mean"), 2)

      st.markdown(f"### NIFTY 50 Benchmark Return ({selected_timeframe}): **{nifty_return}%**")
      
      # Step 2: Apply Filters
      filtered_df = df[df["Price (₹)"] <= max_price]
      
      if "All" not in selected_sectors and len(selected_sectors) > 0:
          filtered_df = filtered_df[filtered_df["Sector"].isin(selected_sectors)]
          
      # Apply relative strength conditions based on checkboxes
      if sector_outperform_nifty:
          filtered_df = filtered_df[filtered_df["Sector Return (%)"] > nifty_return]
          
      if stock_outperform_sector:
          filtered_df = filtered_df[filtered_df["Return (%)"] > filtered_df["Sector Return (%)"]]

      # Reorder columns for a cleaner UI
      cols = ["Ticker", "Company Name", "Sector", "Price (₹)", "Return (%)", "Sector Return (%)", "Market Cap (₹)", "P/E Ratio"]
      filtered_df = filtered_df[[c for c in cols if c in filtered_df.columns]]

      st.success(f"Scan complete! Showing {len(filtered_df)} stocks matching your performance criteria.")
      st.dataframe(filtered_df, use_container_width=True)
      
      # Helpful Context Note
      st.info("💡 **Note on Sector Returns:** The 'Sector Return (%)' is dynamically calculated as the average return of the *scanned* stocks in that sector. For the most accurate sector comparisons, increase the 'Max Stocks to Scan' limit.")
      
    else:
      st.warning("No data retrieved. Try selecting different stocks.")
else:
  st.info("Please select symbols from the sidebar.")
