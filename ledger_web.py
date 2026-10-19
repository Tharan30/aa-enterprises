import streamlit as st
import mysql.connector
import pandas as pd
from datetime import date
from io import BytesIO

# =========================
# PAGE CONFIG
# =========================

st.set_page_config(
    page_title="AA ENTERPRISES",
    page_icon="⛽",
    layout="wide"
)

# =========================
# LIGHT MODE — CLEAN UI
# =========================

st.markdown("""
<style>
/* ---- Global & Typography ---- */
.stApp {
    background-color: #f8fafc;
    color: #1e293b;
}

/* Force dark readable text on all standard headings, labels, and captions */
h1, h2, h3, h4, h5, h6, p, label, .stMarkdown, .stCaption {
    color: #1e293b !important;
}

/* Form input labels & text */
div[data-testid="stWidgetLabel"] label, div[data-testid="stWidgetLabel"] p {
    color: #334155 !important;
    font-weight: 600 !important;
    font-size: 14px !important;
}

/* Input boxes & select boxes styling */
input, select, textarea, div[data-baseweb="select"] {
    color: #0f172a !important;
    background-color: #ffffff !important;
}

/* Expander styling in light mode */
div[data-testid="stExpander"] {
    background-color: #ffffff !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 12px !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
}

div[data-testid="stExpander"] details summary span {
    color: #1e293b !important;
    font-weight: 700 !important;
}

.block-container {
    padding-top: 1.5rem;
    padding-bottom: 2rem;
    max-width: 1200px;
}

/* ---- Header ---- */
.app-header {
    text-align: center;
    padding: 20px 0 10px;
}

.app-title {
    font-size: 38px;
    font-weight: 800;
    color: #1e293b !important;
    margin: 0;
    letter-spacing: -0.5px;
}

.app-subtitle {
    color: #64748b !important;
    font-size: 15px;
    margin-top: 4px;
}

/* ---- Metric Cards ---- */
.metric-row {
    display: flex;
    gap: 16px;
    margin: 20px 0 28px;
}

.m-card {
    flex: 1;
    background: white;
    border-radius: 16px;
    padding: 20px 24px;
    border: 1px solid #e2e8f0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}

.m-card .label {
    font-size: 13px;
    font-weight: 600;
    color: #64748b !important;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

.m-card .value {
    font-size: 28px;
    font-weight: 800;
    margin-top: 4px;
}

.m-card.blue  .value { color: #2563eb !important; }
.m-card.green .value { color: #16a34a !important; }
.m-card.red   .value { color: #dc2626 !important; }
.m-card.amber .value { color: #d97706 !important; }

/* ---- Tabs ---- */
.stTabs [data-baseweb="tab-list"] {
    gap: 8px;
    background: white;
    padding: 6px;
    border-radius: 14px;
    border: 1px solid #e2e8f0;
}

.stTabs [data-baseweb="tab"] {
    border-radius: 10px;
    padding: 10px 20px;
    font-weight: 600;
    color: #475569 !important;
}

.stTabs [data-baseweb="tab"][aria-selected="true"] {
    background: #2563eb;
    color: #ffffff !important;
}

/* ---- Buttons ---- */
.stButton>button {
    border-radius: 10px;
    font-weight: 600;
    border: 1px solid #cbd5e1;
    padding: 8px 20px;
}

.stFormSubmitButton>button {
    background: #2563eb !important;
    color: white !important;
    border-radius: 10px;
    font-weight: 600;
    height: 42px;
    border: none;
}

.stFormSubmitButton>button:hover {
    background: #1d4ed8 !important;
    color: white !important;
}

/* ---- Sidebar ---- */
[data-testid="stSidebar"] {
    background-color: #ffffff !important;
    border-right: 1px solid #e2e8f0;
}

/* ---- Dataframe & Tables ---- */
.stDataFrame {
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid #e2e8f0;
    background: #ffffff;
}

/* ---- Upload area ---- */
[data-testid="stFileUploader"] {
    background: #ffffff;
    border: 1px dashed #cbd5e1;
    border-radius: 12px;
    padding: 12px;
}

/* ---- Form inputs ---- */
.stTextInput>div>div>input, .stNumberInput>div>div>input, .stSelectbox>div>div {
    border-radius: 8px;
    border-color: #cbd5e1;
}
</style>
""", unsafe_allow_html=True)

# =========================
# AUTHENTICATION
# =========================

def check_password():
    """Simple password gate using session state."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    st.markdown("""
    <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; min-height:60vh;">
        <div style="font-size:48px; margin-bottom:8px;">⛽</div>
        <div style="font-size:32px; font-weight:800; color:#1e293b;">AA ENTERPRISES</div>
        <div style="color:#64748b; font-size:15px; margin-bottom:28px;">Enter password to access the dashboard</div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        with st.form("login_form"):
            password = st.text_input("Password", type="password", label_visibility="collapsed", placeholder="Enter password...")
            submitted = st.form_submit_button("Login", use_container_width=True)

            if submitted:
                if password == st.secrets["app_password"]:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Incorrect password")

    return False


if not check_password():
    st.stop()

# =========================
# DATABASE CONNECTION
# =========================

def get_connection():
    """Create a fresh MySQL connection each run."""
    try:
        conn = mysql.connector.connect(
            host=st.secrets["mysql"]["host"],
            port=int(st.secrets["mysql"]["port"]),
            user=st.secrets["mysql"]["user"],
            password=st.secrets["mysql"]["password"],
            database=st.secrets["mysql"]["database"],
            ssl_disabled=st.secrets["mysql"].get("ssl_disabled", False),
            autocommit=False,
            connection_timeout=10
        )
        return conn
    except mysql.connector.Error as e:
        st.error(f"Database connection failed: {e}")
        st.stop()


def run_query(conn, query, params=None):
    """Execute a query safely with a fresh cursor."""
    cursor = conn.cursor(buffered=True)
    cursor.execute(query, params)
    return cursor


def get_dataframe(conn, query, params=None):
    """Read SQL into a DataFrame."""
    try:
        return pd.read_sql(query, conn, params=params)
    except Exception:
        conn.ping(reconnect=True)
        return pd.read_sql(query, conn, params=params)


# Connect
conn = get_connection()

# Ensure default sales record
try:
    cur = run_query(conn, "SELECT COUNT(*) FROM sales WHERE sales_id=1")
    if cur.fetchone()[0] == 0:
        run_query(conn, "INSERT INTO sales (sales_id, sales_name) VALUES (1, %s)", ("AA ENTERPRISES",))
        conn.commit()
    cur.close()
except mysql.connector.Error:
    try:
        conn.rollback()
    except Exception:
        pass

# =========================
# HELPER FUNCTIONS
# =========================

def recalculate_balances(conn, customer_id):
    """Recalculate running balances for a customer."""
    cur = run_query(conn, """
    SELECT id, debit, credit FROM ledger_transactions
    WHERE customer_id=%s ORDER BY trans_date ASC, id ASC
    """, (customer_id,))
    rows = cur.fetchall()
    cur.close()

    running = 0.0
    for row in rows:
        running += float(row[1] or 0) + float(row[2] or 0)
        c = run_query(conn, "UPDATE ledger_transactions SET balance=%s WHERE id=%s",
                      (round(running, 2), row[0]))
        c.close()
    conn.commit()


def get_customers(conn):
    return get_dataframe(conn, "SELECT customer_id, customer_name, phone FROM customers ORDER BY customer_name")


def get_transactions(conn, customer_id):
    return get_dataframe(conn, """
    SELECT id, trans_date, trans_id, vehicle, product, litres, debit, credit, balance
    FROM ledger_transactions WHERE customer_id=%s
    ORDER BY trans_date ASC, id ASC
    """, params=(customer_id,))


# =========================
# HEADER
# =========================

st.markdown("""
<div class="app-header">
    <div class="app-title">⛽ AA ENTERPRISES</div>
    <div class="app-subtitle">Sales Ledger Dashboard</div>
</div>
""", unsafe_allow_html=True)

# =========================
# METRICS
# =========================

customers_df = get_customers(conn)
total_customers = len(customers_df)

cur = run_query(conn, "SELECT COUNT(*) FROM ledger_transactions")
total_transactions = cur.fetchone()[0]
cur.close()

cur = run_query(conn, "SELECT COALESCE(SUM(debit),0), COALESCE(SUM(credit),0) FROM ledger_transactions")
total_debit, total_credit = cur.fetchone()
cur.close()

st.markdown(f"""
<div class="metric-row">
    <div class="m-card blue">
        <div class="label">Customers</div>
        <div class="value">{total_customers}</div>
    </div>
    <div class="m-card green">
        <div class="label">Transactions</div>
        <div class="value">{total_transactions}</div>
    </div>
    <div class="m-card red">
        <div class="label">Total Debit</div>
        <div class="value">₹ {round(float(total_debit), 2):,.2f}</div>
    </div>
    <div class="m-card amber">
        <div class="label">Total Credit</div>
        <div class="value">₹ {round(float(total_credit), 2):,.2f}</div>
    </div>
</div>
""", unsafe_allow_html=True)

# Build customer lookup
customer_dict = {}
if not customers_df.empty:
    customer_dict = dict(zip(customers_df["customer_name"], customers_df["customer_id"]))

# =========================
# TABS
# =========================

tab1, tab2, tab3, tab4 = st.tabs(["👥 Customers", "📒 Ledger", "📥 Import Excel", "⚙️ Manage"])

# =========================
# TAB 1 — CUSTOMERS
# =========================

with tab1:
    col_add, col_list = st.columns([1, 2])

    with col_add:
        st.markdown("#### ➕ Add Customer")
        with st.form("add_customer_form"):
            name = st.text_input("Customer Name")
            phone = st.text_input("Phone Number")
            add_btn = st.form_submit_button("Add Customer", use_container_width=True)

            if add_btn:
                if not name.strip():
                    st.error("Enter a customer name")
                else:
                    try:
                        cur = run_query(conn, "INSERT INTO customers(sales_id, customer_name, phone) VALUES(%s,%s,%s)",
                                        (1, name.strip(), phone.strip()))
                        conn.commit()
                        cur.close()
                        st.success(f"Added **{name.strip()}**")
                        st.rerun()
                    except mysql.connector.Error as e:
                        conn.rollback()
                        st.error(f"Error: {e}")

    with col_list:
        st.markdown("#### 📋 Customer List")
        if customers_df.empty:
            st.info("No customers yet. Add one to get started.")
        else:
            # Display clean sequential S.No (1, 2, 3...) instead of database customer_id
            customer_display_df = customers_df.copy()
            customer_display_df.insert(0, "S.No", range(1, len(customer_display_df) + 1))
            customer_display_df = customer_display_df[["S.No", "customer_name", "phone"]].rename(columns={
                "customer_name": "Customer Name",
                "phone": "Phone Number"
            })
            st.dataframe(customer_display_df, use_container_width=True, hide_index=True, height=400)

# =========================
# TAB 2 — LEDGER
# =========================

with tab2:
    if customers_df.empty:
        st.info("No customers found. Add a customer first in the Customers tab.")
    else:
        selected_name = st.selectbox("Select Customer", list(customer_dict.keys()), key="ledger_customer")
        selected_customer = int(customer_dict[selected_name])

        transactions_df = get_transactions(conn, selected_customer)

        # Balance banner
        if not transactions_df.empty:
            last_balance = round(float(transactions_df["balance"].iloc[-1]), 2)
            bal_color = "#dc2626" if last_balance > 0 else "#16a34a" if last_balance < 0 else "#64748b"
            st.markdown(f"""
            <div style="background:{bal_color}; color:white; padding:16px 24px; border-radius:12px;
                        font-size:20px; font-weight:700; margin-bottom:16px;">
                📌 {selected_name} — Balance: ₹ {last_balance:,.2f}
            </div>
            """, unsafe_allow_html=True)

        # Add transaction form
        with st.expander("➕ Add New Transaction", expanded=False):
            with st.form("add_transaction_form"):
                c1, c2, c3, c4 = st.columns(4)
                trans_date = c1.date_input("Date", date.today())
                trans_id = c2.text_input("Transaction ID")
                vehicle = c3.text_input("Vehicle")
                product = c4.text_input("Product")

                c5, c6, c7 = st.columns(3)
                litres = c5.number_input("Litres", value=0.0, step=0.01)
                debit = c6.number_input("Debit (+)", value=0.0, step=0.01)
                credit = c7.number_input("Credit (−)", value=0.0, step=0.01)

                add_trans = st.form_submit_button("Add Transaction", use_container_width=True)

                if add_trans:
                    try:
                        cur = run_query(conn, """
                        INSERT INTO ledger_transactions(customer_id, trans_date, trans_id, vehicle, product, litres, debit, credit, balance)
                        VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        """, (selected_customer, trans_date, trans_id.strip(), vehicle.strip(),
                              product.strip(), litres, debit, credit, 0))
                        conn.commit()
                        cur.close()
                        recalculate_balances(conn, selected_customer)
                        st.success("Transaction added")
                        st.rerun()
                    except mysql.connector.Error as e:
                        conn.rollback()
                        st.error(f"Error: {e}")

        # Datewise Export Section (Always visible, prominent card)
        st.markdown("""
        <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:14px; padding:20px; margin:20px 0 16px; box-shadow:0 1px 3px rgba(0,0,0,0.05);">
            <div style="display:flex; align-items:center; gap:8px; margin-bottom:8px;">
                <span style="font-size:20px;">📤</span>
                <span style="font-size:17px; font-weight:700; color:#1e293b;">Export Statement (Date-Wise)</span>
            </div>
            <p style="color:#64748b; font-size:13px; margin:0 0 16px 0;">Filter transactions by date and download in Excel or CSV.</p>
        """, unsafe_allow_html=True)

        exp_col1, exp_col2, exp_col3 = st.columns([1.5, 1.5, 1])

        # Get min and max dates
        if not transactions_df.empty:
            min_date = pd.to_datetime(transactions_df["trans_date"]).min().date()
            max_date = pd.to_datetime(transactions_df["trans_date"]).max().date()
        else:
            min_date = date.today()
            max_date = date.today()

        start_dt = exp_col1.date_input("From Date", min_date, key=f"exp_start_{selected_customer}")
        end_dt = exp_col2.date_input("To Date", max_date, key=f"exp_end_{selected_customer}")

        preset = exp_col3.selectbox("Quick Range", ["Custom", "This Month", "All Time"], key=f"exp_preset_{selected_customer}")
        if preset == "This Month":
            today = date.today()
            start_dt = today.replace(day=1)
            end_dt = today
        elif preset == "All Time":
            start_dt = min_date
            end_dt = max_date

        # Filter dataframe
        if not transactions_df.empty:
            filtered_df = transactions_df.copy()
            filtered_df["_dt"] = pd.to_datetime(filtered_df["trans_date"]).dt.date
            filtered_df = filtered_df[(filtered_df["_dt"] >= start_dt) & (filtered_df["_dt"] <= end_dt)]
            filtered_df = filtered_df.drop(columns=["_dt"])
        else:
            filtered_df = pd.DataFrame()

        st.markdown(f"<p style='color:#475569; font-size:13px; margin:8px 0 14px;'>Found <b>{len(filtered_df)}</b> records between <b>{start_dt.strftime('%d-%b-%Y')}</b> and <b>{end_dt.strftime('%d-%b-%Y')}</b></p>", unsafe_allow_html=True)

        if not filtered_df.empty:
            export_df = filtered_df.rename(columns={
                "id": "Sl No",
                "trans_date": "Date",
                "trans_id": "Txn ID",
                "vehicle": "Vehicle",
                "product": "Product",
                "litres": "Litres",
                "debit": "Debit (₹)",
                "credit": "Credit (₹)",
                "balance": "Balance (₹)"
            })

            excel_buffer = BytesIO()
            with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                export_df.to_excel(writer, index=False, sheet_name=selected_name[:30])
            excel_data = excel_buffer.getvalue()

            csv_data = export_df.to_csv(index=False).encode('utf-8')

            btn_c1, btn_c2, _ = st.columns([1.5, 1.5, 2])
            clean_filename = f"{selected_name.replace(' ', '_')}_{start_dt}_{end_dt}"

            btn_c1.download_button(
                label="📥 Download Excel (.xlsx)",
                data=excel_data,
                file_name=f"{clean_filename}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                type="primary"
            )

            btn_c2.download_button(
                label="📄 Download CSV",
                data=csv_data,
                file_name=f"{clean_filename}.csv",
                mime="text/csv",
                use_container_width=True
            )
        else:
            st.warning("No transactions match the selected date range.")

        st.markdown("</div>", unsafe_allow_html=True)

        # Transactions table
        st.markdown("#### 📋 Transaction History")
        if transactions_df.empty:
            st.info("No transactions for this customer yet.")
        else:
            st.dataframe(transactions_df, use_container_width=True, hide_index=True, height=400)

# =========================
# TAB 3 — IMPORT EXCEL
# =========================

with tab3:
    st.markdown("#### 📥 Import Transactions from Excel")

    if customers_df.empty:
        st.info("No customers found. Add a customer first.")
    else:
        import_customer = st.selectbox("Select Customer to Import Into", list(customer_dict.keys()), key="import_customer")
        import_customer_id = int(customer_dict[import_customer])

        st.markdown("""
        <div style="background:#eff6ff; border:1px solid #bfdbfe; border-radius:12px; padding:16px 20px; margin:12px 0; color:#1e40af; font-size:14px;">
            <strong>📋 Excel Format Required:</strong><br>
            Your Excel file should have these columns (header row):<br>
            <code>date</code> · <code>trans_id</code> · <code>vehicle</code> · <code>product</code> · <code>litres</code> · <code>debit</code> · <code>credit</code><br><br>
            Column names are flexible — the importer will match common names like
            <code>Date</code>, <code>Transaction ID</code>, <code>Vehicle No</code>, etc.
        </div>
        """, unsafe_allow_html=True)

        uploaded_file = st.file_uploader("Upload Excel File (.xlsx)", type=["xlsx", "xls"], key="excel_upload")

        if uploaded_file is not None:
            try:
                df = pd.read_excel(uploaded_file)

                if df.empty:
                    st.warning("The uploaded file is empty.")
                else:
                    # Normalize column names
                    col_map = {}
                    for col in df.columns:
                        cl = str(col).strip().lower().replace(" ", "_").replace(".", "")
                        if cl in ("date", "trans_date", "transaction_date"):
                            col_map[col] = "trans_date"
                        elif cl in ("trans_id", "transaction_id", "txn_id", "bill_no", "bill"):
                            col_map[col] = "trans_id"
                        elif cl in ("vehicle", "vehicle_no", "vehicle_number", "veh"):
                            col_map[col] = "vehicle"
                        elif cl in ("product", "item", "fuel", "fuel_type"):
                            col_map[col] = "product"
                        elif cl in ("litres", "liters", "ltr", "qty", "quantity"):
                            col_map[col] = "litres"
                        elif cl in ("debit", "dr", "amount", "debit_amount"):
                            col_map[col] = "debit"
                        elif cl in ("credit", "cr", "payment", "credit_amount"):
                            col_map[col] = "credit"

                    df = df.rename(columns=col_map)

                    # Ensure required columns exist with defaults
                    for needed in ["trans_date", "trans_id", "vehicle", "product", "litres", "debit", "credit"]:
                        if needed not in df.columns:
                            if needed == "trans_date":
                                df[needed] = date.today()
                            elif needed in ("litres", "debit", "credit"):
                                df[needed] = 0.0
                            else:
                                df[needed] = ""

                    # Clean data
                    df["litres"] = pd.to_numeric(df["litres"], errors="coerce").fillna(0.0)
                    df["debit"] = pd.to_numeric(df["debit"], errors="coerce").fillna(0.0)
                    df["credit"] = pd.to_numeric(df["credit"], errors="coerce").fillna(0.0)
                    df["trans_date"] = pd.to_datetime(df["trans_date"], errors="coerce", dayfirst=True).dt.date
                    df["trans_date"] = df["trans_date"].fillna(date.today())
                    df["trans_id"] = df["trans_id"].astype(str).replace("nan", "")
                    df["vehicle"] = df["vehicle"].astype(str).replace("nan", "")
                    df["product"] = df["product"].astype(str).replace("nan", "")

                    # Preview
                    preview_df = df[["trans_date", "trans_id", "vehicle", "product", "litres", "debit", "credit"]]
                    st.markdown(f"**Preview — {len(preview_df)} rows to import for {import_customer}:**")
                    st.dataframe(preview_df, use_container_width=True, hide_index=True, height=350)

                    col_a, col_b = st.columns([1, 3])
                    with col_a:
                        if st.button("✅ Confirm Import", use_container_width=True, type="primary"):
                            success_count = 0
                            error_count = 0

                            for _, row in preview_df.iterrows():
                                try:
                                    cur = run_query(conn, """
                                    INSERT INTO ledger_transactions(customer_id, trans_date, trans_id, vehicle, product, litres, debit, credit, balance)
                                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)
                                    """, (
                                        import_customer_id,
                                        row["trans_date"],
                                        str(row["trans_id"]).strip(),
                                        str(row["vehicle"]).strip(),
                                        str(row["product"]).strip(),
                                        float(row["litres"]),
                                        float(row["debit"]),
                                        float(row["credit"]),
                                        0
                                    ))
                                    cur.close()
                                    success_count += 1
                                except mysql.connector.Error:
                                    error_count += 1

                            conn.commit()
                            recalculate_balances(conn, import_customer_id)

                            if error_count == 0:
                                st.success(f"✅ Successfully imported {success_count} transactions!")
                            else:
                                st.warning(f"Imported {success_count} rows, {error_count} failed.")
                            st.rerun()

            except Exception as e:
                st.error(f"Error reading Excel file: {e}")

        # Download template
        st.markdown("---")
        st.markdown("**Need a template?** Download a sample Excel file:")
        template_df = pd.DataFrame({
            "date": [date.today()],
            "trans_id": ["TXN001"],
            "vehicle": ["TN01AB1234"],
            "product": ["Diesel"],
            "litres": [50.0],
            "debit": [4500.00],
            "credit": [0.00]
        })
        buffer = BytesIO()
        template_df.to_excel(buffer, index=False, engine="openpyxl")
        st.download_button(
            "📄 Download Template",
            data=buffer.getvalue(),
            file_name="import_template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# =========================
# TAB 4 — MANAGE / DELETE
# =========================

with tab4:
    if customers_df.empty:
        st.info("No customers available.")
    else:
        col_del_cust, col_del_trans = st.columns(2)

        with col_del_cust:
            st.markdown("#### 🗑 Delete Customer")
            del_cust_name = st.selectbox("Select Customer", list(customer_dict.keys()), key="del_cust")
            del_cust_id = int(customer_dict[del_cust_name])

            st.caption("⚠️ This will delete all transactions for this customer.")
            if st.button("Delete Customer", key="btn_del_cust"):
                try:
                    cur = run_query(conn, "DELETE FROM customers WHERE customer_id=%s", (del_cust_id,))
                    conn.commit()
                    cur.close()
                    st.success(f"Deleted **{del_cust_name}**")
                    st.rerun()
                except mysql.connector.Error as e:
                    conn.rollback()
                    st.error(f"Error: {e}")

        with col_del_trans:
            st.markdown("#### 🗑 Delete Transaction")
            manage_name = st.selectbox("Select Customer", list(customer_dict.keys()), key="manage_cust")
            manage_id = int(customer_dict[manage_name])

            trans_df = get_transactions(conn, manage_id)

            if trans_df.empty:
                st.info("No transactions for this customer.")
            else:
                st.dataframe(trans_df[["id", "trans_date", "trans_id", "debit", "credit"]],
                             use_container_width=True, hide_index=True, height=250)

                del_trans_id = st.number_input("Transaction DB ID", min_value=1, step=1, key="del_trans_id")

                if st.button("Delete Transaction", key="btn_del_trans"):
                    try:
                        # Verify the transaction belongs to this customer
                        chk = run_query(conn, "SELECT COUNT(*) FROM ledger_transactions WHERE id=%s AND customer_id=%s", (del_trans_id, manage_id))
                        exists = chk.fetchone()[0] > 0
                        chk.close()

                        if not exists:
                            st.error(f"Transaction ID {del_trans_id} not found for {manage_name}.")
                        else:
                            cur = run_query(conn, "DELETE FROM ledger_transactions WHERE id=%s AND customer_id=%s", (del_trans_id, manage_id))
                            conn.commit()
                            cur.close()
                            recalculate_balances(conn, manage_id)
                            st.success(f"Transaction #{del_trans_id} deleted successfully")
                            st.rerun()
                    except mysql.connector.Error as e:
                        conn.rollback()
                        st.error(f"Error: {e}")

# =========================
# SIDEBAR
# =========================

with st.sidebar:
    st.markdown("### ⛽ AA ENTERPRISES")
    st.caption("Sales Ledger System")
    st.markdown("---")
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()