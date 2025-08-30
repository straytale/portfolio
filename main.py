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
    # Data, Code, Type, Action, Currency, Rate_to_TWD, Price, Number

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
