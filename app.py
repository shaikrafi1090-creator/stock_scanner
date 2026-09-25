import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(
    page_title="NSE Screener & RS Matrix", page_icon="📈", layout="wide"
)

st.title("🇮🇳 Advanced NSE Screener & RS Matrix")
st.write("Screen fundamental data and analyze momentum using a multi-timeframe Relative Strength heatmap.")

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
# SIDEBAR FILTERS (Global)
# ==========================================
st.sidebar.header("Global Watchlist")
max_stocks = st.sidebar.slider("Max Stocks to Scan", 5, len(all_nse_symbols), 15, 5)
selected_symbols = st.sidebar.multiselect("Select Specific Stocks", all_nse_symbols, default=all_nse_symbols[:10])

st.sidebar.header("Fundamental Filters (Tab 1)")
max_price = st.sidebar.slider("Maximum Price (₹)", 10, 10000, 5000, 50)
yfinance_sectors = ["All", "Basic Materials", "Communication Services", "Consumer Cyclical", "Energy", "Financial Services", "Healthcare", "Industrials", "Technology", "Utilities"]
selected_sectors = st.sidebar.multiselect("Filter by Sector", yfinance_sectors, default=["All"])

# ==========================================
# DATA FETCHING ENGINE
# ==========================================
@st.cache_data(ttl=3600)
def fetch_matrix_data(tickers):
    fundamental_data = []
    formatted_tickers = [f"{t}.NS" for t in tickers]
    all_tickers = formatted_tickers + ["^NSEI"]  # Include NIFTY 50

    # 1. Fetch 1-Year Historical Price Data for RS Matrix
    hist = yf.download(all_tickers, period="1y", interval="1d", progress=False)
    
    if "Close" in hist:
        closes = hist["Close"]
    else:
        closes = hist

    # Helper function to calculate percentage returns
    def get_return(df, days_back):
        if len(df) <= days_back:
            return pd.Series(0, index=df.columns)
        return (df.iloc[-1] - df.iloc[-days_back]) / df.iloc[-days_back] * 100

    # Approximate trading days: 1W=5, 1M=21, 3M=63, 6M=126
    ret_1w = get_return(closes, 5)
    ret_1m = get_return(closes, 21)
    ret_3m = get_return(closes, 63)
    ret_6m = get_return(closes, 126)

    nifty_rets = {
        "1W": ret_1w.get("^NSEI", 0),
        "1M": ret_1m.get("^NSEI", 0),
        "3M": ret_3m.get("^NSEI", 0),
        "6M": ret_6m.get("^NSEI", 0),
    }

    rs_data = []

    # 2. Fetch Fundamental Data
    for ticker, f_ticker in zip(tickers, formatted_tickers):
        try:
            stock = yf.Ticker(f_ticker)
            info = stock.info
            
            # Fundamentals
            fundamental_data.append({
                "Ticker": ticker,
                "Company Name": info.get("shortName", ticker),
                "Sector": info.get("sector", "Unknown"),
                "Price (₹)": info.get("currentPrice", 0),
                "Market Cap (₹)": info.get("marketCap", 0),
                "P/E Ratio": info.get("trailingPE", 0)
            })

            # Relative Strength Data (Stock Return - Nifty Return)
            rs_data.append({
                "Ticker": ticker,
                "1W RS": round(ret_1w.get(f_ticker, 0) - nifty_rets["1W"], 2),
                "1M RS": round(ret_1m.get(f_ticker, 0) - nifty_rets["1M"], 2),
                "3M RS": round(ret_3m.get(f_ticker, 0) - nifty_rets["3M"], 2),
                "6M RS": round(ret_6m.get(f_ticker, 0) - nifty_rets["6M"], 2),
            })
            
        except Exception:
            continue

    return pd.DataFrame(fundamental_data), pd.DataFrame(rs_data), nifty_rets

# ==========================================
# TABS & UI RENDERING
# ==========================================
target_tickers = selected_symbols if selected_symbols else all_nse_symbols[:max_stocks]

if target_tickers:
    if st.button("Run Analytics Engine"):
        with st.spinner("Processing historical data and fundamentals..."):
            fund_df, rs_df, nifty_rets = fetch_matrix_data(target_tickers)

        if not fund_df.empty:
            tab1, tab2 = st.tabs(["📊 Fundamental Screener", "🔥 Relative Strength (RS) Matrix"])

            # TAB 1: FUNDAMENTAL SCREENER
            with tab1:
                st.subheader("Fundamental Data")
                filtered_df = fund_df[fund_df["Price (₹)"] <= max_price]
                if "All" not in selected_sectors and len(selected_sectors) > 0:
                    filtered_df = filtered_df[filtered_df["Sector"].isin(selected_sectors)]
                st.dataframe(filtered_df, use_container_width=True)

            # TAB 2: RS MATRIX HEATMAP
            with tab2:
                st.subheader("Multi-Timeframe Relative Strength")
                st.markdown(
                    f"**NIFTY 50 Benchmarks:** "
                    f"1W: `{nifty_rets['1W']:.2f}%` | "
                    f"1M: `{nifty_rets['1M']:.2f}%` | "
                    f"3M: `{nifty_rets['3M']:.2f}%` | "
                    f"6M: `{nifty_rets['6M']:.2f}%`"
                )
                st.write("Values show how much the stock beat (+) or lagged (-) the NIFTY 50. Styled as a heatmap for quick momentum scanning.")
                
                # Apply background gradient (Heatmap) to the RS columns
                rs_cols = ["1W RS", "1M RS", "3M RS", "6M RS"]
                
                # RdYlGn is a standard matplotlib colormap (Red -> Yellow -> Green)
                # vmin/vmax locks the color scale to -20% to +20% for consistent visual contrast
                styled_rs = rs_df.style.background_gradient(
                    cmap="RdYlGn", subset=rs_cols, vmin=-20, vmax=20
                ).format(precision=2)

                st.dataframe(styled_rs, use_container_width=True)
                
        else:
            st.warning("No data retrieved.")
