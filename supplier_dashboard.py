import streamlit as st
import pandas as pd
import plotly.express as px

# -------------------------------
# Page Config
# -------------------------------
st.set_page_config(
    page_title="Global Supplier Insights",
    layout="wide"
)

st.title("🌍 Global Supplier Insights Dashboard")
st.write(
    "Analyze supplier costs, profitability, and regional trends. "
    "Run what-if scenarios and ask natural-language questions to the Supplier AI."
)

# -------------------------------
# Sidebar: OpenAI Key (Optional)
# -------------------------------
st.sidebar.header("🔐 AI Configuration (Optional)")
api_key = st.sidebar.text_input(
    "Enter OpenAI API Key",
    type="password",
    help="Optional. If missing or quota exceeded, mock AI responses will be used."
)

client = None
if api_key:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
    except Exception:
        client = None

# -------------------------------
# CSV Upload
# -------------------------------
uploaded_file = st.file_uploader("Upload Supplier CSV", type="csv")

if not uploaded_file:
    st.info("Please upload a supplier CSV file to begin.")
    st.stop()

df = pd.read_csv(uploaded_file)
df.columns = df.columns.str.strip()

# -------------------------------
# Required Columns Check
# -------------------------------
required_cols = [
    "Date", "Supplier", "Region", "Commodity",
    "Unit Cost", "Quantity", "Revenue"
]

missing = [c for c in required_cols if c not in df.columns]
if missing:
    st.error(f"Missing required columns: {', '.join(missing)}")
    st.stop()

# -------------------------------
# Calculations
# -------------------------------
df["Total Cost"] = df["Unit Cost"] * df["Quantity"]
df["Margin"] = df["Revenue"] - df["Total Cost"]

# -------------------------------
# Sidebar Filters & Scenario
# -------------------------------
st.sidebar.header("📊 Filters & What-If Scenario")

regions = st.sidebar.multiselect(
    "Region",
    df["Region"].unique(),
    default=df["Region"].unique()
)

commodities = st.sidebar.multiselect(
    "Commodity",
    df["Commodity"].unique(),
    default=df["Commodity"].unique()
)

cost_increase = st.sidebar.slider(
    "Simulate Cost Increase (%)",
    0, 50, 0
)

filtered = df[
    (df["Region"].isin(regions)) &
    (df["Commodity"].isin(commodities))
].copy()

filtered["Simulated Unit Cost"] = filtered["Unit Cost"] * (1 + cost_increase / 100)
filtered["Simulated Total Cost"] = filtered["Simulated Unit Cost"] * filtered["Quantity"]
filtered["Simulated Margin"] = filtered["Revenue"] - filtered["Simulated Total Cost"]

# -------------------------------
# Executive KPIs
# -------------------------------
col1, col2, col3 = st.columns(3)

col1.metric("Total Spend", f"${filtered['Simulated Total Cost'].sum():,.0f}")
col2.metric("Total Margin", f"${filtered['Simulated Margin'].sum():,.0f}")
col3.metric(
    "Avg Margin %",
    f"{(filtered['Simulated Margin'].sum() / filtered['Revenue'].sum() * 100):.1f}%"
)

# -------------------------------
# Supplier Rankings
# -------------------------------
st.subheader("🏭 Supplier Performance")

expensive = (
    filtered.groupby("Supplier")["Simulated Unit Cost"]
    .mean()
    .sort_values(ascending=False)
    .head(5)
)

profitable = (
    filtered.groupby("Supplier")["Simulated Margin"]
    .sum()
    .sort_values(ascending=False)
    .head(5)
)

col4, col5 = st.columns(2)

col4.write("**Top 5 Most Expensive Suppliers**")
col4.bar_chart(expensive)

col5.write("**Top 5 Most Profitable Suppliers**")
col5.bar_chart(profitable)

# -------------------------------
# Regional Trends
# -------------------------------
st.subheader("📈 Regional Cost & Margin Trends")

trend = (
    filtered.groupby(["Date", "Region"])
    [["Simulated Total Cost", "Simulated Margin"]]
    .sum()
    .reset_index()
)

fig = px.line(
    trend,
    x="Date",
    y=["Simulated Total Cost", "Simulated Margin"],
    color="Region",
    markers=True
)

st.plotly_chart(fig, use_container_width=True)

# -------------------------------
# Executive Summary (Rule-Based)
# -------------------------------
st.subheader("🧠 Executive Summary")

st.write(
    f"• **{profitable.index[0]}** is the most profitable supplier in the selected scope.\n\n"
    f"• **{expensive.index[0]}** shows the highest cost pressure and should be reviewed.\n\n"
)

if cost_increase > 0:
    st.warning(
        f"A simulated {cost_increase}% cost increase materially compresses margins. "
        "Supplier diversification is recommended."
    )

# -------------------------------
# Supplier Metrics for AI
# -------------------------------
supplier_metrics = (
    filtered.groupby("Supplier")
    .agg(
        Revenue=("Revenue", "sum"),
        TotalCost=("Simulated Total Cost", "sum"),
        Margin=("Simulated Margin", "sum"),
        Orders=("Quantity", "sum")
    )
)
supplier_metrics["MarginPct"] = supplier_metrics["Margin"] / supplier_metrics["Revenue"] * 100
max_orders = supplier_metrics["Orders"].max()
supplier_metrics["Utilization"] = supplier_metrics["Orders"] / max_orders * 100
supplier_table_str = supplier_metrics.reset_index().to_string(index=False)

# -------------------------------
# Chatbot Section
# -------------------------------
st.subheader("💬 Ask the Supplier AI")

st.write(
    "Ask questions about supplier costs, margins, utilization, or negotiation strategy.\n\n"
    "**Examples:** Which suppliers deliver strong margin but appear underutilized? Who should we renegotiate with?"
)

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

user_question = st.text_input("Your question")

def mock_chat_response(question):
    q = question.lower()
    if "underutilized" in q or "margin" in q:
        top_underutilized = supplier_metrics[
            (supplier_metrics["MarginPct"] > supplier_metrics["MarginPct"].median()) &
            (supplier_metrics["Utilization"] < 50)
        ]
        bullets = []
        for i, row in top_underutilized.iterrows():
            bullets.append(
                f"• {row.name}: {row['Utilization']:.0f}% utilization, ${row['Margin']:,} margin"
            )
        if not bullets:
            bullets.append("• No high-margin underutilized suppliers found")
        return "\n".join(bullets)

    if "expensive" in q or "renegotiate" in q:
        high_cost = supplier_metrics.sort_values("TotalCost", ascending=False).head(3)
        return "\n".join(
            [f"• {row.name}: ${row['TotalCost']:,} total cost, {row['MarginPct']:.1f}% margin" for _, row in high_cost.iterrows()]
        )

    return "• Focus on high-cost suppliers\n• Monitor margins\n• Use scenario modeling before negotiations"

if user_question:
    st.session_state.chat_history.append(("user", user_question))

    if client:
        try:
            context = f"""
Supplier metrics (Revenue, TotalCost, Margin, Orders, MarginPct, Utilization %):
{supplier_table_str}
"""
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system",
                     "content": (
                         "You are a supply chain strategy advisor for executives. "
                         "Use only the suppliers in the provided table. "
                         "Answer in 3 short bullet points, concise and actionable, referencing numbers where possible."
                     )
                    },
                    {"role": "assistant", "content": context},
                    {"role": "user", "content": user_question}
                ],
                max_tokens=300
            )
            answer = response.choices[0].message.content
        except Exception:
            answer = mock_chat_response(user_question)
    else:
        answer = mock_chat_response(user_question)

    st.session_state.chat_history.append(("assistant", answer))

for role, msg in st.session_state.chat_history:
    if role == "user":
        st.markdown(f"**You:** {msg}")
    else:
        st.markdown(f"**Supplier AI:** {msg}")
