import streamlit as st
import mysql.connector
import pandas as pd
from datetime import date

# =========================
# PAGE CONFIG
# =========================

st.set_page_config(
    page_title="AA ENTERPRISES",
    page_icon="⛽",
    layout="wide"
)

# =========================
# UI CSS
# =========================

st.markdown("""
<style>
.stApp {
    background: linear-gradient(135deg, #020617 0%, #0f172a 50%, #111827 100%);
    color: white;
}

.block-container {
    padding-top: 1.2rem;
}

.big-title {
    font-size: 42px;
    font-weight: 900;
    background: linear-gradient(90deg, #38bdf8, #22c55e, #facc15);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.sub-title {
    color: #cbd5e1;
    font-size: 17px;
    margin-bottom: 20px;
}

.card {
    background: rgba(255,255,255,0.08);
    padding: 22px;
    border-radius: 22px;
    border: 1px solid rgba(255,255,255,0.15);
    box-shadow: 0 12px 35px rgba(0,0,0,0.35);
}

.metric-card {
    background: linear-gradient(135deg, rgba(59,130,246,.25), rgba(34,197,94,.18));
    padding: 22px;
    border-radius: 24px;
    border: 1px solid rgba(255,255,255,.20);
    box-shadow: 0 10px 30px rgba(0,0,0,.30);
}

.metric-title {
    color: #cbd5e1;
    font-size: 15px;
    font-weight: 600;
}

.metric-value {
    color: white;
    font-size: 34px;
    font-weight: 900;
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #020617 0%, #0f172a 100%);
}

.stTabs [data-baseweb="tab-list"] {
    gap: 12px;
}

.stTabs [data-baseweb="tab"] {
    background: rgba(255,255,255,0.08);
    border-radius: 18px;
    padding: 12px 22px;
    color: white;
}

.stButton>button {
    border-radius: 14px;
    height: 45px;
    font-weight: 700;
    border: none;
    background: linear-gradient(90deg, #2563eb, #22c55e);
    color: white;
}

.stButton>button:hover {
    background: linear-gradient(90deg, #22c55e, #facc15);
    color: black;
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

    st.markdown('<div class="big-title">AA ENTERPRISES</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">🔒 Login to Access Dashboard</div>', unsafe_allow_html=True)

    with st.form("login_form"):
        password = st.text_input("Enter Password", type="password")
        submitted = st.form_submit_button("Login")

        if submitted:
            if password == st.secrets["app_password"]:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("❌ Incorrect password")

    return False


if not check_password():
    st.stop()

# =========================
# DATABASE CONNECTION
# =========================

def get_connection():
    """Create a fresh MySQL connection each run to avoid stale connections on cloud."""
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
        st.error(f"❌ Database connection failed: {e}")
        st.stop()


def run_query(conn, query, params=None):
    """Execute a query and return results safely with a fresh cursor."""
    cursor = conn.cursor(buffered=True)
    cursor.execute(query, params)
    return cursor


def get_dataframe(conn, query, params=None):
    """Read SQL into a DataFrame with error handling."""
    try:
        return pd.read_sql(query, conn, params=params)
    except Exception:
        # Reconnect and retry once
        conn.ping(reconnect=True)
        return pd.read_sql(query, conn, params=params)


# Get connection
conn = get_connection()

# Ensure default sales record exists (needed for foreign key)
try:
    cur = run_query(conn, "SELECT COUNT(*) FROM sales WHERE sales_id=1")
    count = cur.fetchone()[0]
    cur.close()
    if count == 0:
        cur = run_query(conn, "INSERT INTO sales (sales_id, sales_name) VALUES (1, %s)", ("AA ENTERPRISES",))
        conn.commit()
        cur.close()
except mysql.connector.Error:
    # Already exists or table issue — safe to ignore
    try:
        conn.rollback()
    except Exception:
        pass

# =========================
# FUNCTIONS
# =========================

def recalculate_balances(conn, customer_id):
    """Recalculate running balances for a customer's transactions."""
    cur = run_query(conn, """
    SELECT id, debit, credit
    FROM ledger_transactions
    WHERE customer_id=%s
    ORDER BY trans_date ASC, id ASC
    """, (customer_id,))

    rows = cur.fetchall()
    cur.close()
    running_balance = 0.0

    for row in rows:
        db_id = row[0]
        debit = float(row[1] or 0)
        credit = float(row[2] or 0)

        running_balance += debit + credit

        cur2 = run_query(conn, """
        UPDATE ledger_transactions
        SET balance=%s
        WHERE id=%s
        """, (round(running_balance, 2), db_id))
        cur2.close()

    conn.commit()


def get_customers(conn):
    """Get all customers as a DataFrame."""
    return get_dataframe(conn, """
    SELECT customer_id, customer_name, phone
    FROM customers
    ORDER BY customer_name
    """)


def get_transactions(conn, customer_id):
    """Get transactions for a customer as a DataFrame."""
    return get_dataframe(conn, """
    SELECT
        id,
        trans_date,
        trans_id,
        vehicle,
        product,
        litres,
        debit,
        credit,
        balance
    FROM ledger_transactions
    WHERE customer_id=%s
    ORDER BY trans_date ASC, id ASC
    """, params=(customer_id,))


# =========================
# HEADER & METRICS
# =========================

st.markdown('<div class="big-title">AA ENTERPRISES</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Sales Ledger Dashboard</div>', unsafe_allow_html=True)

customers_df = get_customers(conn)
total_customers = len(customers_df)

cur = run_query(conn, "SELECT COUNT(*) FROM ledger_transactions")
total_transactions = cur.fetchone()[0]
cur.close()

cur = run_query(conn, "SELECT COALESCE(SUM(debit),0), COALESCE(SUM(credit),0) FROM ledger_transactions")
total_debit, total_credit = cur.fetchone()
cur.close()

m1, m2, m3, m4 = st.columns(4)

with m1:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Total Customers</div>
        <div class="metric-value">{total_customers}</div>
    </div>
    """, unsafe_allow_html=True)

with m2:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Total Transactions</div>
        <div class="metric-value">{total_transactions}</div>
    </div>
    """, unsafe_allow_html=True)

with m3:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Total Debit</div>
        <div class="metric-value">₹ {round(float(total_debit), 2)}</div>
    </div>
    """, unsafe_allow_html=True)

with m4:
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">Total Credit</div>
        <div class="metric-value">₹ {round(float(total_credit), 2)}</div>
    </div>
    """, unsafe_allow_html=True)

st.write("")

# Build customer lookup dict (used across tabs)
customer_dict = {}
if not customers_df.empty:
    customer_dict = dict(zip(
        customers_df["customer_name"],
        customers_df["customer_id"]
    ))

# =========================
# TABS
# =========================

tab1, tab2, tab3 = st.tabs(["👥 Customers", "📒 Ledger", "🗑 Delete / Manage"])

# =========================
# CUSTOMERS TAB
# =========================

with tab1:
    st.subheader("Add New Customer")

    with st.form("add_customer_form"):
        c1, c2 = st.columns(2)

        name = c1.text_input("Customer Name")
        phone = c2.text_input("Phone Number")

        add_customer = st.form_submit_button("Add Customer")

        if add_customer:
            if name.strip() == "":
                st.error("Enter customer name")
            else:
                try:
                    cur = run_query(conn, """
                    INSERT INTO customers(sales_id, customer_name, phone)
                    VALUES(%s,%s,%s)
                    """, (1, name.strip(), phone.strip()))
                    conn.commit()
                    cur.close()
                    st.success("✅ Customer Added Successfully")
                    st.rerun()
                except mysql.connector.Error as e:
                    conn.rollback()
                    st.error(f"❌ Error adding customer: {e}")

    st.subheader("Customer List")
    st.dataframe(customers_df, use_container_width=True, hide_index=True)

# =========================
# LEDGER TAB
# =========================

with tab2:
    st.subheader("Customer Ledger")

    if customers_df.empty:
        st.warning("No customers found. Add a customer first.")
    else:
        selected_name = st.selectbox("Select Customer", list(customer_dict.keys()))
        selected_customer = int(customer_dict[selected_name])

        st.markdown(f"### 📌 {selected_name}")

        with st.form("add_transaction_form"):
            c1, c2, c3, c4 = st.columns(4)

            trans_date = c1.date_input("Date", date.today())
            trans_id = c2.text_input("Transaction ID")
            vehicle = c3.text_input("Vehicle")
            product = c4.text_input("Product")

            c5, c6, c7 = st.columns(3)

            litres = c5.number_input("Litres", value=0.0, step=0.01)
            debit = c6.number_input("Debit", value=0.0, step=0.01)
            credit = c7.number_input("Credit", value=0.0, step=0.01)

            add_trans = st.form_submit_button("Add Transaction")

            if add_trans:
                try:
                    cur = run_query(conn, """
                    INSERT INTO ledger_transactions(
                        customer_id,
                        trans_date,
                        trans_id,
                        vehicle,
                        product,
                        litres,
                        debit,
                        credit,
                        balance
                    )
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """, (
                        selected_customer,
                        trans_date,
                        trans_id.strip(),
                        vehicle.strip(),
                        product.strip(),
                        litres,
                        debit,
                        credit,
                        0
                    ))
                    conn.commit()
                    cur.close()
                    recalculate_balances(conn, selected_customer)
                    st.success("✅ Transaction Added")
                    st.rerun()
                except mysql.connector.Error as e:
                    conn.rollback()
                    st.error(f"❌ Error adding transaction: {e}")

        transactions_df = get_transactions(conn, selected_customer)

        if not transactions_df.empty:
            last_balance = transactions_df["balance"].iloc[-1]

            st.markdown(f"""
            <div class="card">
                <h3>Current Balance: ₹ {round(float(last_balance), 2)}</h3>
            </div>
            """, unsafe_allow_html=True)

            st.write("")

        st.dataframe(transactions_df, use_container_width=True, hide_index=True)

# =========================
# DELETE / MANAGE TAB
# =========================

with tab3:
    st.subheader("Delete Customer")

    if customers_df.empty:
        st.warning("No customers available.")
    else:
        delete_customer_name = st.selectbox(
            "Select Customer to Delete",
            list(customer_dict.keys()),
            key="delete_customer_select"
        )

        delete_customer_id = int(customer_dict[delete_customer_name])

        if st.button("🗑 Delete Selected Customer"):
            try:
                cur = run_query(conn, """
                DELETE FROM customers
                WHERE customer_id=%s
                """, (delete_customer_id,))
                conn.commit()
                cur.close()
                st.success("✅ Customer Deleted")
                st.rerun()
            except mysql.connector.Error as e:
                conn.rollback()
                st.error(f"❌ Error deleting customer: {e}")

    st.divider()

    st.subheader("Delete Transaction")

    if customers_df.empty:
        st.warning("No customers available.")
    else:
        manage_customer_name = st.selectbox(
            "Select Customer",
            list(customer_dict.keys()),
            key="manage_customer_select"
        )

        manage_customer_id = int(customer_dict[manage_customer_name])

        trans_df = get_transactions(conn, manage_customer_id)

        st.dataframe(trans_df, use_container_width=True, hide_index=True)

        delete_trans_id = st.number_input(
            "Enter Transaction DB ID to Delete",
            min_value=0,
            step=1
        )

        if st.button("🗑 Delete Transaction"):
            try:
                cur = run_query(conn, """
                DELETE FROM ledger_transactions
                WHERE id=%s
                """, (delete_trans_id,))
                conn.commit()
                cur.close()
                recalculate_balances(conn, manage_customer_id)
                st.success("✅ Transaction Deleted")
                st.rerun()
            except mysql.connector.Error as e:
                conn.rollback()
                st.error(f"❌ Error deleting transaction: {e}")

# =========================
# SIDEBAR — LOGOUT
# =========================

with st.sidebar:
    st.markdown("---")
    if st.button("🚪 Logout"):
        st.session_state.authenticated = False
        st.rerun()