import pandas as pd
import numpy as np
import yfinance as yf


def get_current_price(code):
    """Get current price (closing price) from Yahoo Finance"""
    ticker = yf.Ticker(code)
    hist = ticker.history(period="1d")["Close"]
    return round(float(hist.iloc[-1]), 4) if not hist.empty else None


def do_statistic(df, price):
    """Generate portfolio statistics"""

    # Number = Buy - Sell
    number_stat = df.groupby(["Code", "Action"])["Number"].sum().unstack(fill_value=0)
    number_stat["Number"] = number_stat.get("BUY", 0) - number_stat.get("SELL", 0)

    # Take Type / Currency
    meta = df.groupby("Code")[["Type", "Currency"]].first()
    statistic = number_stat[["Number"]].join(meta)

    # Current price
    statistic["Price_now"] = statistic.index.map(price.get).fillna(0)

    # Cost (USD & TWD)
    cost_stat = df.groupby(["Code", "Action"])[["cost_TWD", "cost_USD"]].sum().unstack(fill_value=0)

    # Average cost in USD
    net_cost_usd = cost_stat["cost_USD"].get("BUY", 0) - cost_stat["cost_USD"].get("SELL", 0)
    statistic["Avg_cost_USD"] = (net_cost_usd / statistic["Number"]).replace([np.inf, -np.inf, np.nan], 0).round(2)

    # Average cost in TWD
    net_cost_twd = cost_stat["cost_TWD"].get("BUY", 0) - cost_stat["cost_TWD"].get("SELL", 0)
    statistic["Avg_cost_TWD"] = (net_cost_twd / statistic["Number"]).replace([np.inf, -np.inf, np.nan], 0).round(0).astype(np.int64)

    # Total cost (TWD)
    statistic["Total_cost_TWD"] = (statistic["Number"] * statistic["Avg_cost_TWD"]).round(0).astype(np.int64)

    # Total value (TWD)
    usd2twd = price.get("USDTWD=X", 30)
    statistic["Total_TWD"] = np.where(
        statistic["Currency"] == "TWD",
        statistic["Number"] * statistic["Price_now"],
        statistic["Number"] * statistic["Price_now"] * usd2twd
    ).round(0).astype(np.int64)

    # Unrealized PnL
    statistic["Unrealized_PnL"] = statistic["Total_TWD"] - statistic["Total_cost_TWD"]

    # Portfolio ratio
    total_sum = statistic["Total_TWD"].sum()
    statistic["Ratio"] = (statistic["Total_TWD"] / total_sum * 100).map(lambda x: f"{x:.2f}%")

    # Cleanup & sort
    statistic = (
        statistic.reset_index()
        .query("Number != 0")
        .sort_values("Total_TWD", ascending=False)
        .reset_index(drop=True)
    )

    return statistic


def get_data(path="transaction.csv"):
    """Read transaction history and normalize data"""
    df = pd.read_csv(path)

    # Parse columns
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Type"] = df["Type"].where(df["Type"].isin(["CRYPTO", "STOCK"]))
    df["Action"] = df["Action"].where(df["Action"].isin(["SELL", "BUY"]))
    df["Currency"] = df["Currency"].where(df["Currency"].isin(["USD", "TWD"]))

    # Round numerical columns
    df["Price"] = df["Price"].round(4)
    df["Number"] = df["Number"].round(5)

    # Calculate cost
    df["cost_TWD"] = (df["Rate_to_TWD"] * df["Price"] * df["Number"]).round(0).astype(np.int64)
    df["cost_USD"] = np.where(
        df["Currency"] == "TWD",
        np.nan,
        (df["Price"] * df["Number"]).round(2)
    )

    return df


if __name__ == "__main__":
    # Load transaction data
    df = get_data("transaction.csv")

    # Get all tickers + USD/TWD rate
    codes = df["Code"].unique().tolist() + ["USDTWD=X"]
    current_price = {code: get_current_price(code) for code in codes}

    # Generate statistics
    statistic = do_statistic(df, current_price)
    print(statistic)

    # Portfolio summary
    total_cost = statistic["Total_cost_TWD"].sum()
    total_value = statistic["Total_TWD"].sum()
    total_unrealized_pnl = statistic["Unrealized_PnL"].sum()

    print(f"Total cost: NT$ {total_cost:,}")
    print(f"Total value: NT$ {total_value:,}")
    print(f"Total unrealized PnL: NT$ {total_unrealized_pnl:,}")
