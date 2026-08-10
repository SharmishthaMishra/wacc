import yfinance as yf
import pandas as pd

#Fetching live financial statements for Caterpillar Inc. (CAT)
ticker = yf.Ticker("CAT")
balance_sheet = ticker.balance_sheet
cash_flow = ticker.cashflow

#Extracting key metrics for 3 years
combined_raw = pd.concat([balance_sheet, cash_flow])

#export data
with pd.ExcelWriter("raw_financials.xlsx") as writer:
    combined_raw.to_excel(writer, sheet_name="Raw_Financials")

print("Successfully fetched live SEC data and generated raw_financials.xlsx")
