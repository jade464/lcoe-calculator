import streamlit as st
import pandas as pd
import numpy as np
import io
import xlsxwriter

# --- 1. 全局配置 ---
st.set_page_config(page_title="新能源资产持有成本测算 (Fully Unlocked)", layout="wide", page_icon="🔓")

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
# 2. Excel 引擎
# ==========================================
def generate_professional_excel(model_name, inputs, time_series_data, summary_metrics):
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet('Financial Model')
    
    fmt_head = workbook.add_format({'bold': True, 'bg_color': '#2F5597', 'font_color': 'white', 'border': 1, 'align': 'center'})
    fmt_sub = workbook.add_format({'bold': True, 'bg_color': '#D9E1F2', 'border': 1})
    fmt_num = workbook.add_format({'border': 1, 'num_format': '#,##0.00'})
    fmt_money = workbook.add_format({'border': 1, 'num_format': '¥ #,##0'})
    
    # 1. Inputs
    worksheet.write('A1', f"{model_name} - Key Assumptions", workbook.add_format({'bold': True, 'font_size': 14}))
    r = 2
    for k, v in inputs.items():
        worksheet.write(r, 0, k, fmt_sub)
        worksheet.write(r, 1, v, fmt_num)
        r += 1
        
    # 2. Waterfall
    r += 2
    worksheet.write(r, 0, "Cash Flow Waterfall", workbook.add_format({'bold': True, 'font_size': 12}))
    r += 1
    
    cols = ["Year"] + [f"Year {y}" for y in time_series_data["Year"]]
    worksheet.write_row(r, 0, cols, fmt_head)
    r += 1
    
    rows = [
        ("物理发电量 (MWh)", "Generation", fmt_num),
        ("折现系数", "Discount Factor", fmt_num),
        ("折现发电量", "Discounted Gen", fmt_num),
        ("", "", None),
        ("1. 初始投资", "Capex", fmt_money),
        ("2. 运营支出 (税前)", "Opex Pre-tax", fmt_money),
        ("3. 燃料/充电 (税前)", "Fuel/Charge Pre-tax", fmt_money),
        ("4. 资产置换", "Replacement", fmt_money),
        ("5. 残值回收 (税前)", "Salvage Pre-tax", fmt_money),
        ("   >>> 税前净现金流", "Net Cash Flow (Pre-tax)", fmt_money),
        ("", "", None),
        ("--- 税务调节 ---", "", None),
        ("折旧 (D&A)", "Depreciation", fmt_money),
        ("税盾效应 (抵扣)", "Tax Shield", fmt_money),
        ("Opex抵税 (抵扣)", "Opex Tax Benefit", fmt_money),
        ("", "", None),
        ("=== 税后真实净流出 ===", "Net Cost Flow (After-tax)", fmt_money),
        ("折现成本", "PV of Cost (After-tax)", fmt_money),
        ("累计折现成本", "Cum PV Cost (After-tax)", fmt_money)
    ]
    
    for label, key, fmt in rows:
        worksheet.write(r, 0, label, fmt_sub if key=="" or "===" in label else workbook.add_format({'border':1}))
        if key and key in time_series_data:
            worksheet.write_row(r, 1, time_series_data[key], fmt)
        r += 1
        
    workbook.close()
    return output.getvalue()

# ==========================================
# 3. 模块 A: 光伏 + 储能 LCOE (全参数开放)
# ==========================================
def render_pv_ess_lcoe():
    st.markdown("## ☀️ 光伏+储能 LCOE (资产持有者综合视角)")
    
    with st.container():
        st.markdown("### 1. 规模与物理参数")
        c1, c2, c3, c4 = st.columns(4)
        pv_cap = c1.number_input("光伏容量 (MW)", value=200.0)
        pv_hours = c2.number_input("利用小时数 (h)", value=2200.0)
        ess_cap = c3.number_input("储能容量 (MWh)", value=120.0)
        ess_cycles = c4.number_input("循环次数", value=1000.0)
        
        # [新增开放] 效率与衰减
        st.caption("技术细节参数")
        t1, t2 = st.columns(2)
        pv_deg = t1.number_input("光伏年衰减率 (%)", value=0.5, step=0.1) / 100
        ess_eff = t2.number_input("储能系统效率 (%)", value=85.0, step=0.1) / 100
        
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
        salvage_rate = l3.number_input("期末综合残值率 (%)", 5.0)/100

    # --- Calculation ---
    total_inv = capex_pv + capex_ess + capex_grid
    years = [0] + list(range(1, period + 1))
    
    ts = {k: [] for k in ["Year", "Generation", "Discount Factor", "Discounted Gen", "Cum Discounted Gen",
                          "Capex", "Opex Pre-tax", "Fuel/Charge Pre-tax", "Replacement", "Salvage Pre-tax",
                          "Net Cash Flow (Pre-tax)", "Depreciation", "Tax Shield", "Opex Tax Benefit", "Salvage After-tax",
                          "Net Cost Flow (After-tax)", "PV of Cost (After-tax)", "Cum PV Cost (After-tax)",
                          "PV of Cost (Pre-tax)", "Cum PV Cost (Pre-tax)"]}
    
    for k in ts: ts[k].append(0)
    ts["Year"][0] = 0
    ts["Discount Factor"][0] = 1.0
    ts["Capex"][0] = total_inv
    ts["Net Cash Flow (Pre-tax)"][0] = total_inv
    ts["Net Cost Flow (After-tax)"][0] = total_inv
    ts["PV of Cost (Pre-tax)"][0] = total_inv
    ts["Cum PV Cost (Pre-tax)"][0] = total_inv
    ts["PV of Cost (After-tax)"][0] = total_inv
    ts["Cum PV Cost (After-tax)"][0] = total_inv
    
    annual_depr = total_inv / depr_years
    cum_denom = 0
    cum_num_pre = total_inv
    cum_num_after = total_inv
    
    salvage_val_pre = total_inv * salvage_rate

    for y in range(1, period + 1):
        ts["Year"].append(y)
        
        # [修正] 使用用户输入的 pv_deg
        deg = 1 - (y-1) * pv_deg
        if deg < 0: deg = 0
        
        # [修正] 使用用户输入的 ess_eff
        gen = (pv_cap * pv_hours * deg) + (ess_cap * ess_cycles * ess_eff)
        ts["Generation"].append(gen)
        
        df = 1 / ((1+wacc)**y)
        ts["Discount Factor"].append(df)
        g_npv = gen * df
        ts["Discounted Gen"].append(g_npv)
        cum_denom += g_npv
        ts["Cum Discounted Gen"].append(cum_denom)
        
        ts["Capex"].append(0)
        
        opex_pre = (capex_pv*opex_r_pv) + (capex_ess*opex_r_ess) + (capex_grid*opex_r_grid)
        ts["Opex Pre-tax"].append(opex_pre)
        ts["Fuel/Charge Pre-tax"].append(0)
        
        rep = rep_cost if y == rep_yr else 0
        ts["Replacement"].append(rep)
        
        sal_pre = -salvage_val_pre if y == period else 0
        ts["Salvage Pre-tax"].append(sal_pre)
        
        net_pre = opex_pre + rep + sal_pre
        ts["Net Cash Flow (Pre-tax)"].append(net_pre)
        
        c_npv_pre = net_pre * df
        ts["PV of Cost (Pre-tax)"].append(c_npv_pre)
        cum_num_pre += c_npv_pre
        ts["Cum PV Cost (Pre-tax)"].append(cum_num_pre)
        
        curr_depr = annual_depr if y <= depr_years else 0
        ts["Depreciation"].append(curr_depr)
        
        tax_shield = curr_depr * tax_rate
        ts["Tax Shield"].append(-tax_shield)
        
        opex_ben = opex_pre * tax_rate
        ts["Opex Tax Benefit"].append(-opex_ben)
        
        sal_after = sal_pre * (1 - tax_rate)
        ts["Salvage After-tax"].append(sal_after)
        
        net_after = (opex_pre - opex_ben) + rep - tax_shield + sal_after
        ts["Net Cost Flow (After-tax)"].append(net_after)
        
        c_npv_after = net_after * df
        ts["PV of Cost (After-tax)"].append(c_npv_after)
        cum_num_after += c_npv_after
        ts["Cum PV Cost (After-tax)"].append(cum_num_after)
        
    lcoe_pre = (cum_num_pre / cum_denom) * 10 if cum_denom > 0 else 0
    lcoe_after = (cum_num_after / cum_denom) * 10 if cum_denom > 0 else 0
    lcoe_ppa = lcoe_after / (1 - tax_rate) if (1-tax_rate) > 0 else 0
    
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    col1.metric("💡 税后真实 LCOE", f"{lcoe_after:.4f} 元/kWh")
    col2.metric("⚙️ 税前技术 LCOE", f"{lcoe_pre:.4f} 元/kWh")
    col3.metric("📉 盈亏平衡 PPA", f"{lcoe_ppa:.4f} 元/kWh")
    
    with st.expander("📂 导出底稿"):
        excel = generate_professional_excel("PV_ESS_LCOE", {"PV Deg": pv_deg, "ESS Eff": ess_eff}, ts, {"Real LCOE": lcoe_after})
        st.download_button("📥 下载 Excel", excel, "PV_ESS_LCOE.xlsx")

# ==========================================
# 4. 燃气 LCOE (全参数开放)
# ==========================================
def render_gas_lcoe():
    st.markdown("## 🔥 燃气发电 LCOE (资产持有者综合视角)")
    
    with st.container():
        st.markdown("### 1. 规模与投资")
        c1, c2, c3 = st.columns(3)
        gas_cap = c1.number_input("装机 (MW)", value=360.0)
        gas_capex = c2.number_input("投资 (万)", value=60000.0)
        wacc = c3.number_input("WACC (%)", value=8.0)/100
        
        st.markdown("### 2. 运营与燃料")
        c1, c2, c3 = st.columns(3)
        hours = c1.number_input("小时数", value=3000.0)
        heat_rate = c2.number_input("热耗 (GJ/kWh)", value=0.0095, format="%.4f")
        price = c3.number_input("气价 (元/GJ)", value=60.0)
        fixed_opex = st.number_input("固定运维 (万/年)", value=1200.0)

        st.markdown("### 3. 税务与周期")
        f1, f2, f3, f4 = st.columns(4)
        tax_rate = f1.number_input("税率 (%)", value=25.0)/100
        depr_years = f2.number_input("折旧年", value=20)
        period = int(f3.number_input("周期 (年)", value=25))
        # [新增开放] 残值率
        salvage_rate = f4.number_input("残值率 (%)", value=5.0)/100

    total_inv = gas_capex
    years = [0] + list(range(1, period + 1))
    ts = {k: [] for k in ["Year", "Generation", "Discount Factor", "Discounted Gen", "Cum Discounted Gen",
                          "Capex", "Opex Pre-tax", "Fuel/Charge Pre-tax", "Replacement", "Salvage Pre-tax",
                          "Net Cash Flow (Pre-tax)", "Depreciation", "Tax Shield", "Opex Tax Benefit", "Salvage After-tax",
                          "Net Cost Flow (After-tax)", "PV of Cost (After-tax)", "Cum PV Cost (After-tax)",
                          "PV of Cost (Pre-tax)", "Cum PV Cost (Pre-tax)"]}
    
    for k in ts: ts[k].append(0)
    ts["Year"][0] = 0
    ts["Discount Factor"][0] = 1.0
    ts["Capex"][0] = total_inv
    ts["Net Cash Flow (Pre-tax)"][0] = total_inv
    ts["Net Cost Flow (After-tax)"][0] = total_inv
    ts["PV of Cost (Pre-tax)"][0] = total_inv
    ts["Cum PV Cost (Pre-tax)"][0] = total_inv
    ts["PV of Cost (After-tax)"][0] = total_inv
    ts["Cum PV Cost (After-tax)"][0] = total_inv
    
    annual_gen = gas_cap * hours
    annual_fuel_pre = (annual_gen * 1000 * heat_rate * price) / 10000
    annual_depr = total_inv / depr_years
    # [修正] 使用用户输入的残值率
    sal_val_pre = total_inv * salvage_rate
    
    cum_denom = 0
    cum_num_pre = total_inv
    cum_num_after = total_inv
    
    for y in range(1, period + 1):
        ts["Year"].append(y)
        ts["Generation"].append(annual_gen)
        
        df = 1 / ((1+wacc)**y)
        ts["Discount Factor"].append(df)
        g_npv = annual_gen * df
        ts["Discounted Gen"].append(g_npv)
        cum_denom += g_npv
        ts["Cum Discounted Gen"].append(cum_denom)
        
        ts["Capex"].append(0)
        ts["Opex Pre-tax"].append(fixed_opex)
        ts["Fuel/Charge Pre-tax"].append(annual_fuel_pre)
        ts["Replacement"].append(0)
        
        sal_pre = -sal_val_pre if y == period else 0
        ts["Salvage Pre-tax"].append(sal_pre)
        
        net_pre = fixed_opex + annual_fuel_pre + sal_pre
        ts["Net Cash Flow (Pre-tax)"].append(net_pre)
        c_npv_pre = net_pre * df
        ts["PV of Cost (Pre-tax)"].append(c_npv_pre)
        cum_num_pre += c_npv_pre
        ts["Cum PV Cost (Pre-tax)"].append(cum_num_pre)
        
        curr_depr = annual_depr if y <= depr_years else 0
        ts["Depreciation"].append(curr_depr)
        
        shield = curr_depr * tax_rate
        ts["Tax Shield"].append(-shield)
        
        opex_ben = (fixed_opex + annual_fuel_pre) * tax_rate
        ts["Opex Tax Benefit"].append(-opex_ben)
        
        sal_after = sal_pre * (1 - tax_rate)
        ts["Salvage After-tax"].append(sal_after)
        
        net_after = (fixed_opex + annual_fuel_pre - opex_ben) - shield + sal_after
        ts["Net Cost Flow (After-tax)"].append(net_after)
        
        c_npv_after = net_after * df
        ts["PV of Cost (After-tax)"].append(c_npv_after)
        cum_num_after += c_npv_after
        ts["Cum PV Cost (After-tax)"].append(cum_num_after)
        
    lcoe_pre = (cum_num_pre / cum_denom) * 10 if cum_denom > 0 else 0
    lcoe_after = (cum_num_after / cum_denom) * 10 if cum_denom > 0 else 0
    lcoe_ppa = lcoe_after / (1 - tax_rate) if (1-tax_rate) > 0 else 0
    
    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    c1.metric("💡 税后真实 LCOE", f"{lcoe_after:.4f} 元/kWh")
    c2.metric("⚙️ 税前技术 LCOE", f"{lcoe_pre:.4f} 元/kWh")
    c3.metric("📉 盈亏平衡 PPA", f"{lcoe_ppa:.4f} 元/kWh")
    
    with st.expander("📂 导出"):
        excel = generate_professional_excel("Gas_LCOE", {"Salvage": salvage_rate}, ts, {"Real LCOE": lcoe_after})
        st.download_button("📥 下载 Excel", excel, "Gas_LCOE.xlsx")

# ==========================================
# 5. 储能 LCOS (全参数开放 + 修复Bug)
# ==========================================
def render_lcos():
    st.markdown("## 🔋 储能 LCOS (资产持有者综合视角)")
    
    with st.container():
        st.markdown("### 1. 规模与物理参数")
        c1, c2, c3, c4 = st.columns(4)
        ess_cap = c1.number_input("容量 (MWh)", value=200.0)
        cycles = c2.number_input("年循环次数 (次)", value=330.0)
        rte = c3.number_input("系统效率 RTE (%)", value=85.0) / 100
        deg = c4.number_input("年衰减率 (%)", value=2.0) / 100
        
        st.markdown("### 2. 投资与运营")
        c1, c2, c3 = st.columns(3)
        capex = c1.number_input("总投资 (万)", value=25000.0)
        opex_r = c2.number_input("运维%", value=2.0)/100
        charge_p = c3.number_input("充电价 (元/kWh)", value=0.20)
        
        st.markdown("### 3. 财务与税务")
        f1, f2, f3 = st.columns(3)
        wacc = f1.number_input("WACC (%)", value=8.0)/100
        tax_rate = f2.number_input("税率 (%)", value=25.0)/100
        depr_years = f3.number_input("折旧年限", value=15)
        
        st.markdown("### 4. 周期与置换")
        l1, l2, l3, l4 = st.columns(4)
        period = int(l1.number_input("寿命 (年)", value=15))
        rep_yr = l2.number_input("更换年份", 8)
        rep_cost = l3.number_input("更换费用", 10000.0)
        # [新增开放] 残值率
        salvage_rate = l4.number_input("残值率 (%)", value=3.0) / 100

    # Calc
    total_inv = capex
    years = [0] + list(range(1, period + 1))
    ts = {k: [] for k in ["Year", "Generation", "Discount Factor", "Discounted Gen", "Cum Discounted Gen",
                          "Capex", "Opex Pre-tax", "Fuel/Charge Pre-tax", "Replacement", "Salvage Pre-tax",
                          "Net Cash Flow (Pre-tax)", "Depreciation", "Tax Shield", "Opex Tax Benefit", "Salvage After-tax",
                          "Net Cost Flow (After-tax)", "PV of Cost (After-tax)", "Cum PV Cost (After-tax)",
                          "PV of Cost (Pre-tax)", "Cum PV Cost (Pre-tax)"]}
    
    for k in ts: ts[k].append(0)
    ts["Year"][0] = 0
    ts["Discount Factor"][0] = 1.0
    ts["Capex"][0] = total_inv
    ts["Net Cash Flow (Pre-tax)"][0] = total_inv
    ts["Net Cost Flow (After-tax)"][0] = total_inv
    ts["PV of Cost (Pre-tax)"][0] = total_inv
    ts["Cum PV Cost (Pre-tax)"][0] = total_inv
    ts["PV of Cost (After-tax)"][0] = total_inv
    ts["Cum PV Cost (After-tax)"][0] = total_inv
    
    annual_depr = total_inv / depr_years
    cum_denom = 0
    cum_num_pre = total_inv
    cum_num_after = total_inv
    # [修正] 使用用户输入残值率
    sal_val_pre = total_inv * salvage_rate
    
    for y in range(1, period + 1):
        ts["Year"].append(y)
        
        curr_cap = ess_cap * ((1-deg)**(y-1))
        # [Bug修复] 使用用户输入的 rte，而不是写死的0.85
        dis = curr_cap * cycles * rte 
        ts["Generation"].append(dis)
        
        df = 1 / ((1+wacc)**y)
        ts["Discount Factor"].append(df)
        g_npv = dis * df
        ts["Discounted Gen"].append(g_npv)
        cum_denom += g_npv
        ts["Cum Discounted Gen"].append(cum_denom)
        
        ts["Capex"].append(0)
        
        opex_pre = capex * opex_r
        ts["Opex Pre-tax"].append(opex_pre)
        
        # 充电成本基于充电量，放电量才乘效率
        # Charge = Capacity * Cycles
        charge_pre = (curr_cap * cycles * 1000 * charge_p) / 10000
        ts["Fuel/Charge Pre-tax"].append(charge_pre)
        
        rep = rep_cost if y == rep_yr else 0
        ts["Replacement"].append(rep)
        
        # [修正] 启用LCOS残值
        sal_pre = -sal_val_pre if y == period else 0
        ts["Salvage Pre-tax"].append(sal_pre)
        
        # Path A
        net_pre = opex_pre + charge_pre + rep + sal_pre
        ts["Net Cash Flow (Pre-tax)"].append(net_pre)
        c_npv_pre = net_pre * df
        ts["PV of Cost (Pre-tax)"].append(c_npv_pre)
        cum_num_pre += c_npv_pre
        ts["Cum PV Cost (Pre-tax)"].append(cum_num_pre)
        
        # Path B
        curr_depr = annual_depr if y <= depr_years else 0
        ts["Depreciation"].append(curr_depr)
        
        shield = curr_depr * tax_rate
        ts["Tax Shield"].append(-shield)
        
        opex_ben = (opex_pre + charge_pre) * tax_rate
        ts["Opex Tax Benefit"].append(-opex_ben)
        
        sal_after = sal_pre * (1 - tax_rate)
        ts["Salvage After-tax"].append(sal_after)
        
        net_after = (opex_pre + charge_pre - opex_ben) + rep - shield + sal_after
        ts["Net Cost Flow (After-tax)"].append(net_after)
        
        c_npv_after = net_after * df
        ts["PV of Cost (After-tax)"].append(c_npv_after)
        cum_num_after += c_npv_after
        ts["Cum PV Cost (After-tax)"].append(cum_num_after)
        
    lcos_pre = (cum_num_pre / cum_denom) * 10 if cum_denom > 0 else 0
    lcos_after = (cum_num_after / cum_denom) * 10 if cum_denom > 0 else 0
    lcos_ppa = lcos_after / (1 - tax_rate) if (1-tax_rate) > 0 else 0
    
    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    c1.metric("💡 税后真实 LCOS", f"{lcos_after:.4f}", delta="- 税盾")
    c2.metric("⚙️ 税前技术 LCOS", f"{lcos_pre:.4f}")
    c3.metric("📉 盈亏平衡 PPA", f"{lcos_ppa:.4f}")
    
    with st.expander("📂 导出"):
        excel = generate_professional_excel("ESS_LCOS", {"RTE": rte, "Deg": deg}, ts, {"Real LCOS": lcos_after})
        st.download_button("📥 导出", excel, "ESS_LCOS.xlsx")

# ==========================================
# 6. Main
# ==========================================
def main():
    st.sidebar.title("📌 投资测算工具")
    mode = st.sidebar.radio("模块", ("光伏+储能 LCOE", "燃气发电 LCOE", "储能 LCOS"))
    st.sidebar.info("v8.0 | Fully Unlocked & Audited")
    
    if mode == "光伏+储能 LCOE": render_pv_ess_lcoe()
    elif mode == "燃气发电 LCOE": render_gas_lcoe()
    elif mode == "储能 LCOS": render_lcos()

if __name__ == "__main__":
    main()
