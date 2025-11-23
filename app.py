import streamlit as st
import pandas as pd
import numpy as np
import io
import xlsxwriter

# --- 1. 全局配置与样式 ---
st.set_page_config(page_title="新能源项目 LCOE 测算模型 (Tax Shield版)", layout="wide", page_icon="⚖️")

st.markdown("""
<style>
    .main {background-color: #FAFAFA;}
    h1 {color: #0F2948; font-family: 'Helvetica Neue', sans-serif;}
    h2 {color: #1F4E79; border-bottom: 2px solid #1F4E79; padding-bottom: 10px; font-size: 24px;}
    h3 {color: #2F5597; font-size: 18px; margin-top: 20px;}
    .block-container {padding-top: 2rem;}
    section[data-testid="stSidebar"] {background-color: #F0F2F6;}
    div[data-testid="stMetric"] {
        background-color: #FFFFFF; padding: 15px; border-radius: 8px; 
        border: 1px solid #E6E6E6; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 核心引擎：Excel 生成器 (含税务列)
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
    
    # 输入假设
    worksheet.write('A1', f"{model_name} - 关键假设 (Key Assumptions)", fmt_title)
    row = 2
    for k, v in inputs.items():
        worksheet.write(row, 0, k, fmt_sub)
        worksheet.write(row, 1, v, fmt_num)
        row += 1
        
    # 时间轴
    row += 2
    worksheet.write(row, 0, "现金流模型 (Cash Flow Waterfall)", fmt_title)
    row += 1
    
    headers = ["Project Year"] + [f"Year {y}" for y in time_series_data["Year"]]
    worksheet.write_row(row, 0, headers, fmt_header)
    row += 1
    
    map_rows = [
        ("发电量 (MWh)", "Generation", fmt_num),
        ("折现系数", "Discount Factor", fmt_num),
        ("累计折现电量 (含税调整)", "Cum Discounted Gen (Tax Adj)", fmt_num),
        ("", "", None),
        ("1. 初始投资 (Capex)", "Capex", fmt_money),
        ("2. 运营支出 (Opex - 税前)", "Opex Pre-tax", fmt_money),
        ("3. 燃料/充电 (税前)", "Fuel/Charge Pre-tax", fmt_money),
        ("4. 资产置换 (Capex)", "Replacement", fmt_money),
        ("5. 残值回收 (税后)", "Salvage After-tax", fmt_money),
        ("", "", None),
        ("--- 税务调节科目 ---", "", None),
        ("折旧 (D&A)", "Depreciation", fmt_money),
        ("税盾效应 (抵扣)", "Tax Shield", fmt_money),
        ("Opex抵税 (抵扣)", "Opex Tax Benefit", fmt_money),
        ("", "", None),
        ("=== 调整后净现金流 ===", "Net Cash Flow (Adjusted)", fmt_money),
        ("折现成本流", "PV of Cost", fmt_money),
        ("累计折现成本", "Cum PV of Cost", fmt_money),
    ]
    
    for label, key, fmt in map_rows:
        worksheet.write(row, 0, label, fmt_sub if key=="" or "---" in label or "===" in label else workbook.add_format({'border':1}))
        if key and key in time_series_data:
            worksheet.write_row(row, 1, time_series_data[key], fmt)
        row += 1
        
    workbook.close()
    return output.getvalue()

# ==========================================
# 3. 模块 A: 光伏 + 储能 LCOE (含税版)
# ==========================================
def render_pv_ess_lcoe():
    st.markdown("## ☀️ 光伏+储能 LCOE (含税盾 Tax Shield)")
    
    with st.container():
        # Block 1
        st.markdown("### 1. 基础规模")
        c1, c2, c3, c4 = st.columns(4)
        pv_cap = c1.number_input("光伏容量 (MW)", 200.0)
        pv_hours = c2.number_input("年利用小时数 (h)", 2200.0)
        ess_cap = c3.number_input("储能容量 (MWh)", 120.0)
        ess_cycles = c4.number_input("年循环次数", 1000.0)
        ess_eff = 0.85 # 简化显示，默认85%

        st.markdown("---")
        # Block 2
        st.markdown("### 2. 投资与运维")
        c1, c2, c3 = st.columns(3)
        capex_pv = c1.number_input("光伏总投资 (万)", 50000.0)
        capex_ess = c2.number_input("储能总投资 (万)", 10000.0)
        capex_grid = c3.number_input("电网配套投资 (万)", 15000.0)
        
        st.caption("运维费率(%)")
        o1, o2, o3 = st.columns(3)
        opex_r_pv = o1.number_input("光伏Opex%", 1.5)/100
        opex_r_ess = o2.number_input("储能Opex%", 3.0)/100
        opex_r_grid = o3.number_input("配套Opex%", 1.0)/100

        st.markdown("---")
        # Block 3: 税务与财务核心
        st.markdown("### 3. 税务与财务参数 (Tax & Finance)")
        col_tax, col_fin = st.columns(2)
        
        with col_tax:
            tax_rate = st.number_input("企业所得税率 (%)", value=25.0, help="中国/澳洲通常25%-30%") / 100
            depr_years = st.number_input("折旧年限 (年)", value=20, help="计算税盾使用，通常短于项目寿命")
            
        with col_fin:
            wacc = st.number_input("折现率 WACC (%)", value=8.0) / 100
            period = int(st.number_input("项目运营周期 (年)", value=25))

        # LCM
        st.markdown("---")
        st.markdown("### 4. 资产置换与残值")
        l1, l2, l3 = st.columns(3)
        rep_year = l1.number_input("电池更换年份", 10)
        rep_cost = l2.number_input("更换开支 (万)", 5000.0)
        salvage_rate = l3.number_input("期末综合残值率 (%)", 5.0) / 100

    # --- 计算逻辑 (Tax Logic) ---
    years = [0] + list(range(1, period + 1))
    ts = {k: [] for k in ["Year", "Generation", "Discount Factor", 
                          "Capex", "Opex Pre-tax", "Fuel/Charge Pre-tax", "Replacement", "Salvage After-tax",
                          "Depreciation", "Tax Shield", "Opex Tax Benefit",
                          "Net Cash Flow (Adjusted)", "PV of Cost", "Cum PV of Cost", 
                          "Discounted Gen", "Cum Discounted Gen (Tax Adj)"]}
    
    total_inv = capex_pv + capex_ess + capex_grid
    salvage_val_pretax = total_inv * salvage_rate
    
    # 简单的直线折旧法
    annual_depr = total_inv / depr_years
    
    # Year 0
    for k in ts: ts[k].append(0)
    ts["Year"][0] = 0
    ts["Discount Factor"][0] = 1.0
    ts["Capex"][0] = total_inv
    ts["Net Cash Flow (Adjusted)"][0] = total_inv
    ts["PV of Cost"][0] = total_inv
    ts["Cum PV of Cost"][0] = total_inv
    
    cum_gen_tax_adj = 0
    cum_cost = total_inv
    
    for y in range(1, period + 1):
        ts["Year"].append(y)
        
        # 1. 发电 (分母)
        degrade = 1 - (y-1)*0.005
        gen = (pv_cap * pv_hours * degrade) + (ess_cap * ess_cycles * ess_eff)
        ts["Generation"].append(gen)
        
        df = 1 / ((1 + wacc) ** y)
        ts["Discount Factor"].append(df)
        
        # 分母调整：Generation * (1 - Tax Rate)
        # 含义：为了支付1块钱的税后成本，你需要赚取 1/(1-T) 的税前收入。
        # LCOE 公式变化： NPV(Costs_After_Tax) / NPV(Gen * (1-T))
        gen_tax_adj = gen * (1 - tax_rate)
        g_npv = gen_tax_adj * df
        ts["Discounted Gen"].append(g_npv)
        cum_gen_tax_adj += g_npv
        ts["Cum Discounted Gen (Tax Adj)"].append(cum_gen_tax_adj)
        
        # 2. 成本 (分子)
        ts["Capex"].append(0)
        
        # Opex
        opex_pre = (capex_pv*opex_r_pv) + (capex_ess*opex_r_ess) + (capex_grid*opex_r_grid)
        ts["Opex Pre-tax"].append(opex_pre)
        ts["Fuel/Charge Pre-tax"].append(0)
        
        # 税务科目
        # A. Opex 抵税
        opex_benefit = opex_pre * tax_rate 
        ts["Opex Tax Benefit"].append(-opex_benefit) # 负数代表减少流出
        
        # B. 折旧税盾
        curr_depr = annual_depr if y <= depr_years else 0
        ts["Depreciation"].append(curr_depr)
        tax_shield = curr_depr * tax_rate
        ts["Tax Shield"].append(-tax_shield) # 负数代表减少流出
        
        # 置换
        rep = rep_cost if y == rep_year else 0
        ts["Replacement"].append(rep)
        
        # 残值 (税后) -> 假设处置收益全额缴税
        # Salvage Inflow = Val - (Val - 0)*Tax = Val * (1-T)
        sal = 0
        if y == period:
            sal = -(salvage_val_pretax * (1 - tax_rate))
        ts["Salvage After-tax"].append(sal)
        
        # 净现金流 (Net Cost Flow)
        # = Opex + Replacement - Opex_Benefit - Tax_Shield - Salvage
        net = opex_pre + rep - opex_benefit - tax_shield + sal
        ts["Net Cash Flow (Adjusted)"].append(net)
        
        c_npv = net * df
        ts["PV of Cost"].append(c_npv)
        cum_cost += c_npv
        ts["Cum PV of Cost"].append(cum_cost)
        
    lcoe = (cum_cost / cum_gen_tax_adj) * 10 if cum_gen_tax_adj > 0 else 0
    
    st.markdown("---")
    st.markdown("### 📊 测算结果 (Tax Adjusted)")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("PPA LCOE (含税报价)", f"{lcoe:.4f} 元/kWh", delta="需以此价格报价以满足回报")
    c2.metric("税盾贡献", f"{(sum(ts['Tax Shield'])/period):,.0f} 万/年")
    c3.metric("折旧年限", f"{depr_years} 年")

    with st.expander("📂 查看税务底稿 (Tax Waterfall)"):
        st.dataframe(pd.DataFrame(ts).set_index("Year").T, use_container_width=True)
        excel = generate_professional_excel("PV_ESS_LCOE_Tax", {"Tax Rate": tax_rate, "Depr Years": depr_years}, ts, {"LCOE": lcoe})
        st.download_button("📥 导出含税模型底稿", excel, "PV_ESS_Tax_LCOE.xlsx")

# ==========================================
# 4. 模块 B: 燃气 LCOE (含税版)
# ==========================================
def render_gas_lcoe():
    st.markdown("## 🔥 燃气发电 LCOE (含税盾 Tax Shield)")
    
    with st.container():
        st.markdown("### 1. 规模与投资")
        c1, c2, c3 = st.columns(3)
        gas_cap = c1.number_input("装机 (MW)", 360.0)
        gas_capex = c2.number_input("投资 (万)", 60000.0)
        wacc = c3.number_input("WACC (%)", 8.0)/100
        
        st.markdown("---")
        st.markdown("### 2. 运营与燃料")
        c1, c2, c3 = st.columns(3)
        hours = c1.number_input("小时数", 3000.0)
        heat_rate = c2.number_input("热耗 (GJ/kWh)", 0.0095, format="%.4f")
        price = c3.number_input("气价 (元/GJ)", 60.0)
        fixed_opex = st.number_input("固定运维 (万/年)", 1200.0)

        st.markdown("---")
        st.markdown("### 3. 税务参数")
        t1, t2 = st.columns(2)
        tax_rate = t1.number_input("所得税率 (%)", 25.0)/100
        depr_years = t2.number_input("折旧年限", 20)
        period = 25

    # Calc
    years = [0] + list(range(1, period + 1))
    ts = {k: [] for k in ["Year", "Generation", "Discount Factor", 
                          "Capex", "Opex Pre-tax", "Fuel/Charge Pre-tax", "Replacement", "Salvage After-tax",
                          "Depreciation", "Tax Shield", "Opex Tax Benefit",
                          "Net Cash Flow (Adjusted)", "PV of Cost", "Cum PV of Cost", 
                          "Discounted Gen", "Cum Discounted Gen (Tax Adj)"]}
    
    for k in ts: ts[k].append(0)
    ts["Year"][0] = 0
    ts["Discount Factor"][0] = 1.0
    ts["Capex"][0] = gas_capex
    ts["Net Cash Flow (Adjusted)"][0] = gas_capex
    ts["PV of Cost"][0] = gas_capex
    ts["Cum PV of Cost"][0] = gas_capex
    
    annual_gen = gas_cap * hours
    fuel_cost = (annual_gen * 1000 * heat_rate * price) / 10000
    annual_depr = gas_capex / depr_years
    sal_val = gas_capex * 0.05 # 默认5%残值
    
    cum_gen_tax = 0
    cum_cost = gas_capex
    
    for y in range(1, period + 1):
        ts["Year"].append(y)
        ts["Generation"].append(annual_gen)
        
        df = 1 / ((1 + wacc) ** y)
        ts["Discount Factor"].append(df)
        
        gen_tax = annual_gen * (1 - tax_rate)
        g_npv = gen_tax * df
        ts["Discounted Gen"].append(g_npv)
        cum_gen_tax += g_npv
        ts["Cum Discounted Gen (Tax Adj)"].append(cum_gen_tax)
        
        ts["Capex"].append(0)
        ts["Opex Pre-tax"].append(fixed_opex)
        ts["Fuel/Charge Pre-tax"].append(fuel_cost)
        
        # 税盾
        curr_depr = annual_depr if y <= depr_years else 0
        ts["Depreciation"].append(curr_depr)
        
        tax_shield = curr_depr * tax_rate
        ts["Tax Shield"].append(-tax_shield)
        
        opex_ben = (fixed_opex + fuel_cost) * tax_rate
        ts["Opex Tax Benefit"].append(-opex_ben)
        
        ts["Replacement"].append(0)
        
        sal = -(sal_val * (1 - tax_rate)) if y == period else 0
        ts["Salvage After-tax"].append(sal)
        
        # Net = Opex + Fuel - Opex_Ben - Shield + Sal
        net = fixed_opex + fuel_cost - opex_ben - tax_shield + sal
        ts["Net Cash Flow (Adjusted)"].append(net)
        
        c_npv = net * df
        ts["PV of Cost"].append(c_npv)
        cum_cost += c_npv
        ts["Cum PV of Cost"].append(cum_cost)
        
    lcoe = (cum_cost / cum_gen_tax) * 10 if cum_gen_tax > 0 else 0
    
    st.markdown("---")
    st.markdown("### 📊 测算结果")
    k1, k2 = st.columns(2)
    k1.metric("LCOE (含税)", f"{lcoe:.4f}")
    k2.metric("年均税盾抵扣", f"{(sum(ts['Tax Shield'])/period):,.0f} 万")
    
    with st.expander("📂 税务底稿"):
        st.dataframe(pd.DataFrame(ts).set_index("Year").T, use_container_width=True)
        excel = generate_professional_excel("Gas_LCOE_Tax", {"Tax": tax_rate}, ts, {"LCOE": lcoe})
        st.download_button("📥 导出", excel, "Gas_Tax_LCOE.xlsx")

# ==========================================
# 5. 模块 C: 储能 LCOS (含税版)
# ==========================================
def render_lcos():
    st.markdown("## 🔋 储能 LCOS (含税盾 Tax Shield)")
    
    with st.container():
        st.markdown("### 1. 规模与投资")
        c1, c2 = st.columns(2)
        ess_cap = c1.number_input("容量 (MWh)", 200.0)
        capex = c2.number_input("总投资 (万)", 25000.0)
        
        st.markdown("### 2. 运营与充电")
        c1, c2, c3 = st.columns(3)
        charge_p = c1.number_input("充电价 (元/kWh)", 0.2)
        opex_r = c2.number_input("运维%", 2.0)/100
        cycles = c3.number_input("年循环", 330.0)
        
        st.markdown("### 3. 税务")
        t1, t2 = st.columns(2)
        tax_rate = t1.number_input("税率%", 25.0)/100
        depr_years = t2.number_input("折旧年", 15)
        
        wacc = 0.08
        period = 15
        rep_yr = 8
        rep_cost = 10000.0

    # Calc
    years = [0] + list(range(1, period + 1))
    ts = {k: [] for k in ["Year", "Generation", "Discount Factor", 
                          "Capex", "Opex Pre-tax", "Fuel/Charge Pre-tax", "Replacement", "Salvage After-tax",
                          "Depreciation", "Tax Shield", "Opex Tax Benefit",
                          "Net Cash Flow (Adjusted)", "PV of Cost", "Cum PV of Cost", 
                          "Discounted Gen", "Cum Discounted Gen (Tax Adj)"]}
    
    for k in ts: ts[k].append(0)
    ts["Year"][0] = 0
    ts["Discount Factor"][0] = 1.0
    ts["Capex"][0] = capex
    ts["Net Cash Flow (Adjusted)"][0] = capex
    ts["PV of Cost"][0] = capex
    ts["Cum PV of Cost"][0] = capex
    
    annual_depr = capex / depr_years
    cum_gen = 0
    cum_cost = capex
    
    for y in range(1, period + 1):
        ts["Year"].append(y)
        
        curr_cap = ess_cap * ((1-0.02)**(y-1))
        dis = curr_cap * cycles * 0.85
        ts["Generation"].append(dis)
        
        df = 1 / ((1+wacc)**y)
        ts["Discount Factor"].append(df)
        
        # 分母调整
        gen_tax = dis * (1 - tax_rate)
        g_npv = gen_tax * df
        ts["Discounted Gen"].append(g_npv)
        cum_gen += g_npv
        ts["Cum Discounted Gen (Tax Adj)"].append(cum_gen)
        
        ts["Capex"].append(0)
        opex = capex * opex_r
        ts["Opex Pre-tax"].append(opex)
        
        charge = (curr_cap * cycles * 1000 * charge_p) / 10000
        ts["Fuel/Charge Pre-tax"].append(charge)
        
        # 税盾
        curr_depr = annual_depr if y <= depr_years else 0
        ts["Depreciation"].append(curr_depr)
        
        shield = curr_depr * tax_rate
        ts["Tax Shield"].append(-shield)
        
        opex_ben = (opex + charge) * tax_rate
        ts["Opex Tax Benefit"].append(-opex_ben)
        
        rep = rep_cost if y == rep_yr else 0
        ts["Replacement"].append(rep)
        
        sal = 0 # 简化不含残值
        ts["Salvage After-tax"].append(0)
        
        net = opex + charge + rep - shield - opex_ben
        ts["Net Cash Flow (Adjusted)"].append(net)
        
        c_npv = net * df
        ts["PV of Cost"].append(c_npv)
        cum_cost += c_npv
        ts["Cum PV of Cost"].append(cum_cost)
        
    lcos = (cum_cost / cum_gen) * 10 if cum_gen > 0 else 0
    
    st.markdown("---")
    st.metric("LCOS (含税)", f"{lcos:.4f}")
    
    with st.expander("📂 导出"):
        excel = generate_professional_excel("ESS_LCOS_Tax", {"Tax": tax_rate}, ts, {"LCOS": lcos})
        st.download_button("📥 导出", excel, "ESS_Tax_LCOS.xlsx")

# ==========================================
# 6. 主程序
# ==========================================
def main():
    st.sidebar.title("📌 新能源投资测算")
    mode = st.sidebar.radio("模块", ("光伏+储能 LCOE", "燃气发电 LCOE", "储能 LCOS"))
    st.sidebar.info("v5.0 | Tax Shield Added")
    
    if mode == "光伏+储能 LCOE": render_pv_ess_lcoe()
    elif mode == "燃气发电 LCOE": render_gas_lcoe()
    elif mode == "储能 LCOS": render_lcos()

if __name__ == "__main__":
    main()
