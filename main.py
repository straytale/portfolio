import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt
from reportlab.platypus import Table, TableStyle, Image
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth
from datetime import datetime
import io
from reportlab.lib.units import mm

# ---------- Data Functions ----------
def get_current_price(code: str):
    ticker = yf.Ticker(code)
    hist = ticker.history(period="1d")["Close"]
    if hist.empty:
        raise ValueError(f"Invalid code or no price data: {code}")
    return round(float(hist.iloc[-1]), 6)


def get_data(path="transaction.csv"):
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

    total_sum = statistic["Total_TWD"].sum()
    statistic["Ratio"] = (statistic["Total_TWD"] / (total_sum if total_sum != 0 else 1) * 100).map(lambda x: f"{x:.2f}%")

    statistic = (
        statistic.reset_index()
        .query("Quantity != 0")
        .sort_values("Total_TWD", ascending=False)
        .reset_index(drop=True)
    )
    return statistic


# ---------- visualization ----------
def make_pie(labels, sizes, title):
    import matplotlib.pyplot as plt
    import numpy as np
    import io

    labels = list(map(str, labels))
    sizes = list(map(float, sizes))

    fig, ax = plt.subplots(figsize=(4.2, 4.2), facecolor="white")

    if not sizes or sum(sizes) == 0:
        ax.text(0.5, 0.5, "No Data", ha="center", va="center", fontsize=14, fontweight="bold", color="#666666")
        ax.axis("off")
    else:
        # Professional pastel color palette
        colors = ["#4E79A7", "#F28E2B", "#E15759", "#76B7B2", "#59A14F",
                  "#EDC948", "#B07AA1", "#FF9DA7", "#9C755F", "#BAB0AC"]

        wedges, _ = ax.pie(
            sizes,
            labels=None,
            startangle=90,
            wedgeprops={'edgecolor': 'white', 'linewidth': 1},
            colors=colors[:len(sizes)]
        )

        # Smart labels inside wedges
        total = sum(sizes)
        for i, (wedge, size) in enumerate(zip(wedges, sizes)):
            angle = (wedge.theta2 + wedge.theta1) / 2.0
            x = 0.65 * np.cos(np.deg2rad(angle))
            y = 0.65 * np.sin(np.deg2rad(angle))
            pct = size / total * 100 if total > 0 else 0
            ax.text(x, y, f"{labels[i]}\n{pct:.1f}%",
                    ha='center', va='center',
                    fontsize=9, fontweight='bold', color="#333333")

        # Elegant title
        ax.set_title(title, fontsize=14, fontweight='bold', color="#2E2E2E", pad=12)

    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", dpi=220)
    plt.close(fig)
    buf.seek(0)
    return buf


# ---------- PDF export ----------
def build_table(data, page_width, font_name="Helvetica", font_size=8):
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib import colors
    from reportlab.pdfbase.pdfmetrics import stringWidth

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
        # Header
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#2E3B4E")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('ALIGN', (0,0), (-1,0), 'CENTER'),
        ('VALIGN', (0,0), (-1,0), 'MIDDLE'),

        # Body alignment
        ('ALIGN', (0,1), (0,-1), 'LEFT'),     
        ('ALIGN', (2,1), (3,-1), 'CENTER'),   
        ('ALIGN', (1,1), (-1,-1), 'CENTER'),  
        ('VALIGN', (0,1), (-1,-1), 'MIDDLE'),

        # Row striping
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F9FBFD")]),

        # Grid
        ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
        ('FONTSIZE', (0,0), (-1,-1), font_size),
    ]))

    return table



def export_pdf(statistic: pd.DataFrame, pies, filename="portfolio_report.pdf"):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.pdfgen import canvas
    from reportlab.platypus import Image, TableStyle
    from datetime import datetime

    width, height = A4
    margin = 40
    c = canvas.Canvas(filename, pagesize=A4)

    # === Layout ===
    content_h = height - 2 * margin
    block_h = content_h / 3.0
    block1_top = height - margin
    block2_top = block1_top - block_h
    block3_top = block2_top - block_h

    # ---------- Block 1: Title + Table + Summary ----------
    # Title
    c.setFont("Helvetica-Bold", 22)
    c.setFillColor(colors.HexColor("#2E3B4E"))
    c.drawCentredString(width/2, block1_top - 25, "Portfolio Report")

    c.setFont("Helvetica", 10)
    c.setFillColor(colors.HexColor("#666666"))
    c.drawCentredString(width/2, block1_top - 42, f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    def format_number(x):
        try:
            if isinstance(x, (int, float)):
                if abs(x) >= 1:
                    return f"{x:,.2f}" if not float(x).is_integer() else f"{int(x):,}"
                else:
                    return f"{x:,.4f}"  # 小數很小的情況
            else:
                return str(x)
        except:
            return str(x)
    
    # Table
    headers = statistic.columns.tolist()
    display_rows = []
    for _, r in statistic.iterrows():
        out = []
        for col in headers:
            if col in ("Number", "Price_now", "Avg_cost_USD", "Avg_cost_TWD",
                       "Total_cost_TWD", "Total_TWD", "Unrealized_PnL"):
                out.append(format_number(r[col]))
            else:
                out.append(str(r[col]))
        display_rows.append(out)
    table_data = [headers] + display_rows

    avail_w = width - 2 * margin
    table = build_table(table_data, avail_w, font_size=6)
    table_w, table_h = table.wrap(avail_w, block_h / 2)
    table_x = (width - table_w) / 2.0
    table_y = block1_top - 90 - table_h
    table.drawOn(c, table_x, table_y)

    # Summary (3-column)
    total_twd = int(statistic["Total_TWD"].sum())
    total_cost = int(statistic["Total_cost_TWD"].sum())
    total_pnl = int(statistic["Unrealized_PnL"].sum())

    summary_y = table_y - 28
    c.setStrokeColor(colors.HexColor("#DDDDDD"))
    c.line(margin, summary_y + 12, width - margin, summary_y + 12)

    # Styling
    c.setFont("Helvetica-Bold", 11)
    text_color = colors.HexColor("#2E2E2E")
    pnl_color = colors.green if total_pnl > 0 else (colors.red if total_pnl < 0 else text_color)

    c.setFillColor(text_color)
    c.drawString(margin, summary_y, f"Total Value: NT${total_twd:,}")
    c.drawCentredString(width/2, summary_y, f"Total Cost: NT${total_cost:,}")

    c.setFillColor(pnl_color)
    c.drawRightString(width - margin, summary_y, f"Unrealized PnL: NT${total_pnl:,}")
    c.setFillColor(colors.black)

    # ---------- Block 2: Pie Charts ----------
    valid_pies = [p for p in pies if p is not None]
    if valid_pies:
        n = len(valid_pies)
        gap = 20
        max_size_w = (width - 2*margin - (n - 1) * gap) / n
        max_size_h = block_h * 0.9
        img_size = min(max_size_w, max_size_h)
        total_w = n * img_size + (n - 1) * gap
        start_x = (width - total_w) / 2.0
        img_y = block2_top - block_h/2 - img_size/2
        for i, pbuf in enumerate(valid_pies):
            x = start_x + i * (img_size + gap)
            img = Image(pbuf, width=img_size, height=img_size)
            img.drawOn(c, x, img_y)

    # ---------- Block 3: Reserved ----------
    # left blank for future content

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

    # Pie 1: STOCK vs CRYPTO
    labels, sizes = [], []
    if 'Type' in statistic and 'Total_TWD' in statistic:
        grouped = statistic.groupby('Type')['Total_TWD'].sum()
        labels, sizes = grouped.index.tolist(), grouped.values.tolist()
    pie1 = make_pie(labels, sizes, "STOCK vs CRYPTO")

    # Pie 2: CRYPTO Allocation
    labels_crypto, sizes_crypto = [], []
    if 'Type' in statistic and 'Ratio' in statistic:
        statistic['Ratio'] = pd.to_numeric(statistic['Ratio'].astype(str).str.replace('%',''), errors='coerce').fillna(0)
        grouped = statistic[statistic['Type'] == 'CRYPTO'].copy()
        grouped['Label'] = grouped['Code'].astype(str).str[:3]
        labels_crypto = grouped['Label'].tolist()
        sizes_crypto = grouped['Ratio'].tolist()
    pie2 = make_pie(labels_crypto, sizes_crypto, "CRYPTO ALLOCATION")

    # Pie 3: STOCK Allocation
    labels_stock, sizes_stock = [], []
    if 'Type' in statistic and 'Total_TWD' in statistic:
        grouped_stock = statistic[statistic['Type'] == 'STOCK'].copy()
        labels_stock = grouped_stock['Code'].tolist()
        sizes_stock = grouped_stock['Total_TWD'].tolist()
    pie3 = make_pie(labels_stock, sizes_stock, "STOCK ALLOCATION")

    out = export_pdf(statistic, [pie1, pie2, pie3], "portfolio_report.pdf")
    print("PDF generated:", out)
