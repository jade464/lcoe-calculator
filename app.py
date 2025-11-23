import streamlit as st
import pandas as pd
import numpy as np
import io
import xlsxwriter

# --- 1. 全局配置 ---
st.set_page_config(page_title="新能源 LCOE 测算 (Standard Tax Model)", layout="wide", page_icon="⚖️")

st.markdown("""
<style>
    .main {background-color: #FAFAFA;}
    h1, h2, h3 {font-family: 'Helvetica Neue', sans-serif; color: #0F2948;}
    h2 {border-bottom: 2px solid #1F4E79; padding-bottom: 10px;}
    .block-container {padding-top: 2rem;}
    div[data-testid="stMetric"] {
        background-color: #FFF; border: 1px solid #DDD; 
        border-radius: 8px; padding: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. Excel 引擎 (适配新公式)
# ==========================================
def generate_professional_excel(model_name, inputs, time_series_data, summary_metrics):
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet('Financial Model')
    
    fmt_head = workbook.add_format({'bold': True, 'bg_color': '#2F5597', 'font_color': 'white', 'border': 1, 'align': 'center'})
    fmt_sub = workbook.add_format({'bold': True, 'bg_color': '#D9E1F2', 'border': 1})
    fmt_num = workbook.add_format({'border': 1, 'num_format': '#,##0.00'})
    fmt_money = workbook.add_format({'border': 1, 'num_format': '¥ #,##0'})
    
    # 1. 假设
    worksheet.write('A1', f"{model_name} - Key Assumptions", workbook.add_format({'bold': True, 'font_size': 14}))
    r = 2
    for k, v in inputs.items():
        worksheet.write(r, 0, k, fmt_sub)
        worksheet.write(r, 1, v, fmt_num)
        r += 1
        
    # 2. 瀑布流
    r += 2
    worksheet.write(r, 0, "Cash Flow Waterfall", workbook.add_format({'bold': True, 'font_size': 12}))
    r += 1
    
    cols = ["Year"] + [f"Year {y}" for y in time_series_data["Year"]]
    worksheet.write_row(r, 0, cols, fmt_head)
    r += 1
    
    # 定义输出行
    rows = [
        ("物理发电量 (MWh)", "Generation", fmt_num),
        ("折现系数", "Discount Factor", fmt_num),
        ("税后有效电量 (Gen * (1-T))", "Generation Tax Adj", fmt_num), # 关键修正
        ("折现税后电量", "Discounted Gen Tax Adj", fmt_num),
        ("累计折现分母", "Cum Denominator", fmt_num),
        ("", "", None),
        ("1. 初始投资 (Capex)", "Capex", fmt_money),
        ("2. 运营支出 (税后)", "Opex After-tax", fmt_money),
        ("3. 燃料/充电 (税后)", "Fuel/Charge After-tax", fmt_money),
        ("4. 资产置换 (Capex)", "Replacement", fmt_money),
        ("5. 残值回收 (税后)", "Salvage After-tax", fmt_money),
        ("6. 折旧税盾 (抵扣)", "Tax Shield", fmt_money),
        ("", "", None),
        ("=== 净成本流 (税后) ===", "Net Cost Flow", fmt_money),
        ("折现成本", "PV of Cost", fmt_money),
        ("累计折现分子", "Cum Numerator", fmt_money)
    ]
    
    for label, key, fmt in rows:
        worksheet.write(r, 0, label, fmt_sub if key=="" or "===" in label else workbook.add_format({'border':1}))
        if key and key in time_series_data:
            worksheet.write_row(r, 1, time_series_data[key], fmt)
        r += 1
        
    workbook.close()
    return output.getvalue()

# ==========================================
# 3. 光伏+储能 LCOE (修正版)
# ==========================================
def render_pv_ess_lcoe():
    st.markdown("## ☀️ 光伏+储能 LCOE (含税 PPA 倒算)")
    st.info("公式修正：分母采用 [发电量 × (1-税率)] 进行折现。结果代表：为了覆盖成本并获得 WACC 回报所需的**税前电价**。")
    
    with st.container():
        st.markdown("### 1. 规模与物理参数")
        c1, c2, c3, c4 = st.columns(4)
        pv_cap = c1.number_input("光伏容量 (MW)", value=200.0)
        pv_hours = c2.number_input("利用小时数 (h)", value=2200.0)
        ess_cap = c3.number_input("储能容量 (MWh)", value=120.0)
        ess_cycles = c4.number_input("循环次数", value=1000.0)
        ess_eff = 0.85
        
        st.markdown("---")
        st.markdown("### 2. 投资与运维")
        c1, c2, c3 = st.columns(3)
        capex_pv = c1.number_input("光伏投资 (万)", value=50000.0, step=100.0)
        capex_ess = c2.number_input("储能投资 (万)", value=10000.0, step=100.0)
        capex_grid = c3.number_input("配套投资 (万)", value=15000.0, step=100.0)
        
        o1, o2, o3 = st.columns(3)
        opex_r_pv = o1.number_input("光伏运维%", value=1.5, step=0.1)/100
        opex_r_ess = o2.number_input("储能运维%", value=3.0, step=0.1)/100
        opex_r_grid = o3.number_input("配套运维%", value=1.0, step=0.1)/100
        
        st.markdown("---")
        st.markdown("### 3. 财务与税务")
        f1, f2, f3, f4 = st.columns(4)
        wacc = f1.number_input("WACC (%)", value=8.0)/100
        period = int(f2.number_input("周期 (年)", value=25))
        tax_rate = f3.number_input("所得税率 (%)", value=25.0)/100
        depr_years = f4.number_input("折旧年限", value=20)
        
        st.markdown("---")
        st.markdown("### 4. 资产管理")
        l1, l2, l3 = st.columns(3)
        rep_yr = l1.number_input("更换年份", 10)
        rep_cost = l2.number_input("更换费用 (万)", 5000.0)
        salvage_rate = l3.number_input("残值率 (%)", 5.0)/100

    # --- Core Logic ---
    total_inv = capex_pv + capex_ess + capex_grid
    years = [0] + list(range(1, period + 1))
    
    ts = {k: [] for k in ["Year", "Generation", "Discount Factor", "Generation Tax Adj", "Discounted Gen Tax Adj", "Cum Denominator",
                          "Capex", "Opex After-tax", "Fuel/Charge After-tax", "Replacement", "Salvage After-tax", "Tax Shield",
                          "Net Cost Flow", "PV of Cost", "Cum Numerator"]}
    
    # Init Year 0
    for k in ts: ts[k].append(0)
    ts["Year"][0] = 0
    ts["Discount Factor"][0] = 1.0
    ts["Capex"][0] = total_inv
    ts["Net Cost Flow"][0] = total_inv
    ts["PV of Cost"][0] = total_inv
    ts["Cum Numerator"][0] = total_inv
    
    annual_depr = total_inv / depr_years
    cum_denom = 0
    cum_num = total_inv
    
    for y in range(1, period + 1):
        ts["Year"].append(y)
        
        # 1. Denominator: Gen * (1-T)
        deg = 1 - (y-1)*0.005
        gen = (pv_cap * pv_hours * deg) + (ess_cap * ess_cycles * ess_eff)
        ts["Generation"].append(gen)
        
        df = 1 / ((1+wacc)**y)
        ts["Discount Factor"].append(df)
        
        gen_adj = gen * (1 - tax_rate)
        ts["Generation Tax Adj"].append(gen_adj)
        
        g_npv = gen_adj * df
        ts["Discounted Gen Tax Adj"].append(g_npv)
        cum_denom += g_npv
        ts["Cum Denominator"].append(cum_denom)
        
        # 2. Numerator: Net Cost After Tax
        ts["Capex"].append(0)
        
        opex_pre = (capex_pv*opex_r_pv) + (capex_ess*opex_r_ess) + (capex_grid*opex_r_grid)
        ts["Opex After-tax"].append(opex_pre * (1 - tax_rate))
        ts["Fuel/Charge After-tax"].append(0)
        
        curr_depr = annual_depr if y <= depr_years else 0
        shield = curr_depr * tax_rate
        ts["Tax Shield"].append(-shield) # Negative Cost
        
        rep = rep_cost if y == rep_yr else 0
        ts["Replacement"].append(rep)
        
        sal = 0
        if y == period:
            sal = -(total_inv * salvage_rate * (1 - tax_rate)) # Taxed inflow
        ts["Salvage After-tax"].append(sal)
        
        net = (opex_pre * (1 - tax_rate)) + rep - shield + sal
        ts["Net Cost Flow"].append(net)
        
        c_npv = net * df
        ts["PV of Cost"].append(c_npv)
        cum_num += c_npv
        ts["Cum Numerator"].append(cum_num)
        
    lcoe = (cum_num / cum_denom) * 10 if cum_denom > 0 else 0
    
    st.markdown("---")
    c1, c2 = st.columns(2)
    c1.metric("PPA LCOE (含税报价)", f"{lcoe:.4f} 元/kWh")
    c2.metric("税盾NPV贡献", f"{abs(sum(ts['Tax Shield'])):,.0f} 万")
    
    with st.expander("📂 导出底稿"):
        excel = generate_professional_excel("PV_ESS_LCOE", {"Tax": tax_rate, "WACC": wacc}, ts, {"LCOE": lcoe})
        st.download_button("📥 下载 Excel", excel, "PV_ESS_LCOE_Model.xlsx")

# ==========================================
# 4. 燃气 LCOE (修正版)
# ==========================================
def render_gas_lcoe():
    st.markdown("## 🔥 燃气发电 LCOE (含税 PPA 倒算)")
    
    with st.container():
        st.markdown("### 1. 规模与投资")
        c1, c2, c3 = st.columns(3)
        gas_cap = c1.number_input("装机 (MW)", 360.0)
        gas_capex = c2.number_input("投资 (万)", 60000.0)
        wacc = c3.number_input("WACC (%)", 8.0)/100
        
        st.markdown("### 2. 运营与燃料")
        c1, c2, c3 = st.columns(3)
        hours = c1.number_input("小时数", 3000.0)
        heat_rate = c2.number_input("热耗 (GJ/kWh)", 0.0095, format="%.4f")
        price = c3.number_input("气价 (元/GJ)", 60.0)
        fixed_opex = st.number_input("固定运维 (万/年)", 1200.0)

        st.markdown("### 3. 税务与周期")
        f1, f2, f3 = st.columns(3)
        tax_rate = f1.number_input("税率 (%)", 25.0)/100
        depr_years = f2.number_input("折旧年", 20)
        period = int(f3.number_input("周期 (年)", 25))

    total_inv = gas_capex
    years = [0] + list(range(1, period + 1))
    ts = {k: [] for k in ["Year", "Generation", "Discount Factor", "Generation Tax Adj", "Discounted Gen Tax Adj", "Cum Denominator",
                          "Capex", "Opex After-tax", "Fuel/Charge After-tax", "Replacement", "Salvage After-tax", "Tax Shield",
                          "Net Cost Flow", "PV of Cost", "Cum Numerator"]}
    
    for k in ts: ts[k].append(0)
    ts["Year"][0] = 0
    ts["Discount Factor"][0] = 1.0
    ts["Capex"][0] = total_inv
    ts["Net Cost Flow"][0] = total_inv
    ts["PV of Cost"][0] = total_inv
    ts["Cum Numerator"][0] = total_inv
    
    annual_gen = gas_cap * hours
    annual_fuel_pre = (annual_gen * 1000 * heat_rate * price) / 10000
    annual_depr = total_inv / depr_years
    
    cum_denom = 0
    cum_num = total_inv
    
    for y in range(1, period + 1):
        ts["Year"].append(y)
        ts["Generation"].append(annual_gen)
        
        df = 1 / ((1+wacc)**y)
        ts["Discount Factor"].append(df)
        
        g_adj = annual_gen * (1 - tax_rate)
        ts["Generation Tax Adj"].append(g_adj)
        g_npv = g_adj * df
        ts["Discounted Gen Tax Adj"].append(g_npv)
        cum_denom += g_npv
        ts["Cum Denominator"].append(cum_denom)
        
        ts["Capex"].append(0)
        ts["Opex After-tax"].append(fixed_opex * (1 - tax_rate))
        ts["Fuel/Charge After-tax"].append(annual_fuel_pre * (1 - tax_rate))
        
        curr_depr = annual_depr if y <= depr_years else 0
        shield = curr_depr * tax_rate
        ts["Tax Shield"].append(-shield)
        
        ts["Replacement"].append(0)
        
        sal = 0
        if y == period: sal = -(total_inv * 0.05 * (1 - tax_rate))
        ts["Salvage After-tax"].append(sal)
        
        net = (fixed_opex + annual_fuel_pre)*(1-tax_rate) - shield + sal
        ts["Net Cost Flow"].append(net)
        
        c_npv = net * df
        ts["PV of Cost"].append(c_npv)
        cum_num += c_npv
        ts["Cum Numerator"].append(cum_num)
        
    lcoe = (cum_num / cum_denom) * 10 if cum_denom > 0 else 0
    
    st.markdown("---")
    st.metric("PPA LCOE (含税)", f"{lcoe:.4f}")
    with st.expander("📂 导出底稿"):
        excel = generate_professional_excel("Gas_LCOE", {"Tax": tax_rate}, ts, {"LCOE": lcoe})
        st.download_button("📥 下载 Excel", excel, "Gas_LCOE.xlsx")

# ==========================================
# 5. 储能 LCOS (修正版 - WACC已补回)
# ==========================================
def render_lcos():
    st.markdown("## 🔋 储能 LCOS (含税报价倒算)")
    
    with st.container():
        st.markdown("### 1. 规模与投资")
        c1, c2 = st.columns(2)
        ess_cap = c1.number_input("容量 (MWh)", value=200.0)
        capex = c2.number_input("总投资 (万)", value=25000.0)
        
        st.markdown("### 2. 运营与充电")
        c1, c2, c3 = st.columns(3)
        charge_p = c1.number_input("充电价 (元/kWh)", value=0.20)
        opex_r = c2.number_input("运维%", value=2.0)/100
        cycles = c3.number_input("年循环", value=330.0)
        
        st.markdown("### 3. 财务与税务 (已修复WACC)")
        f1, f2, f3 = st.columns(3)
        # 修复：WACC 现在有输入框了
        wacc = f1.number_input("WACC (%)", value=8.0)/100
        tax_rate = f2.number_input("税率 (%)", value=25.0)/100
        depr_years = f3.number_input("折旧年限", value=15)
        
        st.markdown("### 4. 周期与置换")
        l1, l2, l3 = st.columns(3)
        period = int(l1.number_input("寿命 (年)", value=15))
        rep_yr = l2.number_input("更换年份", 8)
        rep_cost = l3.number_input("更换费用", min_value=0.0)

    # Calc
    total_inv = capex
    years = [0] + list(range(1, period + 1))
    ts = {k: [] for k in ["Year", "Generation", "Discount Factor", "Generation Tax Adj", "Discounted Gen Tax Adj", "Cum Denominator",
                          "Capex", "Opex After-tax", "Fuel/Charge After-tax", "Replacement", "Salvage After-tax", "Tax Shield",
                          "Net Cost Flow", "PV of Cost", "Cum Numerator"]}
    
    for k in ts: ts[k].append(0)
    ts["Year"][0] = 0
    ts["Discount Factor"][0] = 1.0
    ts["Capex"][0] = total_inv
    ts["Net Cost Flow"][0] = total_inv
    ts["PV of Cost"][0] = total_inv
    ts["Cum Numerator"][0] = total_inv
    
    annual_depr = total_inv / depr_years
    cum_denom = 0
    cum_num = total_inv
    
    for y in range(1, period + 1):
        ts["Year"].append(y)
        
        curr_cap = ess_cap * ((1-0.02)**(y-1))
        dis = curr_cap * cycles * 0.85
        ts["Generation"].append(dis)
        
        df = 1 / ((1+wacc)**y)
        ts["Discount Factor"].append(df)
        
        # Denom Adj
        g_adj = dis * (1 - tax_rate)
        ts["Generation Tax Adj"].append(g_adj)
        g_npv = g_adj * df
        ts["Discounted Gen Tax Adj"].append(g_npv)
        cum_denom += g_npv
        ts["Cum Denominator"].append(cum_denom)
        
        ts["Capex"].append(0)
        
        opex = capex * opex_r
        ts["Opex After-tax"].append(opex * (1 - tax_rate))
        
        charge = (curr_cap * cycles * 1000 * charge_p) / 10000
        ts["Fuel/Charge After-tax"].append(charge * (1 - tax_rate))
        
        curr_depr = annual_depr if y <= depr_years else 0
        shield = curr_depr * tax_rate
        ts["Tax Shield"].append(-shield)
        
        rep = rep_cost if y == rep_yr else 0
        ts["Replacement"].append(rep)
        
        # 简化 LCOS 残值为0
        ts["Salvage After-tax"].append(0)
        
        net = (opex + charge)*(1-tax_rate) + rep - shield
        ts["Net Cost Flow"].append(net)
        
        c_npv = net * df
        ts["PV of Cost"].append(c_npv)
        cum_num += c_npv
        ts["Cum Numerator"].append(cum_num)
        
    lcos = (cum_num / cum_denom) * 10 if cum_denom > 0 else 0
    
    st.markdown("---")
    c1, c2 = st.columns(2)
    c1.metric("LCOS (含税报价)", f"{lcos:.4f}")
    c2.metric("税盾NPV贡献", f"{abs(sum(ts['Tax Shield'])):,.0f} 万")
    
    with st.expander("📂 导出底稿"):
        excel = generate_professional_excel("ESS_LCOS", {"Tax": tax_rate, "WACC": wacc}, ts, {"LCOS": lcos})
        st.download_button("📥 下载 Excel", excel, "ESS_LCOS.xlsx")

# ==========================================
# 6. Main
# ==========================================
def main():
    st.sidebar.title("📌 投资测算工具")
    mode = st.sidebar.radio("模块", ("光伏+储能 LCOE", "燃气发电 LCOE", "储能 LCOS"))
    st.sidebar.info("v6.0 | Revenue Requirement Method")
    
    if mode == "光伏+储能 LCOE": render_pv_ess_lcoe()
    elif mode == "燃气发电 LCOE": render_gas_lcoe()
    elif mode == "储能 LCOS": render_lcos()

if __name__ == "__main__":
    main()

