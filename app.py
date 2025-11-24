import streamlit as st
import pandas as pd
import numpy as np
import io
import xlsxwriter

# --- 1. 全局配置 ---
st.set_page_config(page_title="WEMPR 2020 标准测算工具", layout="wide", page_icon="📘")

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

# --- 文档公式展示函数 ---
def show_formula(is_lcos=False):
    st.markdown("### 🧮 计算公式 (Source: WEMPR 2020)")
    if is_lcos:
        st.latex(r"LCOS = \frac{\sum_{t=1}^{n} \frac{I_t + M_t + F_t}{(1+r)^t}}{\sum_{t=1}^{n} \frac{E_t}{(1+r)^t}}")
        st.caption("其中：$I_t$=投资支出, $M_t$=运维支出, $F_t$=充电成本(Fuel), $E_t$=放电量, $r$=WACC")
    else:
        st.latex(r"LCOE = \frac{\sum_{t=1}^{n} \frac{I_t + M_t + F_t}{(1+r)^t}}{\sum_{t=1}^{n} \frac{E_t}{(1+r)^t}}")
        st.caption("其中：$I_t$=投资支出, $M_t$=运维支出, $F_t$=燃料支出, $E_t$=发电量, $r$=WACC")
    st.markdown("---")

# ==========================================
# 2. 核心引擎：Excel 生成器 (含真实 Excel 公式)
# ==========================================
def generate_formula_excel(model_name, inputs, df_data, calculated_lcoe):
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet('Calculation')
    
    # 样式
    fmt_head = workbook.add_format({'bold': True, 'bg_color': '#2F5597', 'font_color': 'white', 'border': 1, 'align': 'center'})
    fmt_sub = workbook.add_format({'bold': True, 'bg_color': '#D9E1F2', 'border': 1})
    fmt_num = workbook.add_format({'border': 1, 'num_format': '#,##0.00'})
    fmt_money = workbook.add_format({'border': 1, 'num_format': '#,##0'})
    fmt_res = workbook.add_format({'bold': True, 'bg_color': '#FFEB9C', 'border': 1, 'num_format': '0.0000'})
    
    # 1. 假设区
    worksheet.write('A1', f"{model_name} - Key Assumptions", workbook.add_format({'bold': True, 'font_size': 14}))
    r = 2
    for k, v in inputs.items():
        worksheet.write(r, 0, k, fmt_sub)
        worksheet.write(r, 1, v, fmt_num)
        r += 1
        
    # 2. 数据表区
    r += 2
    worksheet.write(r, 0, "Calculation Waterfall (WEMPR 2020 Method)", workbook.add_format({'bold': True, 'font_size': 12}))
    r += 1
    
    # 列头
    cols = list(df_data.columns)
    worksheet.write_row(r, 0, cols, fmt_head)
    r += 1
    
    # 写入数据
    start_row = r + 1
    for index, row in df_data.iterrows():
        for col_idx, value in enumerate(row):
            worksheet.write(r, col_idx, value, fmt_num if col_idx > 0 else None)
        r += 1
    end_row = r
    
    # 3. 写入 Excel 汇总公式
    r += 2
    worksheet.write(r, 0, "Total PV Cost (Numerator)", fmt_sub)
    # 公式: SUM(PV_Cost列) -> 假设 PV_Cost 是倒数第2列 (index -2)
    cost_col_letter = xlsxwriter.utility.xl_col_to_name(len(cols)-2)
    formula_cost = f"=SUM({cost_col_letter}{start_row}:{cost_col_letter}{end_row})"
    worksheet.write_formula(r, 1, formula_cost, fmt_money)
    
    r += 1
    worksheet.write(r, 0, "Total PV Gen (Denominator)", fmt_sub)
    # 公式: SUM(PV_Gen列) -> 假设 PV_Gen 是倒数第1列 (index -1)
    gen_col_letter = xlsxwriter.utility.xl_col_to_name(len(cols)-1)
    formula_gen = f"=SUM({gen_col_letter}{start_row}:{gen_col_letter}{end_row})"
    worksheet.write_formula(r, 1, formula_gen, fmt_num)
    
    r += 2
    worksheet.write(r, 0, "Calculated LCOE/LCOS", fmt_sub)
    # 公式: Cost / Gen
    formula_lcoe = f"=B{r-2}/B{r-1}" # 引用上面的两个单元格
    worksheet.write_formula(r, 1, formula_lcoe, fmt_res)
    
    workbook.close()
    return output.getvalue()

# ==========================================
# 3. 模块 A: 光伏 + 储能 LCOE
# ==========================================
def render_pv_ess_lcoe():
    st.markdown("## ☀️ 光伏+储能 LCOE")
    show_formula(is_lcos=False)
    
    with st.container():
        st.subheader("1. 物理参数 (Inputs)")
        c1, c2, c3, c4 = st.columns(4)
        pv_cap = c1.number_input("光伏容量 (MW)", value=200.0)
        pv_hours = c2.number_input("光伏利用小时数 (h)", value=2200.0)
        ess_cap = c3.number_input("储能容量 (MWh)", value=120.0)
        ess_cycles = c4.number_input("储能年循环", value=365.0)
        
        t1, t2, t3 = st.columns(3)
        ess_eff = t1.number_input("储能效率 RTE (%)", value=85.0)/100
        pv_deg = t2.number_input("光伏年衰减 (%)", value=0.5)/100
        source = st.radio("储能电力来源", ("来自光伏", "来自电网"), horizontal=True)
        grid_price = 0.0
        if source == "来自电网":
            grid_price = st.number_input("电网充电电价", value=0.20)

        st.markdown("---")
        st.subheader("2. 成本参数 (Costs)")
        c1, c2, c3 = st.columns(3)
        capex_pv = c1.number_input("光伏投资 (万)", value=50000.0)
        capex_ess = c2.number_input("储能投资 (万)", value=10000.0)
        capex_grid = c3.number_input("配套投资 (万)", value=15000.0)
        
        o1, o2, o3 = st.columns(3)
        opex_pv = o1.number_input("光伏运维%", value=1.5)/100
        opex_ess = o2.number_input("储能运维%", value=3.0)/100
        opex_grid = o3.number_input("配套运维%", value=1.0)/100
        
        st.markdown("---")
        st.subheader("3. 财务参数 (Financials)")
        f1, f2, f3, f4 = st.columns(4)
        wacc = f1.number_input("WACC (%)", value=6.0, help="WEMPR range: 6.0% - 8.5%")/100
        period = int(f2.number_input("周期 (年)", value=25))
        rep_yr = f3.number_input("更换年份", value=10)
        rep_cost = f4.number_input("更换费用", value=5000.0)

    # --- Calculation ---
    years = range(0, period + 1)
    data = []
    total_capex = capex_pv + capex_ess + capex_grid
    
    for y in years:
        # 1. Investment (It)
        # WEMPR 假设 Capex 发生在运营第一年或分摊，这里为简化模型标准，设为Y0
        it = total_capex if y == 0 else 0
        if y == rep_yr: it += rep_cost # Replacement is treated as investment
        
        # 2. O&M (Mt)
        mt = 0
        if y > 0:
            mt = (capex_pv*opex_pv) + (capex_ess*opex_ess) + (capex_grid*opex_grid)
            
        # 3. Generation (Et) & Fuel (Ft)
        et = 0
        ft = 0
        
        if y > 0:
            # PV Generation
            deg = 1 - (y-1)*pv_deg
            raw_pv = pv_cap * pv_hours * max(deg, 0)
            
            if source == "来自光伏":
                # Ft = 0 (Free sun)
                # Et = PV - Storage Loss
                # Loss = Charge * (1 - Eff)
                loss = (ess_cap * ess_cycles) * (1 - ess_eff)
                et = raw_pv - loss
            else:
                # Ft = Grid Cost
                # Et = PV + Storage Discharge
                ft = (ess_cap * ess_cycles * 1000 * grid_price) / 10000 # 万
                discharge = ess_cap * ess_cycles * ess_eff
                et = raw_pv + discharge
        
        # 4. Discounting
        df = 1 / ((1 + wacc) ** y)
        total_cost = it + mt + ft
        pv_cost = total_cost * df
        pv_gen = et * df
        
        data.append({
            "Year": y,
            "I(t) Investment": it,
            "M(t) O&M": mt,
            "F(t) Fuel/Charge": ft,
            "Total Cost (I+M+F)": total_cost,
            "E(t) Generation": et,
            "Discount Factor": df,
            "PV(Cost)": pv_cost,
            "PV(Gen)": pv_gen
        })
        
    df = pd.DataFrame(data)
    
    # Final Calc
    sum_pv_cost = df["PV(Cost)"].sum()
    sum_pv_gen = df["PV(Gen)"].sum()
    lcoe = (sum_pv_cost / sum_pv_gen) * 10 if sum_pv_gen > 0 else 0
    
    st.markdown("---")
    st.metric("LCOE Result (WEMPR Method)", f"{lcoe:.4f} 元/kWh")
    
    with st.expander("📂 导出计算底稿"):
        st.dataframe(df, use_container_width=True)
        excel = generate_formula_excel("PV_ESS_LCOE", {"WACC": wacc}, df, lcoe)
        st.download_button("📥 下载 Excel (含公式)", excel, "PV_ESS_WEMPR.xlsx")

# ==========================================
# 4. 燃气 LCOE
# ==========================================
def render_gas_lcoe():
    st.markdown("## 🔥 燃气发电 LCOE")
    show_formula(is_lcos=False)
    
    with st.container():
        st.subheader("Inputs")
        c1, c2, c3 = st.columns(3)
        mw = c1.number_input("装机 (MW)", value=360.0)
        capex = c2.number_input("投资 (万)", value=60000.0)
        wacc = c3.number_input("WACC (%)", value=8.0)/100
        
        c4, c5, c6 = st.columns(3)
        hours = c4.number_input("小时数", value=3000.0)
        rate = c5.number_input("热耗 (GJ/kWh)", value=0.0095, format="%.4f")
        price = c6.number_input("气价 (元/GJ)", value=60.0)
        
        f1, f2 = st.columns(2)
        opex = f1.number_input("年运维 (万)", value=1200.0)
        period = int(f2.number_input("周期", value=25))

    years = range(0, period + 1)
    data = []
    
    for y in years:
        # I(t)
        it = capex if y == 0 else 0
        
        # M(t)
        mt = opex if y > 0 else 0
        
        # E(t)
        et = mw * hours if y > 0 else 0
        
        # F(t) = Gen * HeatRate * Price
        ft = (et * 1000 * rate * price) / 10000 if y > 0 else 0
        
        # Discount
        df = 1 / ((1 + wacc) ** y)
        total_cost = it + mt + ft
        
        data.append({
            "Year": y,
            "I(t) Invest": it,
            "M(t) O&M": mt,
            "F(t) Fuel": ft,
            "Total Cost": total_cost,
            "E(t) Gen": et,
            "Discount Factor": df,
            "PV(Cost)": total_cost * df,
            "PV(Gen)": et * df
        })
        
    df = pd.DataFrame(data)
    lcoe = (df["PV(Cost)"].sum() / df["PV(Gen)"].sum()) * 10 if df["PV(Gen)"].sum() > 0 else 0
    
    st.markdown("---")
    st.metric("LCOE Result", f"{lcoe:.4f}")
    
    with st.expander("📂 导出"):
        st.dataframe(df)
        excel = generate_formula_excel("Gas_LCOE", {"HeatRate": rate}, df, lcoe)
        st.download_button("📥 下载 Excel", excel, "Gas_WEMPR.xlsx")

# ==========================================
# 5. 储能 LCOS
# ==========================================
def render_lcos():
    st.markdown("## 🔋 储能 LCOS")
    show_formula(is_lcos=True)
    
    with st.container():
        st.subheader("Inputs")
        c1, c2, c3, c4 = st.columns(4)
        mwh = c1.number_input("容量 (MWh)", value=200.0)
        cycles = c2.number_input("循环次数", value=330.0)
        rte = c3.number_input("效率 RTE (%)", value=85.0)/100
        deg = c4.number_input("年衰减 (%)", value=2.0)/100
        
        c5, c6, c7 = st.columns(3)
        capex = c5.number_input("投资 (万)", value=25000.0)
        opex_r = c6.number_input("运维率 (%)", value=2.0)/100
        charge_p = c7.number_input("充电价", value=0.20)
        
        f1, f2, f3, f4 = st.columns(4)
        wacc = f1.number_input("WACC (%)", value=8.0)/100
        period = int(f2.number_input("寿命", value=15))
        rep_yr = f3.number_input("更换年", value=8)
        rep_cost = f4.number_input("更换费", value=10000.0)

    years = range(0, period + 1)
    data = []
    
    for y in years:
        # I(t)
        it = capex if y == 0 else 0
        if y == rep_yr: it += rep_cost
        
        # M(t)
        mt = (capex * opex_r) if y > 0 else 0
        
        # E(t) Discharge
        curr_cap = mwh * ((1-deg)**(y-1))
        et = (curr_cap * cycles * rte) if y > 0 else 0
        
        # F(t) Charging Cost (Fuel)
        # Charge Energy = Discharge / RTE  OR Capacity * Cycles?
        # WEMPR assumes charge logic implies efficiency loss. 
        # Standard LCOS: Charge = Capacity * Cycles. Discharge = Charge * RTE.
        charge_energy = curr_cap * cycles
        ft = (charge_energy * 1000 * charge_p) / 10000 if y > 0 else 0
        
        # Discount
        df = 1 / ((1 + wacc) ** y)
        total_cost = it + mt + ft
        
        data.append({
            "Year": y,
            "I(t) Invest": it,
            "M(t) O&M": mt,
            "F(t) Charge": ft,
            "Total Cost": total_cost,
            "E(t) Discharge": et,
            "Discount Factor": df,
            "PV(Cost)": total_cost * df,
            "PV(Discharge)": et * df
        })
        
    df = pd.DataFrame(data)
    lcos = (df["PV(Cost)"].sum() / df["PV(Discharge)"].sum()) * 10 if df["PV(Discharge)"].sum() > 0 else 0
    
    st.markdown("---")
    st.metric("LCOS Result", f"{lcos:.4f}")
    
    with st.expander("📂 导出"):
        st.dataframe(df)
        excel = generate_formula_excel("ESS_LCOS", {"RTE": rte}, df, lcos)
        st.download_button("📥 下载 Excel", excel, "ESS_WEMPR.xlsx")

# ==========================================
# 6. Main
# ==========================================
def main():
    st.sidebar.title("WEMPR 2020 Calculator")
    mode = st.sidebar.radio("模块", ("光伏+储能 LCOE", "燃气发电 LCOE", "储能 LCOS"))
    
    if mode == "光伏+储能 LCOE": render_pv_ess_lcoe()
    elif mode == "燃气发电 LCOE": render_gas_lcoe()
    elif mode == "储能 LCOS": render_lcos()

if __name__ == "__main__":
    main()
