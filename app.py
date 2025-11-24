import streamlit as st
import pandas as pd
import numpy as np
import io
import xlsxwriter

# --- 1. 全局配置 ---
st.set_page_config(page_title="新能源投资双轨测算 (WEMPR & Lazard)", layout="wide", page_icon="⚖️")

st.markdown("""
<style>
    .main {background-color: #FAFAFA;}
    h2 {color: #0F2948; border-bottom: 2px solid #1F4E79; padding-bottom: 10px;}
    .block-container {padding-top: 2rem;}
    div[data-testid="stMetric"] {
        background-color: #FFF; border: 1px solid #DDD; 
        border-radius: 8px; padding: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .big-font {font-size:18px !important; font-weight:bold;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 核心引擎：Excel 生成器 (双 Sheet)
# ==========================================
def generate_dual_excel(model_name, inputs, df_wempr, lcoe_wempr, df_lazard, price_lazard):
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    
    # --- 样式 ---
    fmt_head = workbook.add_format({'bold': True, 'bg_color': '#2F5597', 'font_color': 'white', 'border': 1, 'align': 'center'})
    fmt_sub = workbook.add_format({'bold': True, 'bg_color': '#D9E1F2', 'border': 1})
    fmt_num = workbook.add_format({'border': 1, 'num_format': '#,##0.00'})
    fmt_money = workbook.add_format({'border': 1, 'num_format': '#,##0'})
    fmt_res = workbook.add_format({'bold': True, 'bg_color': '#FFEB9C', 'border': 2, 'num_format': '0.0000', 'font_size': 12})
    
    # ================= Sheet 1: WEMPR Model =================
    ws1 = workbook.add_worksheet('WEMPR (Tech Cost)')
    
    # 1. Inputs
    ws1.write('A1', f"{model_name} - Technical Assumptions", workbook.add_format({'bold': True, 'font_size': 14}))
    r = 2
    for k, v in inputs.items():
        ws1.write(r, 0, k, fmt_sub)
        ws1.write(r, 1, v, fmt_num)
        r += 1
        
    # 2. Waterfall
    r += 2
    ws1.write(r, 0, "WEMPR Methodology (Pre-tax Project Cash Flow)", workbook.add_format({'bold': True}))
    r += 1
    
    cols1 = list(df_wempr.columns)
    ws1.write_row(r, 0, cols1, fmt_head)
    r += 1
    
    start_row = r + 1
    for _, row in df_wempr.iterrows():
        for c, val in enumerate(row):
            ws1.write(r, c, val, fmt_money if "Cost" in cols1[c] or "Invest" in cols1[c] else fmt_num)
        r += 1
    end_row = r
    
    # 3. Formula Calculation
    r += 2
    ws1.write(r, 0, "Total Discounted Cost (Sum)", fmt_sub)
    # Assume PV_Cost is last column
    col_cost = xlsxwriter.utility.xl_col_to_name(len(cols1)-1)
    ws1.write_formula(r, 1, f"=SUM({col_cost}{start_row}:{col_cost}{end_row})", fmt_money)
    
    r += 1
    ws1.write(r, 0, "Total Discounted Gen (Sum)", fmt_sub)
    # Assume PV_Gen is 2nd to last
    col_gen = xlsxwriter.utility.xl_col_to_name(len(cols1)-2)
    ws1.write_formula(r, 1, f"=SUM({col_gen}{start_row}:{col_gen}{end_row})", fmt_num)
    
    r += 2
    ws1.write(r, 0, "WEMPR LCOE (Result)", fmt_sub)
    ws1.write_formula(r, 1, f"=B{r-2}/B{r-1}*10", fmt_res) # *10 for unit conversion if needed, aligned with app logic

    # ================= Sheet 2: Lazard Model =================
    ws2 = workbook.add_worksheet('Lazard (Investor Price)')
    
    ws2.write('A1', "Lazard Methodology (Levered Equity Cash Flow)", workbook.add_format({'bold': True, 'font_size': 14}))
    
    r = 3
    cols2 = list(df_lazard.columns)
    ws2.write_row(r, 0, cols2, fmt_head)
    r += 1
    
    start_row_l = r + 1
    for _, row in df_lazard.iterrows():
        for c, val in enumerate(row):
            ws2.write(r, c, val, fmt_money if c > 0 else fmt_num)
        r += 1
    
    # Lazard Result Display
    r += 2
    ws2.write(r, 0, "Required PPA Price (Lazard)", fmt_sub)
    ws2.write(r, 1, price_lazard, fmt_res)
    ws2.write(r, 2, "Solver Target: Equity NPV = Initial Investment", workbook.add_format({'italic': True}))

    workbook.close()
    return output.getvalue()

# ==========================================
# 3. 计算逻辑函数
# ==========================================
def calculate_wempr(years, capex, opex, fuel_cost, generation, wacc, rep_year, rep_cost):
    """WEMPR: 纯技术成本，全投资现金流，WACC折现"""
    data = []
    for y in years:
        # I(t)
        it = capex if y == 0 else 0
        if y == rep_year: it += rep_cost
        
        # M(t) & F(t)
        mt = opex if y > 0 else 0
        ft = fuel_cost if y > 0 else 0
        
        # E(t)
        et = generation[y] if y < len(generation) else 0
        
        # Discount
        df = 1 / ((1 + wacc) ** y)
        
        total_cost = it + mt + ft
        pv_cost = total_cost * df
        pv_gen = et * df
        
        data.append({
            "Year": y,
            "Generation (MWh)": et,
            "Invest (It)": it,
            "O&M (Mt)": mt,
            "Fuel/Charge (Ft)": ft,
            "Total Cost": total_cost,
            "Discount Factor": df,
            "PV(Gen)": pv_gen,
            "PV(Cost)": pv_cost
        })
    
    df = pd.DataFrame(data)
    num = df["PV(Cost)"].sum()
    den = df["PV(Gen)"].sum()
    lcoe = (num / den) * 10 if den > 0 else 0
    return lcoe, df

def calculate_lazard(years, capex, opex, fuel_cost, generation, 
                     debt_ratio, cost_debt, cost_equity, tax_rate, depr_years, 
                     rep_year, rep_cost):
    """Lazard: 股东视角，倒算PPA价格，考虑税盾、还本付息"""
    
    # 1. 初始资金结构
    initial_investment = capex
    initial_debt = initial_investment * debt_ratio
    initial_equity = initial_investment * (1 - debt_ratio)
    
    # 2. 贷款计算 (简化：等额本金)
    loan_term = min(len(years)-1, 15) # 假设贷款15年或项目寿命
    annual_principal = initial_debt / loan_term if loan_term > 0 else 0
    
    # 3. 求解 PPA Price
    # 公式：Price = (Equity + NPV_Fixed_Outflows) / NPV_Effective_Gen
    # Equity Cash Flow = (Rev - Opex - Interest)*(1-T) + Depr*T - Principal - Augmentation
    # Separate Rev from Costs to solve for P algebraically
    
    npv_numerator_components = initial_equity
    npv_denominator_components = 0 # Will store NPV of Generation*(1-Tax)
    
    data = []
    debt_balance = initial_debt
    
    for y in years:
        if y == 0:
            data.append({"Year":0, "Equity Invest": initial_equity})
            continue
            
        # 运营成本
        mt = opex
        ft = fuel_cost
        rep = rep_cost if y == rep_year else 0
        
        # 发电量
        et = generation[y] if y < len(generation) else 0
        
        # 财务费用
        interest = debt_balance * cost_debt
        principal = annual_principal if y <= loan_term else 0
        debt_balance -= principal
        
        # 折旧 (简化直线)
        depr = initial_investment / depr_years if y <= depr_years else 0
        
        # 折现因子 (Equity Cost)
        df_e = 1 / ((1 + cost_equity) ** y)
        
        # === 分母构建: 收入部分的NPV系数 ===
        # Revenue contributes: Price * Et * (1 - Tax)
        # So denominator adds: Et * (1 - Tax) * DF
        term_gen = et * (1 - tax_rate) * df_e
        npv_denominator_components += term_gen
        
        # === 分子构建: 支出部分的NPV ===
        # Cost terms in FCFE: - [ (Opex+Fuel+Interest)*(1-T) - Depr*T + Principal + Replacement ]
        # Move negative costs to RHS (Numerator) -> They become positive requirements
        
        # 税后运营成本 (Opex+Fuel) * (1-T)
        cost_ops_after_tax = (mt + ft) * (1 - tax_rate)
        
        # 税后利息 Interest * (1-T)
        cost_int_after_tax = interest * (1 - tax_rate)
        
        # 税盾收益 (减项) Depr * T
        benefit_depr = depr * tax_rate
        
        # 刚性支出
        cost_principal = principal
        cost_rep = rep
        
        # Total Cash Requirement for this year
        year_req = cost_ops_after_tax + cost_int_after_tax + cost_principal + cost_rep - benefit_depr
        
        npv_numerator_components += year_req * df_e
        
        data.append({
            "Year": y,
            "Generation": et,
            "Opex": mt,
            "Fuel": ft,
            "Interest": interest,
            "Principal": principal,
            "Depreciation": depr,
            "Replacement": rep,
            "Required Cash Flow": year_req
        })
        
    # Calculate Price
    # Price * Denom = Numerator
    required_price = (npv_numerator_components / npv_denominator_components) * 10 if npv_denominator_components > 0 else 0
    
    df = pd.DataFrame(data)
    return required_price, df

# ==========================================
# 4. 通用渲染函数 (UI Layout)
# ==========================================
def render_model_ui(tech_name, show_storage_options=False, show_gas_options=False):
    st.markdown(f"## {tech_name} (WEMPR vs Lazard)")
    
    # --- Block 1: Physical & Costs (Common) ---
    with st.container():
        st.subheader("1. 物理与成本参数 (Common Inputs)")
        
        col1, col2, col3 = st.columns(3)
        
        # Dynamic Inputs based on Tech
        if show_storage_options:
            # PV + Storage
            c_source = col1.radio("储能电力来源", ("来自光伏", "来自电网"))
            cap_mw = col2.number_input("光伏容量 (MW)", 200.0)
            hours = col3.number_input("光伏小时数", 2200.0)
            cap_ess = col1.number_input("储能容量 (MWh)", 120.0)
            cycles = col2.number_input("循环次数", 365.0)
            eff = col3.number_input("效率 RTE%", 85.0)/100
            
            capex = st.number_input("总投资 (万)", 75000.0)
            opex = st.number_input("年总运维 (万)", 1200.0)
            
            # Derived Logic
            gen_list = []
            fuel_cost = 0 # Annual
            grid_p = 0
            if c_source == "来自电网":
                grid_p = st.number_input("电网充电价", 0.20)
                fuel_cost = (cap_ess * cycles * 1000 * grid_p) / 10000
            
            period = 25
            # Construct Generation Profile
            deg = 0.005
            for y in range(period + 1):
                if y == 0: gen_list.append(0)
                else:
                    raw_pv = cap_mw * hours * (1 - (y-1)*deg)
                    if c_source == "来自光伏":
                        loss = (cap_ess * cycles) * (1 - eff)
                        gen_list.append(raw_pv - loss)
                    else:
                        gen_list.append(raw_pv + (cap_ess * cycles * eff))
            
        elif show_gas_options:
            # Gas
            cap_mw = col1.number_input("装机 (MW)", 360.0)
            hours = col2.number_input("小时数", 3000.0)
            rate = col3.number_input("热耗 (GJ/kWh)", 0.0095, format="%.4f")
            price = col1.number_input("气价 (元/GJ)", 60.0)
            capex = col2.number_input("投资 (万)", 60000.0)
            opex = col3.number_input("固定运维 (万)", 1200.0)
            
            fuel_cost = (cap_mw * hours * 1000 * rate * price) / 10000
            period = 25
            gen_list = [0] + [cap_mw * hours] * period
            
        else:
            # LCOS
            cap_mwh = col1.number_input("容量 (MWh)", 200.0)
            cycles = col2.number_input("循环", 330.0)
            eff = col3.number_input("效率%", 85.0)/100
            capex = col1.number_input("投资 (万)", 25000.0)
            opex = col2.number_input("运维 (万)", 500.0) # Simplified Opex input
            charge_p = col3.number_input("充电价", 0.20)
            
            charge_cost = (cap_mwh * cycles * 1000 * charge_p) / 10000
            fuel_cost = charge_cost # Map to fuel
            
            period = 15
            gen_list = [0] + [cap_mwh * cycles * eff] * period # Discharge

    # --- Block 2: Financial Structure (The Split) ---
    st.markdown("---")
    st.subheader("2. 财务与融资参数 (The Split)")
    
    c1, c2 = st.columns(2)
    
    with c1:
        st.markdown("#### 📘 WEMPR 参数 (Tech)")
        st.info("仅需全投资 WACC，不考虑税务与融资结构。")
        wacc_input = st.number_input("项目全投资 WACC (%)", value=7.0, step=0.1) / 100
        
    with c2:
        st.markdown("#### 🏛️ Lazard 参数 (Finance)")
        st.info("需要详细的资本结构来倒算 PPA。")
        col_a, col_b = st.columns(2)
        debt_ratio = col_a.number_input("债权比例 (%)", 60.0) / 100
        cost_debt = col_b.number_input("债务利率 (%)", 5.0) / 100
        cost_equity = col_a.number_input("股权成本/IRR (%)", 12.0) / 100
        tax_rate = col_b.number_input("所得税率 (%)", 25.0) / 100
        depr_years = st.number_input("折旧年限 (Macrs)", value=min(period, 20))
    
    # --- Block 3: Lifecycle ---
    st.markdown("---")
    st.subheader("3. 资产置换 (Augmentation/Replacement)")
    aug_yr = st.number_input("置换/增容年份", 10)
    aug_cost = st.number_input("置换/增容成本 (万)", 5000.0)

    # ================= Calculation =================
    
    # 1. Run WEMPR
    wempr_lcoe, df_wempr = calculate_wempr(
        range(period + 1), capex, opex, fuel_cost, gen_list, 
        wacc_input, aug_yr, aug_cost
    )
    
    # 2. Run Lazard
    lazard_price, df_lazard = calculate_lazard(
        range(period + 1), capex, opex, fuel_cost, gen_list,
        debt_ratio, cost_debt, cost_equity, tax_rate, depr_years,
        aug_yr, aug_cost
    )
    
    # ================= Output =================
    st.markdown("---")
    st.markdown("### 📊 最终测算结果对比")
    
    m1, m2, m3 = st.columns(3)
    
    m1.metric("📘 WEMPR LCOE (技术成本)", f"{wempr_lcoe:.4f}", 
              help="基于 WEMPR 2020 公式：全生命周期总成本折现 / 总发电量折现。不含税，不分债股。")
    
    m2.metric("🏛️ Lazard Price (投资者报价)", f"{lazard_price:.4f}", 
              help="基于 Lazard v18.0 逻辑：为了满足股权回报率(IRR)，考虑税盾、利息抵税后，倒算出的PPA电价。",
              delta=f"{lazard_price - wempr_lcoe:.4f} (差异)", delta_color="inverse")
              
    m3.metric("隐含加权成本 (Implied WACC)", f"{debt_ratio*cost_debt*(1-tax_rate) + (1-debt_ratio)*cost_equity:.1%}",
              help="Lazard 模型的等效税后 WACC")

    # Export
    inputs_dict = {
        "Total Capex": capex, "Annual Opex": opex, "Annual Fuel/Charge": fuel_cost,
        "WEMPR WACC": wacc_input, 
        "Lazard D/E": f"{debt_ratio}/{1-debt_ratio}", "Cost Equity": cost_equity, "Tax Rate": tax_rate
    }
    
    excel_data = generate_dual_excel(f"{tech_name}_Dual", inputs_dict, df_wempr, wempr_lcoe, df_lazard, lazard_price)
    st.download_button(f"📥 导出双轨底稿 ({tech_name})", excel_data, f"{tech_name}_Dual_Model.xlsx")

# ==========================================
# 5. 主程序路由
# ==========================================
def main():
    st.sidebar.title("Dual-Track LCOE Model")
    mode = st.sidebar.radio("Select Module", ("光伏+储能", "燃气发电", "储能 LCOS"))
    
    if mode == "光伏+储能":
        render_model_ui("PV_Storage", show_storage_options=True)
    elif mode == "燃气发电":
        render_model_ui("Gas_Power", show_gas_options=True)
    elif mode == "储能 LCOS":
        render_model_ui("Standalone_LCOS")

if __name__ == "__main__":
    main()
