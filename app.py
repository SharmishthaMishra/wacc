from flask import Flask, render_template, request
import pandas as pd
import numpy as np

app = Flask(__name__)

def load_data():
    raw_df = pd.read_excel('raw_financials.xlsx', sheet_name='Raw_Financials', index_col=0)
    
    # Standardize index strings by stripping whitespace
    raw_df.index = raw_df.index.astype(str).str.strip()
    
    # Sort columns by date (oldest to newest)
    cols = sorted(raw_df.columns, key=lambda x: str(x))
    
    # Map raw yfinance row labels with fallbacks for variations
    def get_row_val(possible_keys, col):
        for key in possible_keys:
            if key in raw_df.index:
                val = raw_df.loc[key, col]
                if isinstance(val, pd.Series):
                    val = val.iloc[0]
                if not pd.isna(val):
                    return float(val)
        return 0.0

    # Map the latest 3 historical years available from yfinance
    years_keys = ['Year_2022', 'Year_2023', 'Year_2024']
    selected_cols = cols[-3:] if len(cols) >= 3 else cols
    
    liquidity = {}
    fcf_by_year = {}

    for i, col in enumerate(selected_cols):
        yr_key = years_keys[i] if i < len(years_keys) else f"Year_{i}"
        
        ca = get_row_val(['Current Assets', 'Total Current Assets'], col)
        cl = get_row_val(['Current Liabilities', 'Total Current Liabilities'], col)
        cash = get_row_val(['Cash And Cash Equivalents', 'Cash Cash Equivalents And Short Term Investments'], col)
        sec = get_row_val(['Other Short Term Investments', 'Marketable Securities'], col)
        ar = get_row_val(['Receivables', 'Accounts Receivable'], col)
        fcf = get_row_val(['Free Cash Flow', 'Operating Cash Flow'], col)

        current_ratio = ca / cl if cl != 0 else 0
        quick_ratio = (cash + sec + ar) / cl if cl != 0 else 0
        cash_ratio = (cash + sec) / cl if cl != 0 else 0

        liquidity[yr_key] = {
            'Current_Ratio': round(current_ratio, 2),
            'Quick_Ratio': round(quick_ratio, 2),
            'Cash_Ratio': round(cash_ratio, 2)
        }
        fcf_by_year[yr_key] = fcf

    return raw_df, liquidity, fcf_by_year

def run_wacc(cost_of_equity, cost_of_debt, tax_rate, equity_weight, debt_weight, initial_investment, growth_rate, forecast_years=5):
    wacc = (equity_weight * cost_of_equity) + (debt_weight * cost_of_debt * (1 - tax_rate))
    
    _, _, fcf_by_year = load_data()
    # Pull baseline Free Cash Flow from the most recent historical year in raw_financials.xlsx
    base_fcf = fcf_by_year.get('Year_2024', list(fcf_by_year.values())[-1] if fcf_by_year else 1000000)
    
    projected_fcf = []
    discounted_fcf = []
    cumulative_cash = -initial_investment
    payback_period = None
    
    for t in range(1, forecast_years + 1):
        fcf = base_fcf * ((1 + growth_rate) ** t)
        dfcf = fcf / ((1 + wacc) ** t)
        
        projected_fcf.append(round(fcf, 2))
        discounted_fcf.append(round(dfcf, 2))
        
        cumulative_cash += fcf
        if cumulative_cash >= 0 and payback_period is None:
            payback_period = (t - 1) + ((initial_investment - sum(projected_fcf[:-1])) / fcf)
            
    npv = sum(discounted_fcf) - initial_investment
    cash_flows = [-initial_investment] + projected_fcf
    irr_val = get_irr(cash_flows)
    
    return {
        'wacc': round(wacc * 100, 2),
        'npv': round(npv, 2),
        'irr': round(irr_val * 100, 2) if irr_val else "N/A",
        'payback_period': round(payback_period, 2) if payback_period else "5+ Years",
        'projected_fcf': projected_fcf,
        'discounted_fcf': discounted_fcf,
        'years': [f'Year {i}' for i in range(1, forecast_years + 1)]
    }

def get_irr(cash_flows, iterations=1000):
    rate = 0.10
    for _ in range(iterations):
        npv = sum([cf / ((1 + rate) ** i) for i, cf in enumerate(cash_flows)])
        derivative = sum([-i * cf / ((1 + rate) ** (i + 1)) for i, cf in enumerate(cash_flows)])
        if abs(npv) < 1e-5:
            return rate
        if derivative == 0:
            break
        rate -= npv / derivative
    return rate

@app.route('/', methods=['GET', 'POST'])
def index():
    _, liquidity, _ = load_data()
    
    cost_of_equity = float(request.form.get('cost_of_equity', 0.10))
    cost_of_debt = float(request.form.get('cost_of_debt', 0.05))
    tax_rate = 0.21
    equity_weight = float(request.form.get('equity_weight', 0.70))
    debt_weight = 1.0 - equity_weight
    initial_investment = float(request.form.get('initial_investment', 25000000))
    growth_rate = float(request.form.get('growth_rate', 0.05))
    
    model_results = run_wacc(
        cost_of_equity, cost_of_debt, tax_rate, 
        equity_weight, debt_weight, initial_investment, growth_rate
    )
    
    return render_template(
        'index.html',
        liquidity=liquidity,
        model=model_results,
        inputs={
            'cost_of_equity': cost_of_equity,
            'cost_of_debt': cost_of_debt,
            'equity_weight': equity_weight,
            'initial_investment': initial_investment,
            'growth_rate': growth_rate
        }
    )

if __name__ == '__main__':
    app.run(debug=True, port=5000)
