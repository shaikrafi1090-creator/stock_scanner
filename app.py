import pandas as pd
import streamlit as st
import yfinance as yf

st.set_page_config(
    page_title="NSE True RS Matrix", page_icon="📈", layout="wide"
)

st.title("🇮🇳 True Comparative Relative Strength (CRS) Matrix")
st.write("Measures absolute outperformance by calculating the ratio of the Stock Price to the NIFTY 50 Benchmark over time.")

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
# SIDEBAR FILTERS
# ==========================================
st.sidebar.header("Matrix Configuration")
max_stocks = st.sidebar.slider("Max Stocks to Scan", 5, len(all_nse_symbols), 15, 5)
selected_symbols = st.sidebar.multiselect("Select Specific Stocks", all_nse_symbols, default=all_nse_symbols[:10])

# ==========================================
# TRUE RELATIVE STRENGTH (RS) ENGINE
# ==========================================
@st.cache_data(ttl=3600)
def fetch_true_rs_matrix(tickers):
    formatted_tickers = [f"{t}.NS" for t in tickers]
    benchmark = "^NSEI"
    all_tickers = formatted_tickers + [benchmark]

    # Fetch 1-Year Historical Price Data
    hist = yf.download(all_tickers, period="1y", interval="1d", progress=False)
    
    if "Close" in hist:
        closes = hist["Close"]
    else:
        closes = hist

    # Ensure benchmark data exists
    if benchmark not in closes.columns:
        st.error("Benchmark (^NSEI) data failed to download. Please try again.")
        return pd.DataFrame()

    # CRITICAL FIX: Clean missing data to prevent 'None' or 'NaN' errors
    closes = closes.ffill().bfill()

    # 1. Create the True Relative Strength (RS) Ratio DataFrame
    rs_ratios = closes.div(closes[benchmark], axis=0) * 100

    # 2. Helper function to calculate percentage change safely
    def get_rs_momentum(df, days_back):
        if len(df) <= days_back:
            return pd.Series(0, index=df.columns)
        return (df.iloc[-1] - df.iloc[-days_back]) / df.iloc[-days_back] * 100

    # Approximate trading days: 1W=5, 1M=21, 3M=63, 6M=126
    rs_1w = get_rs_momentum(rs_ratios, 5)
    rs_1m = get_rs_momentum(rs_ratios, 21)
    rs_3m = get_rs_momentum(rs_ratios, 63)
    rs_6m = get_rs_momentum(rs_ratios, 126)

    rs_data = []

    # Safe rounding helper to catch lingering NaNs
    def safe_round(val):
        if pd.isna(val):
            return 0.0
        return round(val, 2)

    for ticker, f_ticker in zip(tickers, formatted_tickers):
        if f_ticker in rs_ratios.columns:
            rs_data.append({
                "Ticker": ticker,
                "1W RS Momentum (%)": safe_round(rs_1w.get(f_ticker, 0)),
                "1M RS Momentum (%)": safe_round(rs_1m.get(f_ticker, 0)),
                "3M RS Momentum (%)": safe_round(rs_3m.get(f_ticker, 0)),
                "6M RS Momentum (%)": safe_round(rs_6m.get(f_ticker, 0)),
            })

    return pd.DataFrame(rs_data)

# ==========================================
# UI RENDERING
# ==========================================
target_tickers = selected_symbols if selected_symbols else all_nse_symbols[:max_stocks]

if target_tickers:
    if st.button("Run True RS Matrix"):
        with st.spinner("Calculating Stock/Nifty price ratios..."):
            rs_df = fetch_true_rs_matrix(target_tickers)

        if not rs_df.empty:
            st.subheader("True Comparative RS Matrix")
            st.write("This table shows the percentage change of the **Stock/NIFTY ratio**. Positive numbers (Green) mean the stock is accelerating faster than the market. Negative numbers (Red) mean the stock is lagging the market.")
            
            # Apply background gradient (Heatmap)
            rs_cols = [c for c in rs_df.columns if "Momentum" in c]
            
            styled_rs = rs_df.style.background_gradient(
                cmap="RdYlGn", subset=rs_cols, vmin=-15, vmax=15
            ).format(precision=2)

            st.dataframe(styled_rs, use_container_width=True)
            
            # CSV Download Button
            csv = rs_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="Download RS Data as CSV",
                data=csv,
                file_name="true_rs_matrix.csv",
                mime="text/csv",
            )
        else:
            st.warning("Failed to calculate RS data. Check your network connection to Yahoo Finance.")
