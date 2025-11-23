import streamlit as st
import pandas as pd
import numpy as np
import io
import xlsxwriter

# --- 1. 全局配置与样式 ---
st.set_page_config(page_title="新能源项目 LCOE 测算模型 (税后成本版)", layout="wide", page_icon="📉")

st.markdown("""
<style>
    .main {background-color: #FAFAFA;}
    h1 {color: #0F2948; font-family: 'Helvetica Neue', sans-serif;}
    h2 {color: #1F4E79; border-bottom: 2px solid #1F4E79; padding-bottom: 10px; font-size: 24px;}
    .block-container {padding-top: 2rem;}
    section[data-testid="stSidebar"] {background-color: #F0F2F6;}
    div[data-testid="stMetric"] {
        background-color: #FFFFFF; padding: 15px; border-radius: 8px; 
        border: 1px solid #E6E6E6; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 核心引擎：Excel 生成器
# ==========================================
def generate_professional_excel(model_name, inputs, time_series_data, summary_metrics):
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet('Financial Model')
    
    fmt_title = workbook.add_format({'bold': True, 'font_size': 14, 'font_color': '#1F4E79'})
    fmt_header = workbook.add_format({'bold': True, 'bg_color': '#2F5597', 'font_color': 'white', 'align': 'center', 'border': 1})
    fmt_sub = workbook.add_format({'bold': True, 'bg_color': '#D9E1F2', 'border': 1})
    fmt_num = workbook.add_format({'border': 1, 'num_format': '#,##0.00'})
    fmt_money = workbook.add_format({'border': 1, 'num_format': '¥ #,##0'})
    
    worksheet.write('A1', f"{model_name} - 关键假设", fmt_title)
    row = 2
    for k, v in inputs.items():
        worksheet.write(row, 0, k, fmt_sub)
        worksheet.write(row, 1, v, fmt_num)
        row += 1
        
    row += 2
    worksheet.write(row, 0, "现金流模型 (Cash Flow Waterfall)", fmt_title)
    row += 1
    
    headers = ["Project Year"] + [f"Year {y}" for y in time_series_data["Year"]]
    worksheet.write_row(row, 0, headers, fmt_header)
    row += 1
    
    map_rows = [
        ("发电量 (MWh)", "Generation", fmt_num),
        ("折现系数", "Discount Factor", fmt_num),
        ("折现发电量", "Discounted Gen", fmt_num),
        ("", "", None),
        ("1. 初始投资 (Capex)", "Capex", fmt_money),
        ("2. 运营支出 (Opex - 税后)", "Opex After-tax", fmt_money),
        ("3. 燃料/充电 (税后)", "Fuel/Charge After-tax", fmt_money),
        ("4. 资产置换 (Capex)", "Replacement", fmt_money),
        ("5. 残值回收 (税后)", "Salvage After-tax", fmt_money),
        ("6. 折旧税盾 (抵扣)", "Tax Shield", fmt_money),
        ("", "", None),
        ("=== 税后净成本流 ===", "Net Cost Flow (After-tax)", fmt_money),
        ("折现成本", "PV of Cost", fmt_money),
        ("累计折现成本", "Cum PV of Cost", fmt_money),
        ("", "", None),
        ("参考: 名义折旧额", "Depreciation", fmt_money),
    ]
    
    for label, key, fmt in map_rows:
        worksheet.write(row, 0, label, fmt_sub if key=="" or "===" in label else workbook.add_format({'border':1}))
        if key and key in time_series_data:
            worksheet.write_row(row, 1, time_series_data[key], fmt)
        row += 1
        
    workbook.close()
    return output.getvalue()

# ==========================================
# 3. 模块 A: 光伏 + 储能 LCOE (税后成本版)
# ==========================================
def render_pv_ess_lcoe():
    st.markdown("## ☀️ 光伏+储能 LCOE (税后成本法)")
    st.info("计算逻辑：分子采用扣除税盾后的净现金流，分母为物理发电量。反映企业持有的真实成本。")
    
    with st.container():
        st.markdown("### 1. 基础规模")
        c1, c2, c3, c4 = st.columns(4)
        pv_cap = c1.number_input("光伏容量 (MW)", value=200.0)
        pv_hours = c2.number_input("年利用小时数 (h)", value=2200.0)
        ess_cap = c3.number_input("储能容量 (MWh)", value=120.0)
        ess_cycles = c4.number_input("年循环次数", value=1000.0)
        ess_eff = 0.85

        st.markdown("---")
        st.markdown("### 2. 投资与运维 (无输入限制)")
        c1, c2, c3 = st.columns(3)
        capex_pv = c1.number_input("光伏总投资 (万)", value=50000.0, step=100.0)
        capex_ess = c2.number_input("储能总投资 (万)", value=10000.0, step=100.0)
        capex_grid = c3.number_input("电网配套投资 (万)", value=15000.0, step=100.0)
        
        st.caption("运维费率(%)")
        o1, o2, o3 = st.columns(3)
        opex_r_pv = o1.number_input("光伏Opex%", value=1.5, step=0.1)/100
        opex_r_ess = o2.number_input("储能Opex%", value=3.0, step=0.1)/100
        opex_r_grid = o3.number_input("配套Opex%", value=1.0, step=0.1)/100

        st.markdown("---")
        st.markdown("### 3. 税务与财务 (核心)")
        col_tax, col_fin = st.columns(2)
        with col_tax:
            tax_rate = st.number_input("企业所得税率 (%)", value=25.0) / 100
            depr_years = st.number_input("折旧年限 (年)", value=20)
        with col_fin:
            wacc = st.number_input("WACC (%)", value=8.0) / 100
            period = int(st.number_input("周期 (年)", value=25))

        st.markdown("---")
        st.markdown("### 4. 资产管理")
        l1, l2, l3 = st.columns(3)
        rep_year = l1.number_input("电池更换年份", value=10)
        rep_cost = l2.number_input("更换开支 (万)", value=5000.0)
        salvage_rate = l3.number_input("期末残值率 (%)", value=5.0) / 100

    # --- Calculation Engine ---
    years = [0] + list(range(1, period + 1))
    ts = {k: [] for k in ["Year", "Generation", "Discount Factor", 
                          "Capex", "Opex After-tax", "Fuel/Charge After-tax", "Replacement", "Salvage After-tax",
                          "Depreciation", "Tax Shield",
                          "Net Cost Flow (After-tax)", "PV of Cost", "Cum PV of Cost", 
                          "Discounted Gen", "Cum Discounted Gen"]}
    
    total_inv = capex_pv + capex_ess + capex_grid
    salvage_val_pretax = total_inv * salvage_rate
    annual_depr = total_inv / depr_years if depr_years > 0 else 0
    
    # Year 0
    for k in ts: ts[k].append(0)
    ts["Year"][0] = 0
    ts["Discount Factor"][0] = 1.0
    ts["Capex"][0] = total_inv
    ts["Net Cost Flow (After-tax)"][0] = total_inv
    ts["PV of Cost"][0] = total_inv
    ts["Cum PV of Cost"][0] = total_inv
    
    cum_gen = 0
    cum_cost = total_inv
    
    for y in range(1, period + 1):
        ts["Year"].append(y)
        
        # 1. 发电 (分母不调税，因为算的是成本)
        degrade = 1 - (y-1)*0.005
        gen = (pv_cap * pv_hours * degrade) + (ess_cap * ess_cycles * ess_eff)
        ts["Generation"].append(gen)
        
        df = 1 / ((1 + wacc) ** y)
        ts["Discount Factor"].append(df)
        
        g_npv = gen * df
        ts["Discounted Gen"].append(g_npv)
        cum_gen += g_npv
        ts["Cum Discounted Gen"].append(cum_gen)
        
        # 2. 成本 (分子调税)
        ts["Capex"].append(0)
        
        # Opex: 实际支出 = Opex * (1 - Tax)
        opex_pre = (capex_pv*opex_r_pv) + (capex_ess*opex_r_ess) + (capex_grid*opex_r_grid)
        opex_after = opex_pre * (1 - tax_rate)
        ts["Opex After-tax"].append(opex_after)
        ts["Fuel/Charge After-tax"].append(0)
        
        # 折旧税盾: 减少现金流出
        curr_depr = annual_depr if y <= depr_years else 0
        ts["Depreciation"].append(curr_depr)
        
        tax_shield = curr_depr * tax_rate
        ts["Tax Shield"].append(-tax_shield) # 负值表示减少成本
        
        # 置换 (假设为资本性支出，暂不立即抵税，或按实际情况。此处简化为现金流出)
        rep = rep_cost if y == rep_year else 0
        ts["Replacement"].append(rep)
        
        # 残值 (税后流入): Inflow = Val * (1-T) -> Cost = -Val*(1-T)
        sal = 0
        if y == period:
            sal = -(salvage_val_pretax * (1 - tax_rate))
        ts["Salvage After-tax"].append(sal)
        
        # 净成本流 = Opex(税后) + 置换 + 充电(税后) - 税盾 + 残值(负成本)
        net_cost = opex_after + rep - tax_shield + sal
        ts["Net Cost Flow (After-tax)"].append(net_cost)
        
        c_npv = net_cost * df
        ts["PV of Cost"].append(c_npv)
        cum_cost += c_npv
        ts["Cum PV of Cost"].append(cum_cost)
        
    lcoe = (cum_cost / cum_gen) * 10 if cum_gen > 0 else 0
    
    st.markdown("---")
    st.markdown("### 📊 测算结果 (税后真实成本)")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("税后 LCOE (After-tax Cost)", f"{lcoe:.4f} 元/kWh", delta="- 税盾降低了成本")
    c2.metric("累计税盾收益 (NPV)", f"{abs(sum(ts['Tax Shield'])):,.0f} 万")
    c3.metric("折旧年限", f"{depr_years} 年")

    with st.expander("📂 查看税务底稿"):
        st.dataframe(pd.DataFrame(ts).set_index("Year").T, use_container_width=True)
        excel = generate_professional_excel("PV_ESS_LCOE_AfterTax", {"Tax Rate": tax_rate}, ts, {"LCOE": lcoe})
        st.download_button("📥 导出含税底稿", excel, "PV_ESS_AfterTax_LCOE.xlsx")

# ==========================================
# 4. 模块 B: 燃气 LCOE (税后成本版)
# ==========================================
def render_gas_lcoe():
    st.markdown("## 🔥 燃气发电 LCOE (税后成本法)")
    
    with st.container():
        st.markdown("### 1. 规模与投资")
        c1, c2, c3 = st.columns(3)
        gas_cap = c1.number_input("装机 (MW)", value=360.0)
        gas_capex = c2.number_input("投资 (万)", value=60000.0, step=100.0)
        wacc = c3.number_input("WACC (%)", value=8.0)/100
        
        st.markdown("### 2. 运营与燃料")
        c1, c2, c3 = st.columns(3)
        hours = c1.number_input("小时数", value=3000.0)
        heat_rate = c2.number_input("热耗 (GJ/kWh)", value=0.0095, format="%.4f")
        price = c3.number_input("气价 (元/GJ)", value=60.0, step=1.0)
        fixed_opex = st.number_input("固定运维 (万/年)", value=1200.0)

        st.markdown("### 3. 税务")
        t1, t2 = st.columns(2)
        tax_rate = t1.number_input("所得税率 (%)", value=25.0)/100
        depr_years = t2.number_input("折旧年限", value=20)
        period = 25

    # Calc
    years = [0] + list(range(1, period + 1))
    ts = {k: [] for k in ["Year", "Generation", "Discount Factor", 
                          "Capex", "Opex After-tax", "Fuel/Charge After-tax", "Replacement", "Salvage After-tax",
                          "Depreciation", "Tax Shield",
                          "Net Cost Flow (After-tax)", "PV of Cost", "Cum PV of Cost", 
                          "Discounted Gen", "Cum Discounted Gen"]}
    
    for k in ts: ts[k].append(0)
    ts["Year"][0] = 0
    ts["Discount Factor"][0] = 1.0
    ts["Capex"][0] = gas_capex
    ts["Net Cost Flow (After-tax)"][0] = gas_capex
    ts["PV of Cost"][0] = gas_capex
    ts["Cum PV of Cost"][0] = gas_capex
    
    annual_gen = gas_cap * hours
    fuel_cost_pre = (annual_gen * 1000 * heat_rate * price) / 10000
    annual_depr = gas_capex / depr_years if depr_years > 0 else 0
    sal_val = gas_capex * 0.05
    
    cum_gen = 0
    cum_cost = gas_capex
    
    for y in range(1, period + 1):
        ts["Year"].append(y)
        ts["Generation"].append(annual_gen)
        
        df = 1 / ((1 + wacc) ** y)
        ts["Discount Factor"].append(df)
        
        g_npv = annual_gen * df
        ts["Discounted Gen"].append(g_npv)
        cum_gen += g_npv
        ts["Cum Discounted Gen"].append(cum_gen)
        
        ts["Capex"].append(0)
        
        opex_after = fixed_opex * (1 - tax_rate)
        ts["Opex After-tax"].append(opex_after)
        
        fuel_after = fuel_cost_pre * (1 - tax_rate)
        ts["Fuel/Charge After-tax"].append(fuel_after)
        
        curr_depr = annual_depr if y <= depr_years else 0
        ts["Depreciation"].append(curr_depr)
        
        tax_shield = curr_depr * tax_rate
        ts["Tax Shield"].append(-tax_shield)
        
        ts["Replacement"].append(0)
        
        sal = -(sal_val * (1 - tax_rate)) if y == period else 0
        ts["Salvage After-tax"].append(sal)
        
        net = opex_after + fuel_after - tax_shield + sal
        ts["Net Cost Flow (After-tax)"].append(net)
        
        c_npv = net * df
        ts["PV of Cost"].append(c_npv)
        cum_cost += c_npv
        ts["Cum PV of Cost"].append(cum_cost)
        
    lcoe = (cum_cost / cum_gen) * 10 if cum_gen > 0 else 0
    
    st.markdown("---")
    st.markdown("### 📊 测算结果")
    c1, c2 = st.columns(2)
    c1.metric("税后 LCOE", f"{lcoe:.4f}")
    c2.metric("燃料成本 (税后)", f"{(fuel_cost_pre*(1-tax_rate)*10 / (annual_gen if annual_gen>0 else 1)):.4f}")
    
    with st.expander("📂 导出"):
        excel = generate_professional_excel("Gas_LCOE_Tax", {"Tax": tax_rate}, ts, {"LCOE": lcoe})
        st.download_button("📥 导出", excel, "Gas_AfterTax_LCOE.xlsx")

# ==========================================
# 5. 模块 C: 储能 LCOS (税后成本版)
# ==========================================
def render_lcos():
    st.markdown("## 🔋 储能 LCOS (税后成本法)")
    
    with st.container():
        st.markdown("### 1. 规模与投资")
        c1, c2 = st.columns(2)
        ess_cap = c1.number_input("容量 (MWh)", value=200.0)
        capex = c2.number_input("总投资 (万)", value=25000.0, step=100.0)
        
        st.markdown("### 2. 运营与充电")
        c1, c2, c3 = st.columns(3)
        charge_p = c1.number_input("充电价 (元/kWh)", value=0.20, step=0.01)
        opex_r = c2.number_input("运维%", value=2.0, step=0.1)/100
        cycles = c3.number_input("年循环", value=330.0)
        
        st.markdown("### 3. 税务")
        t1, t2 = st.columns(2)
        tax_rate = t1.number_input("税率%", value=25.0)/100
        depr_years = t2.number_input("折旧年", value=15)
        
        wacc = 0.08
        period = 15
        rep_yr = 8
        rep_cost = 10000.0

    # Calc
    years = [0] + list(range(1, period + 1))
    ts = {k: [] for k in ["Year", "Generation", "Discount Factor", 
                          "Capex", "Opex After-tax", "Fuel/Charge After-tax", "Replacement", "Salvage After-tax",
                          "Depreciation", "Tax Shield",
                          "Net Cost Flow (After-tax)", "PV of Cost", "Cum PV of Cost", 
                          "Discounted Gen", "Cum Discounted Gen"]}
    
    for k in ts: ts[k].append(0)
    ts["Year"][0] = 0
    ts["Discount Factor"][0] = 1.0
    ts["Capex"][0] = capex
    ts["Net Cost Flow (After-tax)"][0] = capex
    ts["PV of Cost"][0] = capex
    ts["Cum PV of Cost"][0] = capex
    
    annual_depr = capex / depr_years if depr_years > 0 else 0
    cum_gen = 0
    cum_cost = capex
    
    for y in range(1, period + 1):
        ts["Year"].append(y)
        
        curr_cap = ess_cap * ((1-0.02)**(y-1))
        dis = curr_cap * cycles * 0.85
        ts["Generation"].append(dis)
        
        df = 1 / ((1+wacc)**y)
        ts["Discount Factor"].append(df)
        
        g_npv = dis * df
        ts["Discounted Gen"].append(g_npv)
        cum_gen += g_npv
        ts["Cum Discounted Gen"].append(cum_gen)
        
        ts["Capex"].append(0)
        
        opex_pre = capex * opex_r
        opex_after = opex_pre * (1 - tax_rate)
        ts["Opex After-tax"].append(opex_after)
        
        charge_pre = (curr_cap * cycles * 1000 * charge_p) / 10000
        charge_after = charge_pre * (1 - tax_rate)
        ts["Fuel/Charge After-tax"].append(charge_after)
        
        curr_depr = annual_depr if y <= depr_years else 0
        ts["Depreciation"].append(curr_depr)
        
        tax_shield = curr_depr * tax_rate
        ts["Tax Shield"].append(-tax_shield)
        
        rep = rep_cost if y == rep_yr else 0
        ts["Replacement"].append(rep)
        
        ts["Salvage After-tax"].append(0)
        
        net = opex_after + charge_after + rep - tax_shield
        ts["Net Cost Flow (After-tax)"].append(net)
        
        c_npv = net * df
        ts["PV of Cost"].append(c_npv)
        cum_cost += c_npv
        ts["Cum PV of Cost"].append(cum_cost)
        
    lcos = (cum_cost / cum_gen) * 10 if cum_gen > 0 else 0
    
    st.markdown("---")
    st.metric("LCOS (税后真实成本)", f"{lcos:.4f}")
    
    with st.expander("📂 导出"):
        excel = generate_professional_excel("ESS_LCOS_Tax", {"Tax": tax_rate}, ts, {"LCOS": lcos})
        st.download_button("📥 导出", excel, "ESS_AfterTax_LCOS.xlsx")

# ==========================================
# 6. 主程序
# ==========================================
def main():
    st.sidebar.title("📌 新能源投资测算")
    mode = st.sidebar.radio("模块", ("光伏+储能 LCOE", "燃气发电 LCOE", "储能 LCOS"))
    st.sidebar.info("v5.2 | After-Tax Cost")
    
    if mode == "光伏+储能 LCOE": render_pv_ess_lcoe()
    elif mode == "燃气发电 LCOE": render_gas_lcoe()
    elif mode == "储能 LCOS": render_lcos()

if __name__ == "__main__":
    main()
