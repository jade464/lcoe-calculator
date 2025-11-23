import streamlit as st
import pandas as pd
import numpy as np
import io
import xlsxwriter

# --- 全局配置 ---
st.set_page_config(page_title="LCOE Pro Investment Model", layout="wide", page_icon="⚡")

# --- CSS: 优化表格显示 ---
st.markdown("""
<style>
    .metric-card {background-color: #f0f2f6; padding: 15px; border-radius: 10px; border-left: 5px solid #ff4b4b;}
    div[data-testid="stDataFrameResizable"] {border: 1px solid #e6e9ef;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 核心引擎：生成标准投行风格 Excel 模型
# ==========================================
def generate_professional_excel(model_name, inputs, time_series_data, summary_metrics):
    output = io.BytesIO()
    
    # 创建 Excel
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet('LCOE Calculation')
    
    # --- 样式定义 (Styles) ---
    # 标题样式
    fmt_header = workbook.add_format({'bold': True, 'font_size': 12, 'bg_color': '#2F5597', 'font_color': 'white', 'align': 'center', 'valign': 'vcenter', 'border': 1})
    fmt_subheader = workbook.add_format({'bold': True, 'font_size': 11, 'bg_color': '#D9E1F2', 'border': 1})
    # 数据样式
    fmt_text = workbook.add_format({'border': 1, 'align': 'left'})
    fmt_number = workbook.add_format({'border': 1, 'num_format': '#,##0.00'})
    fmt_currency = workbook.add_format({'border': 1, 'num_format': '¥ #,##0'}) # 显示人民币/金额
    fmt_percent = workbook.add_format({'border': 1, 'num_format': '0.00%'})
    fmt_lcoe_res = workbook.add_format({'bold': True, 'font_size': 12, 'bg_color': '#FFF2CC', 'num_format': '0.0000', 'border': 2})
    
    # --- Part 1: 输入假设区 (Inputs) ---
    worksheet.merge_range('A1:D1', f"{model_name} - 关键假设输入 (Key Assumptions)", fmt_header)
    
    row = 2
    for key, value in inputs.items():
        worksheet.write(row, 0, key, fmt_text)
        # 根据值类型判断格式
        if "率" in key or "Rate" in key or "WACC" in key:
            worksheet.write(row, 1, value, fmt_percent)
        else:
            worksheet.write(row, 1, value, fmt_number)
        row += 1
    
    # --- Part 2: 结果摘要 (Summary) ---
    res_start_row = 2
    worksheet.merge_range('F1:G1', "测算结果摘要 (Summary)", fmt_header)
    
    r = res_start_row
    for key, value in summary_metrics.items():
        worksheet.write(r, 5, key, fmt_subheader)
        worksheet.write(r, 6, value, fmt_lcoe_res)
        r += 1
        
    # --- Part 3: 现金流瀑布 (Waterfall Model) ---
    # 这里的 data 是一个包含 Year 0 - Year N 的字典列表
    
    # 准备表头
    start_row = row + 3
    worksheet.write(start_row, 0, "LCOE Calculation Model", fmt_subheader)
    
    # 获取年份列表 (包含Year 0)
    years = time_series_data['Year']
    
    # 写入年份表头 (B列开始向右)
    col_idx = 1
    for y in years:
        label = f"Year {int(y)}"
        worksheet.write(start_row, col_idx, label, fmt_header)
        col_idx += 1
        
    # 定义要展示的行 (Rows)
    # 格式: (显示名称, 数据Key, 格式)
    rows_config = [
        ("1. 物理发电量 (MWh)", "Generation", fmt_number),
        ("   折现系数 (Discount Factor)", "Discount Factor", fmt_number),
        ("   折现发电量 (Discounted Gen)", "Discounted Gen", fmt_number),
        ("   >>> 累计折现发电量 (Cum. Gen)", "Cum Discounted Gen", fmt_number), # 新增累计
        ("", "", fmt_text), # 空行
        ("2. 资金流出 (万元)", "", fmt_subheader),
        ("   初始投资 (Capex)", "Capex", fmt_currency),
        ("   运营支出 (Opex)", "Opex", fmt_currency),
        ("   燃料/充电成本 (Fuel/Charge)", "Fuel/Charge", fmt_currency),
        ("   资产置换 (Replacement)", "Replacement", fmt_currency),
        ("   残值回收 (Salvage)", "Salvage", fmt_currency),
        ("   净现金流 (Net Cash Flow)", "Net Cash Flow", fmt_currency),
        ("   折现现金流 (PV of Costs)", "PV of Cost", fmt_currency),
        ("   >>> 累计折现成本 (Cum. PV)", "Cum PV of Cost", fmt_currency), # 新增累计
    ]
    
    curr_row = start_row + 1
    
    for row_label, data_key, cell_fmt in rows_config:
        worksheet.write(curr_row, 0, row_label, fmt_text) # 写行名
        
        if data_key: # 如果有数据key
            col_idx = 1
            for i, _ in enumerate(years):
                val = time_series_data[data_key][i]
                worksheet.write(curr_row, col_idx, val, cell_fmt)
                col_idx += 1
        
        curr_row += 1
        
    # 调整列宽
    worksheet.set_column(0, 0, 30) # 标题列宽
    worksheet.set_column(1, len(years), 12) # 数据列宽
    
    workbook.close()
    return output.getvalue()

# ==========================================
# 辅助：将计算数据转为横向 List 供 Excel 使用
# ==========================================
def prep_timeseries(period, wacc, investment, annual_gen_func, cashflow_func):
    # Year 0
    years = [0] + list(range(1, period + 1))
    
    # 初始化列表
    data = {
        "Year": years,
        "Generation": [0],
        "Discount Factor": [1.0],
        "Discounted Gen": [0],
        "Cum Discounted Gen": [0],
        
        "Capex": [investment], # Year 0 发生
        "Opex": [0],
        "Fuel/Charge": [0],
        "Replacement": [0],
        "Salvage": [0],
        "Net Cash Flow": [investment],
        "PV of Cost": [investment],
        "Cum PV of Cost": [investment]
    }
    
    cum_gen = 0
    cum_cost = investment
    
    for y in range(1, period + 1):
        # 获取当年的各个分项 (需要在主函数里把这些分项拆出来，这里为了通用化简化处理)
        # 为了更精准的底稿，我们将在主函数里构建这个 data 字典，这里仅作占位说明
        pass 
        
    return data

# ==========================================
# 模块 1: 光伏 + 储能 LCOE (底稿增强版)
# ==========================================
def render_pv_ess_lcoe():
    st.header("☀️ 光伏+储能 LCOE (Pro)")
    
    col_in1, col_in2 = st.columns([1, 2])
    with col_in1:
        st.subheader("1. 财务与规模")
        wacc = st.number_input("折现率 WACC (%)", min_value=0.0, value=8.0, step=0.1, key="pv_wacc") / 100
        period = int(st.number_input("运营周期 (年)", min_value=1, value=25, key="pv_period"))
        
        st.subheader("2. 初始投资 (万元)")
        capex_pv = st.number_input("光伏系统投资", min_value=0.0, value=50000.0)
        capex_ess = st.number_input("储能系统投资", min_value=0.0, value=10000.0)
        capex_grid = st.number_input("电网/升压站投资", min_value=0.0, value=15000.0)
        
    with col_in2:
        st.subheader("3. 运维与参数")
        c1, c2, c3 = st.columns(3)
        opex_rate_pv = c1.number_input("光伏运维费率%", value=1.5)/100
        opex_rate_ess = c2.number_input("储能运维费率%", value=3.0)/100
        opex_rate_grid = c3.number_input("配套运维费率%", value=1.0)/100
        
        c4, c5 = st.columns(2)
        pv_cap = c4.number_input("光伏容量(MW)", value=200.0)
        pv_hours = c4.number_input("利用小时数(h)", value=2200.0)
        ess_cap = c5.number_input("储能容量(MWh)", value=120.0)
        ess_cycles = c5.number_input("循环次数", value=1000.0)
        ess_eff = c5.number_input("综合效率%", value=85.0)/100
        
        st.subheader("4. 资产管理")
        rep_year = st.number_input("更换年份", value=10)
        rep_cost = st.number_input("更换成本", value=5000.0)
        salvage_rate_pv = st.number_input("光伏残值率%", value=5.0)/100
        salvage_rate_grid = st.number_input("配套残值率%", value=10.0)/100

    # --- 计算引擎 (List 结构) ---
    years = [0] + list(range(1, period + 1))
    total_initial_inv = capex_pv + capex_ess + capex_grid
    
    # 准备数据容器
    ts_data = {k: [] for k in ["Year", "Generation", "Discount Factor", "Discounted Gen", "Cum Discounted Gen", 
                               "Capex", "Opex", "Fuel/Charge", "Replacement", "Salvage", 
                               "Net Cash Flow", "PV of Cost", "Cum PV of Cost"]}
    
    # Year 0 数据填充
    ts_data["Year"].append(0)
    ts_data["Generation"].append(0)
    ts_data["Discount Factor"].append(1.0)
    ts_data["Discounted Gen"].append(0)
    ts_data["Cum Discounted Gen"].append(0)
    ts_data["Capex"].append(total_initial_inv)
    ts_data["Opex"].append(0)
    ts_data["Fuel/Charge"].append(0)
    ts_data["Replacement"].append(0)
    ts_data["Salvage"].append(0)
    ts_data["Net Cash Flow"].append(total_initial_inv)
    ts_data["PV of Cost"].append(total_initial_inv)
    ts_data["Cum PV of Cost"].append(total_initial_inv)
    
    cum_gen_npv = 0
    cum_cost_npv = total_initial_inv
    
    salvage_val_total = (capex_pv * salvage_rate_pv) + (capex_grid * salvage_rate_grid)
    
    for y in range(1, period + 1):
        ts_data["Year"].append(y)
        
        # 1. 发电
        degrade = 1 - (y-1)*0.005
        gen = (pv_cap * pv_hours * degrade) + (ess_cap * ess_cycles * ess_eff)
        ts_data["Generation"].append(gen)
        
        # 2. 折现
        df = 1 / ((1 + wacc) ** y)
        ts_data["Discount Factor"].append(df)
        
        gen_npv = gen * df
        ts_data["Discounted Gen"].append(gen_npv)
        cum_gen_npv += gen_npv
        ts_data["Cum Discounted Gen"].append(cum_gen_npv)
        
        # 3. 成本
        ts_data["Capex"].append(0) # 运营期无初始投资
        
        opex = (capex_pv*opex_rate_pv) + (capex_ess*opex_rate_ess) + (capex_grid*opex_rate_grid)
        ts_data["Opex"].append(opex)
        ts_data["Fuel/Charge"].append(0)
        
        rep = rep_cost if y == rep_year else 0
        ts_data["Replacement"].append(rep)
        
        sal = -salvage_val_total if y == period else 0
        ts_data["Salvage"].append(sal) # 负数代表流入
        
        # 净流
        net_cf = opex + rep + sal
        ts_data["Net Cash Flow"].append(net_cf)
        
        cost_npv = net_cf * df
        ts_data["PV of Cost"].append(cost_npv)
        cum_cost_npv += cost_npv
        ts_data["Cum PV of Cost"].append(cum_cost_npv)

    # 结果
    lcoe = (cum_cost_npv / cum_gen_npv) * 10 if cum_gen_npv > 0 else 0
    
    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    c1.metric("LCOE (元/kWh)", f"{lcoe:.4f}")
    c2.metric("NPC (万元)", f"{cum_cost_npv:,.0f}")
    c3.metric("总电量现值 (MWh)", f"{cum_gen_npv:,.0f}")

    # --- 底稿展示与导出 ---
    st.subheader("📋 投资测算模型底稿")
    
    # 将字典转为DataFrame用于页面展示 (转置显示，更像Excel)
    df_display = pd.DataFrame(ts_data).set_index("Year").T
    st.dataframe(df_display, use_container_width=True, height=400)
    
    # 导出 Excel
    inputs = {
        "WACC": wacc, "Period": period, "Initial Capex": total_initial_inv,
        "PV Capacity (MW)": pv_cap, "ESS Capacity (MWh)": ess_cap
    }
    summary = {
        "LCOE (CNY/kWh)": lcoe, 
        "Total NPC (Wan)": cum_cost_npv,
        "Total NPV Gen (MWh)": cum_gen_npv
    }
    
    excel_file = generate_professional_excel("PV_ESS_LCOE", inputs, ts_data, summary)
    
    st.download_button(
        label="📥 下载标准 Excel 财务模型 (.xlsx)",
        data=excel_file,
        file_name="PV_ESS_Financial_Model.xlsx",
        mime="application/vnd.ms-excel"
    )

# ==========================================
# 模块 2: 燃气 LCOE (底稿增强版)
# ==========================================
def render_gas_lcoe():
    st.header("🔥 燃气发电 LCOE (Pro)")
    
    col1, col2 = st.columns(2)
    with col1:
        wacc = st.number_input("折现率%", value=8.0)/100
        period = int(st.number_input("周期", value=25))
        capex = st.number_input("总投资(万)", value=60000.0)
        fixed_opex = st.number_input("固定运维(万/年)", value=1200.0)
        salvage_rate = st.number_input("残值率%", value=5.0)/100
    with col2:
        cap_mw = st.number_input("容量(MW)", value=360.0)
        hours = st.number_input("小时数", value=3000.0)
        price_gj = st.number_input("气价(元/GJ)", value=60.0)
        heat_rate = st.number_input("热耗(GJ/kWh)", value=0.0095, format="%.4f")

    # --- 计算 ---
    years = [0] + list(range(1, period + 1))
    ts_data = {k: [] for k in ["Year", "Generation", "Discount Factor", "Discounted Gen", "Cum Discounted Gen", 
                               "Capex", "Opex", "Fuel/Charge", "Replacement", "Salvage", 
                               "Net Cash Flow", "PV of Cost", "Cum PV of Cost"]}
    
    # Year 0
    for k in ts_data: ts_data[k].append(0)
    ts_data["Year"][0] = 0
    ts_data["Discount Factor"][0] = 1.0
    ts_data["Capex"][0] = capex
    ts_data["Net Cash Flow"][0] = capex
    ts_data["PV of Cost"][0] = capex
    ts_data["Cum PV of Cost"][0] = capex
    
    cum_gen_npv = 0
    cum_cost_npv = capex
    
    annual_gen = cap_mw * hours
    fuel_cost = (annual_gen * 1000 * heat_rate * price_gj) / 10000 # 万元
    salvage_val = capex * salvage_rate

    for y in range(1, period + 1):
        ts_data["Year"].append(y)
        ts_data["Generation"].append(annual_gen)
        
        df = 1 / ((1 + wacc) ** y)
        ts_data["Discount Factor"].append(df)
        
        g_npv = annual_gen * df
        ts_data["Discounted Gen"].append(g_npv)
        cum_gen_npv += g_npv
        ts_data["Cum Discounted Gen"].append(cum_gen_npv)
        
        ts_data["Capex"].append(0)
        ts_data["Opex"].append(fixed_opex)
        ts_data["Fuel/Charge"].append(fuel_cost)
        ts_data["Replacement"].append(0)
        
        sal = -salvage_val if y == period else 0
        ts_data["Salvage"].append(sal)
        
        net_cf = fixed_opex + fuel_cost + sal
        ts_data["Net Cash Flow"].append(net_cf)
        
        c_npv = net_cf * df
        ts_data["PV of Cost"].append(c_npv)
        cum_cost_npv += c_npv
        ts_data["Cum PV of Cost"].append(cum_cost_npv)
        
    lcoe = (cum_cost_npv / cum_gen_npv) * 10 if cum_gen_npv > 0 else 0
    
    st.markdown("---")
    st.metric("LCOE (元/kWh)", f"{lcoe:.4f}")
    
    # DataFrame
    df_display = pd.DataFrame(ts_data).set_index("Year").T
    st.dataframe(df_display, use_container_width=True, height=400)
    
    # Export
    inputs = {"WACC": wacc, "Gas Price (Yuan/GJ)": price_gj, "Heat Rate": heat_rate}
    summary = {"LCOE": lcoe}
    excel_file = generate_professional_excel("Gas_Power_LCOE", inputs, ts_data, summary)
    
    st.download_button("📥 下载标准 Excel 财务模型", excel_file, "Gas_LCOE_Model.xlsx")

# ==========================================
# 模块 3: 储能 LCOS (底稿增强版)
# ==========================================
def render_lcos():
    st.header("🔋 储能 LCOS (Pro)")
    
    col1, col2 = st.columns(2)
    with col1:
        lcos_wacc = st.number_input("WACC%", value=8.0)/100
        period = int(st.number_input("寿命(年)", value=15))
        capex = st.number_input("投资(万)", value=25000.0)
        opex_rate = st.number_input("运维%", value=2.0)/100
        salvage_rate = st.number_input("残值%", value=3.0)/100
    with col2:
        cap_mwh = st.number_input("容量(MWh)", value=200.0)
        cycles = st.number_input("循环次数", value=330.0)
        rte = st.number_input("效率%", value=85.0)/100
        deg = st.number_input("衰减%", value=2.0)/100
        charge_p = st.number_input("充电价(元/kWh)", value=0.2)
        rep_y = st.number_input("更换年", value=8)
        rep_c = st.number_input("更换费(万)", value=10000.0)

    # --- 计算 ---
    years = [0] + list(range(1, period + 1))
    ts_data = {k: [] for k in ["Year", "Generation", "Discount Factor", "Discounted Gen", "Cum Discounted Gen", 
                               "Capex", "Opex", "Fuel/Charge", "Replacement", "Salvage", 
                               "Net Cash Flow", "PV of Cost", "Cum PV of Cost"]}
    
    # Year 0
    for k in ts_data: ts_data[k].append(0)
    ts_data["Year"][0] = 0
    ts_data["Discount Factor"][0] = 1.0
    ts_data["Capex"][0] = capex
    ts_data["Net Cash Flow"][0] = capex
    ts_data["PV of Cost"][0] = capex
    ts_data["Cum PV of Cost"][0] = capex
    
    cum_gen_npv = 0
    cum_cost_npv = capex
    salvage_val = capex * salvage_rate
    
    for y in range(1, period + 1):
        ts_data["Year"].append(y)
        
        curr_cap = cap_mwh * ((1 - deg) ** (y-1))
        discharge = curr_cap * cycles * rte
        ts_data["Generation"].append(discharge) # 这里 Generation 指放电量
        
        df = 1 / ((1 + lcos_wacc) ** y)
        ts_data["Discount Factor"].append(df)
        
        g_npv = discharge * df
        ts_data["Discounted Gen"].append(g_npv)
        cum_gen_npv += g_npv
        ts_data["Cum Discounted Gen"].append(cum_gen_npv)
        
        ts_data["Capex"].append(0)
        
        opex = capex * opex_rate
        ts_data["Opex"].append(opex)
        
        charge_cost = (curr_cap * cycles * 1000 * charge_p) / 10000
        ts_data["Fuel/Charge"].append(charge_cost)
        
        rep = rep_c if y == rep_y else 0
        ts_data["Replacement"].append(rep)
        
        sal = -salvage_val if y == period else 0
        ts_data["Salvage"].append(sal)
        
        net_cf = opex + charge_cost + rep + sal
        ts_data["Net Cash Flow"].append(net_cf)
        
        c_npv = net_cf * df
        ts_data["PV of Cost"].append(c_npv)
        cum_cost_npv += c_npv
        ts_data["Cum PV of Cost"].append(cum_cost_npv)
        
    lcos = (cum_cost_npv / cum_gen_npv) * 10 if cum_gen_npv > 0 else 0
    
    st.markdown("---")
    st.metric("LCOS (元/kWh)", f"{lcos:.4f}")
    
    df_display = pd.DataFrame(ts_data).set_index("Year").T
    st.dataframe(df_display, use_container_width=True, height=400)
    
    inputs = {"WACC": lcos_wacc, "Charging Price": charge_p}
    summary = {"LCOS": lcos}
    excel_file = generate_professional_excel("ESS_LCOS", inputs, ts_data, summary)
    st.download_button("📥 下载标准 Excel 财务模型", excel_file, "LCOS_Model.xlsx")

# ==========================================
# 主程序
# ==========================================
def main():
    st.sidebar.title("LCOE Pro Model")
    mode = st.sidebar.radio("选择模型", ("光伏+储能 LCOE", "燃气发电 LCOE", "储能 LCOS"))
    
    if mode == "光伏+储能 LCOE": render_pv_ess_lcoe()
    elif mode == "燃气发电 LCOE": render_gas_lcoe()
    elif mode == "储能 LCOS": render_lcos()

if __name__ == "__main__":
    main()
