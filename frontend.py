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
    st.header("COD Intelligence")

    st.markdown("Use filters below and click **Apply filters**. Toggle views to focus on decisions or see full details.")

    # Filters
    cols = st.columns([1, 1, 1, 0.5])
    with cols[0]:
        sku_input = st.text_input("SKU(s)", placeholder="SKU0002 (comma-separated for multiple)")
    with cols[1]:
        wh_input = st.text_input("Warehouse", placeholder="WH_east")
    with cols[2]:
        policy_filter = st.selectbox("Policy action (optional)", options=["", "ALLOW", "LIMIT", "DISABLE"], index=0)
    with cols[3]:
        allow_all = st.checkbox("Allow fetch all", value=False, help="Check to allow fetching the full COD dataset (use with care)")

    view_mode = st.radio("View", ["Decision view", "Details view"], index=0, horizontal=True)

    if st.button("Apply filters"):
        # build params for API calls
        params = {}
        sku_input = (sku_input or "").strip()
        wh_input = (wh_input or "").strip()
        policy_filter = (policy_filter or "").strip()

        if not sku_input and not wh_input and not policy_filter and not allow_all:
            st.warning("Please supply at least one filter or enable 'Allow fetch all' to retrieve all rows.")
            st.stop()

        # support multiple SKUs via comma-splitting client-side
        skus = [s.strip() for s in sku_input.split(",") if s.strip()] if sku_input else [None]

        all_rows = []
        try:
            # If user supplied multiple SKUs, call /cod per SKU to limit payload
            if skus and any(skus):
                for s in skus:
                    p = {"sku_id": s} if s else {}
                    if wh_input:
                        p["warehouse_id"] = wh_input
                    rows = api_get(api_base, "/cod", p)
                    all_rows.extend(rows)
            else:
                p = {}
                if wh_input:
                    p["warehouse_id"] = wh_input
                rows = api_get(api_base, "/cod", p)
                all_rows.extend(rows)

            # client-side policy filter if requested (exact match)
            if policy_filter:
                all_rows = [r for r in all_rows if r.get("cod_policy_action") == policy_filter]

            if not all_rows:
                st.info("No COD rows matched the filters.")
                st.stop()

            df = pd.DataFrame(all_rows)

            # Decision view: minimal columns
            if view_mode == "Decision view":
                show_cols = [c for c in ["sku_id", "warehouse_id", "cod_policy_action", "cod_risk_bucket"] if c in df.columns]
                st.dataframe(df[show_cols], use_container_width=True, height=TABLE_HEIGHT, hide_index=True)
                st.caption(f"Rows returned: {len(df)}")

            # Details view: show numeric fields and metadata
            else:
                # preferred order, only present if in df
                cols_order = ["sku_id", "warehouse_id", "cod_policy_action", "cod_risk_bucket", "cod_share", "cod_rto_rate", "cod_success_rate", "financial_risk_flag", "description"]
                show_cols = [c for c in cols_order if c in df.columns]
                st.dataframe(df[show_cols], use_container_width=True, height=TABLE_HEIGHT, hide_index=True)
                st.caption(f"Rows returned: {len(df)}")

            # allow per-row inspection
            with st.expander("Inspect rows (JSON)"):
                for i, row in enumerate(all_rows[:500]):
                    st.write(row)

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

