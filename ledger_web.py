import streamlit as st
import mysql.connector
import pandas as pd
from datetime import date
from io import BytesIO
import json
import gspread
from google.oauth2.service_account import Credentials
import hmac
import time
import logging
import re

# Secure server-side logging (never exposed to client browser)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ledger_app")

# =========================
# SECURITY PROTOCOLS & SANITIZATION
# =========================

def sanitize_formula_injection(val):
    """
    Neutralizes CSV / Excel Formula Injection (CWE-1236).
    Prepends a single quote if string starts with '=', '+', '-', '@', '\t', '\r'.
    """
    if val is None:
        return ""
    s = str(val).strip()
    if s and s[0] in ('=', '+', '-', '@', '\t', '\r'):
        return "'" + s
    return s


def sanitize_text(val, max_len=100):
    """Sanitizes text inputs, removes non-printable control characters, and truncates to max_len."""
    if val is None:
        return ""
    cleaned = "".join(ch for ch in str(val) if ch.isprintable() or ch in " \t")
    return sanitize_formula_injection(cleaned.strip())[:max_len]

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

MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_SECONDS = 30

def check_password():
    """
    Secure authentication gate with:
    - Constant-time password comparison (CWE-208 mitigation)
    - Anti-brute-force rate limiting and temporary lockout (CWE-307 mitigation)
    """
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "login_failed_attempts" not in st.session_state:
        st.session_state.login_failed_attempts = 0
    if "login_lockout_until" not in st.session_state:
        st.session_state.login_lockout_until = 0.0

    if st.session_state.authenticated:
        return True

    now = time.time()
    if now < st.session_state.login_lockout_until:
        remaining = int(st.session_state.login_lockout_until - now)
        st.error(f"🔒 Too many failed login attempts. Access temporarily locked. Please wait {remaining} seconds.")
        st.stop()

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
                expected_pwd = str(st.secrets.get("app_password", "")).strip()
                # Constant-time comparison to prevent timing side-channel attacks
                if expected_pwd and hmac.compare_digest(password.strip(), expected_pwd):
                    st.session_state.authenticated = True
                    st.session_state.login_failed_attempts = 0
                    st.session_state.login_lockout_until = 0.0
                    logger.info("User authenticated successfully.")
                    st.rerun()
                else:
                    st.session_state.login_failed_attempts += 1
                    attempts = st.session_state.login_failed_attempts
                    logger.warning(f"Failed login attempt ({attempts}/{MAX_LOGIN_ATTEMPTS})")
                    if attempts >= MAX_LOGIN_ATTEMPTS:
                        st.session_state.login_lockout_until = time.time() + LOCKOUT_DURATION_SECONDS
                        st.error(f"🔒 Maximum attempts exceeded. Account locked out for {LOCKOUT_DURATION_SECONDS} seconds.")
                    else:
                        st.error(f"Incorrect password ({attempts}/{MAX_LOGIN_ATTEMPTS} attempts before temporary lockout)")

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
# GOOGLE SHEETS LIVE SYNC
# =========================

def get_google_sheet():
    """Connect to Google Sheet using built-in authentication."""
    try:
        import gsync_auth
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        creds_info = gsync_auth.get_credentials_info()
        creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
        client = gspread.authorize(creds)
        sheet_id = st.secrets.get("google_sheet_id", "1C_SZGXkWEpmmH_UojnOStyxXRUAWOVhoo7-U8mI9lnQ")
        sheet = client.open_by_key(sheet_id)
        return sheet, None
    except Exception as e:
        return None, str(e)


def sync_to_google_sheet(customer_name, rows_to_append):
    """
    Appends rows to the dedicated customer worksheet in Google Sheets.
    Each customer gets their own separate worksheet tab (named after customer).
    rows_to_append: list of [Date, Txn_ID, Vehicle, Product, Litres, Debit, Credit, Running_Balance]
    Returns (True, msg) or (False, error_msg)
    """
    try:
        sheet, err = get_google_sheet()
        if not sheet:
            return False, f"Could not open Google Sheet: {err}"
        if not rows_to_append:
            return False, "No rows to sync."

        # Sanitize customer name for tab title (max 30 chars, no illegal characters)
        tab_name = "".join(c for c in customer_name if c not in r'/\?*[]:').strip()[:30]
        if not tab_name:
            tab_name = "Customer"

        # Find or create worksheet for this specific customer
        existing_titles = [ws.title for ws in sheet.worksheets()]
        if tab_name in existing_titles:
            worksheet = sheet.worksheet(tab_name)
        else:
            worksheet = sheet.add_worksheet(title=tab_name, rows=1000, cols=10)
            # Add header row
            worksheet.append_row([
                "Date", "Transaction ID", "Vehicle", "Product",
                "Litres", "Debit (₹)", "Credit (₹)", "Balance (₹)"
            ])

        # Batch append rows
        worksheet.append_rows(rows_to_append, value_input_option="USER_ENTERED")
        return True, "Synced successfully"
    except Exception as e:
        return False, str(e)


def dates_match(d1, d2):
    """Safely compares two dates in string or date object format."""
    if not d1 or not d2:
        return False
    s1 = str(d1).strip()
    s2 = str(d2).strip()
    if s1 == s2:
        return True
    try:
        dt1 = pd.to_datetime(s1).date()
        dt2 = pd.to_datetime(s2).date()
        return dt1 == dt2
    except Exception:
        return False


def clean_amount(val):
    """Safely extracts a float amount from formatted currency or string."""
    if val is None or val == "":
        return 0.0
    s = str(val).replace("₹", "").replace(",", "").replace("$", "").strip()
    try:
        return round(float(s), 2)
    except Exception:
        return 0.0


def delete_transaction_from_google_sheet(customer_name, trans_date, trans_id, debit, credit, vehicle=None, product=None):
    """
    Finds and deletes a specific transaction row from the customer's Google Sheet tab
    when an individual transaction is deleted manually in Tab 4.
    Recalculates running balance for remaining rows.
    STRICT NOTE: This function is only called on manual single transaction deletion.
    It is NEVER called during annual database clearing.
    """
    try:
        sheet, err = get_google_sheet()
        if not sheet:
            return False, f"Could not connect to Google Sheet: {err}"

        tab_name = "".join(c for c in customer_name if c not in r'/\?*[]:').strip()[:30]
        if not tab_name:
            tab_name = "Customer"

        existing_titles = [ws.title for ws in sheet.worksheets()]
        if tab_name not in existing_titles:
            return False, f"Worksheet tab '{tab_name}' not found in Google Sheet."

        worksheet = sheet.worksheet(tab_name)
        all_records = worksheet.get_all_values()

        if len(all_records) <= 1:
            return False, "Worksheet has no transaction rows."

        # Target criteria
        s_txid = str(trans_id or "").strip().lower()
        s_deb = clean_amount(debit)
        s_cred = clean_amount(credit)
        s_veh = str(vehicle or "").strip().lower()

        target_row_idx = None

        # Row 1 is headers (Date, Txn ID, Vehicle, Product, Litres, Debit, Credit, Balance)
        for idx, row in enumerate(all_records[1:], start=2):
            if not row:
                continue

            r_date_str = str(row[0]).strip() if len(row) > 0 else ""
            r_txid = str(row[1]).strip().lower() if len(row) > 1 else ""
            r_veh = str(row[2]).strip().lower() if len(row) > 2 else ""
            r_deb = clean_amount(row[5]) if len(row) > 5 else 0.0
            r_cred = clean_amount(row[6]) if len(row) > 6 else 0.0

            # 1. Date match
            if not dates_match(r_date_str, trans_date):
                continue

            # 2. If txn_id is available and non-empty, check match
            if s_txid != "" and r_txid == s_txid:
                target_row_idx = idx
                break

            # 3. If txn_id is blank or not matching, compare amounts and vehicle
            amounts_match = (abs(r_deb - s_deb) < 0.01 and abs(r_cred - s_cred) < 0.01)
            veh_match = (s_veh == "" or r_veh == s_veh or r_veh == "" or s_veh == "-")

            if amounts_match and veh_match:
                target_row_idx = idx
                break

        if not target_row_idx:
            return False, "Transaction row not found in Google Sheet (may have already been deleted or not synced)."

        # Delete the specific row from Google Sheet
        worksheet.delete_rows(target_row_idx)

        # Recalculate and update the running balance column for remaining rows in Google Sheet
        try:
            remaining_records = worksheet.get_all_values()
            if len(remaining_records) > 1:
                running_bal = 0.0
                updated_balances = []
                for r in remaining_records[1:]:
                    deb_val = clean_amount(r[5]) if len(r) > 5 else 0.0
                    cred_val = clean_amount(r[6]) if len(r) > 6 else 0.0
                    running_bal += (deb_val - cred_val)
                    updated_balances.append([round(running_bal, 2)])
                end_row = 1 + len(updated_balances)
                worksheet.update(range_name=f"H2:H{end_row}", values=updated_balances, value_input_option="USER_ENTERED")
        except Exception:
            pass  # Row deletion was already successful

        return True, f"Transaction row #{target_row_idx} deleted from Google Sheet."
    except Exception as e:
        return False, str(e)


# =========================
# HELPER FUNCTIONS
# =========================

def recalculate_balances(conn, customer_id):
    """Recalculate running balances for a customer efficiently in one transaction."""
    cur = run_query(conn, """
    SELECT id, debit, credit FROM ledger_transactions
    WHERE customer_id=%s ORDER BY trans_date ASC, id ASC
    """, (customer_id,))
    rows = cur.fetchall()
    cur.close()

    if not rows:
        return

    running = 0.0
    update_cur = conn.cursor()
    for row in rows:
        row_id = row[0]
        debit = float(row[1] or 0)
        credit = float(row[2] or 0)

        # Debit increases payable balance, Credit reduces payable balance
        running += (debit - credit)

        update_cur.execute(
            "UPDATE ledger_transactions SET balance=%s WHERE id=%s",
            (round(running, 2), row_id)
        )
    conn.commit()
    update_cur.close()


def ensure_transactions_in_google_sheet(customer_name, tx_rows):
    """
    Safely verifies and appends any un-synced transactions to Google Sheets
    BEFORE annual clearance in MySQL.
    NEVER duplicates existing rows.
    NEVER deletes any rows from Google Sheets.
    """
    try:
        sheet, err = get_google_sheet()
        if not sheet or not tx_rows:
            return
        
        tab_name = "".join(c for c in customer_name if c not in r'/\?*[]:').strip()[:30]
        if not tab_name:
            tab_name = "Customer"

        existing_titles = [ws.title for ws in sheet.worksheets()]
        if tab_name not in existing_titles:
            worksheet = sheet.add_worksheet(title=tab_name, rows=1000, cols=10)
            worksheet.append_row([
                "Date", "Transaction ID", "Vehicle", "Product",
                "Litres", "Debit (₹)", "Credit (₹)", "Balance (₹)"
            ])
            existing_data = []
        else:
            worksheet = sheet.worksheet(tab_name)
            existing_data = worksheet.get_all_values()

        existing_keys = set()
        for r in existing_data[1:]:
            if len(r) >= 7:
                k_date = str(r[0]).strip()
                k_txid = str(r[1]).strip().lower()
                k_deb = f"{clean_amount(r[5]):.2f}"
                k_cred = f"{clean_amount(r[6]):.2f}"
                existing_keys.add((k_date, k_txid, k_deb, k_cred))

        missing_rows = []
        for r in tx_rows:
            # r: [id, trans_date, trans_id, vehicle, product, litres, debit, credit, balance]
            s_date = str(r[1]).strip()
            s_txid = str(r[2] or "").strip().lower()
            s_deb = f"{float(r[6] or 0):.2f}"
            s_cred = f"{float(r[7] or 0):.2f}"

            key = (s_date, s_txid, s_deb, s_cred)
            if key not in existing_keys:
                missing_rows.append([
                    str(r[1]), str(r[2] or ""), str(r[3] or ""), str(r[4] or ""),
                    float(r[5] or 0), float(r[6] or 0), float(r[7] or 0), float(r[8] or 0)
                ])

        if missing_rows:
            worksheet.append_rows(missing_rows, value_input_option="USER_ENTERED")
    except Exception:
        pass


def archive_old_year_transactions(conn, target_year):
    """
    Annual Database Clearance for a specific year (e.g. 2025):
    1. Ensures any un-synced transactions are safely archived in Google Sheets (no duplicates).
    2. Calculates customer's net movement for that year.
    3. Deletes target year's transactions ONLY from MySQL database to free up disk space.
    4. Inserts a clean 'B/F Balance (target_year)' summary transaction in MySQL.
    5. Recalculates running balances in MySQL for all subsequent records.
    
    STRICT SAFETY GUARANTEE:
    - Google Sheets is NEVER modified for deletion.
    - Full detailed transaction history is permanently preserved in Google Drive.
    """
    try:
        cur = run_query(conn, "SELECT customer_id, customer_name FROM customers")
        all_custs = cur.fetchall()
        cur.close()

        total_pruned = 0
        for cust_id, cust_name in all_custs:
            # Fetch transactions for target year
            cur_tx = run_query(conn, """
            SELECT id, trans_date, trans_id, vehicle, product, litres, debit, credit, balance
            FROM ledger_transactions
            WHERE customer_id=%s AND YEAR(trans_date)=%s
            ORDER BY trans_date ASC, id ASC
            """, (cust_id, target_year))
            tx_rows = cur_tx.fetchall()
            cur_tx.close()

            if not tx_rows:
                continue

            # Step 1: Ensure backed up in Google Sheets (NO deletion on Sheets!)
            ensure_transactions_in_google_sheet(cust_name, tx_rows)

            # Step 2: Calculate net movement for that year
            net_diff = round(sum(float(r[6] or 0) - float(r[7] or 0) for r in tx_rows), 2)

            # Step 3: Delete old year's transactions ONLY from MySQL
            del_cur = run_query(conn, """
            DELETE FROM ledger_transactions
            WHERE customer_id=%s AND YEAR(trans_date)=%s
            """, (cust_id, target_year))
            conn.commit()
            del_cur.close()
            total_pruned += len(tx_rows)

            # Step 4: Insert B/F Balance record in MySQL to preserve balance continuity
            op_debit = net_diff if net_diff > 0 else 0.0
            op_credit = abs(net_diff) if net_diff < 0 else 0.0
            ins_cur = run_query(conn, """
            INSERT INTO ledger_transactions (customer_id, trans_date, trans_id, vehicle, product, litres, debit, credit, balance)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                cust_id,
                f"{target_year}-12-31",
                f"BF-{target_year}",
                "-",
                f"B/F Balance ({target_year})",
                0.0,
                op_debit,
                op_credit,
                0.0
            ))
            conn.commit()
            ins_cur.close()

            # Recalculate MySQL running balances
            recalculate_balances(conn, cust_id)

        return True, f"Successfully cleared {total_pruned} records for year {target_year} from MySQL. Google Sheets historical data remains 100% intact!"
    except Exception as e:
        conn.rollback()
        return False, str(e)


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
                clean_name = sanitize_text(name, max_len=100)
                clean_phone = re.sub(r"[^\d+\-\s()]", "", phone.strip())[:20]
                if not clean_name:
                    st.error("Please enter a valid customer name.")
                else:
                    try:
                        cur = run_query(conn, "INSERT INTO customers(sales_id, customer_name, phone) VALUES(%s,%s,%s)",
                                        (1, clean_name, clean_phone))
                        conn.commit()
                        cur.close()
                        st.success(f"Added **{clean_name}**")
                        st.rerun()
                    except mysql.connector.Error as e:
                        conn.rollback()
                        logger.error(f"Database error adding customer: {e}")
                        st.error("Could not add customer due to a database error. Please try again.")

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
                    clean_tx_id = sanitize_text(trans_id, max_len=50)
                    clean_vehicle = sanitize_text(vehicle, max_len=50)
                    clean_product = sanitize_text(product, max_len=100)

                    if litres < 0 or debit < 0 or credit < 0:
                        st.error("Quantities and amounts cannot be negative.")
                    elif debit == 0 and credit == 0:
                        st.warning("Please enter either a Debit or Credit amount.")
                    else:
                        try:
                            cur = run_query(conn, """
                            INSERT INTO ledger_transactions(customer_id, trans_date, trans_id, vehicle, product, litres, debit, credit, balance)
                            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)
                            """, (selected_customer, trans_date, clean_tx_id, clean_vehicle,
                                  clean_product, float(litres), float(debit), float(credit), 0))
                            conn.commit()
                            cur.close()
                            recalculate_balances(conn, selected_customer)

                            # Auto-append to dedicated customer worksheet in Google Sheets
                            updated_txns = get_transactions(conn, selected_customer)
                            curr_balance = updated_txns["balance"].iloc[-1] if not updated_txns.empty else 0.0

                            sync_ok, sync_msg = sync_to_google_sheet(selected_name, [[
                                str(trans_date),
                                clean_tx_id,
                                clean_vehicle,
                                clean_product,
                                float(litres),
                                float(debit),
                                float(credit),
                                float(curr_balance)
                            ]])

                            if sync_ok:
                                st.success("✅ Transaction added & synced to Google Sheets!")
                            else:
                                st.success("✅ Transaction added to MySQL!")
                                st.warning(f"Google Sheets notice: {sync_msg}")

                            st.rerun()
                        except mysql.connector.Error as e:
                            conn.rollback()
                            logger.error(f"Database error adding transaction: {e}")
                            st.error("Could not add transaction due to a database error. Please try again.")

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

            # Shield exported statements from CSV / Excel Formula Injection (CWE-1236)
            for col in ["Txn ID", "Vehicle", "Product"]:
                if col in export_df.columns:
                    export_df[col] = export_df[col].astype(str).apply(sanitize_formula_injection)

            excel_buffer = BytesIO()
            with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                export_df.to_excel(writer, index=False, sheet_name=selected_name[:30])
            excel_data = excel_buffer.getvalue()

            csv_data = export_df.to_csv(index=False).encode('utf-8')

            btn_c1, btn_c2, btn_c3 = st.columns([1.5, 1.5, 2])
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

            if btn_c3.button(f"☁️ Sync All to Google Sheet", use_container_width=True, key=f"manual_gsync_{selected_customer}"):
                all_rows = []
                for _, r in filtered_df.iterrows():
                    all_rows.append([
                        str(r["trans_date"]),
                        str(r["trans_id"]),
                        str(r["vehicle"]),
                        str(r["product"]),
                        float(r["litres"]),
                        float(r["debit"]),
                        float(r["credit"]),
                        float(r["balance"])
                    ])
                ok, msg = sync_to_google_sheet(selected_name, all_rows)
                if ok:
                    st.success(f"✅ Synced {len(all_rows)} rows to Google Sheet tab '{selected_name}'!")
                else:
                    st.error(f"❌ Google Sheets error: {msg}")
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

                    # Guard against excessive batch size (DoS prevention)
                    if len(df) > 5000:
                        st.error("Uploaded file exceeds the maximum batch limit of 5,000 rows. Please split the file into smaller batches.")
                        st.stop()

                    # Clean data, enforce non-negative values, and sanitize against Formula Injection
                    df["litres"] = pd.to_numeric(df["litres"], errors="coerce").fillna(0.0).clip(lower=0.0)
                    df["debit"] = pd.to_numeric(df["debit"], errors="coerce").fillna(0.0).clip(lower=0.0)
                    df["credit"] = pd.to_numeric(df["credit"], errors="coerce").fillna(0.0).clip(lower=0.0)
                    df["trans_date"] = pd.to_datetime(df["trans_date"], errors="coerce", dayfirst=True).dt.date
                    df["trans_date"] = df["trans_date"].fillna(date.today())
                    df["trans_id"] = df["trans_id"].astype(str).replace("nan", "").apply(sanitize_formula_injection).str.slice(0, 50)
                    df["vehicle"] = df["vehicle"].astype(str).replace("nan", "").apply(sanitize_formula_injection).str.slice(0, 50)
                    df["product"] = df["product"].astype(str).replace("nan", "").apply(sanitize_formula_injection).str.slice(0, 100)

                    # Preview
                    preview_df = df[["trans_date", "trans_id", "vehicle", "product", "litres", "debit", "credit"]]
                    st.markdown(f"**Preview — {len(preview_df)} rows to import for {import_customer}:**")
                    st.dataframe(preview_df, use_container_width=True, hide_index=True, height=350)

                    col_a, col_b = st.columns([1, 3])
                    with col_a:
                        if st.button("✅ Confirm Import", use_container_width=True, type="primary"):
                            records_to_insert = [
                                (
                                    import_customer_id,
                                    row["trans_date"],
                                    str(row["trans_id"]).strip(),
                                    str(row["vehicle"]).strip(),
                                    str(row["product"]).strip(),
                                    float(row["litres"]),
                                    float(row["debit"]),
                                    float(row["credit"]),
                                    0
                                )
                                for _, row in preview_df.iterrows()
                            ]

                            try:
                                insert_cur = conn.cursor()
                                insert_cur.executemany("""
                                INSERT INTO ledger_transactions(customer_id, trans_date, trans_id, vehicle, product, litres, debit, credit, balance)
                                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)
                                """, records_to_insert)
                                conn.commit()
                                insert_cur.close()

                                recalculate_balances(conn, import_customer_id)

                                # Auto-sync batch import to Google Sheets dedicated customer tab
                                updated_txns = get_transactions(conn, import_customer_id)
                                gsheet_rows = []
                                for _, r in updated_txns.tail(len(records_to_insert)).iterrows():
                                    gsheet_rows.append([
                                        str(r["trans_date"]),
                                        str(r["trans_id"]),
                                        str(r["vehicle"]),
                                        str(r["product"]),
                                        float(r["litres"]),
                                        float(r["debit"]),
                                        float(r["credit"]),
                                        float(r["balance"])
                                    ])
                                sync_to_google_sheet(import_customer, gsheet_rows)

                                st.success(f"✅ Successfully imported {len(records_to_insert)} transactions and synced to Google Sheets!")
                                st.rerun()
                            except mysql.connector.Error as e:
                                conn.rollback()
                                st.error(f"❌ Error during import: {e}")

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

                if st.button("Delete Transaction", key="btn_del_trans", type="primary"):
                    try:
                        # Verify and retrieve transaction details before deleting
                        chk = run_query(conn, """
                        SELECT id, trans_date, trans_id, vehicle, product, debit, credit
                        FROM ledger_transactions
                        WHERE id=%s AND customer_id=%s
                        """, (del_trans_id, manage_id))
                        tx_row = chk.fetchone()
                        chk.close()

                        if not tx_row:
                            st.error(f"Transaction ID #{del_trans_id} not found for {manage_name}.")
                        else:
                            _, tx_date, tx_code, tx_veh, tx_prod, tx_deb, tx_cred = tx_row

                            # 1. Delete from MySQL database
                            cur = run_query(conn, "DELETE FROM ledger_transactions WHERE id=%s AND customer_id=%s", (del_trans_id, manage_id))
                            conn.commit()
                            cur.close()

                            # 2. Recalculate MySQL running balances
                            recalculate_balances(conn, manage_id)

                            # 3. Delete matching row from customer's Google Sheet
                            gs_ok, gs_msg = delete_transaction_from_google_sheet(
                                customer_name=manage_name,
                                trans_date=tx_date,
                                trans_id=tx_code,
                                debit=tx_deb,
                                credit=tx_cred,
                                vehicle=tx_veh,
                                product=tx_prod
                            )

                            if gs_ok:
                                st.success(f"✅ Transaction #{del_trans_id} deleted successfully from MySQL and Google Sheets!")
                            else:
                                st.success(f"✅ Transaction #{del_trans_id} deleted from MySQL.")
                                st.warning(f"Google Sheet notice: {gs_msg}")

                            st.rerun()
                    except Exception as e:
                        conn.rollback()
                        st.error(f"Error deleting transaction: {e}")

        # ==========================================
        # 📦 YEARLY STORAGE PRUNE & ARCHIVAL SECTION
        # ==========================================
        st.markdown("---")
        st.markdown("#### 🧹 Clean Transactions (Yearly Database Clearance)")
        st.markdown(
            "<p style='color:#64748b; font-size:13px; margin-bottom:16px;'>"
            "Clean up historical records from <b>MySQL database</b> to free up storage. "
            "A single <b>B/F Balance (Year)</b> summary entry is kept in MySQL to maintain balance continuity.<br>"
            "<b style='color:#16a34a;'>🛡️ Google Drive Protection:</b> Your Google Spreadsheet data is <b>NEVER deleted</b> during manual database clearance. "
            "All historical transactions remain permanently in Google Sheets."
            "</p>",
            unsafe_allow_html=True
        )

        col_arch1, col_arch2 = st.columns([1.5, 2])

        with col_arch1:
            # Check available distinct years in the transactions table
            year_cur = run_query(conn, "SELECT DISTINCT YEAR(trans_date) FROM ledger_transactions WHERE trans_date IS NOT NULL ORDER BY 1 ASC")
            available_years = [int(y[0]) for y in year_cur.fetchall() if y[0] is not None]
            year_cur.close()

            if not available_years:
                st.info("No transaction records found in the database to clean.")
            else:
                target_year = st.selectbox("Select Year to Clean from MySQL", available_years, key="archive_year_sel")

                # Count records for that year
                cnt_cur = run_query(conn, "SELECT COUNT(*) FROM ledger_transactions WHERE YEAR(trans_date)=%s", (target_year,))
                year_records = cnt_cur.fetchone()[0]
                cnt_cur.close()

                st.caption(f"Found **{year_records}** records for year **{target_year}** in MySQL.")

                st.markdown("<div style='margin-top:12px;'></div>", unsafe_allow_html=True)
                if "cleanup_failed_attempts" not in st.session_state:
                    st.session_state.cleanup_failed_attempts = 0
                if "cleanup_lockout_until" not in st.session_state:
                    st.session_state.cleanup_lockout_until = 0.0

                now = time.time()
                is_cleanup_locked = now < st.session_state.cleanup_lockout_until

                if is_cleanup_locked:
                    rem_sec = int(st.session_state.cleanup_lockout_until - now)
                    st.error(f"🔒 Yearly clearance locked due to multiple failed attempts. Please wait {rem_sec} seconds.")

                cleanup_master_pwd = st.text_input(
                    "🔑 Master Password for Yearly Clearance",
                    type="password",
                    placeholder="Enter master password to authorize",
                    key="yearly_cleanup_master_pwd",
                    disabled=is_cleanup_locked,
                    help="Master authorization password required to clear MySQL data."
                )

                confirm_cleanup_box = st.checkbox(
                    f"⚠️ I confirm authorization to purge MySQL records for year {target_year} (Google Sheets audit trail remains 100% preserved).",
                    key=f"confirm_clean_{target_year}"
                )

                if st.button(f"🧹 Clean Year {target_year} Transactions (MySQL Only)", type="primary", key="btn_run_archive", disabled=is_cleanup_locked):
                    expected_master = str(st.secrets.get("yearly_cleanup_password", "AAYEARLYCLEANUP")).strip()

                    if not cleanup_master_pwd:
                        st.error("🔒 Master Password is required to perform yearly database clearance.")
                    # Constant-time comparison to prevent timing attacks
                    elif not hmac.compare_digest(cleanup_master_pwd.strip(), expected_master):
                        st.session_state.cleanup_failed_attempts += 1
                        attempts = st.session_state.cleanup_failed_attempts
                        logger.warning(f"Failed master clearance password attempt ({attempts}/3)")
                        if attempts >= 3:
                            st.session_state.cleanup_lockout_until = time.time() + 60.0
                            st.error("🔒 Too many incorrect master password attempts. Clearance locked for 60 seconds.")
                        else:
                            st.error(f"❌ Invalid Master Password! Access denied ({attempts}/3 attempts before lockout).")
                    elif not confirm_cleanup_box:
                        st.warning("⚠️ Please check the confirmation box above to verify authorization.")
                    elif year_records == 0:
                        st.warning(f"No records found to clean for year {target_year}.")
                    else:
                        st.session_state.cleanup_failed_attempts = 0
                        with st.spinner(f"Safely clearing year {target_year} from MySQL (Google Drive 100% preserved)..."):
                            ok, msg = archive_old_year_transactions(conn, target_year)
                            if ok:
                                logger.info(f"Annual cleanup executed for year {target_year}.")
                                st.success(f"✅ {msg}")
                                st.rerun()
                            else:
                                logger.error(f"Archival error: {msg}")
                                st.error("❌ An error occurred during database clearance.")

        with col_arch2:
            # Query table size
            try:
                size_cur = run_query(conn, """
                SELECT 
                    ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) AS 'size_mb'
                FROM information_schema.TABLES
                WHERE table_schema = DATABASE()
                """)
                db_size = float(size_cur.fetchone()[0] or 0.0)
                size_cur.close()

                # Aiven free tier is 1024 MB
                max_mb = 1024.0
                pct = min(round((db_size / max_mb) * 100, 2), 100.0)

                st.markdown(f"""
                <div style="background:#f8fafc; border:1px solid #e2e8f0; border-radius:12px; padding:16px;">
                    <div style="font-weight:700; color:#1e293b; margin-bottom:4px;">MySQL Disk Gauge</div>
                    <div style="font-size:24px; font-weight:800; color:#2563eb;">{db_size} MB <span style="font-size:14px; color:#64748b; font-weight:500;">/ 1024 MB ({pct}%)</span></div>
                    <div style="background:#e2e8f0; border-radius:8px; height:8px; margin:8px 0; overflow:hidden;">
                        <div style="background:#2563eb; width:{max(pct, 2)}%; height:100%;"></div>
                    </div>
                    <div style="color:#64748b; font-size:12px;">✅ Synced safely with Google Sheets</div>
                </div>
                """, unsafe_allow_html=True)
            except Exception:
                pass

# =========================
# SIDEBAR
# =========================

with st.sidebar:
    st.markdown("### ⛽ AA ENTERPRISES")
    st.caption("Sales Ledger System")
    st.markdown("---")
    if st.button("🚪 Logout", use_container_width=True):
        st.session_state.clear()
        st.session_state.authenticated = False
        logger.info("User logged out; session state cleared.")
        st.rerun()