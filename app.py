import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# --- 页面配置 ---
st.set_page_config(page_title="新能源 LCOE 专业测算工具", layout="wide")

# --- 侧边栏：输入边界条件 ---
st.sidebar.header("🛠️ 核心边界条件")
st.sidebar.info("💡 特别说明：所有涉及金额的单位均为【万元】，电量计算基础为【MWh】")

st.sidebar.subheader("1. 财务参数")
wacc = st.sidebar.number_input("折现率 WACC (%)", value=8.0, step=0.1) / 100
period = st.sidebar.number_input("运营周期 (年)", value=25, step=1)

st.sidebar.subheader("2. 发电系统 (PV/Wind)")
gen_capacity = st.sidebar.number_input("装机容量 (MW)", value=200.0)
gen_hours = st.sidebar.number_input("年利用小时数 (h)", value=2200)
# 默认值 5亿 = 50000万
gen_capex = st.sidebar.number_input("发电系统投资 (万元)", value=50000.0) 
gen_opex_rate = st.sidebar.number_input("发电运维费率 (%)", value=1.5, step=0.1) / 100
gen_salvage_rate = st.sidebar.number_input("发电残值率 (%)", value=5.0) / 100

st.sidebar.subheader("3. 储能系统 (ESS)")
# 默认值 120MWh
ess_capacity = st.sidebar.number_input("储能容量 (MWh)", value=120.0) 
# 默认值 1亿 = 10000万
ess_capex = st.sidebar.number_input("储能系统投资 (万元)", value=10000.0) 
ess_opex_rate = st.sidebar.number_input("储能运维费率 (%)", value=3.0, step=0.1) / 100
ess_cycles = st.sidebar.number_input("年循环次数 (次)", value=1000)
ess_efficiency = st.sidebar.slider("系统综合效率 (%)", 70, 100, 85) / 100
replace_year = st.sidebar.number_input("电池更换年份 (第X年)", value=10)
replace_cost_ratio = st.sidebar.slider("更换成本占初始投资比例 (%)", 0, 100, 50) / 100

st.sidebar.subheader("4. 配套设施 (Grid)")
# 默认值 1.5亿 = 15000万
grid_capex = st.sidebar.number_input("电网/其他配套投资 (万元)", value=15000.0) 
grid_opex_rate = st.sidebar.number_input("配套运维费率 (%)", value=1.0) / 100

# --- 核心计算逻辑 ---
def calculate_model():
    # 1. 物理量计算 (MWh)
    annual_gen_pv = gen_capacity * gen_hours # MW * h = MWh
    annual_gen_ess = ess_capacity * ess_cycles * ess_efficiency # MWh
    total_annual_gen = annual_gen_pv + annual_gen_ess # MWh (直接叠加)
    
    # 2. 现金流计算 (万元)
    years = np.arange(1, period + 1)
    
    # 基础年运维费 (Base Opex)
    annual_opex_base = (gen_capex * gen_opex_rate) + \
                       (ess_capex * ess_opex_rate) + \
                       (grid_capex * grid_opex_rate)
    
    cash_flows = []     # 记录每年的名义支出（不含折现）
    
    # 初始化 NPV
    initial_inv = gen_capex + ess_capex + grid_capex
    total_npv_cost = initial_inv # 第0年投入
    total_npv_gen = 0
    
    for y in years:
        # 当年名义支出
        cf_out = annual_opex_base
        
        # 事件：电池更换
        if y == replace_year:
            cf_out += (ess_capex * replace_cost_ratio)
            
        # 事件：残值回收 (视为负支出)
        if y == period:
            salvage = gen_capex * gen_salvage_rate
            cf_out -= salvage
            
        cash_flows.append(cf_out)
        
        # 折现计算
        discount_factor = 1 / ((1 + wacc) ** y)
        
        total_npv_cost += cf_out * discount_factor
        total_npv_gen += total_annual_gen * discount_factor
        
    # 3. LCOE 计算 (核心修正部分)
    # LCOE (Wan/MWh) = NPV_Cost (Wan) / NPV_Gen (MWh)
    if total_npv_gen > 0:
        lcoe_wan_per_mwh = total_npv_cost / total_npv_gen
        
        # 单位换算核心逻辑：
        # 1 Wan = 10,000 units
        # 1 MWh = 1,000 kWh
        # 1 Wan/MWh = 10,000 / 1,000 = 10 units/kWh
        
        lcoe_final_unit = lcoe_wan_per_mwh * 10
    else:
        lcoe_final_unit = 0
    
    return lcoe_final_unit, total_npv_cost, total_npv_gen, initial_inv, cash_flows

# --- 执行计算 ---
lcoe_val, npv_cost, npv_gen, i0, cf_list = calculate_model()

# --- 主界面展示 ---
st.title("📊 新能源电站 LCOE 投资测算看板 (Pro)")
st.markdown("---")

# 1. 结果验证区 (顶部最醒目)
st.markdown("### 🎯 测算结论")
col1, col2, col3, col4 = st.columns(4)

# 醒目展示 LCOE
col1.metric(
    label="平准化度电成本 (LCOE)", 
    value=f"{lcoe_val:.4f}", 
    help="单位：元/kWh 或 AUD/kWh (取决于您的输入货币)"
)
col2.metric(
    label="LCOE (分/cents)", 
    value=f"{(lcoe_val * 100):.2f} ¢"
)

# 展示中间过程，方便核对
col3.metric(
    label="全生命周期成本现值 (NPC)", 
    value=f"{npv_cost:,.0f} 万元",
    help="所有投资与运维成本折现后的总和"
)
col4.metric(
    label="全生命周期发电量现值", 
    value=f"{npv_gen/10000:,.2f} 亿kWh", # 换算成亿kWh方便阅读
    help="折现后的总发电量"
)

# 2. 图表分析区
st.subheader("📈 现金流结构分析")

tab1, tab2 = st.tabs(["年度现金流 (Cash Flow)", "初始投资构成 (Capex)"])

with tab1:
    fig_cf = go.Figure()
    years_axis = list(range(1, period + 1))
    
    # 初始投资柱
    fig_cf.add_trace(go.Bar(
        x=[0], y=[i0], 
        name="初始投资 (第0年)", 
        marker_color='#FF5733',
        text=[f"{i0:,.0f}"],
        textposition='auto'
    ))
    
    # 运营支出柱
    fig_cf.add_trace(go.Bar(
        x=years_axis, y=cf_list, 
        name="年度净支出 (含更换/残值)", 
        marker_color='#3498DB'
    ))
    
    fig_cf.update_layout(
        title="项目全生命周期资金流出 (单位: 万元)", 
        xaxis_title="年份", 
        yaxis_title="金额 (万元)",
        hovermode="x unified"
    )
    st.plotly_chart(fig_cf, use_container_width=True)

with tab2:
    labels = ['发电系统', '储能系统', '电网配套']
    values = [gen_capex, ess_capex, grid_capex]
    
    fig_pie = go.Figure(data=[go.Pie(
        labels=labels, 
        values=values, 
        hole=.4,
        textinfo='label+percent',
        marker=dict(colors=['#2ECC71', '#F1C40F', '#9B59B6'])
    )])
    fig_pie.update_layout(title=f"初始总投资: {i0:,.0f} 万元")
    st.plotly_chart(fig_pie, use_container_width=True)

# 3. 详细数据表 (展开查看)
with st.expander("📋 点击查看详细计算底表"):
    df_details = pd.DataFrame({
        "年份": range(1, period + 1),
        "名义支出 (万元)": [round(x, 2) for x in cf_list],
        "折现系数": [round(1 / ((1 + wacc) ** y), 4) for y in range(1, period + 1)],
        "折现后成本 (万元)": [round(x * (1 / ((1 + wacc) ** y)), 2) for y, x in enumerate(cf_list, 1)],
        "当年发电 (MWh)": [round((gen_capacity*gen_hours) + (ess_capacity*ess_cycles*ess_efficiency), 0)] * period
    })
    st.dataframe(df_details, use_container_width=True)
