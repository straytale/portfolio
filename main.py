import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt
import tempfile
import os
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.lib.units import cm
from datetime import datetime


# ---------- Data Functions ----------
def get_current_price(code: str):
    """Fetch latest close price for a ticker using yfinance."""
    ticker = yf.Ticker(code)
    hist = ticker.history(period="1d")["Close"]
    if hist.empty:
        raise ValueError(f"Invalid code or no price data: {code}")
    return round(float(hist.iloc[-1]), 6)


def get_data(path="transaction.csv"):
    """Load transaction data and preprocess with cost calculations."""
    df = pd.read_csv(path)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Type"] = df["Type"].where(df["Type"].isin(["CRYPTO", "STOCK"]))
    df["Action"] = df["Action"].where(df["Action"].isin(["SELL", "BUY"]))
    df["Currency"] = df["Currency"].where(df["Currency"].isin(["USD", "TWD"]))

    df["Price"] = df["Price"].round(2)
    df["Quantity"] = df["Quantity"].round(6)

    df["cost_TWD"] = (df["Rate_to_TWD"] * df["Price"] * df["Quantity"]).round(0).astype(np.int64)
    df["cost_USD"] = np.where(
        df["Currency"] == "TWD",
        np.nan,
        (df["Price"] * df["Quantity"]).round(4)
    )
    return df


def do_statistic(df: pd.DataFrame, price: dict):
    number_stat = df.groupby(["Code", "Action"])["Quantity"].sum().unstack(fill_value=0)
    number_stat["Quantity"] = number_stat.get("BUY", 0) - number_stat.get("SELL", 0)

    meta = df.groupby("Code")[["Type", "Currency"]].first()
    statistic = number_stat[["Quantity"]].join(meta)
    statistic["Price_now"] = (statistic.index.map(price.get).fillna(0)).round(2)

    cost_stat = df.groupby(["Code", "Action"])[["cost_TWD", "cost_USD"]].sum().unstack(fill_value=0)

    net_cost_usd = cost_stat["cost_USD"].get("BUY", 0) - cost_stat["cost_USD"].get("SELL", 0)
    statistic["Avg_cost_USD"] = (net_cost_usd / statistic["Quantity"]).replace([np.inf, -np.inf, np.nan], 0).round(2)

    net_cost_twd = cost_stat["cost_TWD"].get("BUY", 0) - cost_stat["cost_TWD"].get("SELL", 0)
    statistic["Avg_cost_TWD"] = (net_cost_twd / statistic["Quantity"]).replace([np.inf, -np.inf, np.nan], 0).round(0).astype(np.int64)

    statistic["Total_cost_TWD"] = (statistic["Quantity"] * statistic["Avg_cost_TWD"]).round(0).astype(np.int64)

    usd2twd = price.get("USDTWD=X", 30)
    statistic["Total_TWD"] = np.where(
        statistic["Currency"] == "TWD",
        statistic["Quantity"] * statistic["Price_now"],
        statistic["Quantity"] * statistic["Price_now"] * usd2twd
    ).round(0).astype(np.int64)

    statistic["Unrealized_PnL"] = statistic["Total_TWD"] - statistic["Total_cost_TWD"]

    # --- FIX: ratio calculation ---
    total_abs = statistic["Total_TWD"].abs().sum()
    statistic["Ratio"] = (statistic["Total_TWD"].abs() / (total_abs if total_abs != 0 else 1) * 100).map(lambda x: f"{x:.2f}%")

    statistic = (
        statistic.reset_index()
        .query("Quantity != 0")
        .sort_values("Total_TWD", ascending=False)
        .reset_index(drop=True)
    )
    return statistic


# ---------- PDF Helpers ----------
def build_table(data, page_width, font_name="Helvetica", font_size=8):
    """Build a ReportLab table with auto column sizing and styling."""
    col_count = len(data[0])
    col_widths = []

    for col in range(col_count):
        max_text = max([str(r[col]) for r in data], key=len)
        w = stringWidth(str(max_text), font_name, font_size) + 20
        col_widths.append(w)

    total_w = sum(col_widths)
    if total_w > page_width:
        scale = page_width / total_w
        col_widths = [w * scale for w in col_widths]

    table = Table(data, colWidths=col_widths, repeatRows=1)

    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#2E3B4E")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('VALIGN', (0,0), (-1,0), 'MIDDLE'),

        ('ALIGN', (0,1), (0,-1), 'LEFT'),
        ('ALIGN', (1,1), (-1,-1), 'CENTER'),
        ('VALIGN', (0,1), (-1,-1), 'MIDDLE'),

        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F9FBFD")]),
        ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
        ('FONTSIZE', (0,0), (-1,-1), font_size),
    ]))

    return table


def plot_block2_charts(statistic):
    """Generate pie charts for distribution summary."""
    imgs = {}
    custom_colors = ["#DCD6F7", "#A6B1E1", "#CACFD6", "#D6E5E3", "#424874"]

    # Stock vs Crypto
    stock_val = statistic.loc[statistic["Type"].str.upper()=="STOCK", "Total_TWD"].abs().sum()
    crypto_val = statistic.loc[statistic["Type"].str.upper()=="CRYPTO", "Total_TWD"].abs().sum()
    values = [stock_val, crypto_val]
    labels = ["Stock", "Crypto"]

    if sum(values) > 0:
        fig, ax = plt.subplots(figsize=(3,3))
        ax.pie(values, labels=labels, autopct="%1.2f%%", startangle=90,
               colors=custom_colors[:2], textprops={'color':'black', 'fontsize':8})
        tmp1 = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        plt.savefig(tmp1.name, bbox_inches="tight", dpi=150)
        imgs["vs"] = tmp1.name
        plt.close()

    # Stock distribution
    stock_df = statistic[statistic["Type"].str.upper()=="STOCK"].copy()
    if not stock_df.empty:
        vals = stock_df["Total_TWD"].abs()
        fig, ax = plt.subplots(figsize=(3,3))
        ax.pie(vals, labels=stock_df["Code"], autopct="%1.2f%%",
               startangle=90, colors=custom_colors[:len(stock_df)],
               textprops={'color':'black', 'fontsize':8})
        tmp2 = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        plt.savefig(tmp2.name, bbox_inches="tight", dpi=150)
        imgs["stock"] = tmp2.name
        plt.close()

    # Crypto distribution
    crypto_df = statistic[statistic["Type"].str.upper()=="CRYPTO"].copy()
    if not crypto_df.empty:
        crypto_df["ShortCode"] = crypto_df["Code"].str[:3]
        vals = crypto_df["Total_TWD"].abs()
        fig, ax = plt.subplots(figsize=(3,3))
        ax.pie(vals, labels=crypto_df["ShortCode"], autopct="%1.2f%%",
               startangle=90, colors=custom_colors[:len(crypto_df)],
               textprops={'color':'black', 'fontsize':8})
        tmp3 = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        plt.savefig(tmp3.name, bbox_inches="tight", dpi=150)
        imgs["crypto"] = tmp3.name
        plt.close()

    return imgs


def format_number(x):
    """Format numbers nicely for table export."""
    try:
        if isinstance(x, (int, float)):
            if abs(x) >= 1:
                return f"{x:,.2f}" if not float(x).is_integer() else f"{int(x):,}"
            else:
                return f"{x:,.4f}"
        else:
            return str(x)
    except:
        return str(x)


def export_pdf(statistic: pd.DataFrame, filename="portfolio_report.pdf"):
    """Export the report to a PDF file."""
    width, height = landscape(A4)
    margin = 1 * cm
    c = canvas.Canvas(filename, pagesize=landscape(A4))

    # === Page 1 ===
    content_h = height - 2 * margin
    block_h = content_h / 2.0
    block1_top = height - margin

    # Title
    c.setFont("Helvetica-Bold", 22)
    c.setFillColor(colors.HexColor("#2E3B4E"))
    c.drawCentredString(width/2, block1_top - 25, "Portfolio Report")

    c.setFont("Helvetica", 10)
    c.setFillColor(colors.HexColor("#666666"))
    c.drawCentredString(width/2, block1_top - 42,
                        f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    # Table
    headers = statistic.columns.tolist()
    display_rows = []
    for _, r in statistic.iterrows():
        row = []
        for col in headers:
            if col in ("Quantity", "Price_now", "Avg_cost_USD", "Avg_cost_TWD",
                       "Total_cost_TWD", "Total_TWD", "Unrealized_PnL"):
                row.append(format_number(r[col]))
            else:
                row.append(str(r[col]))
        display_rows.append(row)
    table_data = [headers] + display_rows

    avail_w = width - 2 * margin
    table = build_table(table_data, avail_w, font_size=9)
    table_w, table_h = table.wrap(avail_w, block_h * 0.8)
    table_x = (width - table_w) / 2.0
    table_y = block1_top - 90 - table_h
    table.drawOn(c, table_x, table_y)

    # Summary
    total_twd = int(statistic["Total_TWD"].sum())
    total_cost = int(statistic["Total_cost_TWD"].sum())
    total_pnl = int(statistic["Unrealized_PnL"].sum())

    summary_y = table_y - 45
    c.setStrokeColor(colors.HexColor("#DDDDDD"))
    c.line(margin, summary_y + 20, width - margin, summary_y + 20)

    c.setFont("Helvetica-Bold", 13)
    pnl_color = colors.green if total_pnl > 0 else (colors.red if total_pnl < 0 else colors.black)
    c.setFillColor(colors.black)
    c.drawString(margin, summary_y, f"Total Value: NT${total_twd:,}")
    c.drawCentredString(width/2, summary_y, f"Total Cost: NT${total_cost:,}")
    c.setFillColor(pnl_color)
    c.drawRightString(width - margin, summary_y, f"Unrealized PnL: NT${total_pnl:,}")

    # Charts
    charts = plot_block2_charts(statistic)
    col_w = (width - 2*margin) / 3.0
    chart_h = block_h - 20

    for i, key in enumerate(["vs", "stock", "crypto"]):
        if key in charts:
            x = margin + i*col_w
            c.drawImage(charts[key], x, margin, width=col_w, height=chart_h,
                        preserveAspectRatio=True, anchor="c")

    for f in charts.values():
        os.unlink(f)

    c.showPage()

    # === Page 2 (Placeholder blocks) ===
    block_w = (width - 2*margin) / 2
    block_h = (height - 2*margin) / 2

    c.setFont("Helvetica-Bold", 14)
    c.setStrokeColor(colors.grey)
    c.setDash(6, 3)

    labels = ["Block A", "Block B", "Block C", "Block D"]
    for i in range(2):
        for j in range(2):
            x = margin + j * block_w
            y = height - margin - (i+1) * block_h
            c.rect(x, y, block_w, block_h, stroke=1, fill=0)
            c.drawCentredString(x + block_w/2, y + block_h/2, labels[i*2 + j])

    c.save()
    return filename


# ---------- Main ----------
if __name__ == "__main__":
    df = get_data("transaction.csv")
    codes = df["Code"].unique().tolist()
    if "USDTWD=X" not in codes:
        codes.append("USDTWD=X")

    current_price = {}
    for code in codes:
        try:
            current_price[code] = get_current_price(code)
        except Exception as e:
            print(f"Warning: {code} skipped ({e})")
            current_price[code] = 0

    statistic = do_statistic(df, current_price)
    print(statistic)

    out = export_pdf(statistic, "portfolio_report.pdf")
    print("PDF generated:", out)
