import streamlit as st
import pandas as pd
import numpy as np
import io
import xlsxwriter

# --- 1. 全局配置 ---
st.set_page_config(page_title="新能源投资测算 (v16.0 Hybrid)", layout="wide", page_icon="💼")

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
# 2. 核心引擎：Excel 混合生成器 (Hardcode Data + Formula Result)
# ==========================================
def generate_hybrid_excel(model_name, inputs, df_wempr, lcoe_wempr, df_lazard, price_lazard):
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    
    # --- 样式 ---
    fmt_head = workbook.add_format({'bold': True, 'bg_color': '#2F5597', 'font_color': 'white', 'border': 1, 'align': 'center'})
    fmt_sub = workbook.add_format({'bold': True, 'bg_color': '#D9E1F2', 'border': 1})
    fmt_num = workbook.add_format({'border': 1, 'num_format': '#,##0.00'})
    fmt_money = workbook.add_format({'border': 1, 'num_format': '#,##0'})
    # 结果单元格样式：黄色背景，突出显示
    fmt_res = workbook.add_format({'bold': True, 'bg_color': '#FFFF00', 'border': 2, 'num_format': '0.0000', 'font_size': 12})
    
    # --- 辅助函数：清洗数据防止报错 ---
    def clean_df(df):
        return df.fillna(0).replace([np.inf, -np.inf], 0)

    df_w = clean_df(df_wempr)
    df_l = clean_df(df_lazard)

    # ================= Sheet 1: WEMPR (Technical) =================
    ws1 = workbook.add_worksheet('WEMPR (Tech)')
    
    # 1. Inputs
    ws1.write('A1', f"{model_name} - Technical Assumptions", workbook.add_format({'bold': True, 'font_size': 14}))
    r = 2
    for k, v in inputs.items():
        ws1.write(r, 0, k, fmt_sub)
        # 简单的类型检查
        val = v if isinstance(v, (int, float, str)) else str(v)
        ws1.write(r, 1, val, fmt_num if isinstance(val, (int, float)) else None)
        r += 1
        
    # 2. Data Table (Hardcoded Values)
    r += 2
    ws1.write(r, 0, "Cash Flow Table (Hardcoded Values)", workbook.add_format({'bold': True}))
    r += 1
    
    cols1 = list(df_w.columns)
    ws1.write_row(r, 0, cols1, fmt_head)
    r += 1
    
    start_row = r + 1
    for _, row in df_w.iterrows():
        for c, val in enumerate(row):
            ws1.write(r, c, val, fmt_money if "Cost" in cols1[c] or "Invest" in cols1[c] else fmt_num)
        r += 1
    end_row = r
    
    # 3. Summary Formulas (The "Live" Part)
    r += 2
    ws1.write(r, 0, ">>> 汇总计算 (Excel Formulas)", fmt_sub)
    
    # 找到 PV(Cost) 和 PV(Gen) 的列索引
    try:
        idx_cost = cols1.index("PV(Cost)")
        idx_gen = cols1.index("PV(Gen)")
        
        col_char_cost = xlsxwriter.utility.xl_col_to_name(idx_cost)
        col_char_gen = xlsxwriter.utility.xl_col_to_name(idx_gen)
        
        # 写入 SUM 公式
        ws1.write(r, idx_cost, "Total Cost:", fmt_sub)
        ws1.write_formula(r, idx_cost + 1, f"=SUM({col_char_cost}{start_row}:{col_char_cost}{end_row})", fmt_money)
        
        ws1.write(r+1, idx_cost, "Total Gen:", fmt_sub)
        ws1.write_formula(r+1, idx_cost + 1, f"=SUM({col_char_gen}{start_row}:{col_char_gen}{end_row})", fmt_num)
        
        ws1.write(r+2, idx_cost, "LCOE:", fmt_sub)
        # LCOE Formula: Cost / Gen * 10
        cell_cost_sum = xlsxwriter.utility.xl_rowcol_to_cell(r, idx_cost + 1)
        cell_gen_sum = xlsxwriter.utility.xl_rowcol_to_cell(r+1, idx_cost + 1)
        ws1.write_formula(r+2, idx_cost + 1, f"={cell_cost_sum}/{cell_gen_sum}*10", fmt_res)
        
    except ValueError:
        pass # 如果列名不对，跳过公式生成

    # ================= Sheet 2: Lazard (Financial) =================
    ws2 = workbook.add_worksheet('Lazard (Investor)')
    ws2.write('A1', "Lazard Investor View (Levered Cash Flow)", workbook.add_format({'bold': True, 'font_size': 14}))
    
    r = 3
    cols2 = list(df_l.columns)
    ws2.write_row(r, 0, cols2, fmt_head)
    r += 1
    
    start_row = r + 1
    for _, row in df_l.iterrows():
        for c, val in enumerate(row):
            ws2.write(r, c, val, fmt_money if c > 0 else fmt_num)
        r += 1
    end_row = r
    
    # Formula for Lazard Price
    # Price = NPV(Required Cash) / NPV(Gen_After_Tax)
    try:
        idx_req = cols2.index("Required Cash Flow")
        idx_gen_tax = cols2.index("Discounted Gen(1-T)")
        
        col_char_req = xlsxwriter.utility.xl_col_to_name(idx_req)
        col_char_gen = xlsxwriter.utility.xl_col_to_name(idx_gen_tax)
        
        r += 2
        ws2.write(r, 0, "Total Required Equity Cash (PV):", fmt_sub)
        ws2.write_formula(r, 1, f"=SUM({col_char_req}{start_row}:{col_char_req}{end_row})", fmt_money)
        
        ws2.write(r+1, 0, "Total Effective Gen (PV):", fmt_sub)
        ws2.write_formula(r+1, 1, f"=SUM({col_char_gen}{start_row}:{col_char_gen}{end_row})", fmt_num)
        
        ws2.write(r+2, 0, "Lazard Required Price:", fmt_sub)
        cell_req_sum = "B" + str(r+1)
        cell_gen_sum = "B" + str(r+2)
        ws2.write_formula(r+2, 1, f"={cell_req_sum}/{cell_gen_sum}*10", fmt_res)
        
    except ValueError:
        pass

    workbook.close()
    return output.getvalue()

# ==========================================
# 3. 计算引擎 (Python Logic)
# ==========================================
def calc_wempr(years, capex, opex, fuel, gen_list, wacc, rep_yr, rep_cost, salvage_rate):
    # 纯技术模型：全投资，无税，无债
    data = []
    salvage_val = capex * salvage_rate
    
    for y in years:
        it = capex if y == 0 else 0
        if y == rep_yr: it += rep_cost
        
        mt = opex if y > 0 else 0
        ft = fuel if y > 0 else 0
        et = gen_list[y] if y < len(gen_list) else 0
        
        # 残值作为负成本
        sal = -salvage_val if y == years[-1] else 0
        
        total_cost = it + mt + ft + sal
        df = 1 / ((1 + wacc) ** y)
        
        data.append({
            "Year": y,
            "Generation": et,
            "Capex": it,
            "Opex": mt,
            "Fuel": ft,
            "Salvage": sal,
            "Total Cost": total_cost,
            "DF": df,
            "PV(Gen)": et * df,
            "PV(Cost)": total_cost * df
        })
    
    df = pd.DataFrame(data)
    lcoe = (df["PV(Cost)"].sum() / df["PV(Gen)"].sum()) * 10 if df["PV(Gen)"].sum() > 0 else 0
    return lcoe, df

def calc_lazard(years, capex, opex, fuel, gen_list, 
                debt_ratio, cost_debt, cost_equity, tax_rate, depr_years, 
                rep_yr, rep_cost, salvage_rate):
    # 财务模型：股权视角，含税，含债
    
    initial_debt = capex * debt_ratio
    initial_equity = capex * (1 - debt_ratio)
    
    # 贷款偿还模拟 (等额本金)
    loan_term = min(len(years)-1, 15)
    principal_per_year = initial_debt / loan_term if loan_term > 0 else 0
    
    debt_bal = initial_debt
    salvage_val = capex * salvage_rate
    
    data = []
    
    for y in years:
        if y == 0:
            data.append({
                "Year": 0, "Required Cash Flow": initial_equity, "Discounted Gen(1-T)": 0,
                "Generation":0, "Interest":0, "Principal":0, "Tax Shield":0
            })
            continue
            
        et = gen_list[y] if y < len(gen_list) else 0
        
        # 1. 运营流 (税后)
        ops_cost = (opex + fuel) * (1 - tax_rate)
        
        # 2. 债务流
        interest = debt_bal * cost_debt
        principal = principal_per_year if y <= loan_term else 0
        debt_bal -= principal
        if debt_bal < 0: debt_bal = 0
        
        # 利息抵税后的实际支付
        int_after_tax = interest * (1 - tax_rate)
        
        # 3. 税盾 (非现金流入)
        # 假设直线折旧
        depr = capex / depr_years if y <= depr_years else 0
        shield = depr * tax_rate
        
        # 4. 置换与残值
        rep = rep_cost if y == rep_yr else 0
        # 残值流入需缴税，故抵扣成本 = Sal * (1-T)
        sal_benefit = 0
        if y == years[-1]:
            sal_benefit = salvage_val * (1 - tax_rate)
            
        # === 股权视角的年度资金需求 (Required Revenue) ===
        # 逻辑：为了让 Equity NPV=0，当年的收入(税后)必须覆盖所有支出(税后)
        # Req_Rev * (1-T) = Ops(1-T) + Int(1-T) + Principal + Rep - Shield - Sal_Benefit
        # 移项得：
        # Year_Req_Cash (分子) = Ops(1-T) + Int(1-T) + Principal + Rep - Shield - Sal_Benefit
        # Discounted Gen (分母) = Et * (1-T) * DF
        
        req_cash = ops_cost + int_after_tax + principal + rep - shield - sal_benefit
        
        df_e = 1 / ((1 + cost_equity) ** y)
        
        # 分母项
        denom_term = et * (1 - tax_rate) * df_e
        
        data.append({
            "Year": y,
            "Generation": et,
            "Opex(Taxed)": ops_cost,
            "Interest": interest,
            "Principal": principal,
            "Tax Shield": -shield,
            "Replacement": rep,
            "Salvage Benefit": -sal_benefit,
            "Required Cash Flow": req_cash * df_e, # 记录折现后的值方便Excel求和验证
            "Discounted Gen(1-T)": denom_term
        })
        
    df = pd.DataFrame(data)
    
    # Price = Sum(PV Req Cash) / Sum(PV Gen 1-T)
    # 注意：Y0 的 initial_equity 也要加到分子里
    num = df["Required Cash Flow"].sum()
    den = df["Discounted Gen(1-T)"].sum()
    
    price = (num / den) * 10 if den > 0 else 0
    return price, df

# ==========================================
# 4. 模块 UI 渲染
# ==========================================
def render_module(tech_type):
    st.markdown(f"## 📊 {tech_type} 投资模型 (v16.0)")
    
    # --- 区域 1: 物理与成本 (Common) ---
    with st.container():
        st.subheader("1. 物理与分项成本")
        
        c1, c2, c3 = st.columns(3)
        
        # 默认值
        gen_list = []
        fuel_cost = 0
        capex_total = 0
        opex_total = 0
        period = 25
        
        if tech_type == "光伏+储能":
            source = c1.radio("储能电力来源", ("光伏", "电网"))
            cap_mw = c2.number_input("光伏容量 (MW)", min_value=0.0)
            hours = c3.number_input("光伏小时数", min_value=0.0)
            cap_ess = c1.number_input("储能容量 (MWh)", min_value=0.0)
            cycles = c2.number_input("循环次数", min_value=0.0)
            eff = c3.number_input("效率 RTE%", min_value=0.0)/100
            
            st.markdown("**💰 成本明细**")
            cc1, cc2, cc3 = st.columns(3)
            cx_pv = cc1.number_input("光伏造价 (万)", min_value=0.0)
            cx_ess = cc2.number_input("储能造价 (万)", min_value=0.0)
            cx_grid = cc3.number_input("配套造价 (万)", min_value=0.0)
            capex_total = cx_pv + cx_ess + cx_grid
            
            st.markdown("**🔧 运维明细**")
            oo1, oo2, oo3 = st.columns(3)
            op_pv = oo1.number_input("光伏运维%", min_value=0.0)/100
            op_ess = oo2.number_input("储能运维%", min_value=0.0)/100
            op_grid = oo3.number_input("配套运维%", min_value=0.0)/100
            opex_total = (cx_pv*op_pv) + (cx_ess*op_ess) + (cx_grid*op_grid)
            
            # 燃料/充电成本
            if source == "电网":
                p_grid = st.number_input("充电电价", min_value=0.0)
                fuel_cost = (cap_ess * cycles * 1000 * p_grid) / 10000
            
            # 发电量序列
            deg = 0.005
            for y in range(period + 1):
                if y == 0: gen_list.append(0)
                else:
                    base = cap_mw * hours * (1 - (y-1)*deg)
                    if source == "光伏":
                        loss = (cap_ess * cycles) * (1 - eff)
                        gen_list.append(max(base - loss, 0))
                    else:
                        gen_list.append(base + (cap_ess * cycles * eff))
                        
        elif tech_type == "燃气发电":
            cap_mw = c1.number_input("装机 (MW)", min_value=0.0)
            hours = c2.number_input("小时数", min_value=0.0)
            rate = c3.number_input("热耗 (GJ/kWh)", min_value=0.0, format="%.4f")
            price = c1.number_input("气价 (元/GJ)", min_value=0.0)
            
            capex_total = c2.number_input("总投资 (万)", min_value=0.0)
            opex_total = c3.number_input("固定运维 (万)", min_value=0.0)
            
            fuel_cost = (cap_mw * hours * 1000 * rate * price) / 10000
            gen_list = [0] + [cap_mw * hours] * period
            
        elif tech_type == "储能 LCOS":
            cap_mwh = c1.number_input("容量 (MWh)", min_value=0.0)
            cycles = c2.number_input("循环", min_value=0.0)
            eff = c3.number_input("效率%", min_value=0.0)/100
            
            capex_total = c1.number_input("总投资 (万)", min_value=0.0)
            opex_total = c2.number_input("总运维 (万)", min_value=0.0)
            p_charge = c3.number_input("充电价", min_value=0.0)
            
            fuel_cost = (cap_mwh * cycles * 1000 * p_charge) / 10000
            period = 15
            gen_list = [0] + [cap_mwh * cycles * eff] * period

    # --- 区域 2: 财务与融资 (Added per request) ---
    st.markdown("---")
    st.subheader("2. 财务与融资参数 (Financials)")
    
    col_f1, col_f2 = st.columns(2)
    
    with col_f1:
        st.markdown("###### 📘 WEMPR 参数 (技术测算)")
        wacc_tech = st.number_input("全投资 WACC (%)", min_value=0.0) / 100
        
    with col_f2:
        st.markdown("###### 🏛️ Lazard 参数 (股东回报测算)")
        f_a, f_b = st.columns(2)
        debt_ratio = f_a.number_input("债权比例 (Debt Ratio %)", min_value=0.0) / 100
        cost_debt = f_b.number_input("贷款利率 (Interest Rate %)", min_value=0.0) / 100
        cost_equity = f_a.number_input("股权成本 (ROE/IRR %)", min_value=0.0) / 100
        tax_rate = f_b.number_input("所得税率 (Tax %)", min_value=0.0) / 100
        
    # 残值率 (Added per request)
    st.markdown("###### ♻️ 资产回收")
    sal_col1, sal_col2, sal_col3 = st.columns(3)
    salvage_rate = sal_col1.number_input("期末残值率 (%)", min_value=0.0) / 100
    rep_yr = sal_col2.number_input("设备置换年份", min_value=0.0)
    rep_cost = sal_col3.number_input("置换成本 (万)", min_value=0.0)
    
    depr_years = 20 # Simplified hidden input or add to UI if needed

    # ================= 计算与展示 =================
    
    # 1. WEMPR Calc
    wempr_val, df_w = calc_wempr(range(period+1), capex_total, opex_total, fuel_cost, gen_list, 
                                 wacc_tech, rep_yr, rep_cost, salvage_rate)
    
    # 2. Lazard Calc
    lazard_val, df_l = calc_lazard(range(period+1), capex_total, opex_total, fuel_cost, gen_list,
                                   debt_ratio, cost_debt, cost_equity, tax_rate, depr_years,
                                   rep_yr, rep_cost, salvage_rate)
    
    st.markdown("---")
    st.markdown("### 🎯 测算结果")
    
    m1, m2, m3 = st.columns(3)
    m1.metric("📘 WEMPR LCOE (技术成本)", f"{wempr_val:.4f}", help="不含税，全投资WACC折现")
    # 满足您的需求：页面上必须显示 Lazard 结果
    m2.metric("🏛️ Lazard Price (投资者报价)", f"{lazard_val:.4f}", help="含税，满足股权IRR，考虑杠杆")
    m3.metric("差异 (报价溢价)", f"{lazard_val - wempr_val:.4f}")
    
    # Export
    inputs_dict = {
        "Tech Type": tech_type, "Capex": capex_total, "Opex": opex_total, "Fuel": fuel_cost,
        "WEMPR WACC": wacc_tech, 
        "Debt Ratio": debt_ratio, "Interest Rate": cost_debt, "ROE": cost_equity, "Tax": tax_rate,
        "Result WEMPR": wempr_val, "Result Lazard": lazard_val
    }
    
    excel_data = generate_hybrid_excel(tech_type, inputs_dict, df_w, wempr_val, df_l, lazard_val)
    st.download_button(f"📥 下载 Excel 底稿 ({tech_type})", excel_data, f"{tech_type}_Model_v16.xlsx")

# ==========================================
# 5. Main
# ==========================================
def main():
    st.sidebar.title("新能源建模 v16")
    mode = st.sidebar.radio("选择模块", ("光伏+储能", "燃气发电", "储能 LCOS"))
    render_module(mode)

if __name__ == "__main__":
    main()



