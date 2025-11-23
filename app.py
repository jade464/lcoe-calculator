import streamlit as st
import pandas as pd
import numpy as np
import io
import xlsxwriter

# --- 1. 全局配置 ---
st.set_page_config(page_title="新能源资产持有成本测算 (Owner's View)", layout="wide", page_icon="🏢")

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
    
    worksheet.write('A1', f"{model_name} - 关键假设", workbook.add_format({'bold': True, 'font_size': 14}))
    r = 2
    for k, v in inputs.items():
        worksheet.write(r, 0, k, fmt_sub)
        worksheet.write(r, 1, v, fmt_num)
        r += 1
        
    r += 2
    worksheet.write(r, 0, "Cash Flow Waterfall", workbook.add_format({'bold': True, 'font_size': 12}))
    r += 1
    
    cols = ["Year"] + [f"Year {y}" for y in time_series_data["Year"]]
    worksheet.write_row(r, 0, cols, fmt_head)
    r += 1
    
    rows = [
        ("物理发电/放电量 (MWh)", "Generation", fmt_num),
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
        ("--- 税务调节 (Tax Adjustments) ---", "", None),
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
# 3. 模块 A: 光伏 + 储能 LCOE
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
        # 这里虽然是LCOE，但为了统一也加上效率
        ess_eff = 0.85 
        
        st.markdown("---")
        st.markdown("### 2. 投资与运维")
        c1, c2, c3 = st.columns(3)
        capex_pv = c1.number_input("光伏投资 (万)", value=50000.0, step=100.0)
        capex_ess = c2.number_input("储能投资 (万)", value=10000.0, step=100.0)
        capex_grid = c3.number_input("配套投资 (万)", value=15000.0, step=100.0)
        
        o1, o2, o3 = st.columns(3)
        opex_r_pv = o1.number_input("光伏运维%", value=1.5,
