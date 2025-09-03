# 📊 投資組合統計工具

這是一個使用 **Python** 撰寫的投資組合統計程式，透過 **Yahoo Finance
API**
取得即時價格，並根據交易紀錄檔（`transaction.csv`）計算持倉數量、平均成本、總市值與未實現損益。此工具可用於股票與加密貨幣投資組合的分析與追蹤。

------------------------------------------------------------------------

## 📁 專案結構

    portfolio/
    ├── main.py             # 主程式入口，讀取資料並輸出統計結果
    ├── transaction.csv     # 交易紀錄檔（使用者需自行準備）

------------------------------------------------------------------------

## 🚀 程式流程

1.  **交易資料讀取 (`get_data`)**
    -   讀取
        `transaction.csv`，並解析欄位（日期、股票/幣種、交易行為、貨幣等）。\
    -   計算交易成本（TWD 與 USD）。
2.  **即時價格取得 (`get_current_price`)**
    -   透過 `yfinance` 抓取 Yahoo Finance 的最新收盤價。\
    -   同時查詢美金兌台幣匯率 (`USDTWD=X`)。
3.  **投資組合統計 (`do_statistic`)**
    -   計算各標的的持倉數量、平均成本、總市值（TWD）、未實現損益。\
    -   產生各標的在投資組合中的比例。
4.  **輸出結果**
    -   顯示各標的統計表格。\
    -   印出整體投資組合的成本、市值與未實現損益。

------------------------------------------------------------------------

## 🧠 展示概念

-   即時金融資料查詢（Yahoo Finance API）\
-   投資組合持倉計算（買賣加總、平均成本）\
-   匯率轉換（USD ↔ TWD）\
-   統計表格與比重分析

------------------------------------------------------------------------

## 🛠️ 執行方式

1.  安裝相依套件：

    ``` bash
    pip install pandas numpy yfinance matplotlib reportlab
    ```

2.  準備交易紀錄檔 `transaction.csv`，範例格式：

    ``` csv
    Date,Code,Type,Action,Currency,Rate_to_TWD,Price,Number
    2024-01-01,AAPL,STOCK,BUY,USD,31.5,150,10
    2024-02-01,TSLA,STOCK,BUY,USD,31.2,700,2
    2024-03-01,2330.TW,STOCK,BUY,TWD,1,550,5
    ```

3.  執行程式：

    ``` bash
    python main.py
    ```

4.  範例輸出：

    ``` bash
               Code     Quantity    Type Currency  Price_now  Avg_cost_USD  Avg_cost_TWD  Total_cost_TWD  Total_TWD  Unrealized_PnL   Ratio
    0        VWRA.L   778.000000   STOCK      USD     158.50        143.32          4496         3497888    3767706          269818  87.94%
    1       SOL-USD    31.460000  CRYPTO      USD     205.24        160.51          5064          159313     197283           37970   4.60%
    2       BTC-USD     0.052984  CRYPTO      USD  109271.29      89603.00       2915673          154484     176896           22412   4.13%
    3  SUI20947-USD   900.220000  CRYPTO      USD       3.33          4.04           125          112528      91593          -20935   2.14%
    4       ADA-USD  2000.200000  CRYPTO      USD       0.83          0.84            26           52005      50725           -1280   1.18%
    ```

5.  產生PDF報告
   
<p align="center"> <img src="https://github.com/user-attachments/assets/5d3a90a5-4225-4a37-8b1e-4c706538ee39" width="650"/>

6. 欄位說明

   ``` bash
   Code : 代號
   Quantity : 持有數量
   Type : 股票或是加密貨幣
   Currency : 計價幣別
   Price_now : 現價
   Avg_cost_USD : 每單位平均成本(美金)
   Avg_cost_TWD : 每單位平均成本(台幣)
   Total_cost_TWD : 總成本(台幣)
   Total_TWD : 總現值(台幣)
   Unrealized_PnL : 未實現損益(台幣)
   ```
   
------------------------------------------------------------------------

## 📌 注意事項

-   交易紀錄必須符合指定格式，否則會報錯。\
-   僅支援股票（`STOCK`）與加密貨幣（`CRYPTO`）。\
-   使用 Yahoo Finance API，查詢代碼需符合 Yahoo Finance 的標準（如
    `AAPL`, `TSLA`, `2330.TW`, `BTC-USD`）。\
-   匯率以 `USDTWD=X` 取得，若無法取得，將使用預設值。

------------------------------------------------------------------------

## 📚 補充

-   不考慮 **已實現損益** 計算（長期持有才是最佳策略）。

- ~~待更新~~
  - 指定時間區間的損益波動
  - 與同期大盤的比較（VT, VOO, VXUS, 0050）
 
- **停止更新** 
  - 試算表是個好選擇
