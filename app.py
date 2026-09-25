import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(
    page_title="NSE Stock Screener", page_icon="📈", layout="wide"
)

st.title("🇮🇳 NSE Listed Stock Screener")
st.write(
    "Screen live data across all NSE-listed equities using Python & Streamlit."
)


@st.cache_data(ttl=86400)  # Cache the ticker list for 24 hours
def get_nse_tickers():
  # Official NSE equity list CSV URL mirror or source
  url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
  # Adding headers so NSE allows the request
  headers = {"User-Agent": "Mozilla/5.0"}
  try:
    df = pd.read_csv(url, storage_options=headers)
    # Clean symbol columns and append Yahoo Finance suffix (.NS)
    symbols = df["SYMBOL"].str.strip().tolist()
    return symbols
  except Exception as root_err:
    # Fallback to a core list if network blocks the direct CSV call
    st.warning(
        f"Could not download live NSE master list ({root_err}). Using fallback list."
    )
    return [
        "RELIANCE",
        "TCS",
        "HDFCBANK",
        "INFY",
        "ICICIBANK",
        "HINDUNILVR",
        "ITC",
        "SBIN",
        "BHARTIARTL",
        "LICI",
    ]


all_nse_symbols = get_nse_tickers()

# Sidebar Filters
st.sidebar.header("Screener Filters")

# Standard Yahoo Finance Sectors
yfinance_sectors = [
    "All",
    "Basic Materials",
    "Communication Services",
    "Consumer Cyclical",
    "Consumer Defensive",
    "Energy",
    "Financial Services",
    "Healthcare",
    "Industrials",
    "Real Estate",
    "Technology",
    "Utilities"
]

selected_sectors = st.sidebar.multiselect(
    "Filter by Sector",
    yfinance_sectors,
    default=["All"]
)

# Let users choose how many stocks to scan to manage execution speed
max_stocks_to_scan = st.sidebar.slider(
    "Max Stocks to Scan (Performance Control)",
    min_value=5,
    max_value=len(all_nse_symbols),
    value=20,
    step=5,
)

selected_symbols = st.sidebar.multiselect(
    "Select Specific Stocks (Leave blank to scan top N)",
    all_nse_symbols,
    default=all_nse_symbols[:5],
)

max_price = st.sidebar.slider(
    "Maximum Price (₹)", min_value=10, max_value=10000, value=2000, step=50
)


@st.cache_data(ttl=3600)  # Cache stock data results for 1 hour
def fetch_stock_data(tickers):
  data_list = []
  for ticker in tickers:
    formatted_ticker = f"{ticker}.NS"
    try:
      stock = yf.Ticker(formatted_ticker)
      info = stock.info
      data_list.append({
          "Ticker": ticker,
          "Company Name": info.get("shortName", ticker),
          "Sector": info.get("sector", "Unknown"),
          "Price (₹)": info.get("currentPrice", info.get("regularMarketPrice", 0)),
          "Market Cap (₹)": info.get("marketCap", 0),
          "P/E Ratio": info.get("trailingPE", 0),
          "52W High (₹)": info.get("fiftyTwoWeekHigh", 0),
      })
    except Exception:
      continue
  return pd.DataFrame(data_list)


# Determine symbols to process
target_tickers = (
    selected_symbols
    if selected_symbols
    else all_nse_symbols[:max_stocks_to_scan]
)

if target_tickers:
  if st.button("Run Screener"):
    with st.spinner(
        f"Fetching live market data for {len(target_tickers)} stocks..."
    ):
      df = fetch_stock_data(target_tickers)

    if not df.empty:
      # 1. Apply Price filter
      filtered_df = df[df["Price (₹)"] <= max_price]
      
      # 2. Apply Sector filter
      if "All" not in selected_sectors and len(selected_sectors) > 0:
          filtered_df = filtered_df[filtered_df["Sector"].isin(selected_sectors)]

      st.success(
          f"Scan complete! Showing {len(filtered_df)} matching stocks."
      )
      st.dataframe(filtered_df, use_container_width=True)

      # CSV Download Button
      csv = filtered_df.to_csv(index=False).encode("utf-8")
      st.download_button(
          label="Download Results as CSV",
          data=csv,
          file_name="nse_filtered_stocks.csv",
          mime="text/csv",
      )
    else:
      st.warning("No data retrieved. Try selecting different stocks.")
  else:
    st.info("Click **Run Screener** in the main panel to fetch data.")
else:
    st.info("Please choose or select symbols from the sidebar.")
