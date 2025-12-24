import streamlit as st
import requests
import pandas as pd


st.set_page_config(page_title="StockIQ", layout="wide")


TABLE_HEIGHT = 520


DEFAULT_API_BASE = "http://127.0.0.1:8000"


def api_get(base: str, path: str, params: dict | None = None):
    url = f"{base.rstrip('/')}/{path.lstrip('/')}"
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    return r.json()

# Forecasts page
def page_forecasts(api_base: str):
    st.header("Forecasts")

    sku_id = st.text_input("sku_id", placeholder="SKU0002")
    start_week = st.text_input("start_week (YYYY-MM-DD)")
    end_week = st.text_input("end_week (YYYY-MM-DD)")
    limit = st.number_input("limit", min_value=1, value=50,)

    if st.button("Fetch forecasts"):
        sku_id = str(sku_id).strip()
        start_week = str(start_week).strip()
        end_week = str(end_week).strip()

        if not sku_id and not start_week and not end_week:
            st.warning("Enter at least one filter (sku_id or date range) before fetching.")
            return

        params = {}
        if sku_id:
            params["sku_id"] = sku_id
        if start_week:
            params["start_week"] = start_week
        if end_week:
            params["end_week"] = end_week
        if limit:
            params["limit"] = limit

        try:
            data = api_get(api_base, "/forecasts", params)
            df = pd.DataFrame(data)
            st.dataframe(df, use_container_width=True, height=TABLE_HEIGHT, hide_index=True)

            if "week" in df.columns and "p50" in df.columns:
                df["week"] = pd.to_datetime(df["week"])
                chart_df = df.sort_values("week").set_index("week")
                st.line_chart(chart_df[["p50"]])

        except Exception as e:
            st.error(str(e))

# Reorder Recommendations page
def page_reorders(api_base: str):
    st.header("Reorder Recommendations")

    sku_id = st.text_input("sku_id",placeholder="SKU0002")
    warehouse_id = st.text_input("warehouse_id", placeholder="WH_east")

    if st.button("Fetch reorders"):
        sku_id = str(sku_id).strip()
        warehouse_id = str(warehouse_id).strip()

        if not sku_id and not warehouse_id:
            st.warning("Enter sku_id and/or warehouse_id before fetching.")
            return

        params = {}
        if sku_id:
            params["sku_id"] = sku_id
        if warehouse_id:
            params["warehouse_id"] = warehouse_id

        try:
            data = api_get(api_base, "/reorder", params)
            df = pd.DataFrame(data)
            st.dataframe(df, use_container_width=True, height=TABLE_HEIGHT, hide_index=True)
        except Exception as e:
            st.error(str(e))

# COD Decisions page
def page_cod_decision(api_base: str):
    st.header("COD Decision")

    sku_id = st.text_input("sku_id", placeholder="SKU0002")
    warehouse_id = st.text_input("warehouse_id", placeholder="east")

    if st.button("Get COD decision"):
        if not sku_id or not warehouse_id:
            st.error("Both sku_id and warehouse_id are required")
            return

        try:
            decision = api_get(
                api_base,
                "/cod/decision",
                {
                    "sku_id": sku_id,
                    "warehouse_id": warehouse_id,
                },
            )
            st.json(decision)
        except Exception as e:
            st.error(str(e))


# Main app
def main_page():
    st.title("StockIQ — Decision Dashboard")

    st.sidebar.header("Backend")
    api_base = st.sidebar.text_input("FastAPI base URL", DEFAULT_API_BASE)

    page = st.sidebar.radio(
        "Page",
        ["Forecasts", "Reorders", "COD Decision"],
    )

    if page == "Forecasts":
        page_forecasts(api_base)
    elif page == "Reorders":
        page_reorders(api_base)
    elif page == "COD Decision":
        page_cod_decision(api_base)


if __name__ == "__main__":
    main_page()

