from flask import Flask, render_template, request
import pandas as pd
import numpy as np

app = Flask(__name__)

#cleanse extracted data
def load_data():
    raw_df = pd.read_excel('raw_financials.xlsx', skiprows=1)
    
    raw_df.columns = ['Metric', 'Year_2022', 'Year_2023', 'Year_2024']
    
    raw_df['Metric'] = raw_df['Metric'].astype(str).str.strip()
    
    df = raw_df.dropna(subset=['Metric']).set_index('Metric')
    
    liquidity = {}
    years = ['Year_2022', 'Year_2023', 'Year_2024']
    
    for yr in years:
        ca = float(df.loc['Total Current Assets', yr])
        cl = float(df.loc['Total Current Liabilities', yr])
        cash = float(df.loc['Cash and Cash Equivalents', yr])
        sec = float(df.loc['Marketable Securities', yr])
        ar = float(df.loc['Accounts Receivable', yr])
        
        current_ratio = ca / cl
        quick_ratio = (cash + sec + ar) / cl
        cash_ratio = (cash + sec) / cl
        
        liquidity[yr] = {
            'Current_Ratio': round(current_ratio, 2),
            'Quick_Ratio': round(quick_ratio, 2),
            'Cash_Ratio': round(cash_ratio, 2)
        }
        
    return df, liquidity

# wacc model 
def run_wacc(cost_of_equity, cost_of_debt, tax_rate, equity_weight, debt_weight, initial_investment, growth_rate, forecast_years=5):
    
    wacc = (equity_weight * cost_of_equity) + (debt_weight * cost_of_debt * (1 - tax_rate))
    
    # Pull baseline Free Cash Flow from recent historical year (2024) in raw_financials.xlsx
    df, _ = load_data()
    base_fcf = float(df.loc['Free Cash Flow (FCF)', 'Year_2024'])
    
    projected_fcf = []
    discounted_fcf = []
    cumulative_cash = -initial_investment
    payback_period = None
    
    # Multi-year cash flow projections and discounting
    for t in range(1, forecast_years + 1):
        fcf = base_fcf * ((1 + growth_rate) ** t)
        dfcf = fcf / ((1 + wacc) ** t)
        
        projected_fcf.append(round(fcf, 2))
        discounted_fcf.append(round(dfcf, 2))
        
        cumulative_cash += fcf
        if cumulative_cash >= 0 and payback_period is None:
            # Linear interpolation for payback calculation
            payback_period = (t - 1) + ((initial_investment - sum(projected_fcf[:-1])) / fcf)
            
    # Net Present Value (NPV)
    npv = sum(discounted_fcf) - initial_investment
    
    # Internal Rate of Return (IRR) numerical calculation
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
    # Newton-Raphson method for IRR evaluation
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
    df, liquidity = load_data()
    
    # Capture user form inputs or set financial model defaults
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
