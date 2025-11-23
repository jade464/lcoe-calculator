import streamlit as st
import pandas as pd
import numpy as np
import io
import xlsxwriter

# --- 1. 全局配置与样式 ---
st.set_page_config(page_title="新能源项目投资测算模型 (Pro)", layout="wide", page_icon="📊")

# 专业级 CSS 样式注入
st.markdown("""
<style>
    /* 全局字体与背景 */
    .main {background-color: #FAFAFA;}
    h1 {color: #0F2948; font-family: 'Helvetica Neue', sans-serif;}
    h2 {color: #1F4E79; border-bottom: 2px solid #1F4E79; padding-bottom: 10px; font-size: 24px;}
    h3 {color: #2F5597; font-size: 18px; margin-top: 20px;}
    
    /* 输入框区域卡片化 */
    .block-container {padding-top: 2rem;}
    section[data-testid="stSidebar"] {background-color: #F0F2F6;}
    
    /* 指标卡片样式 */
    div[data-testid="stMetric"] {
        background-color: #FFFFFF;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #E6E6E6;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    label[data-testid="stMetricLabel"] {color: #666; font-size: 14px;}
    div[data-testid="stMetricValue"] {color: #0F2948; font-weight: 700;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 核心引擎：Excel 生成器 (保持不变)
# ==========================================
def generate_professional_excel(model_name, inputs, time_series_data, summary_metrics):
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet('Financial Model')
    
    # 样式
    fmt_title = workbook.add_format({'bold': True, 'font_size': 14, 'font_color': '#1F4E79'})
    fmt_header = workbook.add_format({'bold': True, 'bg_color': '#2F5597', 'font_color': 'white', 'align': 'center', 'border': 1})
    fmt_sub = workbook.add_format({'bold': True, 'bg_color': '#D9E1F2', 'border': 1})
    fmt_num = workbook.add_format({'border': 1, 'num_format': '#,##0.00'})
    fmt_money = workbook.add_format({'border': 1, 'num_format': '¥ #,##0'})
    
    # 写入输入假设
    worksheet.write('A1', f"{model_name} - 关键假设 (Key Assumptions)", fmt_title)
    row = 2
    for k, v in inputs.items():
        worksheet.write(row, 0, k, fmt_sub)
        worksheet.write(row, 1, v, fmt_num)
        row += 1
        
    # 写入时间轴数据
    row += 2
    worksheet.write(row, 0, "现金流模型 (Cash Flow Waterfall)", fmt_title)
    row += 1
    
    # 表头
    headers = ["Project Year"] + [f"Year {y}" for y in time_series_data["Year"]]
    worksheet.write_row(row, 0, headers, fmt_header)
    row += 1
    
    # 数据行映射
    map_rows = [
        ("发电量 (MWh)", "Generation", fmt_num),
        ("折现系数", "Discount Factor", fmt_num),
        ("折现电量", "Discounted Gen", fmt_num),
        ("累计折现电量", "Cum Discounted Gen", fmt_num),
        ("", "", None),
        ("初始投资 (Capex)", "Capex", fmt_money),
        ("运营支出 (Opex)", "Opex", fmt_money),
        ("燃料/充电", "Fuel/Charge", fmt_money),
        ("资产置换", "Replacement", fmt_money),
        ("残值回收", "Salvage", fmt_money),
        ("净现金流", "Net Cash Flow", fmt_money),
        ("折现成本", "PV of Cost", fmt_money),
        ("累计折现成本", "Cum PV of Cost", fmt_money),
    ]
    
    for label, key, fmt in map_rows:
        worksheet.write(row, 0, label, fmt_sub if key=="" else workbook.add_format({'border':1}))
        if key:
            worksheet.write_row(row, 1, time_series_data[key], fmt)
        row += 1
        
    workbook.close()
    return output.getvalue()

# ==========================================
# 3. 模块 A: 光伏 + 储能 LCOE (重构版)
# ==========================================
def render_pv_ess_lcoe():
    st.markdown("## ⚡️ 新能源+储能平准化度电成本 (LCOE) 测算")
    
    # --- Input Section ---
    with st.container():
        # Block 1: 规模与参数
        st.markdown("### 1. 基础规模与物理参数 (Project Scale)")
        c1, c2, c3, c4, c5 = st.columns(5)
        pv_cap = c1.number_input("光伏/风电装机容量 (MW)", value=200.0, min_value=0.0)
        pv_hours = c2.number_input("光伏/风电年利用小时数 (h)", value=2200.0, min_value=0.0)
        ess_cap = c3.number_input("储能容量 (MWh)", value=120.0, min_value=0.0)
        ess_cycles = c4.number_input("储能年循环次数 (次)", value=1000.0, min_value=0.0)
        ess_eff = c5.number_input("储能系统综合效率 (%)", value=85.0, min_value=0.0, max_value=100.0) / 100

        st.markdown("---")

        # Block 2: 初始投资
        st.markdown("### 2. 初始投资概算 (Capex)")
        st.caption("单位：万元 (CNY/AUD Wan)")
        c1, c2, c3 = st.columns(3)
        capex_pv = c1.number_input("光伏/风电系统总投资", value=50000.0, step=100.0)
        capex_ess = c2.number_input("储能系统总投资", value=10000.0, step=100.0)
        capex_grid = c3.number_input("电网配套/升压站投资", value=15000.0, step=100.0)

        st.markdown("---")

        # Block 3: 运维支出
        st.markdown("### 3. 运营维护支出 (Opex)")
        c1, c2, c3 = st.columns(3)
        opex_rate_pv = c1.number_input("光伏/风电年运维费率 (%)", value=1.5, step=0.1) / 100
        opex_rate_ess = c2.number_input("储能年运维费率 (%)", value=3.0, step=0.1) / 100
        opex_rate_grid = c3.number_input("配套设施年运维费率 (%)", value=1.0, step=0.1) / 100

        st.markdown("---")

        # Block 4: 资产管理与财务
        st.markdown("### 4. 资产全生命周期管理 (LCM) 与财务假设")
        
        col_lcm, col_fin = st.columns([3, 2])
        
        with col_lcm:
            st.markdown("**🔧 关键设备置换与残值**")
            l1, l2 = st.columns(2)
            rep_year = l1.number_input("储能电池更换年份 (第N年)", value=10, min_value=1)
            rep_cost = l2.number_input("更换一次性资本开支 (万元)", value=5000.0, help="通常为初始电池部分BOM成本")
            
            l3, l4, l5 = st.columns(3)
            salvage_rate_pv = l3.number_input("光伏/风电组件残值率 (%)", value=5.0) / 100
            salvage_rate_ess = l4.number_input("储能设备残值率 (%)", value=0.0, help="化学电池通常残值为0") / 100
            salvage_rate_grid = l5.number_input("电网/土地残值率 (%)", value=10.0) / 100
            
        with col_fin:
            st.markdown("**💰 核心财务指标**")
            wacc = st.number_input("折现率 WACC (%)", value=8.0, step=0.1) / 100
            period = int(st.number_input("项目运营周期 (年)", value=25))

    # --- Calculation Engine ---
    years = [0] + list(range(1, period + 1))
    ts_data = {k: [] for k in ["Year", "Generation", "Discount Factor", "Discounted Gen", "Cum Discounted Gen", 
                               "Capex", "Opex", "Fuel/Charge", "Replacement", "Salvage", 
                               "Net Cash Flow", "PV of Cost", "Cum PV of Cost"]}
    
    # Initial Setup
    total_inv = capex_pv + capex_ess + capex_grid
    salvage_val = (capex_pv * salvage_rate_pv) + (capex_ess * salvage_rate_ess) + (capex_grid * salvage_rate_grid)
    
    # Year 0
    for k in ts_data: ts_data[k].append(0)
    ts_data["Year"][0] = 0
    ts_data["Discount Factor"][0] = 1.0
    ts_data["Capex"][0] = total_inv
    ts_data["Net Cash Flow"][0] = total_inv
    ts_data["PV of Cost"][0] = total_inv
    ts_data["Cum PV of Cost"][0] = total_inv
    
    cum_gen_npv = 0
    cum_cost_npv = total_inv
    
    for y in range(1, period + 1):
        ts_data["Year"].append(y)
        
        # Gen
        degrade = 1 - (y-1)*0.005
        gen = (pv_cap * pv_hours * degrade) + (ess_cap * ess_cycles * ess_eff)
        ts_data["Generation"].append(gen)
        
        # Discount
        df = 1 / ((1 + wacc) ** y)
        ts_data["Discount Factor"].append(df)
        g_npv = gen * df
        ts_data["Discounted Gen"].append(g_npv)
        cum_gen_npv += g_npv
        ts_data["Cum Discounted Gen"].append(cum_gen_npv)
        
        # Costs
        ts_data["Capex"].append(0)
        opex = (capex_pv*opex_rate_pv) + (capex_ess*opex_rate_ess) + (capex_grid*opex_rate_grid)
        ts_data["Opex"].append(opex)
        ts_data["Fuel/Charge"].append(0)
        
        rep = rep_cost if y == rep_year else 0
        ts_data["Replacement"].append(rep)
        
        sal = -salvage_val if y == period else 0
        ts_data["Salvage"].append(sal)
        
        net = opex + rep + sal
        ts_data["Net Cash Flow"].append(net)
        
        c_npv = net * df
        ts_data["PV of Cost"].append(c_npv)
        cum_cost_npv += c_npv
        ts_data["Cum PV of Cost"].append(cum_cost_npv)
        
    lcoe = (cum_cost_npv / cum_gen_npv) * 10 if cum_gen_npv > 0 else 0

    # --- Result Display ---
    st.markdown("---")
    st.markdown("### 📊 测算结果 (Results)")
    
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("LCOE (元/kWh)", f"{lcoe:.4f}", delta="核心指标")
    kpi2.metric("全生命周期成本现值 (NPC)", f"{cum_cost_npv:,.0f} 万")
    kpi3.metric("全生命周期电量现值", f"{cum_gen_npv/10000:,.2f} 亿kWh")
    kpi4.metric("期末残值回收", f"{salvage_val:,.0f} 万")

    with st.expander("📂 查看详细计算底稿与导出 (Data Deck)", expanded=True):
        df_show = pd.DataFrame(ts_data).set_index("Year").T
        st.dataframe(df_show, use_container_width=True)
        
        excel = generate_professional_excel("PV_ESS_LCOE", 
                                            {"WACC": wacc, "PV MW": pv_cap, "Capex": total_inv},
                                            ts_data, 
                                            {"LCOE": lcoe})
        st.download_button("📥 导出标准 Excel 底稿", excel, "PV_ESS_LCOE.xlsx")

# ==========================================
# 4. 模块 B: 燃气 LCOE (重构版)
# ==========================================
def render_gas_lcoe():
    st.markdown("## 🔥 燃气发电平准化度电成本 (LCOE) 测算")
    
    with st.container():
        st.markdown("### 1. 基础规模与物理参数")
        c1, c2, c3 = st.columns(3)
        gas_cap = c1.number_input("燃机装机容量 (MW)", value=360.0)
        gas_hours = c2.number_input("年运行小时数 (h)", value=3000.0)
        heat_rate = c3.number_input("平均热耗率 (GJ/kWh)", value=0.0095, format="%.4f", help="越低越好，CCGT通常在0.007左右")

        st.markdown("---")
        st.markdown("### 2. 初始投资 (Capex)")
        st.caption("单位：万元")
        c1, c2 = st.columns(2)
        gas_capex = c1.number_input("项目总投资", value=60000.0)
        
        st.markdown("---")
        st.markdown("### 3. 运维与燃料 (Opex)")
        c1, c2 = st.columns(2)
        fixed_opex = c1.number_input("固定运维成本 (万元/年)", value=1200.0)
        gas_price = c2.number_input("天然气价格 (元/GJ)", value=60.0, help="注意单位是GJ")

        st.markdown("---")
        st.markdown("### 4. 资产管理与财务")
        c1, c2, c3 = st.columns(3)
        wacc = c1.number_input("折现率 WACC (%)", value=8.0) / 100
        period = int(c2.number_input("运营周期 (年)", value=25))
        salvage_rate = c3.number_input("期末资产残值率 (%)", value=5.0) / 100

    # Calc
    years = [0] + list(range(1, period + 1))
    ts_data = {k: [] for k in ["Year", "Generation", "Discount Factor", "Discounted Gen", "Cum Discounted Gen", 
                               "Capex", "Opex", "Fuel/Charge", "Replacement", "Salvage", 
                               "Net Cash Flow", "PV of Cost", "Cum PV of Cost"]}
    
    # Year 0
    for k in ts_data: ts_data[k].append(0)
    ts_data["Year"][0] = 0
    ts_data["Discount Factor"][0] = 1.0
    ts_data["Capex"][0] = gas_capex
    ts_data["Net Cash Flow"][0] = gas_capex
    ts_data["PV of Cost"][0] = gas_capex
    ts_data["Cum PV of Cost"][0] = gas_capex
    
    annual_gen = gas_cap * gas_hours
    fuel_cost = (annual_gen * 1000 * heat_rate * gas_price) / 10000
    salvage_val = gas_capex * salvage_rate
    
    cum_gen = 0
    cum_cost = gas_capex
    
    for y in range(1, period + 1):
        ts_data["Year"].append(y)
        ts_data["Generation"].append(annual_gen)
        
        df = 1 / ((1 + wacc) ** y)
        ts_data["Discount Factor"].append(df)
        g_npv = annual_gen * df
        ts_data["Discounted Gen"].append(g_npv)
        cum_gen += g_npv
        ts_data["Cum Discounted Gen"].append(cum_gen)
        
        ts_data["Capex"].append(0)
        ts_data["Opex"].append(fixed_opex)
        ts_data["Fuel/Charge"].append(fuel_cost)
        ts_data["Replacement"].append(0)
        
        sal = -salvage_val if y == period else 0
        ts_data["Salvage"].append(sal)
        
        net = fixed_opex + fuel_cost + sal
        ts_data["Net Cash Flow"].append(net)
        
        c_npv = net * df
        ts_data["PV of Cost"].append(c_npv)
        cum_cost += c_npv
        ts_data["Cum PV of Cost"].append(cum_cost)
        
    lcoe = (cum_cost / cum_gen) * 10 if cum_gen > 0 else 0
    
    st.markdown("---")
    st.markdown("### 📊 测算结果")
    k1, k2, k3 = st.columns(3)
    k1.metric("LCOE (元/kWh)", f"{lcoe:.4f}")
    k2.metric("燃料成本占比", f"{fuel_cost/(fixed_opex+fuel_cost):.1%}")
    k3.metric("年燃料支出", f"{fuel_cost:,.0f} 万")
    
    with st.expander("📂 底稿与导出"):
        df_show = pd.DataFrame(ts_data).set_index("Year").T
        st.dataframe(df_show, use_container_width=True)
        excel = generate_professional_excel("Gas_LCOE", {"Gas Price": gas_price}, ts_data, {"LCOE": lcoe})
        st.download_button("📥 导出 Excel", excel, "Gas_LCOE.xlsx")

# ==========================================
# 5. 模块 C: 储能 LCOS (重构版)
# ==========================================
def render_lcos():
    st.markdown("## 🔋 储能全生命周期成本 (LCOS) 测算")
    
    with st.container():
        st.markdown("### 1. 基础规模与物理参数")
        c1, c2, c3, c4, c5 = st.columns(5)
        ess_power = c1.number_input("额定功率 (MW)", value=100.0)
        ess_cap = c2.number_input("额定容量 (MWh)", value=200.0)
        cycles = c3.number_input("年循环次数 (次)", value=330.0)
        rte = c4.number_input("往返效率 RTE (%)", value=85.0) / 100
        deg = c5.number_input("年衰减率 (%)", value=2.0) / 100
        
        st.markdown("---")
        st.markdown("### 2. 初始投资 (Capex)")
        st.caption("单位：万元")
        c1, c2 = st.columns(2)
        capex = c1.number_input("储能电站总投资", value=25000.0)
        
        st.markdown("---")
        st.markdown("### 3. 运维与充电成本 (Opex)")
        c1, c2 = st.columns(2)
        opex_rate = c1.number_input("年运维费率 (%)", value=2.0) / 100
        charge_price = c2.number_input("充电电价 (元/kWh)", value=0.20, help="非常关键的变量，影响LCOS的充电成本部分")
        
        st.markdown("---")
        st.markdown("### 4. 资产管理与财务")
        col_lcm, col_fin = st.columns([3, 2])
        with col_lcm:
            st.markdown("**🔧 设备置换**")
            r1, r2, r3 = st.columns(3)
            rep_yr = r1.number_input("电池更换年份", value=8)
            rep_cost = r2.number_input("更换资本开支 (万)", value=10000.0)
            sal_rate = r3.number_input("期末残值率 (%)", value=3.0) / 100
        with col_fin:
            st.markdown("**💰 财务**")
            wacc = st.number_input("WACC (%)", value=8.0) / 100
            period = int(st.number_input("寿命 (年)", value=15))

    # Calc
    years = [0] + list(range(1, period + 1))
    ts_data = {k: [] for k in ["Year", "Generation", "Discount Factor", "Discounted Gen", "Cum Discounted Gen", 
                               "Capex", "Opex", "Fuel/Charge", "Replacement", "Salvage", 
                               "Net Cash Flow", "PV of Cost", "Cum PV of Cost"]}
    
    for k in ts_data: ts_data[k].append(0)
    ts_data["Year"][0] = 0
    ts_data["Discount Factor"][0] = 1.0
    ts_data["Capex"][0] = capex
    ts_data["Net Cash Flow"][0] = capex
    ts_data["PV of Cost"][0] = capex
    ts_data["Cum PV of Cost"][0] = capex
    
    sal_val = capex * sal_rate
    cum_gen = 0
    cum_cost = capex
    
    for y in range(1, period + 1):
        ts_data["Year"].append(y)
        
        curr_cap = ess_cap * ((1 - deg) ** (y-1))
        dis = curr_cap * cycles * rte
        ts_data["Generation"].append(dis)
        
        df = 1 / ((1 + wacc) ** y)
        ts_data["Discount Factor"].append(df)
        g_npv = dis * df
        ts_data["Discounted Gen"].append(g_npv)
        cum_gen += g_npv
        ts_data["Cum Discounted Gen"].append(cum_gen)
        
        ts_data["Capex"].append(0)
        opex = capex * opex_rate
        ts_data["Opex"].append(opex)
        
        charge = (curr_cap * cycles * 1000 * charge_price) / 10000
        ts_data["Fuel/Charge"].append(charge)
        
        rep = rep_cost if y == rep_yr else 0
        ts_data["Replacement"].append(rep)
        
        sal = -sal_val if y == period else 0
        ts_data["Salvage"].append(sal)
        
        net = opex + charge + rep + sal
        ts_data["Net Cash Flow"].append(net)
        
        c_npv = net * df
        ts_data["PV of Cost"].append(c_npv)
        cum_cost += c_npv
        ts_data["Cum PV of Cost"].append(cum_cost)
        
    lcos = (cum_cost / cum_gen) * 10 if cum_gen > 0 else 0
    
    st.markdown("---")
    st.markdown("### 📊 测算结果")
    k1, k2 = st.columns(2)
    k1.metric("LCOS (元/kWh)", f"{lcos:.4f}")
    k2.metric("总放电量现值", f"{cum_gen/10000:.2f} 亿kWh")
    
    with st.expander("📂 底稿与导出"):
        df_show = pd.DataFrame(ts_data).set_index("Year").T
        st.dataframe(df_show, use_container_width=True)
        excel = generate_professional_excel("ESS_LCOS", {"Charge Price": charge_price}, ts_data, {"LCOS": lcos})
        st.download_button("📥 导出 Excel", excel, "ESS_LCOS.xlsx")

# ==========================================
# 6. 主导航
# ==========================================
def main():
    st.sidebar.title("📌 投资测算工具箱")
    mode = st.sidebar.radio("选择模型模块", ("光伏+储能 LCOE", "燃气发电 LCOE", "储能 LCOS"))
    st.sidebar.markdown("---")
    st.sidebar.info("v4.0 Pro | Investment Grade")
    
    if mode == "光伏+储能 LCOE": render_pv_ess_lcoe()
    elif mode == "燃气发电 LCOE": render_gas_lcoe()
    elif mode == "储能 LCOS": render_lcos()

if __name__ == "__main__":
    main()

