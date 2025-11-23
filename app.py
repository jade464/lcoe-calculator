import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import io

# --- 全局页面配置 ---
st.set_page_config(page_title="综合能源投资测算平台 Pro", layout="wide", page_icon="⚡")

# --- CSS样式微调 ---
st.markdown("""
<style>
    .metric-card {background-color: #f0f2f6; padding: 15px; border-radius: 10px; border-left: 5px solid #ff4b4b;}
    div[data-testid="stMetricValue"] {font-size: 24px;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 工具函数：Excel 导出引擎
# ==========================================
def convert_df_to_excel(df):
    output = io.BytesIO()
    # 使用 xlsxwriter 引擎
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='LCOE_Model')
        # 简单的格式化
        workbook = writer.book
        worksheet = writer.sheets['LCOE_Model']
        money_fmt = workbook.add_format({'num_format': '#,##0.00'})
        worksheet.set_column('B:Z', 15, money_fmt) # 设置列宽和格式
    return output.getvalue()

def display_data_deck(df, filename="lcoe_model.xlsx"):
    """展示数据底稿并提供下载"""
    st.markdown("### 📂 投资测算数据底稿 (Data Deck)")
    with st.expander("查看详细年度现金流表 (Yearly Cash Flow)", expanded=True):
        st.dataframe(df, use_container_width=True)
        
        # 导出按钮
        excel_data = convert_df_to_excel(df)
        st.download_button(
            label="📥 导出 Excel 底稿",
            data=excel_data,
            file_name=filename,
            mime="application/vnd.ms-excel"
        )

# ==========================================
# 模块 1: 光伏 + 储能 LCOE (精细化残值版)
# ==========================================
def render_pv_ess_lcoe():
    st.header("☀️ 光伏+储能 LCOE (Pro)")
    st.info("包含：分项残值计算、Excel底稿导出")
    
    col_in1, col_in2 = st.columns([1, 2])
    
    with col_in1:
        st.subheader("1. 财务与规模")
        wacc = st.number_input("折现率 WACC (%)", min_value=0.0, value=8.0, step=0.1, key="pv_wacc") / 100
        period = int(st.number_input("运营周期 (年)", min_value=1, value=25, key="pv_period"))
        
        st.subheader("2. 初始投资 (万元)")
        capex_pv = st.number_input("光伏系统投资", min_value=0.0, value=50000.0)
        capex_ess = st.number_input("储能系统投资", min_value=0.0, value=10000.0)
        capex_grid = st.number_input("电网/升压站投资", min_value=0.0, value=15000.0)
        
        st.subheader("3. 运维费率 (%)")
        opex_rate_pv = st.number_input("光伏运维费率", min_value=0.0, value=1.5) / 100
        opex_rate_ess = st.number_input("储能运维费率", min_value=0.0, value=3.0) / 100
        opex_rate_grid = st.number_input("配套运维费率", min_value=0.0, value=1.0) / 100
        
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
            
        st.subheader("5. 资产生命周期管理 (LCM)")
        # 资产置换
        rep_year = st.slider("电池更换年份", 1, period, 10, key="pv_rep_year")
        rep_cost = st.number_input("更换成本 (万元)", min_value=0.0, value=5000.0)
        
        # --- 精细化残值设置 ---
        st.markdown("##### 💰 分项残值率 (Salvage Value)")
        rc1, rc2, rc3 = st.columns(3)
        salvage_rate_pv = rc1.number_input("光伏残值率 %", 0.0, 100.0, 5.0) / 100
        salvage_rate_ess = rc2.number_input("储能残值率 %", 0.0, 100.0, 0.0, help="电池寿命结束通常残值极低") / 100
        salvage_rate_grid = rc3.number_input("配套/土地残值率 %", 0.0, 100.0, 10.0, help="铜缆、钢铁及土地残值较高") / 100

    # --- 计算引擎 (生成 DataFrame) ---
    years = np.arange(1, period + 1)
    data = []
    
    total_inv = capex_pv + capex_ess + capex_grid
    
    # 累计 NPV 初始化
    cum_npv_cost = total_inv
    cum_npv_gen = 0
    
    # 残值计算
    sv_pv = capex_pv * salvage_rate_pv
    sv_ess = capex_ess * salvage_rate_ess
    sv_grid = capex_grid * salvage_rate_grid
    total_salvage = sv_pv + sv_ess + sv_grid

    for y in years:
        # 1. 运营支出
        opex_pv = capex_pv * opex_rate_pv
        opex_ess = capex_ess * opex_rate_ess
        opex_grid = capex_grid * opex_rate_grid
        total_opex = opex_pv + opex_ess + opex_grid
        
        # 2. 资本性支出 (Capex Events)
        capex_event = 0
        if y == rep_year:
            capex_event = rep_cost
        
        # 3. 残值回收 (现金流入，记为负成本)
        salvage_event = 0
        if y == period:
            salvage_event = -total_salvage
            
        # 4. 当年净现金流 (名义)
        net_cf = total_opex + capex_event + salvage_event
        
        # 5. 发电量 (含衰减)
        degrade = 1 - (y-1)*0.005 
        gen_pv = pv_cap * pv_hours * degrade
        gen_ess = ess_cap * ess_cycles * ess_eff
        total_gen = gen_pv + gen_ess
        
        # 6. 折现
        df_factor = 1 / ((1 + wacc) ** y)
        dcf = net_cf * df_factor
        dgen = total_gen * df_factor
        
        cum_npv_cost += dcf
        cum_npv_gen += dgen
        
        # 记录数据行
        data.append({
            "Year": y,
            "Opex (万元)": round(total_opex, 2),
            "Replacement (万元)": round(capex_event, 2),
            "Salvage (万元)": round(abs(salvage_event) if salvage_event < 0 else 0, 2), # 展示为正数方便阅读
            "Net Cash Flow (万元)": round(net_cf, 2),
            "Discount Factor": round(df_factor, 4),
            "DCF (万元)": round(dcf, 2),
            "Generation (MWh)": round(total_gen, 2),
            "Discounted Gen (MWh)": round(dgen, 2)
        })

    # 创建 DataFrame
    df_calc = pd.DataFrame(data)
    
    # 最终计算
    lcoe = (cum_npv_cost / cum_npv_gen) * 10 if cum_npv_gen > 0 else 0
    
    # --- 结果展示 ---
    st.markdown("---")
    res_col1, res_col2, res_col3, res_col4 = st.columns(4)
    res_col1.metric("LCOE (元/kWh)", f"{lcoe:.4f}")
    res_col2.metric("LCOE (分/kWh)", f"{lcoe*100:.2f} ¢")
    res_col3.metric("NPC (万元)", f"{cum_npv_cost:,.0f}")
    res_col4.metric("期末总残值 (万元)", f"{total_salvage:,.0f}")
    
    # --- 底稿展示 ---
    st.markdown("---")
    display_data_deck(df_calc, filename="PV_ESS_LCOE_Model.xlsx")


# ==========================================
# 模块 2: 燃气发电 LCOE (GJ 版 + 底稿)
# ==========================================
def render_gas_lcoe():
    st.header("🔥 燃气发电 LCOE (Pro)")
    st.info("包含：GJ燃料计算、Excel底稿导出")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("1. 投资与运维")
        wacc = st.number_input("折现率 WACC (%)", min_value=0.0, value=8.0, key="gas_wacc") / 100
        period = int(st.number_input("运营周期 (年)", min_value=1, value=25, key="gas_period"))
        gas_capex = st.number_input("项目总投资 (万元)", min_value=0.0, value=60000.0)
        gas_fixed_opex = st.number_input("固定运维费 (万元/年)", min_value=0.0, value=1200.0)
        gas_salvage_rate = st.number_input("期末固定资产残值率 (%)", min_value=0.0, value=5.0, key="gas_salvage") / 100
        
    with col2:
        st.subheader("2. 燃料与效率 (GJ标准)")
        gas_cap = st.number_input("装机容量 (MW)", min_value=0.0, value=360.0)
        gas_hours = st.number_input("年运行小时数 (h)", min_value=0.0, value=3000.0)
        gas_price_gj = st.number_input("天然气价格 (元/GJ)", min_value=0.0, value=60.0, step=1.0)
        gas_heat_rate = st.number_input("机组平均热耗率 (GJ/kWh)", min_value=0.0, value=0.0095, format="%.4f")

    # --- 计算引擎 ---
    years = np.arange(1, period + 1)
    data = []
    
    # 燃料费常数
    annual_gen_mwh = gas_cap * gas_hours
    fuel_cost_per_mwh_yuan = 1000 * gas_heat_rate * gas_price_gj
    annual_fuel_cost_wan = (annual_gen_mwh * fuel_cost_per_mwh_yuan) / 10000
    
    cum_npv_cost = gas_capex
    cum_npv_gen = 0
    salvage_val = gas_capex * gas_salvage_rate
    
    for y in years:
        # 成本构成
        opex_fixed = gas_fixed_opex
        opex_fuel = annual_fuel_cost_wan
        total_opex = opex_fixed + opex_fuel
        
        # 残值
        salvage_flow = 0
        if y == period:
            salvage_flow = -salvage_val
            
        net_cf = total_opex + salvage_flow
        
        # 折现
        df_factor = 1 / ((1 + wacc) ** y)
        dcf = net_cf * df_factor
        dgen = annual_gen_mwh * df_factor
        
        cum_npv_cost += dcf
        cum_npv_gen += dgen
        
        data.append({
            "Year": y,
            "Fixed Opex (万元)": opex_fixed,
            "Fuel Cost (万元)": round(opex_fuel, 2),
            "Salvage (万元)": abs(salvage_flow),
            "Net Cash Flow (万元)": round(net_cf, 2),
            "Discount Factor": round(df_factor, 4),
            "DCF (万元)": round(dcf, 2),
            "Generation (MWh)": round(annual_gen_mwh, 2),
            "Discounted Gen (MWh)": round(dgen, 2)
        })
        
    df_calc = pd.DataFrame(data)
    lcoe = (cum_npv_cost / cum_npv_gen) * 10 if cum_npv_gen > 0 else 0
    
    # --- 结果 ---
    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    c1.metric("LCOE (元/kWh)", f"{lcoe:.4f}")
    c2.metric("燃料成本 (元/kWh)", f"{fuel_cost_per_mwh_yuan/1000:.4f}")
    c3.metric("NPC (万元)", f"{cum_npv_cost:,.0f}")
    
    # --- 底稿 ---
    st.markdown("---")
    display_data_deck(df_calc, filename="Gas_LCOE_Model.xlsx")


# ==========================================
# 模块 3: 储能 LCOS (Pro)
# ==========================================
def render_lcos():
    st.header("🔋 储能 LCOS (Pro)")
    st.info("包含：充电成本明细、Excel底稿导出")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("1. 系统参数")
        lcos_wacc = st.number_input("折现率 WACC (%)", min_value=0.0, value=8.0, key="lcos_wacc") / 100
        lcos_period = int(st.number_input("项目寿命 (年)", min_value=1, value=15, key="lcos_period"))
        ess_power = st.number_input("额定功率 (MW)", min_value=0.0, value=100.0)
        ess_capacity = st.number_input("额定容量 (MWh)", min_value=0.0, value=200.0)
        lcos_capex = st.number_input("储能系统总投资 (万元)", min_value=0.0, value=25000.0)
        lcos_opex_rate = st.number_input("年运维费率 (%)", min_value=0.0, value=2.0, key="lcos_opex") / 100
        lcos_salvage_rate = st.number_input("期末固定资产残值率 (%)", min_value=0.0, value=3.0, key="lcos_salvage") / 100

    with col2:
        st.subheader("2. 运行与充电")
        cycles_per_year = st.number_input("年循环次数", min_value=0.0, value=330.0)
        rte = st.slider("往返效率 RTE (%)", 70, 95, 85, key="lcos_rte") / 100
        degradation = st.number_input("年容量衰减率 (%)", min_value=0.0, value=2.0) / 100
        charge_price = st.number_input("平均充电电价 (元/kWh)", min_value=0.0, value=0.20)
        replace_yr = st.number_input("电池更换年份", min_value=0, value=8, key="lcos_rep")
        replace_val = st.number_input("更换投入 (万元)", min_value=0.0, value=10000.0)

    # --- 计算引擎 ---
    years = np.arange(1, lcos_period + 1)
    data = []
    
    cum_npv_numerator = lcos_capex
    cum_npv_denominator = 0
    cum_charging_cost = 0
    
    salvage_val = lcos_capex * lcos_salvage_rate
    
    for y in years:
        # 物理量
        curr_cap = ess_capacity * ((1 - degradation) ** (y-1))
        if curr_cap < 0: curr_cap = 0
        
        annual_discharge = curr_cap * cycles_per_year * rte
        annual_charge = curr_cap * cycles_per_year
        
        # 成本项
        cost_opex = lcos_capex * lcos_opex_rate
        cost_charge = annual_charge * 1000 * charge_price / 10000 # 万元
        cost_replace = replace_val if y == replace_yr else 0
        
        # 残值
        cost_salvage = 0
        if y == lcos_period:
            cost_salvage = -salvage_val
            
        total_out = cost_opex + cost_charge + cost_replace + cost_salvage
        
        # 折现
        df_factor = 1 / ((1 + lcos_wacc) ** y)
        dcf_cost = total_out * df_factor
        dcf_gen = annual_discharge * df_factor
        dcf_charge_only = cost_charge * df_factor
        
        cum_npv_numerator += dcf_cost
        cum_npv_denominator += dcf_gen
        cum_charging_cost += dcf_charge_only
        
        data.append({
            "Year": y,
            "Capacity (MWh)": round(curr_cap, 1),
            "Opex (万元)": round(cost_opex, 2),
            "Charging Cost (万元)": round(cost_charge, 2),
            "Replacement (万元)": cost_replace,
            "Salvage (万元)": abs(cost_salvage),
            "Total Outflow (万元)": round(total_out, 2),
            "Discount Factor": round(df_factor, 4),
            "DCF (万元)": round(dcf_cost, 2),
            "Discharged (MWh)": round(annual_discharge, 2)
        })
        
    df_calc = pd.DataFrame(data)
    lcos = (cum_npv_numerator / cum_npv_denominator) * 10 if cum_npv_denominator > 0 else 0
    lcos_addon = ((cum_npv_numerator - cum_charging_cost) / cum_npv_denominator) * 10 if cum_npv_denominator > 0 else 0

    # --- 结果 ---
    st.markdown("---")
    r1, r2, r3 = st.columns(3)
    r1.metric("全周期 LCOS (元/kWh)", f"{lcos:.4f}")
    r2.metric("加工成本 (元/kWh)", f"{lcos_addon:.4f}")
    r3.metric("期末残值 (万元)", f"{salvage_val:,.0f}")
    
    # --- 底稿 ---
    st.markdown("---")
    display_data_deck(df_calc, filename="LCOS_Model.xlsx")

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
    st.sidebar.caption("v3.0 | Pro Edition with Excel Export")
    
    if mode == "光伏+储能 LCOE":
        render_pv_ess_lcoe()
    elif mode == "燃气发电 LCOE":
        render_gas_lcoe()
    elif mode == "储能 LCOS":
        render_lcos()

if __name__ == "__main__":
    main()
