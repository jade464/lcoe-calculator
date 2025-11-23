import streamlit as st
import pandas as pd
import numpy as np
import io
import xlsxwriter

# --- 1. 全局配置 ---
st.set_page_config(page_title="新能源资产持有成本测算 (Pro Logic)", layout="wide", page_icon="⚡")

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
    
    worksheet.write('A1', f"{model_name} - Key Assumptions", workbook.add_format({'bold': True, 'font_size': 14}))
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
        ("系统有效上网电量 (MWh)", "System Generation", fmt_num),
        ("折现系数", "Discount Factor", fmt_num),
        ("折现电量 (税后调整)", "Discounted Gen Tax Adj", fmt_num),
        ("累计折现分母", "Cum Denominator", fmt_num),
        ("", "", None),
        ("1. 初始投资", "Capex", fmt_money),
        ("2. 运营支出 (税前)", "Opex Pre-tax", fmt_money),
        ("3. 电网充电成本 (税前)", "Grid Charge Cost", fmt_money),
        ("4. 资产置换", "Replacement", fmt_money),
        ("5. 残值回收 (税前)", "Salvage Pre-tax", fmt_money),
        ("", "", None),
        ("折旧税盾 (+)", "Tax Shield", fmt_money),
        ("成本抵税 (+)", "Opex Tax Benefit", fmt_money),
        ("残值缴税 (-)", "Salvage Tax", fmt_money),
        ("", "", None),
        ("=== 税后净成本流 ===", "Net Cost Flow (After-tax)", fmt_money),
        ("折现成本", "PV of Cost", fmt_money),
        ("累计折现分子", "Cum Numerator", fmt_money)
    ]
    
    for label, key, fmt in rows:
        worksheet.write(r, 0, label, fmt_sub if key=="" or "===" in label else workbook.add_format({'border':1}))
        if key and key in time_series_data:
            worksheet.write_row(r, 1, time_series_data[key], fmt)
        r += 1
        
    workbook.close()
    return output.getvalue()

# ==========================================
# 3. 模块 A: 光伏 + 储能 LCOE (修正逻辑版)
# ==========================================
def render_pv_ess_lcoe():
    st.markdown("## ☀️ 光伏+储能 LCOE (系统耦合逻辑)")
    st.info("逻辑修正：区分储能电力来源。若来自光伏，则扣除储能损耗，避免电量重复计算；若来自电网，则计入充电成本。")
    
    with st.container():
        st.markdown("### 1. 系统配置")
        # 增加电力来源选择
        charge_source = st.radio("🔋 储能电力来源 (Energy Source)", 
                                 ("来自光伏 (From PV)", "来自电网 (From Grid)"),
                                 horizontal=True)
        
        c1, c2, c3, c4 = st.columns(4)
        pv_cap = c1.number_input("光伏容量 (MW)", value=200.0)
        pv_hours = c2.number_input("光伏利用小时数 (h)", value=2200.0)
        ess_cap = c3.number_input("储能容量 (MWh)", value=120.0)
        ess_cycles = c4.number_input("储能年循环次数", value=365.0, help="光储一体化通常每日1充1放")
        
        t1, t2 = st.columns(2)
        ess_eff = t1.number_input("储能综合效率 RTE (%)", value=85.0)/100
        pv_deg = t2.number_input("光伏年衰减 (%)", value=0.5)/100
        
        # 如果来自电网，需要输入买电价格
        grid_charge_price = 0.0
        if charge_source == "来自电网 (From Grid)":
            st.markdown("##### 🔌 电网参数")
            grid_charge_price = st.number_input("谷时充电电价 (元/kWh)", value=0.20, help="作为LCOE的输入成本")
        
        st.markdown("---")
        st.markdown("### 2. 投资与运维")
        c1, c2, c3 = st.columns(3)
        capex_pv = c1.number_input("光伏投资 (万)", value=50000.0, step=100.0)
        capex_ess = c2.number_input("储能投资 (万)", value=10000.0, step=100.0)
        capex_grid = c3.number_input("配套投资 (万)", value=15000.0, step=100.0)
        
        o1, o2, o3 = st.columns(3)
        opex_r_pv = o1.number_input("光伏运维%", value=1.5)/100
        opex_r_ess = o2.number_input("储能运维%", value=3.0)/100
        opex_r_grid = o3.number_input("配套运维%", value=1.0)/100
        
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

    # --- Calculation Engine ---
    total_inv = capex_pv + capex_ess + capex_grid
    years = [0] + list(range(1, period + 1))
    
    ts = {k: [] for k in ["Year", "System Generation", "Discount Factor", "Discounted Gen Tax Adj", "Cum Denominator",
                          "Capex", "Opex Pre-tax", "Grid Charge Cost", "Replacement", "Salvage Pre-tax",
                          "Tax Shield", "Opex Tax Benefit", "Salvage Tax",
                          "Net Cost Flow (After-tax)", "PV of Cost", "Cum Numerator"]}
    
    # Init Year 0
    for k in ts: ts[k].append(0)
    ts["Year"][0] = 0
    ts["Discount Factor"][0] = 1.0
    ts["Capex"][0] = total_inv
    ts["Net Cost Flow (After-tax)"][0] = total_inv
    ts["PV of Cost"][0] = total_inv
    ts["Cum Numerator"][0] = total_inv
    
    annual_depr = total_inv / depr_years
    cum_denom = 0
    cum_num = total_inv
    salvage_val_pre = total_inv * salvage_rate

    for y in range(1, period + 1):
        ts["Year"].append(y)
        
        # === 关键逻辑修正：分母计算 ===
        deg_factor = 1 - (y-1) * pv_deg
        if deg_factor < 0: deg_factor = 0
        
        raw_pv_gen = pv_cap * pv_hours * deg_factor # 光伏原始发电
        ess_discharge = ess_cap * ess_cycles * ess_eff # 储能放电
        ess_charge_energy = ess_cap * ess_cycles # 储能需要充入的电量
        
        sys_gen = 0
        grid_charge_cost = 0
        
        if charge_source == "来自光伏 (From PV)":
            # 逻辑：总电量 = 光伏发电 - 充入储能的电 + 储能放出来的电
            # 也就等于：光伏发电 - 储能损耗
            # 损耗 = 充入 - 放出 = 充入 * (1 - eff)
            loss = ess_charge_energy * (1 - ess_eff)
            sys_gen = raw_pv_gen - loss
            grid_charge_cost = 0 # 没花钱买电
            
        else: # 来自电网
            # 逻辑：储能是独立电源，光伏是独立电源
            sys_gen = raw_pv_gen + ess_discharge
            # 成本增加：买电费
            grid_charge_cost = (ess_charge_energy * 1000 * grid_charge_price) / 10000
        
        ts["System Generation"].append(sys_gen)
        
        # 分母：税后电量 (Revenue Requirement Method)
        df = 1 / ((1+wacc)**y)
        ts["Discount Factor"].append(df)
        
        gen_tax_adj = sys_gen * (1 - tax_rate)
        g_npv = gen_tax_adj * df
        ts["Discounted Gen Tax Adj"].append(g_npv)
        cum_denom += g_npv
        ts["Cum Denominator"].append(cum_denom)
        
        # === 分子：税后成本 ===
        ts["Capex"].append(0)
        
        opex_pre = (capex_pv*opex_r_pv) + (capex_ess*opex_r_ess) + (capex_grid*opex_r_grid)
        ts["Opex Pre-tax"].append(opex_pre)
        ts["Grid Charge Cost"].append(grid_charge_cost)
        
        rep = rep_cost if y == rep_yr else 0
        ts["Replacement"].append(rep)
        
        sal_pre = -salvage_val_pre if y == period else 0
        ts["Salvage Pre-tax"].append(sal_pre)
        
        # 税务计算
        curr_depr = annual_depr if y <= depr_years else 0
        shield = curr_depr * tax_rate
        ts["Tax Shield"].append(shield) # 记录为正数以便查看
        
        opex_ben = (opex_pre + grid_charge_cost) * tax_rate
        ts["Opex Tax Benefit"].append(opex_ben)
        
        sal_tax = 0
        if y == period:
            sal_tax = sal_pre * tax_rate # 残值流入对应的税负(流出)
        ts["Salvage Tax"].append(sal_tax)
        
        # 税后净流出 = (Opex+Charge)*(1-T) + Rep + Sal_Pre - Shield + Sal_Tax
        # 简化写法： (Opex+Charge) - Benefit + Rep - Shield + Sal_Pre - Sal_Tax
        # 注意 Sal_Pre 是负数(流入)
        
        net_after = (opex_pre + grid_charge_cost - opex_ben) + rep - shield + (sal_pre - sal_tax)
        ts["Net Cost Flow (After-tax)"].append(net_after)
        
        c_npv = net_after * df
        ts["PV of Cost"].append(c_npv)
        cum_num += c_npv
        ts["Cum Numerator"].append(cum_num)
        
    lcoe = (cum_num / cum_denom) * 10 if cum_denom > 0 else 0
    
    st.markdown("---")
    st.markdown("### 📊 测算结果")
    c1, c2 = st.columns(2)
    c1.metric("PPA LCOE (含税)", f"{lcoe:.4f} 元/kWh", help="此价格已考虑：1.储能带来的电量损耗或充电成本 2.税盾收益")
    c2.metric("系统全生命周期总电量", f"{sum(ts['System Generation'])/10000:.2f} 亿kWh")
    
    with st.expander("📂 导出底稿"):
        excel = generate_professional_excel("PV_ESS_LCOE", {"Source": charge_source}, ts, {"LCOE": lcoe})
        st.download_button("📥 下载 Excel", excel, "PV_ESS_Pro_LCOE.xlsx")

# ==========================================
# 4. 燃气 LCOE (保持 v8.0)
# ==========================================
def render_gas_lcoe():
    st.markdown("## 🔥 燃气发电 LCOE")
    # ... (此处代码与 v8.0 相同，篇幅原因略，请直接保留原有的 Gas 模块代码) ...
    # 为保证完整性，简写如下：
    with st.container():
        c1,c2,c3 = st.columns(3)
        cap = c1.number_input("装机(MW)", 360.0)
        capex = c2.number_input("投资(万)", 60000.0)
        wacc = c3.number_input("WACC%", 8.0)/100
        c4,c5,c6 = st.columns(3)
        hr = c4.number_input("小时", 3000.0)
        rate = c5.number_input("热耗", 0.0095, format="%.4f")
        price = c6.number_input("气价", 60.0)
        opex = st.number_input("运维", 1200.0)
        f1,f2,f3 = st.columns(3)
        tax = f1.number_input("税率%", 25.0)/100
        depr = f2.number_input("折旧年", 20)
        per = int(f3.number_input("周期", 25))
        sal = st.number_input("残值%", 5.0)/100

    # ... Calc Logic Same as v8.0 ...
    # 建议直接复用 v8.0 的 gas 逻辑，未做改动
    st.info("燃气模块逻辑未变，沿用 Tax Shield + Unlocked Inputs")

# ==========================================
# 5. 储能 LCOS (保持 v8.0)
# ==========================================
def render_lcos():
    st.markdown("## 🔋 储能 LCOS")
    # ... (此处代码与 v8.0 相同，篇幅原因略) ...
    st.info("储能 LCOS 模块逻辑未变，沿用 Tax Shield + Unlocked Inputs")
    # 建议直接复用 v8.0 的 lcos 逻辑

# ==========================================
# 6. Main
# ==========================================
def main():
    st.sidebar.title("📌 投资测算工具")
    mode = st.sidebar.radio("模块", ("光伏+储能 LCOE", "燃气发电 LCOE", "储能 LCOS"))
    st.sidebar.info("v9.0 | Logic Fix: Energy Source")
    
    if mode == "光伏+储能 LCOE": render_pv_ess_lcoe()
    # 注意：实际部署时，请把 v8.0 的 render_gas_lcoe 和 render_lcos 完整复制过来
    elif mode == "燃气发电 LCOE": 
        # 这里为了演示方便，您可以把 v8.0 的函数体贴回来
        st.warning("请复用 v8.0 的燃气代码") 
    elif mode == "储能 LCOS": 
        st.warning("请复用 v8.0 的储能代码")

if __name__ == "__main__":
    main()
