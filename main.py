import pandas as pd
import numpy as np
import yfinance as yf
  
def get_current_price(code):

    # yahoo finance
    ticker = yf.Ticker(code)
    price = None
    
    if not ticker.history(period="1d").empty:
        price = round(float(ticker.history(period="1d")["Close"].iloc[-1]), 4)

    return price

if __name__ == "__main__":
    # Read data form csv
    df = pd.read_csv('transaction.csv')

    # Data format
    # Date, Code, Type, Action, Currency, Rate_to_TWD, Price, Number

    # Cost
    df["cost_TWD"] = df["Rate_to_TWD"] * df["Price"] * df["Number"]
    df["cost_USD"] = (df["Price"] * df["Number"]).where(df["Currency"] != "TWD", "-")

    # Normalization
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Type"] = df["Type"].where(df["Type"].isin(["CRYPTO", "STOCK"]), np.nan)
    df["Action"] = df["Action"].where(df["Action"].isin(["SELL", "BUY"]), np.nan)
    df["Currency"] = df["Currency"].where(df["Currency"].isin(["USD", "TWD"]), np.nan)
    df["Rate_to_TWD"] = df["Rate_to_TWD"]
    df["Price"] = df["Price"].round(4)
    df["Number"] = df["Number"].round(5)
    df["cost_TWD"] = (df["Rate_to_TWD"] * df["Price"] * df["Number"]).round(0).astype("Int64")
    df["cost_USD"] = np.where(
        df["Currency"] == "TWD",
        np.nan,
        (df["Price"] * df["Number"]).round(2)
    )

    # Current price dictionary
    codes = df["Code"].tolist()
    codes.append('USDTWD=X')
    current_price = {code: get_current_price(code) for code in set(codes)}

    # Statistic
    number_stat = df.groupby(["Code", "Action"])["Number"].sum().unstack(fill_value=0)
    number_stat["Number"] = number_stat.get("BUY", 0) - number_stat.get("SELL", 0)
    meta = df.groupby("Code")[["Type", "Currency"]].first()
    statistic = number_stat[["Number"]].join(meta)

    # Price now
    statistic["Price_now"] = statistic.index.map(lambda x: current_price.get(x, 0))

    # Avg cost USD
    cost_stat = df.groupby(["Code", "Action"])["cost_USD"].sum().unstack(fill_value=0)
    cost_stat["net_cost_USD"] = cost_stat.get("BUY", 0) - cost_stat.get("SELL", 0)
    statistic = statistic.merge(cost_stat[["net_cost_USD"]], left_on="Code", right_index=True, how="left")
    statistic["Avg_cost_USD"] = statistic.apply(
        lambda row: row["net_cost_USD"] / row["Number"] if row["Number"] != 0 else 0,
        axis=1
    ).round(2)
    statistic = statistic.drop(columns=["net_cost_USD"])

    # Avg cost TWD
    cost_stat = df.groupby(["Code", "Action"])["cost_TWD"].sum().unstack(fill_value=0)
    cost_stat["net_cost_TWD"] = cost_stat.get("BUY", 0) - cost_stat.get("SELL", 0)
    statistic = statistic.merge(cost_stat[["net_cost_TWD"]], left_on="Code", right_index=True, how="left")
    statistic["Avg_cost_TWD"] = statistic.apply(
        lambda row: row["net_cost_TWD"] / row["Number"] if row["Number"] != 0 else 0,
        axis=1
    ).round(0).astype("Int64")
    statistic = statistic.drop(columns=["net_cost_TWD"])

    # Total cost in TWD
    statistic["Total_cost_TWD"] = (statistic["Number"] * statistic["Avg_cost_TWD"]).round(0).astype("Int64")

    # Total in TWD
    usd2twd = get_current_price("USDTWD=X")
    statistic["Total_TWD"] = statistic.apply(
        lambda row: row["Number"] * row["Price_now"]
        if row["Currency"] == "TWD"
        else row["Number"] * row["Price_now"] * usd2twd,
        axis=1
    ).round(0).astype("Int64")

    # Unrealized PnL in TWD
    statistic["Unrealized_PnL"] = statistic["Total_TWD"] - statistic["Total_cost_TWD"]

    # Ratio
    total_sum = statistic["Total_TWD"].sum()
    statistic["Ratio"] = statistic["Total_TWD"] / total_sum * 100
    statistic["Ratio"] = statistic["Ratio"].map(lambda x: f"{x:.2f}%")

    statistic = statistic.reset_index()
    statistic = statistic.sort_values("Total_TWD", ascending=False).reset_index(drop=True)
    statistic = statistic[statistic["Number"] != 0].reset_index(drop=True)

    print(statistic)

    total_cost = (statistic["Number"] * statistic["Avg_cost_TWD"]).round(0).astype("Int64").sum()
    total_value = statistic["Total_TWD"].round(0).astype("Int64").sum()
    total_unrealized_PnL = statistic["Unrealized_PnL"].round(0).astype("Int64").sum()

    print("Total cost: NT$", total_cost)
    print("Total value: NT$", total_value)
    print("Total unrealized_PnL: NT$", total_unrealized_PnL)