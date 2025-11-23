import streamlit as st
import pandas as pd
import numpy as np
import io
import xlsxwriter

# --- 1. 全局配置 ---
st.set_page_config(page_title="新能源投资测算 (Stable Edition)", layout="wide", page_icon="🛡️")

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
# 2. 核心引擎：Excel 生成器 (防崩溃版)
# ==========================================
def sanitize_data(data_list):
    """清洗数据：将 NaN, Inf, NumPy类型 转换为标准的 Python float/int"""
    clean_list = []
    for item in data_list:
        # 处理 NaN 和 Inf
        if pd.isna(item) or (isinstance(item, (float, int, np.number)) and np.isinf(item)):
            clean_list.append(0)
        # 处理 NumPy 数据类型 (如 np.float64) 转为原生 float
        elif isinstance(item, (np.generic)):
            clean_list.append(item.item())
        else:
            clean_list.append(item)
    return clean_list

def generate_professional_excel(model_name, inputs, time_series_data, summary_metrics):
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet('Financial Model')
    
    # 样式定义
    fmt_head = workbook.add_format({'bold': True, 'bg_color': '#2F5597', 'font_color': 'white', 'border': 1, 'align': 'center'})
    fmt_sub = workbook.add_format({'bold': True, 'bg_color': '#D9E1F2', 'border': 1})
    fmt_num = workbook.add_format({'border': 1, 'num_format': '#,##0.00'})
    fmt_money = workbook.add_format({'border': 1, 'num_format': '¥ #,##0'})
    
    # 1. 写入假设 (Inputs)
    worksheet.write('A1', f"{model_name} - Key Assumptions", workbook.add_format({'bold': True, 'font_size': 14}))
    r = 2
    for k, v in inputs.items():
        worksheet.write(r, 0, k, fmt_sub)
        # 清洗 value
        safe_v = 0
        if pd.isna(v) or np.isinf(v): safe_v = 0
        elif isinstance(v, np.generic): safe_v = v.item()
        else: safe_v = v
        worksheet.write(r, 1, safe_v, fmt_num)
        r += 1
        
    # 2. 写入瀑布流 (Waterfall)
    r += 2
    worksheet.write(r, 0, "Cash Flow Waterfall", workbook.add_format({'bold': True, 'font_size': 12}))
    r += 1
    
    # 表头
    cols = ["Year"] + [f"Year {y}" for y in time_series_data["Year"]]
    worksheet.write_row(r, 0, cols, fmt_head)
    r += 1
    
    # 定义所有可能出现的行 (通用配置)
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
        # 写行标题
        worksheet.write(r, 0, label, fmt_sub if key=="" or "===" in label else workbook.add_format({'border':1}))
        
        # 写数据 (如果存在该key)
        if key and key in time_series_data:
            # === 关键修复：数据清洗 ===
            raw_data = time_series_data[key]
            safe_data = sanitize_data(raw_data)
            # ========================
            worksheet.write_row(r, 1, safe_data, fmt)
        r += 1
        
    workbook.close()
    return output.getvalue()

# ==========================================
# 3. 模块 A: 光伏 + 储能 LCOE (V11)
# ==========================================
def render_pv_ess_lcoe():
    st.markdown("## ☀️ 光伏+储能 LCOE (修复版)")
    
    with st.container():
        st.markdown("### 1. 系统配置")
        charge_source = st.radio("🔋 储能电力来源", ("来自光伏 (From PV)", "来自电网 (From Grid)"), horizontal=True)
        
        c1, c2, c3, c4 = st.columns(4)
        pv_cap = c1.number_input("光伏容量 (MW)", value=200.0)
        pv_hours = c2.number_input("光伏利用小时数 (h)", value=2200.0)
        ess_cap = c3.number_input("储能容量 (MWh)", value=120.0)
        ess_cycles = c4.number_input("储能年循环次数", value=365.0)
        
        t1, t2 = st.columns(2)
        ess_eff = t1.number_input("储能综合效率 RTE (%)", value=85.0, step=0.1)/100
        pv_deg = t2.number_input("光伏年衰减率 (%)", value=0.5, step=0.1)/100
        
        grid_charge_price = 0.0
        if charge_source == "来自电网 (From Grid)":
            grid_charge_price = st.number_input("谷时充电电价 (元/kWh)", value=0.20)
        
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
        st.markdown("### 3. 税务与财务")
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

    # Calc
    total_inv = capex_pv + capex_ess + capex_grid
    years = [0] + list(range(1, period + 1))
    
    ts = {k: [] for k in ["Year", "Generation", "Discount Factor", "Discounted Gen", "Discounted Gen Tax Adj", "Cum Denominator",
                          "Capex", "Opex Pre-tax", "Grid Charge Cost", "Replacement", "Salvage Pre-tax",
                          "Tax Shield", "Opex Tax Benefit", "Salvage Tax",
                          "Net Cost Flow (After-tax)", "PV of Cost", "Cum Numerator"]}
    
    # Init 0
    for k in ts: ts[k].append(0)
    ts["Year"][0] = 0
    ts["Discount Factor"][0] = 1.0
    ts["Capex"][0] = total_inv
    ts["Net Cost Flow (After-tax)"][0] = total_inv
    ts["PV of Cost"][0] = total_inv
    ts["Cum Numerator"][0] = total_inv
    
    annual_depr = total_inv / depr_years if depr_years > 0 else 0
    cum_denom = 0
    cum_num = total_inv
    salvage_val_pre = total_inv * salvage_rate

    for y in range(1, period + 1):
        ts["Year"].append(y)
        
        # Gen
        deg = 1 - (y-1)*pv_deg
        if deg < 0: deg = 0
        raw_pv = pv_cap * pv_hours * deg
        
        sys_gen = 0
        grid_cost = 0
        
        if charge_source == "来自光伏 (From PV)":
            # PV -> ESS Loss
            charge_energy = ess_cap * ess_cycles
            loss = charge_energy * (1 - ess_eff)
            sys_gen = raw_pv - loss
        else:
            # PV + ESS(Grid)
            charge_energy = ess_cap * ess_cycles
            discharge = charge_energy * ess_eff
            sys_gen = raw_pv + discharge
            grid_cost = (charge_energy * 1000 * grid_charge_price) / 10000
            
        ts["Generation"].append(sys_gen)
        
        df = 1 / ((1+wacc)**y)
        ts["Discount Factor"].append(df)
        
        g_npv = sys_gen * df
        ts["Discounted Gen"].append(g_npv)
        
        # PPA 分母调整
        g_npv_tax = sys_gen * (1-tax_rate) * df
        ts["Discounted Gen Tax Adj"].append(g_npv_tax)
        cum_denom += g_npv_tax
        ts["Cum Denominator"].append(cum_denom)
        
        ts["Capex"].append(0)
        
        opex = (capex_pv*opex_r_pv) + (capex_ess*opex_r_ess) + (capex_grid*opex_r_grid)
        ts["Opex Pre-tax"].append(opex)
        ts["Grid Charge Cost"].append(grid_cost)
        
        rep = rep_cost if y == rep_yr else 0
        ts["Replacement"].append(rep)
        
        sal = -salvage_val_pre if y == period else 0
        ts["Salvage Pre-tax"].append(sal)
        
        # Tax
        cur_depr = annual_depr if y <= depr_years else 0
        shield = cur_depr * tax_rate
        ts["Tax Shield"].append(-shield)
        
        op_ben = (opex + grid_cost) * tax_rate
        ts["Opex Tax Benefit"].append(-op_ben)
        
        sal_tax = sal * tax_rate if y == period else 0
        ts["Salvage Tax"].append(sal_tax)
        
        net_after = (opex + grid_cost - op_ben) + rep - shield + (sal - sal_tax)
        ts["Net Cost Flow (After-tax)"].append(net_after)
        
        c_npv = net_after * df
        ts["PV of Cost"].append(c_npv)
        cum_num += c_npv
        ts["Cum Numerator"].append(cum_num)
        
    real_lcoe = (cum_num / sum(ts["Discounted Gen"])) * 10 if sum(ts["Discounted Gen"]) > 0 else 0
    ppa_lcoe = (cum_num / cum_denom) * 10 if cum_denom > 0 else 0
    
    st.markdown("---")
    c1, c2 = st.columns(2)
    c1.metric("💡 真实持有成本 (Real LCOE)", f"{real_lcoe:.4f}", help="分母不含税调整")
    c2.metric("📉 盈亏平衡报价 (PPA Price)", f"{ppa_lcoe:.4f}", help="分母含税调整")
    
    with st.expander("📂 导出底稿"):
        excel = generate_professional_excel("PV_ESS_LCOE", {"Tax": tax_rate}, ts, {"Real LCOE": real_lcoe})
        st.download_button("📥 下载 Excel (Safe)", excel, "PV_ESS_LCOE.xlsx")

# ==========================================
# 4. 燃气 LCOE (V11)
# ==========================================
def render_gas_lcoe():
    st.markdown("## 🔥 燃气发电 LCOE (修复版)")
    
    with st.container():
        c1, c2, c3 = st.columns(3)
        gas_cap = c1.number_input("装机 (MW)", value=360.0)
        gas_capex = c2.number_input("投资 (万)", value=60000.0)
        wacc = c3.number_input("WACC (%)", value=8.0)/100
        c1, c2, c3 = st.columns(3)
        hours = c1.number_input("小时数", value=3000.0)
        heat_rate = c2.number_input("热耗 (GJ/kWh)", value=0.0095, format="%.4f")
        price = c3.number_input("气价 (元/GJ)", value=60.0)
        fixed_opex = st.number_input("固定运维 (万/年)", value=1200.0)
        f1, f2, f3, f4 = st.columns(4)
        tax_rate = f1.number_input("税率 (%)", value=25.0)/100
        depr_years = f2.number_input("折旧年", value=20)
        period = int(f3.number_input("周期", value=25))
        salvage_rate = f4.number_input("残值率 (%)", value=5.0)/100

    total_inv = gas_capex
    years = [0] + list(range(1, period + 1))
    ts = {k: [] for k in ["Year", "Generation", "Discount Factor", "Discounted Gen", "Discounted Gen Tax Adj", "Cum Denominator",
                          "Capex", "Opex Pre-tax", "Fuel/Charge Pre-tax", "Replacement", "Salvage Pre-tax",
                          "Tax Shield", "Opex Tax Benefit", "Salvage Tax",
                          "Net Cost Flow (After-tax)", "PV of Cost", "Cum Numerator"]}
    
    for k in ts: ts[k].append(0)
    ts["Year"][0] = 0
    ts["Discount Factor"][0] = 1.0
    ts["Capex"][0] = total_inv
    ts["Net Cost Flow (After-tax)"][0] = total_inv
    ts["PV of Cost"][0] = total_inv
    ts["Cum Numerator"][0] = total_inv
    
    annual_gen = gas_cap * hours
    annual_fuel = (annual_gen * 1000 * heat_rate * price) / 10000
    annual_depr = total_inv / depr_years if depr_years > 0 else 0
    sal_val_pre = total_inv * salvage_rate
    
    cum_denom = 0
    cum_num = total_inv
    
    for y in range(1, period + 1):
        ts["Year"].append(y)
        ts["Generation"].append(annual_gen)
        
        df = 1 / ((1+wacc)**y)
        ts["Discount Factor"].append(df)
        g_npv = annual_gen * df
        ts["Discounted Gen"].append(g_npv)
        
        g_npv_tax = annual_gen * (1-tax_rate) * df
        ts["Discounted Gen Tax Adj"].append(g_npv_tax)
        cum_denom += g_npv_tax
        ts["Cum Denominator"].append(cum_denom)
        
        ts["Capex"].append(0)
        ts["Opex Pre-tax"].append(fixed_opex)
        ts["Fuel/Charge Pre-tax"].append(annual_fuel)
        ts["Replacement"].append(0)
        
        sal_pre = -sal_val_pre if y == period else 0
        ts["Salvage Pre-tax"].append(sal_pre)
        
        curr_depr = annual_depr if y <= depr_years else 0
        shield = curr_depr * tax_rate
        ts["Tax Shield"].append(-shield)
        
        op_ben = (fixed_opex + annual_fuel) * tax_rate
        ts["Opex Tax Benefit"].append(-op_ben)
        
        sal_tax = sal_pre * tax_rate if y == period else 0
        ts["Salvage Tax"].append(sal_tax)
        
        net_after = (fixed_opex + annual_fuel - op_ben) - shield + (sal_pre - sal_tax)
        ts["Net Cost Flow (After-tax)"].append(net_after)
        
        c_npv = net_after * df
        ts["PV of Cost"].append(c_npv)
        cum_num += c_npv
        ts["Cum Numerator"].append(cum_num)
        
    real_lcoe = (cum_num / sum(ts["Discounted Gen"])) * 10 if sum(ts["Discounted Gen"]) > 0 else 0
    ppa_lcoe = (cum_num / cum_denom) * 10 if cum_denom > 0 else 0
    
    st.markdown("---")
    c1, c2 = st.columns(2)
    c1.metric("💡 真实持有成本", f"{real_lcoe:.4f}")
    c2.metric("📉 盈亏平衡 PPA", f"{ppa_lcoe:.4f}")
    
    with st.expander("📂 导出"):
        excel = generate_professional_excel("Gas_LCOE", {"Tax": tax_rate}, ts, {"Real LCOE": real_lcoe})
        st.download_button("📥 下载 Excel", excel, "Gas_LCOE.xlsx")

# ==========================================
# 5. 储能 LCOS (V11)
# ==========================================
def render_lcos():
    st.markdown("## 🔋 储能 LCOS (修复版)")
    
    with st.container():
        c1, c2, c3, c4 = st.columns(4)
        ess_cap = c1.number_input("容量 (MWh)", value=200.0)
        cycles = c2.number_input("循环", value=330.0)
        rte = c3.number_input("效率 RTE%", value=85.0)/100
        deg = c4.number_input("衰减%", value=2.0)/100
        
        c1, c2, c3 = st.columns(3)
        capex = c1.number_input("投资 (万)", value=25000.0)
        opex_r = c2.number_input("运维%", value=2.0)/100
        charge_p = c3.number_input("充电价", value=0.20)
        
        f1, f2, f3 = st.columns(3)
        wacc = f1.number_input("WACC%", value=8.0)/100
        tax_rate = f2.number_input("税率%", value=25.0)/100
        depr_years = f3.number_input("折旧年", value=15)
        
        l1, l2, l3, l4 = st.columns(4)
        period = int(l1.number_input("寿命", value=15))
        rep_yr = l2.number_input("更换年", 8)
        rep_cost = l3.number_input("更换费", 10000.0)
        sal_rate = l4.number_input("残值%", value=3.0)/100

    total_inv = capex
    years = [0] + list(range(1, period + 1))
    ts = {k: [] for k in ["Year", "Generation", "Discount Factor", "Discounted Gen", "Discounted Gen Tax Adj", "Cum Denominator",
                          "Capex", "Opex Pre-tax", "Fuel/Charge Pre-tax", "Replacement", "Salvage Pre-tax",
                          "Tax Shield", "Opex Tax Benefit", "Salvage Tax",
                          "Net Cost Flow (After-tax)", "PV of Cost", "Cum Numerator"]}
    
    for k in ts: ts[k].append(0)
    ts["Year"][0] = 0
    ts["Discount Factor"][0] = 1.0
    ts["Capex"][0] = total_inv
    ts["Net Cost Flow (After-tax)"][0] = total_inv
    ts["PV of Cost"][0] = total_inv
    ts["Cum Numerator"][0] = total_inv
    
    annual_depr = total_inv / depr_years if depr_years > 0 else 0
    sal_val_pre = total_inv * sal_rate
    cum_denom = 0
    cum_num = total_inv
    
    for y in range(1, period + 1):
        ts["Year"].append(y)
        
        curr_cap = ess_cap * ((1-deg)**(y-1))
        dis = curr_cap * cycles * rte
        ts["Generation"].append(dis)
        
        df = 1 / ((1+wacc)**y)
        ts["Discount Factor"].append(df)
        g_npv = dis * df
        ts["Discounted Gen"].append(g_npv)
        
        g_npv_tax = dis * (1-tax_rate) * df
        ts["Discounted Gen Tax Adj"].append(g_npv_tax)
        cum_denom += g_npv_tax
        ts["Cum Denominator"].append(cum_denom)
        
        ts["Capex"].append(0)
        
        opex_pre = capex * opex_r
        ts["Opex Pre-tax"].append(opex_pre)
        
        charge_pre = (curr_cap * cycles * 1000 * charge_p) / 10000
        ts["Fuel/Charge Pre-tax"].append(charge_pre)
        
        rep = rep_cost if y == rep_yr else 0
        ts["Replacement"].append(rep)
        
        sal_pre = -sal_val_pre if y == period else 0
        ts["Salvage Pre-tax"].append(sal_pre)
        
        curr_depr = annual_depr if y <= depr_years else 0
        shield = curr_depr * tax_rate
        ts["Tax Shield"].append(-shield)
        
        op_ben = (opex_pre + charge_pre) * tax_rate
        ts["Opex Tax Benefit"].append(-op_ben)
        
        sal_tax = sal_pre * tax_rate if y == period else 0
        ts["Salvage Tax"].append(sal_tax)
        
        net_after = (opex_pre + charge_pre - op_ben) + rep - shield + (sal_pre - sal_tax)
        ts["Net Cost Flow (After-tax)"].append(net_after)
        
        c_npv = net_after * df
        ts["PV of Cost"].append(c_npv)
        cum_num += c_npv
        ts["Cum Numerator"].append(cum_num)
        
    real_lcos = (cum_num / sum(ts["Discounted Gen"])) * 10 if sum(ts["Discounted Gen"]) > 0 else 0
    ppa_lcos = (cum_num / cum_denom) * 10 if cum_denom > 0 else 0
    
    st.markdown("---")
    c1, c2 = st.columns(2)
    c1.metric("💡 真实 LCOS", f"{real_lcos:.4f}")
    c2.metric("📉 报价 PPA", f"{ppa_lcos:.4f}")
    
    with st.expander("📂 导出"):
        excel = generate_professional_excel("ESS_LCOS", {"Tax": tax_rate}, ts, {"Real LCOS": real_lcos})
        st.download_button("📥 下载 Excel", excel, "ESS_LCOS.xlsx")

# ==========================================
# 6. Main
# ==========================================
def main():
    st.sidebar.title("📌 投资测算工具")
    mode = st.sidebar.radio("模块", ("光伏+储能 LCOE", "燃气发电 LCOE", "储能 LCOS"))
    st.sidebar.info("v11.0 | Excel Crash Fixed")
    
    if mode == "光伏+储能 LCOE": render_pv_ess_lcoe()
    elif mode == "燃气发电 LCOE": render_gas_lcoe()
    elif mode == "储能 LCOS": render_lcos()

if __name__ == "__main__":
    main()
