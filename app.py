import streamlit as st
import pandas as pd
import numpy as np
import io
import xlsxwriter

# --- 1. 全局配置 ---
st.set_page_config(page_title="新能源投资测算 (Stable v12.1)", layout="wide", page_icon="🛡️")

st.markdown("""
<style>
    .main {background-color: #FAFAFA;}
    h2 {color: #0F2948; border-bottom: 2px solid #1F4E79; padding-bottom: 10px;}
    .block-container {padding-top: 2rem;}
    div[data-testid="stMetric"] {
        background-color: #FFF; border: 1px solid #DDD; 
        border-radius: 8px; padding: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 核心引擎：Excel 生成器 (Pandas 暴力清洗版)
# ==========================================
def generate_professional_excel(model_name, inputs, time_series_data, summary_metrics):
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet('Financial Model')
    
    # 样式定义
    fmt_head = workbook.add_format({'bold': True, 'bg_color': '#2F5597', 'font_color': 'white', 'border': 1, 'align': 'center'})
    fmt_sub = workbook.add_format({'bold': True, 'bg_color': '#D9E1F2', 'border': 1})
    fmt_num = workbook.add_format({'border': 1, 'num_format': '#,##0.00'})
    fmt_money = workbook.add_format({'border': 1, 'num_format': '#,##0'}) 
    
    # --- 阶段 0: 数据清洗 ---
    try:
        df_raw = pd.DataFrame(time_series_data)
        df_clean = df_raw.apply(pd.to_numeric, errors='coerce')
        df_clean = df_clean.fillna(0)
        df_clean = df_clean.replace([np.inf, -np.inf], 0)
        clean_ts = df_clean.to_dict(orient='list')
    except Exception as e:
        st.error(f"数据序列化错误: {e}")
        return output.getvalue()

    # --- 阶段 1: 写入假设 ---
    worksheet.write('A1', f"{model_name} - Key Assumptions", workbook.add_format({'bold': True, 'font_size': 14}))
    r = 2
    for k, v in inputs.items():
        worksheet.write(r, 0, k, fmt_sub)
        safe_v = 0
        try:
            if pd.isna(v) or np.isinf(v): safe_v = 0
            else: safe_v = float(v)
        except:
            safe_v = 0
        worksheet.write(r, 1, safe_v, fmt_num)
        r += 1
        
    # --- 阶段 2: 写入瀑布流 ---
    r += 2
    worksheet.write(r, 0, "Cash Flow Waterfall", workbook.add_format({'bold': True, 'font_size': 12}))
    r += 1
    
    safe_years = [int(y) for y in clean_ts.get("Year", [])]
    cols = ["Item"] + [f"Year {y}" for y in safe_years]
    worksheet.write_row(r, 0, cols, fmt_head)
    r += 1
    
    rows_config = [
        ("物理发电量 (MWh)", "Generation", fmt_num),
        ("折现系数", "Discount Factor", fmt_num),
        ("折现发电量", "Discounted Gen", fmt_num),
        ("折现税后电量", "Discounted Gen Tax Adj", fmt_num),
        ("", "", None),
        ("1. 初始投资", "Capex", fmt_money),
        ("2. 运营支出 (税前)", "Opex Pre-tax", fmt_money),
        ("3. 燃料/充电 (税前)", "Fuel/Charge Pre-tax", fmt_money),
        ("4. 资产置换", "Replacement", fmt_money),
        ("5. 残值回收 (税前)", "Salvage Pre-tax", fmt_money),
        ("", "", None),
        ("折旧税盾 (+)", "Tax Shield", fmt_money),
        ("成本抵税 (+)", "Opex Tax Benefit", fmt_money),
        ("残值缴税 (-)", "Salvage Tax", fmt_money),
        ("", "", None),
        ("=== 税后净成本流 ===", "Net Cost Flow (After-tax)", fmt_money),
        ("折现成本", "PV of Cost", fmt_money),
        ("累计折现成本", "Cum Numerator", fmt_money)
    ]
    
    for label, key, fmt in rows_config:
        worksheet.write(r, 0, label, fmt_sub if key=="" or "===" in label else workbook.add_format({'border':1}))
        if key and key in clean_ts:
            worksheet.write_row(r, 1, clean_ts[key], fmt)
        r += 1
        
    workbook.close()
    return output.getvalue()

# ==========================================
# 3. 模块 A: 光伏 + 储能 LCOE
# ==========================================
def render_pv_ess_lcoe():
    st.markdown("## ☀️ 光伏+储能 LCOE (Fix V12.1)")
    
    with st.container():
        c1, c2, c3, c4 = st.columns(4)
        pv_cap = c1.number_input("光伏容量 (MW)", value=200.0, min_value=0.0)
        pv_hours = c2.number_input("利用小时数 (h)", value=2200.0, min_value=0.0)
        ess_cap = c3.number_input("储能容量 (MWh)", value=120.0, min_value=0.0)
        ess_cycles = c4.number_input("循环次数", value=365.0, min_value=0.0)
        
        charge_source = st.radio("⚡ 储能电力来源", ("来自光伏", "来自电网"), horizontal=True)
        
        t1, t2, t3 = st.columns(3)
        ess_eff = t1.number_input("RTE 效率%", value=85.0, step=0.1)/100
        pv_deg = t2.number_input("光伏年衰减%", value=0.5, step=0.1)/100
        grid_p = 0.0
        if charge_source == "来自电网":
            grid_p = t3.number_input("充电电价", value=0.20)
            
        st.markdown("---")
        c1, c2, c3 = st.columns(3)
        capex_pv = c1.number_input("光伏投资(万)", value=50000.0, step=100.0)
        capex_ess = c2.number_input("储能投资(万)", value=10000.0, step=100.0)
        capex_grid = c3.number_input("配套投资(万)", value=15000.0, step=100.0)
        
        o1, o2, o3 = st.columns(3)
        opex_r_pv = o1.number_input("光伏Opex%", value=1.5)/100
        opex_r_ess = o2.number_input("储能Opex%", value=3.0)/100
        opex_r_grid = o3.number_input("配套Opex%", value=1.0)/100
        
        st.markdown("---")
        f1, f2, f3, f4 = st.columns(4)
        wacc = f1.number_input("WACC%", value=8.0)/100
        period = int(f2.number_input("周期(年)", value=25, min_value=1))
        tax_rate = f3.number_input("税率%", value=25.0)/100
        depr_years = f4.number_input("折旧年", value=20, min_value=0)
        
        l1, l2, l3 = st.columns(3)
        rep_yr = l1.number_input("更换年", value=10)
        rep_cost = l2.number_input("更换费", value=5000.0)
        sal_rate = l3.number_input("残值%", value=5.0)/100

    # --- Calc ---
    total_inv = capex_pv + capex_ess + capex_grid
    years = [0] + list(range(1, period + 1))
    
    ts = {k: [0.0]*(period+1) for k in ["Year", "Generation", "Discount Factor", "Discounted Gen", "Discounted Gen Tax Adj", "Cum Denominator",
                          "Capex", "Opex Pre-tax", "Grid Charge Cost", "Replacement", "Salvage Pre-tax",
                          "Tax Shield", "Opex Tax Benefit", "Salvage Tax",
                          "Net Cost Flow (After-tax)", "PV of Cost", "Cum Numerator"]}
    
    ts["Year"][0] = 0
    ts["Discount Factor"][0] = 1.0
    ts["Capex"][0] = total_inv
    ts["Net Cost Flow (After-tax)"][0] = total_inv
    ts["PV of Cost"][0] = total_inv
    ts["Cum Numerator"][0] = total_inv
    
    safe_depr_years = max(depr_years, 1) if depr_years > 0 else 9999
    annual_depr = total_inv / safe_depr_years if depr_years > 0 else 0
    
    cum_denom = 0
    cum_num = total_inv
    sal_val_pre = total_inv * sal_rate

    for i in range(1, period + 1):
        y = i 
        ts["Year"][i] = y
        
        deg = 1 - (y-1)*pv_deg
        if deg < 0: deg = 0
        raw_pv = pv_cap * pv_hours * deg
        
        sys_gen = 0
        grid_cost = 0
        
        if charge_source == "来自光伏":
            loss = (ess_cap * ess_cycles) * (1 - ess_eff)
            sys_gen = raw_pv - loss
        else:
            dis = (ess_cap * ess_cycles) * ess_eff
            sys_gen = raw_pv + dis
            grid_cost = (ess_cap * ess_cycles * 1000 * grid_p) / 10000
            
        ts["Generation"][i] = sys_gen
        ts["Grid Charge Cost"][i] = grid_cost
        
        df = 1 / ((1+wacc)**y)
        ts["Discount Factor"][i] = df
        
        g_npv = sys_gen * df
        ts["Discounted Gen"][i] = g_npv
        
        g_npv_tax = sys_gen * (1-tax_rate) * df
        ts["Discounted Gen Tax Adj"][i] = g_npv_tax
        cum_denom += g_npv_tax
        ts["Cum Denominator"][i] = cum_denom
        
        opex = (capex_pv*opex_r_pv) + (capex_ess*opex_r_ess) + (capex_grid*opex_r_grid)
        ts["Opex Pre-tax"][i] = opex
        
        rep = rep_cost if y == rep_yr else 0
        ts["Replacement"][i] = rep
        
        sal = -sal_val_pre if y == period else 0
        ts["Salvage Pre-tax"][i] = sal
        
        cur_depr = annual_depr if y <= depr_years else 0
        shield = cur_depr * tax_rate
        ts["Tax Shield"][i] = -shield
        
        op_ben = (opex + grid_cost) * tax_rate
        ts["Opex Tax Benefit"][i] = -op_ben
        
        sal_tax = sal * tax_rate if y == period else 0
        ts["Salvage Tax"][i] = sal_tax
        
        net = (opex + grid_cost) + rep + sal - shield - op_ben + sal_tax
        ts["Net Cost Flow (After-tax)"][i] = net
        
        c_npv = net * df
        ts["PV of Cost"][i] = c_npv
        cum_num += c_npv
        ts["Cum Numerator"][i] = cum_num
        
    sum_disc_gen = sum(ts["Discounted Gen"])
    real_lcoe = (cum_num / sum_disc_gen) * 10 if sum_disc_gen > 0 else 0
    ppa_lcoe = (cum_num / cum_denom) * 10 if cum_denom > 0 else 0
    
    st.markdown("---")
    c1, c2 = st.columns(2)
    c1.metric("💡 真实持有成本 (Real LCOE)", f"{real_lcoe:.4f}")
    c2.metric("📉 盈亏平衡报价 (PPA Price)", f"{ppa_lcoe:.4f}")
    
    with st.expander("📂 导出底稿"):
        excel = generate_professional_excel("PV_ESS_LCOE", {"Tax": tax_rate}, ts, {"Real LCOE": real_lcoe})
        st.download_button("📥 下载 Excel (Safe)", excel, "PV_ESS_LCOE.xlsx")

# ==========================================
# 4. 燃气 LCOE
# ==========================================
def render_gas_lcoe():
    st.markdown("## 🔥 燃气发电 LCOE (Fix V12.1)")
    
    with st.container():
        c1, c2, c3 = st.columns(3)
        gas_cap = c1.number_input("装机(MW)", value=360.0)
        gas_capex = c2.number_input("投资(万)", value=60000.0)
        wacc = c3.number_input("WACC%", value=8.0)/100
        c1, c2, c3 = st.columns(3)
        hours = c1.number_input("小时", value=3000.0)
        heat_rate = c2.number_input("热耗", value=0.0095, format="%.4f")
        price = c3.number_input("气价", value=60.0)
        fixed_opex = st.number_input("固定运维", value=1200.0)
        f1, f2, f3, f4 = st.columns(4)
        tax_rate = f1.number_input("税率%", value=25.0)/100
        depr_years = f2.number_input("折旧年", value=20, min_value=0)
        period = int(f3.number_input("周期", value=25))
        sal_rate = f4.number_input("残值%", value=5.0)/100

    total_inv = gas_capex
    years = [0] + list(range(1, period + 1))
    ts = {k: [0.0]*(period+1) for k in ["Year", "Generation", "Discount Factor", "Discounted Gen", "Discounted Gen Tax Adj", "Cum Denominator",
                          "Capex", "Opex Pre-tax", "Fuel/Charge Pre-tax", "Replacement", "Salvage Pre-tax",
                          "Tax Shield", "Opex Tax Benefit", "Salvage Tax",
                          "Net Cost Flow (After-tax)", "PV of Cost", "Cum Numerator"]}
    
    ts["Year"][0] = 0
    ts["Discount Factor"][0] = 1.0
    ts["Capex"][0] = total_inv
    ts["Net Cost Flow (After-tax)"][0] = total_inv
    ts["PV of Cost"][0] = total_inv
    ts["Cum Numerator"][0] = total_inv
    
    safe_depr_years = max(depr_years, 1) if depr_years > 0 else 9999
    annual_depr = total_inv / safe_depr_years if depr_years > 0 else 0
    sal_val_pre = total_inv * sal_rate
    
    cum_denom = 0
    cum_num = total_inv
    
    annual_gen = gas_cap * hours
    annual_fuel = (annual_gen * 1000 * heat_rate * price) / 10000
    
    for i in range(1, period + 1):
        y = i
        ts["Year"][i] = y
        ts["Generation"][i] = annual_gen
        
        df = 1 / ((1+wacc)**y)
        ts["Discount Factor"][i] = df
        
        g_npv = annual_gen * df
        ts["Discounted Gen"][i] = g_npv
        
        g_npv_tax = annual_gen * (1-tax_rate) * df
        ts["Discounted Gen Tax Adj"][i] = g_npv_tax
        cum_denom += g_npv_tax
        ts["Cum Denominator"][i] = cum_denom
        
        ts["Opex Pre-tax"][i] = fixed_opex
        ts["Fuel/Charge Pre-tax"][i] = annual_fuel
        
        cur_depr = annual_depr if y <= depr_years else 0
        shield = cur_depr * tax_rate
        ts["Tax Shield"][i] = -shield
        
        op_ben = (fixed_opex + annual_fuel) * tax_rate
        ts["Opex Tax Benefit"][i] = -op_ben
        
        sal = -sal_val_pre if y == period else 0
        ts["Salvage Pre-tax"][i] = sal
        
        sal_tax = sal * tax_rate if y == period else 0
        ts["Salvage Tax"][i] = sal_tax
        
        net = (fixed_opex + annual_fuel) + sal - shield - op_ben + sal_tax
        ts["Net Cost Flow (After-tax)"][i] = net
        
        c_npv = net * df
        ts["PV of Cost"][i] = c_npv
        cum_num += c_npv
        ts["Cum Numerator"][i] = cum_num
        
    real_lcoe = (cum_num / sum(ts["Discounted Gen"])) * 10 if sum(ts["Discounted Gen"]) > 0 else 0
    ppa_lcoe = (cum_num / cum_denom) * 10 if cum_denom > 0 else 0
    
    st.markdown("---")
    c1, c2 = st.columns(2)
    c1.metric("💡 真实 LCOE", f"{real_lcoe:.4f}")
    c2.metric("📉 报价 PPA", f"{ppa_lcoe:.4f}")
    
    with st.expander("📂 导出"):
        excel = generate_professional_excel("Gas_LCOE", {"Tax": tax_rate}, ts, {"Real LCOE": real_lcoe})
        st.download_button("📥 下载 Excel (Safe)", excel, "Gas_LCOE.xlsx")

# ==========================================
# 5. 储能 LCOS (Fix V12.1)
# ==========================================
def render_lcos():
    st.markdown("## 🔋 储能 LCOS (Fix V12.1)")
    
    with st.container():
        c1, c2, c3, c4 = st.columns(4)
        ess_cap = c1.number_input("容量", value=200.0, min_value=0.0)
        cycles = c2.number_input("循环", value=330.0, min_value=0.0)
        rte = c3.number_input("效率%", value=85.0)/100
        deg = c4.number_input("衰减%", value=2.0)/100
        
        c1, c2, c3 = st.columns(3)
        capex = c1.number_input("投资 (万)", value=25000.0)
        opex_r = c2.number_input("运维%", value=2.0)/100
        charge_p = c3.number_input("充电价", value=0.20)
        
        f1, f2, f3 = st.columns(3)
        wacc = f1.number_input("WACC%", value=8.0)/100
        tax_rate = f2.number_input("税率%", value=25.0)/100
        # 关键修复点：显式指定 value，避免歧义
        depr_years = f3.number_input("折旧年", value=15, min_value=0)
        
        l1, l2, l3, l4 = st.columns(4)
        period = int(l1.number_input("寿命", value=15))
        rep_yr = l2.number_input("更换年", value=8)
        rep_cost = l3.number_input("更换费", value=10000.0)
        sal_rate = l4.number_input("残值%", value=3.0)/100

    total_inv = capex
    years = [0] + list(range(1, period + 1))
    ts = {k: [0.0]*(period+1) for k in ["Year", "Generation", "Discount Factor", "Discounted Gen", "Discounted Gen Tax Adj", "Cum Denominator",
                          "Capex", "Opex Pre-tax", "Fuel/Charge Pre-tax", "Replacement", "Salvage Pre-tax",
                          "Tax Shield", "Opex Tax Benefit", "Salvage Tax",
                          "Net Cost Flow (After-tax)", "PV of Cost", "Cum Numerator"]}
    
    ts["Year"][0] = 0
    ts["Discount Factor"][0] = 1.0
    ts["Capex"][0] = total_inv
    ts["Net Cost Flow (After-tax)"][0] = total_inv
    ts["PV of Cost"][0] = total_inv
    ts["Cum Numerator"][0] = total_inv
    
    safe_depr = max(depr_years, 1) if depr_years > 0 else 9999
    annual_depr = total_inv / safe_depr if depr_years > 0 else 0
    sal_val_pre = total_inv * sal_rate
    
    cum_denom = 0
    cum_num = total_inv
    
    for i in range(1, period + 1):
        y = i
        ts["Year"][i] = y
        
        curr_cap = ess_cap * ((1-deg)**(y-1))
        dis = curr_cap * cycles * rte
        ts["Generation"][i] = dis
        
        df = 1 / ((1+wacc)**y)
        ts["Discount Factor"][i] = df
        g_npv = dis * df
        ts["Discounted Gen"][i] = g_npv
        
        g_npv_tax = dis * (1-tax_rate) * df
        ts["Discounted Gen Tax Adj"][i] = g_npv_tax
        cum_denom += g_npv_tax
        ts["Cum Denominator"][i] = cum_denom
        
        ts["Opex Pre-tax"][i] = capex * opex_r
        
        charge = (curr_cap * cycles * 1000 * charge_p) / 10000
        ts["Fuel/Charge Pre-tax"][i] = charge
        
        rep = rep_cost if y == rep_yr else 0
        ts["Replacement"][i] = rep
        
        sal = -sal_val_pre if y == period else 0
        ts["Salvage Pre-tax"][i] = sal
        
        cur_depr = annual_depr if y <= depr_years else 0
        shield = cur_depr * tax_rate
        ts["Tax Shield"][i] = -shield
        
        op_ben = (ts["Opex Pre-tax"][i] + charge) * tax_rate
        ts["Opex Tax Benefit"][i] = -op_ben
        
        sal_tax = sal * tax_rate if y == period else 0
        ts["Salvage Tax"][i] = sal_tax
        
        net = (ts["Opex Pre-tax"][i] + charge) + rep + sal - shield - op_ben + sal_tax
        ts["Net Cost Flow (After-tax)"][i] = net
        
        c_npv = net * df
        ts["PV of Cost"][i] = c_npv
        cum_num += c_npv
        ts["Cum Numerator"][i] = cum_num
        
    real_lcos = (cum_num / sum(ts["Discounted Gen"])) * 10 if sum(ts["Discounted Gen"]) > 0 else 0
    ppa_lcos = (cum_num / cum_denom) * 10 if cum_denom > 0 else 0
    
    st.markdown("---")
    c1, c2 = st.columns(2)
    c1.metric("💡 真实 LCOS", f"{real_lcos:.4f}")
    c2.metric("📉 报价 PPA", f"{ppa_lcos:.4f}")
    
    with st.expander("📂 导出"):
        excel = generate_professional_excel("ESS_LCOS", {"Tax": tax_rate}, ts, {"Real LCOS": real_lcos})
        st.download_button("📥 下载 Excel (Safe)", excel, "ESS_LCOS.xlsx")

# ==========================================
# 6. Main
# ==========================================
def main():
    st.sidebar.title("📌 投资测算工具")
    mode = st.sidebar.radio("模块", ("光伏+储能 LCOE", "燃气发电 LCOE", "储能 LCOS"))
    st.sidebar.info("v12.1 | Final Fix")
    
    if mode == "光伏+储能 LCOE": render_pv_ess_lcoe()
    elif mode == "燃气发电 LCOE": render_gas_lcoe()
    elif mode == "储能 LCOS": render_lcos()

if __name__ == "__main__":
    main()
