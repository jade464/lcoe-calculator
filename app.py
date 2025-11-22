import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# --- 全局页面配置 ---
st.set_page_config(page_title="综合能源投资测算平台", layout="wide", page_icon="⚡")

# --- CSS样式微调 ---
st.markdown("""
<style>
    .metric-card {background-color: #f0f2f6; padding: 15px; border-radius: 10px; border-left: 5px solid #ff4b4b;}
    div[data-testid="stMetricValue"] {font-size: 24px;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 工具函数：通用 LCOE/LCOS 计算内核
# ==========================================
def calculate_dcf(period, wacc, initial_invest, annual_opex_func, annual_gen_func, special_costs=None, salvage_val=0):
    years = np.arange(1, period + 1)
    cash_flows = []
    total_npv_cost = initial_invest
    total_npv_output = 0
    
    for y in years:
        # 1. 当年名义支出
        cf_out = annual_opex_func(y)
        if special_costs and y in special_costs:
            cf_out += special_costs[y]
        if y == period:
            cf_out -= salvage_val
        cash_flows.append(cf_out)
        
        # 2. 当年物理产出
        output = annual_gen_func(y)
        
        # 3. 折现
        discount_factor = 1 / ((1 + wacc) ** y)
        total_npv_cost += cf_out * discount_factor
        total_npv_output += output * discount_factor
        
    return total_npv_cost, total_npv_output, cash_flows

# ==========================================
# 模块 1: 光伏 + 储能 LCOE
# ==========================================
def render_pv_ess_lcoe():
    st.header("⚡️ 新能源+储能 LCOE 测算")
    st.info("适用于：集中式光伏电站、光储一体化项目的度电成本测算")
    
    col_in1, col_in2 = st.columns([1, 2])
    
    with col_in1:
        st.subheader("1. 财务与规模")
        wacc = st.number_input("折现率 WACC (%)", min_value=0.0, value=8.0, step=0.1, key="pv_wacc") / 100
        period = int(st.number_input("运营周期 (年)", min_value=1, value=25, key="pv_period"))
        
        st.subheader("2. 初始投资 (万元)")
        capex_pv = st.number_input("光伏系统投资", min_value=0.0, value=50000.0)
        capex_ess = st.number_input("储能系统投资", min_value=0.0, value=10000.0)
        capex_grid = st.number_input("电网/升压站投资", min_value=0.0, value=15000.0)
        
        st.subheader("3. 运维参数")
        opex_rate_pv = st.number_input("光伏年运维费率 (%)", min_value=0.0, value=1.5) / 100
        opex_rate_ess = st.number_input("储能年运维费率 (%)", min_value=0.0, value=3.0) / 100
        opex_rate_grid = st.number_input("配套年运维费率 (%)", min_value=0.0, value=1.0) / 100
        
    with col_in2:
        st.subheader("4. 发电与性能")
        c1, c2 = st.columns(2)
        with c1:
            pv_cap = st.number_input("光伏容量 (MW)", min_value=0.0, value=200.0)
            pv_hours = st.number_input("光伏利用小时数 (h)", min_value=0.0, value=2200.0)
        with c2:
            ess_cap = st.number_input("储能容量 (MWh)", min_value=0.0, value=120.0)
            ess_cycles = st.number_input("储能年循环次数", min_value=0.0, value=1000.0)
            ess_eff = st.slider("储能综合效率 (%)", 70, 100, 85, key="pv_eff") / 100
            
        st.subheader("5. 资产置换")
        rep_year = st.slider("电池更换年份", 1, period, 10, key="pv_rep_year")
        rep_cost = st.number_input("更换成本 (万元)", min_value=0.0, value=5000.0)
        salvage_rate = st.number_input("期末综合残值率 (%)", min_value=0.0, value=5.0) / 100

    # --- Logic ---
    total_inv = capex_pv + capex_ess + capex_grid
    
    def get_opex(y):
        return (capex_pv*opex_rate_pv) + (capex_ess*opex_rate_ess) + (capex_grid*opex_rate_grid)
    
    def get_gen(y):
        degrade = 1 - (y-1)*0.005 
        return (pv_cap * pv_hours * degrade) + (ess_cap * ess_cycles * ess_eff)
    
    special_costs = {rep_year: rep_cost}
    salvage = (capex_pv + capex_grid) * salvage_rate 
    
    npv_cost, npv_gen, cf_flows = calculate_dcf(period, wacc, total_inv, get_opex, get_gen, special_costs, salvage)
    lcoe = (npv_cost / npv_gen) * 10 if npv_gen > 0 else 0
    
    # --- Output ---
    st.markdown("---")
    res_col1, res_col2, res_col3, res_col4 = st.columns(4)
    res_col1.metric("LCOE (元/kWh)", f"{lcoe:.4f}")
    res_col2.metric("LCOE (分/kWh)", f"{lcoe*100:.2f} ¢")
    res_col3.metric("NPC (万元)", f"{npv_cost:,.0f}")
    res_col4.metric("全生命周期电量 (亿kWh)", f"{npv_gen/10000:.2f}")

    fig = go.Figure()
    fig.add_trace(go.Bar(x=list(range(1, period+1)), y=cf_flows, name="年度净支出", marker_color='#3498DB'))
    fig.add_trace(go.Bar(x=[0], y=[total_inv], name="初始投资", marker_color='#E74C3C'))
    fig.update_layout(title="项目现金流出结构", height=400, yaxis_title="万元")
    st.plotly_chart(fig, use_container_width=True)

# ==========================================
# 模块 2: 燃气发电 LCOE (已升级为 GJ 单位)
# ==========================================
def render_gas_lcoe():
    st.header("🔥 燃气发电 LCOE 测算")
    st.info("适用于：燃气轮机(GT)、联合循环(CCGT)。已采用 GJ 热值计价标准。")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("1. 投资与运维")
        wacc = st.number_input("折现率 WACC (%)", min_value=0.0, value=8.0, key="gas_wacc") / 100
        period = int(st.number_input("运营周期 (年)", min_value=1, value=25, key="gas_period"))
        gas_capex = st.number_input("项目总投资 (万元)", min_value=0.0, value=60000.0)
        gas_fixed_opex = st.number_input("固定运维费 (万元/年)", min_value=0.0, value=1200.0, help="含人员、保险、长协服务费")
        
    with col2:
        st.subheader("2. 燃料与效率 (GJ标准)")
        gas_cap = st.number_input("装机容量 (MW)", min_value=0.0, value=360.0)
        gas_hours = st.number_input("年运行小时数 (h)", min_value=0.0, value=3000.0)
        
        st.markdown("##### ⛽ 燃料成本核心参数")
        # 澳洲市场 GJ 价格通常在
