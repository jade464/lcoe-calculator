import streamlit as st
import pandas as pd
import numpy_financial as npf
import plotly.express as px
import plotly.graph_objects as go

# ==========================================
# 页面配置
# ==========================================
st.set_page_config(page_title="亿利集团重组项目财务测算模型", layout="wide")
st.title("🏜️ 亿利集团“沙戈荒”风光氢醇及SAF一体化财务测算模型")
st.markdown("""
本模型基于亿利集团**阿拉善250万千瓦立体风光氢治沙制取航空燃料（SAF）一体化项目**的基准数据构建。
您可以通过调整左侧的**土地税率**、**SAF国际售价**等核心参数，动态进行全生命周期（25年）的**IRR敏感性分析**与现金流压力测试。
""")

# ==========================================
# 侧边栏：核心参数调节区
# ==========================================
st.sidebar.header("⚙️ 核心参数动态调节")

st.sidebar.subheader("1. 政策与土地成本参数")
# 1万亩 = 666.67万平方米
land_area_wanmu = st.sidebar.number_input("项目占地面积 (万亩)", min_value=1.0, max_value=200.0, value=15.0, step=1.0)
land_tax_rate = st.sidebar.slider("城镇土地使用税率 (元/平方米/年)", min_value=0.0, max_value=10.0, value=0.6, step=0.1, 
                                  help="内蒙古现行最低标准为0.6元，免税政策取消后将面临全额征收。")

st.sidebar.subheader("2. 市场与产品增值参数")
saf_price = st.sidebar.number_input("SAF 国际市场售价 (元/吨)", min_value=5000, max_value=30000, value=15552, step=500)
naphtha_price = st.sidebar.number_input("生物石脑油 售价 (元/吨)", min_value=3000, max_value=15000, value=10080, step=100)
capacity_rate = st.sidebar.slider("产能达成负荷率 (%)", min_value=50, max_value=100, value=100, step=1)

st.sidebar.subheader("3. 初始投资与运营参数")
capex = st.sidebar.number_input("项目总投资 CAPEX (亿元)", min_value=50.0, max_value=500.0, value=219.33, step=5.0)
opex_base = st.sidebar.number_input("年均基础运营成本 OPEX (亿元/年)", min_value=5.0, max_value=50.0, value=20.5, step=0.5,
                                    help="包含设备折旧维护、人工及其他原材料成本（不含地税）。")
project_life = st.sidebar.number_input("项目全生命运营周期 (年)", min_value=15, max_value=30, value=25, step=1)

# ==========================================
# 后台财务数据测算逻辑
# ==========================================
# 1. 产能及收入计算 (满产基准：SAF 29万吨，石脑油 7.44万吨)
annual_saf_revenue = (290000 * (capacity_rate / 100.0) * saf_price) / 100000000  # 亿元
annual_naphtha_revenue = (74400 * (capacity_rate / 100.0) * naphtha_price) / 100000000  # 亿元
total_revenue = annual_saf_revenue + annual_naphtha_revenue

# 2. 土地税计算
# 1万亩 = 6666666.67 平方米
land_area_sqm = land_area_wanmu * 6666666.67
annual_land_tax = (land_area_sqm * land_tax_rate) / 100000000  # 亿元

# 3. 净现金流测算
annual_opex_total = opex_base + annual_land_tax
annual_net_cash_flow = total_revenue - annual_opex_total

# 构建现金流列表 (第0年为负的CAPEX，此后为每年的正向现金流)
cash_flows = [-capex] + [annual_net_cash_flow] * int(project_life)

# 4. 核心财务指标计算
try:
    project_irr = npf.irr(cash_flows) * 100  # 转换为百分比
except:
    project_irr = 0.0

# 假设基准折现率为 8% 计算 NPV
discount_rate = 0.08
project_npv = npf.npv(discount_rate, cash_flows)

# 静态投资回收期
payback_period = capex / annual_net_cash_flow if annual_net_cash_flow > 0 else 999

# ==========================================
# 仪表盘：核心指标看板
# ==========================================
st.subheader("📊 核心财务指标看板")

col1, col2, col3, col4 = st.columns(4)
col1.metric(label="全投资内部收益率 (IRR)", value=f"{project_irr:.2f} %", 
            delta="面临严重亏损" if project_irr < 4.0 else "收益良好")
col2.metric(label="项目净现值 (NPV @8%)", value=f"{project_npv:.2f} 亿元")
col3.metric(label="静态投资回收期", value=f"{payback_period:.1f} 年")
col4.metric(label="年均新增土地税金", value=f"{annual_land_tax:.2f} 亿元", 
            delta=f"占总营收 {(annual_land_tax/total_revenue)*100:.1f}%", delta_color="inverse")

st.divider()

# ==========================================
# 图表区：现金流与敏感性分析
# ==========================================
col_chart1, col_chart2 = st.columns(2)

with col_chart1:
    st.markdown("#### 📈 25年全生命周期累计现金流曲线")
    # 累计现金流计算
    cumulative_cf = [sum(cash_flows[:i+1]) for i in range(len(cash_flows))]
    df_cf = pd.DataFrame({
        "年份": list(range(int(project_life) + 1)),
        "当期现金流 (亿元)": cash_flows,
        "累计净现金流 (亿元)": cumulative_cf
    })
    
    fig_cf = px.line(df_cf, x="年份", y="累计净现金流 (亿元)", markers=True, 
                     title="累计现金流回本轨迹",
                     color_discrete_sequence=['#2E86C1'])
    fig_cf.add_hline(y=0, line_dash="dash", line_color="red", annotation_text="盈亏平衡线")
    st.plotly_chart(fig_cf, use_container_width=True)

with col_chart2:
    st.markdown("#### 🌪️ 敏感性分析：土地税率 vs SAF售价 双因素雷达")
    
    # 构建二维数据矩阵用于热力图
    tax_rates = [0.0, 0.6, 2.0, 5.0, 10.0]
    saf_prices = [10000, 13000, 15552, 18000, 22000]
    
    sensitivity_data = []
    for t_rate in tax_rates:
        row = []
        for s_price in saf_prices:
            # 重新计算
            temp_tax = (land_area_sqm * t_rate) / 100000000
            temp_rev = (290000 * (capacity_rate / 100.0) * s_price) / 100000000 + annual_naphtha_revenue
            temp_ncf = temp_rev - opex_base - temp_tax
            temp_cfs = [-capex] + [temp_ncf] * int(project_life)
            try:
                temp_irr = npf.irr(temp_cfs) * 100
            except:
                temp_irr = -100
            row.append(round(temp_irr, 2))
        sensitivity_data.append(row)
        
    fig_heatmap = go.Figure(data=go.Heatmap(
        z=sensitivity_data,
        x=[f"{p}元/吨" for p in saf_prices],
        y=[f"{t}元/平米" for t in tax_rates],
        colorscale='RdYlGn',
        text=sensitivity_data,
        texttemplate="%{text}%"
    ))
    fig_heatmap.update_layout(
        title="不同情境下的 IRR (%) 变化矩阵",
        xaxis_title="SAF 国际售价",
        yaxis_title="土地使用税率"
    )
    st.plotly_chart(fig_heatmap, use_container_width=True)

# ==========================================
# 财务总结与政策应对建议
# ==========================================
st.markdown("### 💡 动态模型结论与投资建议")
st.info(f"""
* **税收黑天鹅的破坏力**：在当前设置下，若内蒙古全面实施 **{land_tax_rate} 元/平方米** 的土地税征收标准，项目每年将凭空蒸发 **{annual_land_tax:.2f} 亿元** 的净现金流。这意味着传统的低毛利“光伏卖电”模式必将全线亏损，只有转向高毛利的SAF化工品才能对冲此风险。
* **SAF绿色溢价的安全垫作用**：目前项目年均总营收约为 **{total_revenue:.2f} 亿元**。在满产状态下，若能长期锚定国际航空合规碳市场的绿油溢价（当前设定为 {saf_price} 元/吨），即便面临一定的地税压力，全投资IRR仍能稳定在 **{project_irr:.2f}%** 左右，具备极强的跨周期韧性，这也是吸引中信等央国企入局重组的最核心商业底座。
""")
