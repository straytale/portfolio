import pandas as pd
import numpy as np
import yfinance as yf
import sys
import matplotlib.pyplot as plt
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, HRFlowable
)
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from datetime import datetime
import io
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.platypus import Frame, PageTemplate, BaseDocTemplate
from reportlab.pdfbase.pdfmetrics import stringWidth

def get_current_price(code):
    ticker = yf.Ticker(code)
    hist = ticker.history(period="1d")["Close"]
    if hist.empty:
        print(f"ERROR! Invalid code: {code}")
        sys.exit(1)
    return round(float(hist.iloc[-1]), 4)


def do_statistic(df, price):
    number_stat = df.groupby(["Code", "Action"])["Number"].sum().unstack(fill_value=0)
    number_stat["Number"] = number_stat.get("BUY", 0) - number_stat.get("SELL", 0)

    meta = df.groupby("Code")[["Type", "Currency"]].first()
    statistic = number_stat[["Number"]].join(meta)
    statistic["Price_now"] = statistic.index.map(price.get).fillna(0)

    cost_stat = df.groupby(["Code", "Action"])[["cost_TWD", "cost_USD"]].sum().unstack(fill_value=0)
    net_cost_usd = cost_stat["cost_USD"].get("BUY", 0) - cost_stat["cost_USD"].get("SELL", 0)
    statistic["Avg_cost_USD"] = (net_cost_usd / statistic["Number"]).replace([np.inf, -np.inf, np.nan], 0).round(2)

    net_cost_twd = cost_stat["cost_TWD"].get("BUY", 0) - cost_stat["cost_TWD"].get("SELL", 0)
    statistic["Avg_cost_TWD"] = (net_cost_twd / statistic["Number"]).replace([np.inf, -np.inf, np.nan], 0).round(0).astype(np.int64)

    statistic["Total_cost_TWD"] = (statistic["Number"] * statistic["Avg_cost_TWD"]).round(0).astype(np.int64)

    usd2twd = price.get("USDTWD=X", 30)
    statistic["Total_TWD"] = np.where(
        statistic["Currency"] == "TWD",
        statistic["Number"] * statistic["Price_now"],
        statistic["Number"] * statistic["Price_now"] * usd2twd
    ).round(0).astype(np.int64)

    statistic["Unrealized_PnL"] = statistic["Total_TWD"] - statistic["Total_cost_TWD"]

    total_sum = statistic["Total_TWD"].sum()
    statistic["Ratio"] = (statistic["Total_TWD"] / total_sum * 100).map(lambda x: f"{x:.2f}%")

    statistic = (
        statistic.reset_index()
        .query("Number != 0")
        .sort_values("Total_TWD", ascending=False)
        .reset_index(drop=True)
    )

    return statistic


def get_data(path="transaction.csv"):
    df = pd.read_csv(path)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Type"] = df["Type"].where(df["Type"].isin(["CRYPTO", "STOCK"]))
    df["Action"] = df["Action"].where(df["Action"].isin(["SELL", "BUY"]))
    df["Currency"] = df["Currency"].where(df["Currency"].isin(["USD", "TWD"]))

    df["Price"] = df["Price"].round(4)
    df["Number"] = df["Number"].round(5)

    df["cost_TWD"] = (df["Rate_to_TWD"] * df["Price"] * df["Number"]).round(0).astype(np.int64)
    df["cost_USD"] = np.where(
        df["Currency"] == "TWD",
        np.nan,
        (df["Price"] * df["Number"]).round(2)
    )
    return df


def make_pie(labels, sizes, title):
    # 放大圖，字體也稍加大
    fig, ax = plt.subplots(figsize=(3.6, 3.6))
    ax.pie(
        sizes,
        labels=labels,
        autopct='%1.1f%%',
        textprops={'fontsize': 8}
    )
    ax.set_title(title, fontsize=10, fontweight='bold')
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches="tight", dpi=150)
    plt.close(fig)
    buf.seek(0)
    return buf


def export_pdf(statistic, pies, filename="portfolio_report.pdf"):
    c = canvas.Canvas(filename, pagesize=A4)
    width, height = A4
    margin = 30
    block_height = (height - 2*margin) / 3

    styles = getSampleStyleSheet()

    # ===== 區塊 1：標題 =====
    top_y = height - margin
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width/2, top_y-20, "Portfolio Report")
    c.setFont("Helvetica", 8)

    # ===== 區塊 1：表格（嚴格限制在區塊高度內）=====
    headers = statistic.columns.tolist()
    rows = statistic.astype(str).values.tolist()
    table_data = [headers] + rows

    # 表格寬度必須在左右邊界內
    col_w = (width - 2*margin) / len(headers)

    def build_table(data, page_width):
        # 估算每欄寬度
        font_name = "Helvetica"
        font_size = 6.5
        col_widths = []
        for col in range(len(data[0])):
            max_text = max([str(row[col]) for row in data], key=len)
            text_w = stringWidth(max_text, font_name, font_size)
            col_widths.append(text_w + 12)  # 加 padding

        # 如果總寬度超過頁面寬度，就等比縮小
        total_w = sum(col_widths)
        max_w = page_width
        if total_w > max_w:
            scale = max_w / total_w
            col_widths = [w * scale for w in col_widths]

        t = Table(data, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4F81BD")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),  
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), 
            ("FONTSIZE", (0, 0), (-1, -1), font_size),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.lightgrey]),
            ("BOX", (0, 0), (-1, -1), 0.25, colors.black),
            ("LINEBEFORE", (0, 0), (0, -1), 0.25, colors.black),
            ("LINEAFTER", (-1, 0), (-1, -1), 0.25, colors.black),
        ]))
        return t

    table = build_table(table_data, width - 2*margin)
    # 區塊可用高度（扣掉標題與間距）
    avail_h = block_height - 70
    # 如果超高就迭代刪除最後一列直到能塞進去
    truncated = False
    while True:
        tw, th = table.wrapOn(c, width - 2*margin, avail_h)
        if th <= avail_h:
            break
        if len(table_data) <= 2:  # 只剩表頭與一列，沒辦法再砍
            break
        truncated = True
        table_data = table_data[:-1]
        table = build_table(table_data)

    if truncated:
        # 加上一列省略提示；若仍超高，再刪到能容納
        ellipsis_row = ['…'] * len(headers)
        table_data = table_data + [ellipsis_row]
        table = build_table(table_data)
        while True:
            tw, th = table.wrapOn(c, width - 2*margin, avail_h)
            if th <= avail_h:
                break
            # 移除省略列前的一列再重試
            if len(table_data) > 2:
                table_data = table_data[:-2] + [ellipsis_row]
                table = build_table(table_data)
            else:
                break

    # 繪製表格
    table_w, table_h = table.wrapOn(c, width - 2*margin, avail_h)
    table.drawOn(c, margin, top_y - 60 - table_h)

    # 總結資訊（固定畫在表格正下方，不會跨出區塊）
    total_twd = int(statistic["Total_TWD"].sum())
    total_cost = int(statistic["Total_cost_TWD"].sum())
    total_pnl = int(statistic["Unrealized_PnL"].sum())

    pnl_color = colors.green if total_pnl > 0 else (colors.red if total_pnl < 0 else colors.black)
    summary = f"Total TWD: {total_twd:,}   Total Cost: {total_cost:,}   PnL: {total_pnl:,}"

    c.setFillColor(pnl_color)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(margin, top_y - 60 - table_h - 15, summary)
    c.setFillColor(colors.black)

    # ===== 區塊 2：三個圓餅圖（放到能塞的最大尺寸）=====
    mid_y = top_y - block_height
    gap = 30  # 圖與圖的固定間距
    img_size = (width - 2*margin - 2*gap) / 3.0  # 最大尺寸（正好塞滿一排）
    y_img = mid_y - img_size - 20

    for i, p in enumerate(pies):
        img = Image(p, width=img_size, height=img_size)
        img.drawOn(c, margin + i*(img_size + gap), y_img)

    # ===== 區塊 3：空白/備註 =====
    bottom_y = mid_y - block_height
    c.setFont("Helvetica-Oblique", 8)

    # 頁尾
    c.setFont("Helvetica", 8)
    c.drawString(margin, margin/2, f"Generated {datetime.now().strftime('%Y-%m-%d')}")

    c.save()


if __name__ == "__main__":
    df = get_data("transaction.csv")
    codes = df["Code"].unique().tolist() + ["USDTWD=X"]
    current_price = {code: get_current_price(code) for code in codes}

    statistic = do_statistic(df, current_price)
    print(statistic)

    pie1 = make_pie(statistic['Type'].value_counts().index, statistic['Type'].value_counts().values, "STOCK vs CRYPTO")
    pie2 = make_pie(statistic[statistic['Type'] == 'STOCK']['Code'], statistic[statistic['Type'] == 'STOCK']['Total_TWD'], "Stock Allocation")
    pie3 = make_pie(statistic[statistic['Type'] == 'CRYPTO']['Code'], statistic[statistic['Type'] == 'CRYPTO']['Total_TWD'], "Crypto Allocation")

    export_pdf(statistic, [pie1, pie2, pie3], "portfolio_report.pdf")
    print("PDF generated: portfolio_report.pdf")
