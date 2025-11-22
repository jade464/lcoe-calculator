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
        
        # 加入特殊支出 (如电池更换)
        if special_costs and y in special_costs:
            cf_out += special_costs[y]
            
        # 扣除残值 (最后一年作为负成本)
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
            
        st.subheader("5. 资产置换与残值")
        rep_year = st.slider("电池更换年份", 1, period, 10, key="pv_rep_year")
        rep_cost = st.number_input("更换成本 (万元)", min_value=0.0, value=5000.0)
        # 原有逻辑保留
        salvage_rate = st.number_input("期末综合残值率 (%)", min_value=0.0, value=5.0, key="pv_salvage") / 100

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
# 模块 2: 燃气发电 LCOE (含残值更新)
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
        gas_fixed_opex = st.number_input("固定运维费 (万元/年)", min_value=0.0, value=1200.0)
        
        # [新增] 残值率输入
        st.markdown("##### 💰 资产残值")
        gas_salvage_rate = st.number_input("期末固定资产残值率 (%)", min_value=0.0, value=5.0, key="gas_salvage") / 100
        
    with col2:
        st.subheader("2. 燃料与效率 (GJ标准)")
        gas_cap = st.number_input("装机容量 (MW)", min_value=0.0, value=360.0)
        gas_hours = st.number_input("年运行小时数 (h)", min_value=0.0, value=3000.0)
        
        st.markdown("##### ⛽ 燃料成本核心参数")
        gas_price_gj = st.number_input("天然气价格 (元/GJ)", min_value=0.0, value=60.0, step=1.0)
        gas_heat_rate = st.number_input("机组平均热耗率 (GJ/kWh)", min_value=0.0, value=0.0095, format="%.4f", step=0.0001)
        
        efficiency = 0.0036 / gas_heat_rate if gas_heat_rate > 0 else 0
        st.caption(f"当前热耗对应等效热效率: :blue[{efficiency:.1%}]")

    # --- 计算逻辑 ---
    annual_gen_mwh = gas_cap * gas_hours
    fuel_cost_per_mwh_yuan = 1000 * gas_heat_rate * gas_price_gj
    annual_fuel_cost_wan = (annual_gen_mwh * fuel_cost_per_mwh_yuan) / 10000
    
    def get_opex_gas(y):
        return gas_fixed_opex + annual_fuel_cost_wan
    
    def get_gen_gas(y):
        return annual_gen_mwh
    
    # [修正逻辑] 使用用户输入的残值率
    salvage = gas_capex * gas_salvage_rate
    
    npv_cost, npv_gen, cf_flows = calculate_dcf(period, wacc, gas_capex, get_opex_gas, get_gen_gas, salvage_val=salvage)
    lcoe = (npv_cost / npv_gen) * 10 if npv_gen > 0 else 0
    
    # --- 结果 ---
    st.markdown("---")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("LCOE (元/kWh)", f"{lcoe:.4f}")
    c2.metric("其中：燃料成本", f"{fuel_cost_per_mwh_yuan/1000:.4f} 元/kWh", delta_color="off")
    c3.metric("年燃料支出 (万元)", f"{annual_fuel_cost_wan:,.0f}")
    c4.metric("期末残值回收 (万元)", f"{salvage:,.0f}", help="在第N年抵扣现金流出")
    
    cost_labels = ["初始投资(摊销)", "固定运维", "燃料成本"]
    ann_capex = gas_capex / period 
    fig = go.Figure(data=[go.Pie(labels=cost_labels, values=[ann_capex, gas_fixed_opex, annual_fuel_cost_wan], hole=.4)])
    fig.update_layout(title="年度成本结构估算 (名义值)", height=350)
    st.plotly_chart(fig, use_container_width=True)

# ==========================================
# 模块 3: 储能 LCOS 测算 (含残值更新)
# ==========================================
def render_lcos():
    st.header("🔋 储能 LCOS 平准化成本测算")
    st.info("适用于：独立储能电站的生命周期成本分析")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("1. 系统参数")
        lcos_wacc = st.number_input("折现率 WACC (%)", min_value=0.0, value=8.0, key="lcos_wacc") / 100
        lcos_period = int(st.number_input("项目寿命 (年)", min_value=1, value=15, key="lcos_period"))
        
        ess_power = st.number_input("额定功率 (MW)", min_value=0.0, value=100.0)
        ess_capacity = st.number_input("额定容量 (MWh)", min_value=0.0, value=200.0)
        
        lcos_capex = st.number_input("储能系统总投资 (万元)", min_value=0.0, value=25000.0)
        lcos_opex_rate = st.number_input("年运维费率 (%)", min_value=0.0, value=2.0, key="lcos_opex") / 100
        
        # [新增] 残值率输入
        st.markdown("##### 💰 资产残值")
        lcos_salvage_rate = st.number_input("期末固定资产残值率 (%)", min_value=0.0, value=3.0, key="lcos_salvage", help="电池通常无残值，但升压站和集装箱有一定残值") / 100

    with col2:
        st.subheader("2. 运行与充电")
        cycles_per_year = st.number_input("年循环次数", min_value=0.0, value=330.0)
        rte = st.slider("往返效率 RTE (%)", 70, 95, 85, key="lcos_rte") / 100
        degradation = st.number_input("年容量衰减率 (%)", min_value=0.0, value=2.0) / 100
        
        st.markdown("##### 🔌 充电成本")
        charge_price = st.number_input("平均充电电价 (元/kWh)", min_value=0.0, value=0.20)
        
        replace_yr = st.number_input("电池更换年份", min_value=0, value=8, key="lcos_rep")
        replace_val = st.number_input("更换投入 (万元)", min_value=0.0, value=10000.0)

    # --- Logic ---
    def get_lcos_vars(y):
        current_capacity = ess_capacity * ((1 - degradation) ** (y-1))
        if current_capacity < 0: current_capacity = 0
        
        annual_discharge = current_capacity * cycles_per_year * rte
        annual_charge = current_capacity * cycles_per_year 
        charging_cost_wan = annual_charge * 1000 * charge_price / 10000
        opex_wan = lcos_capex * lcos_opex_rate
        total_out_wan = opex_wan + charging_cost_wan
        
        return total_out_wan, annual_discharge, charging_cost_wan

    years = np.arange(1, lcos_period + 1)
    npv_numerator = lcos_capex
    npv_denominator = 0
    debug_charging_cost = 0 
    
    # [修正逻辑] 计算残值金额
    lcos_salvage_val = lcos_capex * lcos_salvage_rate

    for y in years:
        cost_wan, discharge_mwh, charge_cost_wan = get_lcos_vars(y)
        
        # 电池更换支出
        if y == replace_yr: 
            cost_wan += replace_val
            
        # [修正逻辑] 最后一年扣减残值
        if y == lcos_period:
            cost_wan -= lcos_salvage_val
            
        discount = 1 / ((1 + lcos_wacc) ** y)
        npv_numerator += cost_wan * discount
        npv_denominator += discharge_mwh * discount
        debug_charging_cost += charge_cost_wan * discount
        
    lcos = (npv_numerator / npv_denominator) * 10 if npv_denominator > 0 else 0
    lcos_addon = ((npv_numerator - debug_charging_cost) / npv_denominator) * 10 if npv_denominator > 0 else 0

    # --- Output ---
    st.markdown("---")
    res1, res2, res3 = st.columns(3)
    res1.metric("全周期 LCOS (元/kWh)", f"{lcos:.4f}", help="含充电成本")
    res2.metric("储能加工成本 (元/kWh)", f"{lcos_addon:.4f}", help="不含充电成本", delta_color="inverse")
    res3.metric("期末残值回收 (万元)", f"{lcos_salvage_val:,.0f}")

# ==========================================
# 主程序入口
# ==========================================
def main():
    st.sidebar.title("🚀 测算模型选择")
    mode = st.sidebar.radio(
        "请选择计算模块：",
        ("光伏+储能 LCOE", "燃气发电 LCOE", "储能 LCOS")
    )
    
    st.sidebar.markdown("---")
    st.sidebar.caption("v2.3 | Residual Value Added")
    
    if mode == "光伏+储能 LCOE":
        render_pv_ess_lcoe()
    elif mode == "燃气发电 LCOE":
        render_gas_lcoe()
    elif mode == "储能 LCOS":
        render_lcos()

if __name__ == "__main__":
    main()
