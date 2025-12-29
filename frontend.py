import streamlit as st
import requests
import pandas as pd
import altair as alt
from datetime import datetime

# --- CONFIGURATION ---
st.set_page_config(
    page_title="StockIQ | Warehouse Decision Hub",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

DEFAULT_API_BASE = "http://127.0.0.1:8000"

# --- STYLE ---
st.markdown("""
    <style>
    .main {
        background-color: #f8f9fa;
    }
    .stMetric {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #e9ecef;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        color: #31333F !important;
    }
    .stMetric label {
        color: #6c757d !important;
    }
    .stMetric [data-testid="stMetricValue"] {
        color: #212529 !important;
    }
    div[data-testid="stExpander"] {
        background-color: #ffffff;
        border-radius: 8px;
        border: 1px solid #e9ecef;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        color: #31333F !important;
    }
    div[data-testid="stExpander"] p {
        color: #31333F !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- API HELPERS ---
def api_get(path: str, params: dict | None = None):
    api_base = st.session_state.get("api_base", DEFAULT_API_BASE)
    url = f"{api_base.rstrip('/')}/{path.lstrip('/')}"
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"Backend Connection Error: {e}")
        return None

# --- DATA FETCHING ---
@st.cache_data(ttl=60)
def get_reorder_data(sku_id=None, warehouse_id=None):
    params = {}
    if sku_id: params["sku_id"] = sku_id
    if warehouse_id: params["warehouse_id"] = warehouse_id
    data = api_get("/reorder", params)
    return pd.DataFrame(data) if data else pd.DataFrame()

@st.cache_data(ttl=60)
def get_forecast_data(sku_id, limit=52):
    data = api_get("/forecast", {"sku_id": sku_id, "limit": limit})
    return pd.DataFrame(data) if data else pd.DataFrame()

@st.cache_data(ttl=60)
def get_cod_data(sku_id=None, warehouse_id=None):
    params = {}
    if sku_id: params["sku_id"] = sku_id
    if warehouse_id: params["warehouse_id"] = warehouse_id
    data = api_get("/cod", params)
    return pd.DataFrame(data) if data else pd.DataFrame()

# --- UI COMPONENTS ---

def render_overview():
    st.title("Warehouse Overview")
    st.subheader("What needs your attention today?")

    reorder_df = get_reorder_data()
    cod_df = get_cod_data()

    if reorder_df.empty:
        st.info("No reorder data available. Ensure backend is running and artifacts are loaded.")
        return

    # KPIs
    col1, col2, col3, col4 = st.columns(4)
    
    critical_count = len(reorder_df[reorder_df["sku_status"] == "REORDER"]) if "sku_status" in reorder_df.columns else 0
    high_risk_cod = len(cod_df[cod_df["cod_risk_bucket"] == "HIGH"]) if not cod_df.empty and "cod_risk_bucket" in cod_df.columns else 0
    down_trends = len(reorder_df[reorder_df["demand_trend"] == "DOWN"]) if "demand_trend" in reorder_df.columns else 0
    
    with col1:
        st.metric("Critical Reorders", critical_count, delta=f"{critical_count} items", delta_color="inverse")
    with col2:
        st.metric("High COD Risk Lanes", high_risk_cod, delta_color="off")
    with col3:
        st.metric("Declining Demand", down_trends, help="SKUs with a DOWN demand trend")
    with col4:
        st.metric("Active Warehouses", reorder_df["warehouse_id"].nunique() if "warehouse_id" in reorder_df.columns else 0)

    st.divider()

    # Top Alerts
    st.subheader("Critical Action Items")
    if critical_count > 0:
        alerts = reorder_df[reorder_df["sku_status"] == "REORDER"].copy()
        # Sort by how much we are below reorder point
        if "reorder_point" in alerts.columns and "inventory_position" in alerts.columns:
            alerts["shortfall"] = alerts["reorder_point"] - alerts["inventory_position"]
            alerts = alerts.sort_values("shortfall", ascending=False).head(10)
        
        display_cols = [c for c in ["sku_id", "warehouse_id", "inventory_position", "reorder_point", "recommended_order_qty", "decision_reason"] if c in alerts.columns]
        st.table(alerts[display_cols])
    else:
        st.success("All inventory levels are healthy!")

def render_reorder_page():
    st.title("Reorder Decisions")
    st.markdown("Authoritative SKU × Warehouse planning based on lead time and safety stock.")

    # Filters
    with st.expander("Filters", expanded=True):
        f_col1, f_col2, f_col3 = st.columns(3)
        with f_col1:
            sku_filter = st.text_input("Filter by SKU ID")
        with f_col2:
            wh_filter = st.text_input("Filter by Warehouse")
        with f_col3:
            trend_filter = st.multiselect("Demand Trend", options=["UP", "DOWN", "STABLE"], default=[])

    df = get_reorder_data(sku_filter, wh_filter)
    
    if df.empty:
        st.warning("No matching reorder records found.")
        return

    if trend_filter and "demand_trend" in df.columns:
        df = df[df["demand_trend"].isin(trend_filter)]

    # Main Table
    st.subheader("Decision Matrix")
    
    # Color coding for status
    def color_status(val):
        color = '#ff4b4b' if val == 'REORDER' else '#28a745'
        return f'background-color: {color}; color: white; font-weight: bold; border-radius: 4px; padding: 2px 5px;'

    def color_trend(val):
        if val == 'UP': color = '#28a745'
        elif val == 'DOWN': color = '#ff4b4b'
        else: color = '#6c757d'
        return f'color: {color}; font-weight: bold;'

    styled_df = df.style
    if "sku_status" in df.columns:
        styled_df = styled_df.map(color_status, subset=['sku_status'])
    if "demand_trend" in df.columns:
        styled_df = styled_df.map(color_trend, subset=['demand_trend'])

    st.dataframe(
        styled_df,
        use_container_width=True,
        height=400,
        hide_index=True
    )

    st.divider()

    # Deep Dive
    st.subheader("Inventory Deep Dive")
    if "sku_id" in df.columns:
        selected_sku = st.selectbox("Select SKU for visual analysis", options=df["sku_id"].unique())
        
        sku_data = df[df["sku_id"] == selected_sku].iloc[0]
        
        d_col1, d_col2 = st.columns([1, 2])
        
        with d_col1:
            st.write(f"**SKU:** {selected_sku}")
            st.write(f"**Warehouse:** {sku_data.get('warehouse_id', 'N/A')}")
            st.write(f"**Status:** {sku_data.get('sku_status', 'N/A')}")
            st.info(f"**Reason:** {sku_data.get('decision_reason', 'N/A')}")
            
            st.markdown(f"""
            - **Safety Stock:** {sku_data.get('safety_stock', 0):.2f} 
              *(Buffer for demand spikes)*
            - **Reorder Point:** {sku_data.get('reorder_point', 0):.2f} 
              *(Trigger point: Lead Time Demand + Safety Stock)*
            - **Lead Time:** {sku_data.get('lead_time_weeks', 'N/A')} weeks
            """)

        with d_col2:
            # Inventory Level Chart
            chart_data = pd.DataFrame({
                'Metric': ['On Hand', 'Reorder Point', 'Safety Stock'],
                'Value': [sku_data.get('inventory_position', 0), sku_data.get('reorder_point', 0), sku_data.get('safety_stock', 0)]
            })
            
            bar_chart = alt.Chart(chart_data).mark_bar().encode(
                x=alt.X('Metric', sort=None),
                y='Value',
                color=alt.Color('Metric', scale=alt.Scale(range=['#007bff', '#ffc107', '#6c757d']))
            ).properties(height=300)
            
            st.altair_chart(bar_chart, use_container_width=True)

def render_forecast_page():
    st.title("Forecast Insights")
    st.markdown("Probabilistic demand projections (P10/P50/P90) to understand future risk.")

    sku_id = st.text_input("Enter SKU ID to view forecast", value="SKU0001")
    
    if sku_id:
        df = get_forecast_data(sku_id)
        
        if df.empty:
            st.warning(f"No forecast data found for {sku_id}")
            return

        if "week" in df.columns:
            df["week"] = pd.to_datetime(df["week"])
            
            # Altair Chart with Band
            base = alt.Chart(df).encode(x='week:T')

            line = base.mark_line(color='#007bff', strokeWidth=3).encode(
                y=alt.Y('p50:Q', title='Demand Units'),
                tooltip=['week', 'p10', 'p50', 'p90']
            )

            band = base.mark_area(opacity=0.2, color='#007bff').encode(
                y='p10:Q',
                y2='p90:Q'
            )

            st.altair_chart((band + line).properties(height=400), use_container_width=True)
            
            st.caption("**P50 (Line):** Most likely outcome. **P10-P90 (Shaded):** 80% confidence interval. Wider bands mean higher uncertainty.")
            
            with st.expander("View Raw Forecast Data"):
                st.dataframe(df, use_container_width=True)

def render_cod_page():
    st.title("COD Risk & Policy")
    st.markdown("Manage Cash-on-Delivery risk and enforce automated policy actions.")

    df = get_cod_data()
    
    if df.empty:
        st.warning("No COD data available.")
        return

    # Risk Distribution
    if "cod_risk_bucket" in df.columns:
        st.subheader("Risk Profile")
        risk_counts = df["cod_risk_bucket"].value_counts().reset_index()
        risk_counts.columns = ["Risk Bucket", "Count"]
        
        risk_chart = alt.Chart(risk_counts).mark_arc(innerRadius=50).encode(
            theta=alt.Theta(field="Count", type="quantitative"),
            color=alt.Color(field="Risk Bucket", type="nominal", scale=alt.Scale(domain=['LOW', 'MEDIUM', 'HIGH'], range=['#28a745', '#ffc107', '#ff4b4b'])),
            tooltip=["Risk Bucket", "Count"]
        ).properties(height=300)
        
        st.altair_chart(risk_chart, use_container_width=True)

    st.divider()

    # Policy Table
    st.subheader("Policy Enforcement")
    
    def color_risk(val):
        if val == 'HIGH': return 'background-color: #ff4b4b; color: white;'
        if val == 'MEDIUM': return 'background-color: #ffc107;'
        return 'background-color: #28a745; color: white;'

    def color_flag(val):
        return 'color: #ff4b4b; font-weight: bold;' if val is True else ''

    display_cols = [c for c in ["sku_id", "warehouse_id", "cod_risk_bucket", "cod_policy_action", "cod_share", "financial_risk_flag"] if c in df.columns]
    
    styled_df = df[display_cols].style
    if "cod_risk_bucket" in df.columns:
        styled_df = styled_df.map(color_risk, subset=['cod_risk_bucket'])
    if "financial_risk_flag" in df.columns:
        styled_df = styled_df.map(color_flag, subset=['financial_risk_flag'])

    st.dataframe(
        styled_df,
        use_container_width=True,
        height=500,
        hide_index=True
    )

# --- MAIN APP ---
def main():
    st.sidebar.title("StockIQ")
    st.sidebar.markdown("---")
    
    # Sidebar Config
    api_base = st.sidebar.text_input("FastAPI Base URL", DEFAULT_API_BASE)
    st.session_state["api_base"] = api_base
    
    page = st.sidebar.radio(
        "Navigation",
        ["Overview", "Reorder Decisions", "Forecast Insights", "COD Risk"]
    )
    
    st.sidebar.markdown("---")
    st.sidebar.caption(f"Last Sync: {datetime.now().strftime('%H:%M:%S')}")
    
    if page == "Overview":
        render_overview()
    elif page == "Reorder Decisions":
        render_reorder_page()
    elif page == "Forecast Insights":
        render_forecast_page()
    elif page == "COD Risk":
        render_cod_page()

if __name__ == "__main__":
    main()

