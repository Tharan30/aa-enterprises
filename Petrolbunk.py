
# AA ENTERPRISES - SALES LEDGER SYSTEM - CORRECTED VERSION
# =========================================================

# INSTALL:
# pip install customtkinter mysql-connector-python tkcalendar pandas reportlab openpyxl

import customtkinter as ctk
from tkinter import ttk, messagebox, filedialog
import mysql.connector
from datetime import datetime
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from tkcalendar import DateEntry
import pandas as pd


# =========================================================
# MYSQL CONNECTION
# =========================================================

conn = mysql.connector.connect(
    host="192.168.1.40",
    user="ledger_user",
    password="StrongPassword@123",
    database="aa_enterprises"
)

# IMPORTANT: buffered=True prevents "Unread result found"
cursor = conn.cursor(buffered=True)


# =========================================================
# CREATE TABLES
# =========================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS sales (
    sales_id INT AUTO_INCREMENT PRIMARY KEY,
    sales_name VARCHAR(100)
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS customers (
    customer_id INT AUTO_INCREMENT PRIMARY KEY,
    sales_id INT,
    customer_name VARCHAR(150),
    phone VARCHAR(20),
    FOREIGN KEY (sales_id)
    REFERENCES sales(sales_id)
    ON DELETE CASCADE
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS ledger_transactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT,
    trans_date DATE,
    trans_id VARCHAR(50),
    vehicle VARCHAR(20),
    product VARCHAR(50),
    litres DECIMAL(10,2),
    debit DECIMAL(10,2),
    credit DECIMAL(10,2),
    balance DECIMAL(10,2),
    FOREIGN KEY (customer_id)
    REFERENCES customers(customer_id)
    ON DELETE CASCADE
)
""")

conn.commit()

# If old table already had trans_id as BIGINT, convert it safely to VARCHAR.
try:
    cursor.execute("""
    ALTER TABLE ledger_transactions
    MODIFY COLUMN trans_id VARCHAR(50)
    """)
    conn.commit()
except Exception:
    pass


# =========================================================
# INSERT SALES HEADER
# =========================================================

cursor.execute("""
INSERT IGNORE INTO sales(sales_id, sales_name)
VALUES(1, 'Sales')
""")

conn.commit()


# =========================================================
# APP SETTINGS
# =========================================================

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

app = ctk.CTk()
app.geometry("1500x850")
app.title("AA ENTERPRISES")


# =========================================================
# GLOBAL VARIABLES
# =========================================================

selected_customer = None


# =========================================================
# HELPER FUNCTIONS
# =========================================================

def parse_amount(entry_widget):
    text = entry_widget.get().strip()

    if text == "":
        return 0.0

    text = text.replace(",", "")

    return float(text)


def parse_text(value):
    if pd.isna(value):
        return ""

    return str(value).strip()


def parse_number(value):
    if pd.isna(value):
        return 0.0

    value = str(value).replace(",", "").strip()

    if value == "":
        return 0.0

    return float(value)


def clear_customer_fields():
    customer_name_entry.delete(0, "end")
    phone_entry.delete(0, "end")


def clear_transaction_table():
    for item in trans_tree.get_children():
        trans_tree.delete(item)


# =========================================================
# BALANCE FUNCTIONS
# =========================================================

def recalculate_balances(customer_id):
    """
    Signed ledger calculation:
    - If DEBIT is entered/imported as negative, it reduces balance.
    - If CREDIT is positive, it increases balance.
    - Negative credit is also supported.
    """

    cursor.execute("""
    SELECT
        id,
        debit,
        credit
    FROM ledger_transactions
    WHERE customer_id=%s
    ORDER BY trans_date ASC, id ASC
    """, (customer_id,))

    rows = cursor.fetchall()

    running_balance = 0.0

    for row in rows:
        db_id = row[0]
        debit = float(row[1] or 0)
        credit = float(row[2] or 0)

        # Debit and credit are treated as signed values.
        running_balance += debit + credit

        cursor.execute("""
        UPDATE ledger_transactions
        SET balance=%s
        WHERE id=%s
        """, (
            round(running_balance, 2),
            db_id
        ))

    conn.commit()


# =========================================================
# LOAD FUNCTIONS
# =========================================================

def load_customers():
    for item in customer_tree.get_children():
        customer_tree.delete(item)

    cursor.execute("""
    SELECT
        customer_id,
        customer_name,
        phone
    FROM customers
    ORDER BY customer_name
    """)

    rows = cursor.fetchall()

    for row in rows:
        customer_tree.insert(
            "",
            "end",
            values=(
                row[0],
                row[1],
                row[2]
            )
        )


def load_transactions(customer_id):
    for item in trans_tree.get_children():
        trans_tree.delete(item)

    cursor.execute("""
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
    """, (customer_id,))

    rows = cursor.fetchall()

    for row in rows:
        trans_tree.insert(
            "",
            "end",
            values=row
        )


# =========================================================
# CUSTOMER FUNCTIONS
# =========================================================

def add_customer():
    name = customer_name_entry.get().strip()
    phone = phone_entry.get().strip()

    if name == "":
        messagebox.showerror(
            "Error",
            "Enter Customer Name"
        )
        return

    cursor.execute("""
    INSERT INTO customers(
        sales_id,
        customer_name,
        phone
    )
    VALUES(%s,%s,%s)
    """, (
        1,
        name,
        phone
    ))

    conn.commit()

    load_customers()
    clear_customer_fields()
    clear_transaction_table()

    customer_title.configure(text="Select Customer")
    customer_name_entry.focus()

    messagebox.showinfo(
        "Success",
        "Customer Added"
    )


def update_customer():
    global selected_customer

    selected = customer_tree.focus()

    if not selected:
        messagebox.showerror(
            "Error",
            "Select Customer"
        )
        return

    values = customer_tree.item(
        selected,
        "values"
    )

    customer_id = int(values[0])

    new_name = customer_name_entry.get().strip()
    new_phone = phone_entry.get().strip()

    if new_name == "":
        messagebox.showerror(
            "Error",
            "Customer Name Required"
        )
        return

    cursor.execute("""
    UPDATE customers
    SET
        customer_name=%s,
        phone=%s
    WHERE customer_id=%s
    """, (
        new_name,
        new_phone,
        customer_id
    ))

    conn.commit()

    selected_customer = customer_id

    load_customers()
    customer_title.configure(text=new_name)

    messagebox.showinfo(
        "Success",
        "Customer Updated"
    )


def delete_customer():
    global selected_customer

    selected = customer_tree.focus()

    if not selected:
        messagebox.showerror(
            "Error",
            "Select Customer"
        )
        return

    values = customer_tree.item(
        selected,
        "values"
    )

    customer_id = int(values[0])
    customer_name = values[1]

    confirm = messagebox.askyesno(
        "Confirm Delete",
        f"Delete customer '{customer_name}' and all transactions?"
    )

    if not confirm:
        return

    cursor.execute("""
    DELETE FROM customers
    WHERE customer_id=%s
    """, (customer_id,))

    conn.commit()

    selected_customer = None

    load_customers()
    clear_customer_fields()
    clear_transaction_table()

    customer_title.configure(text="Select Customer")

    messagebox.showinfo(
        "Deleted",
        "Customer Deleted"
    )


def select_customer(event):
    global selected_customer

    selected = customer_tree.focus()

    if not selected:
        return

    values = customer_tree.item(
        selected,
        "values"
    )

    selected_customer = int(values[0])
    customer_name = values[1]
    phone = values[2]

    customer_title.configure(text=customer_name)

    clear_customer_fields()

    customer_name_entry.insert(0, customer_name)
    phone_entry.insert(0, phone)

    load_transactions(selected_customer)


# =========================================================
# TRANSACTION FUNCTIONS
# =========================================================

def add_transaction():
    global selected_customer

    if selected_customer is None:
        messagebox.showerror(
            "Error",
            "Select Customer"
        )
        return

    try:
        formatted_date = datetime.strptime(
            date_entry.get().strip(),
            "%Y-%m-%d"
        ).date()

        trans_id = transid_entry.get().strip()
        vehicle = vehicle_entry.get().strip()
        product = product_entry.get().strip()
        litres = parse_amount(litres_entry)
        debit = parse_amount(debit_entry)
        credit = parse_amount(credit_entry)

        cursor.execute("""
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
            formatted_date,
            trans_id,
            vehicle,
            product,
            litres,
            debit,
            credit,
            0
        ))

        conn.commit()

        recalculate_balances(selected_customer)
        load_transactions(selected_customer)
        clear_transaction_fields()

        messagebox.showinfo(
            "Success",
            "Transaction Added"
        )

    except Exception as e:
        messagebox.showerror(
            "Error",
            str(e)
        )


def update_transaction():
    global selected_customer

    if selected_customer is None:
        messagebox.showerror(
            "Error",
            "Select Customer"
        )
        return

    selected = trans_tree.focus()

    if not selected:
        messagebox.showerror(
            "Error",
            "Select Transaction"
        )
        return

    try:
        values = trans_tree.item(
            selected,
            "values"
        )

        db_id = int(values[0])

        formatted_date = datetime.strptime(
            date_entry.get().strip(),
            "%Y-%m-%d"
        ).date()

        trans_id = transid_entry.get().strip()
        vehicle = vehicle_entry.get().strip()
        product = product_entry.get().strip()
        litres = parse_amount(litres_entry)
        debit = parse_amount(debit_entry)
        credit = parse_amount(credit_entry)

        cursor.execute("""
        UPDATE ledger_transactions
        SET
            trans_date=%s,
            trans_id=%s,
            vehicle=%s,
            product=%s,
            litres=%s,
            debit=%s,
            credit=%s,
            balance=%s
        WHERE id=%s
        """, (
            formatted_date,
            trans_id,
            vehicle,
            product,
            litres,
            debit,
            credit,
            0,
            db_id
        ))

        conn.commit()

        recalculate_balances(selected_customer)
        load_transactions(selected_customer)
        clear_transaction_fields()

        messagebox.showinfo(
            "Success",
            "Transaction Updated"
        )

    except Exception as e:
        messagebox.showerror(
            "Error",
            str(e)
        )


def delete_transaction():
    global selected_customer

    if selected_customer is None:
        messagebox.showerror(
            "Error",
            "Select Customer"
        )
        return

    selected = trans_tree.focus()

    if not selected:
        messagebox.showerror(
            "Error",
            "Select Transaction"
        )
        return

    values = trans_tree.item(
        selected,
        "values"
    )

    db_id = int(values[0])

    confirm = messagebox.askyesno(
        "Confirm Delete",
        "Delete this transaction?"
    )

    if not confirm:
        return

    try:
        cursor.execute(
            "DELETE FROM ledger_transactions WHERE id=%s",
            (db_id,)
        )

        conn.commit()

        recalculate_balances(selected_customer)
        load_transactions(selected_customer)
        clear_transaction_fields()

        messagebox.showinfo(
            "Deleted",
            "Transaction Deleted"
        )

    except Exception as e:
        messagebox.showerror(
            "Error",
            str(e)
        )


def delete_selected_transactions():
    global selected_customer

    if selected_customer is None:
        messagebox.showerror(
            "Error",
            "Select Customer"
        )
        return

    selected_items = trans_tree.selection()

    if not selected_items:
        messagebox.showerror(
            "Error",
            "Select Transactions"
        )
        return

    confirm = messagebox.askyesno(
        "Confirm Delete",
        f"Delete {len(selected_items)} selected transactions?"
    )

    if not confirm:
        return

    try:
        for item in selected_items:
            values = trans_tree.item(
                item,
                "values"
            )

            db_id = int(values[0])

            cursor.execute("""
            DELETE FROM ledger_transactions
            WHERE id=%s
            """, (db_id,))

        conn.commit()

        recalculate_balances(selected_customer)
        load_transactions(selected_customer)
        clear_transaction_fields()

        messagebox.showinfo(
            "Success",
            "Selected Transactions Deleted"
        )

    except Exception as e:
        messagebox.showerror(
            "Error",
            str(e)
        )


def clear_transaction_fields():
    transid_entry.delete(0, "end")
    vehicle_entry.delete(0, "end")
    product_entry.delete(0, "end")
    litres_entry.delete(0, "end")
    debit_entry.delete(0, "end")
    credit_entry.delete(0, "end")
    date_entry.delete(0, "end")

    date_entry.insert(
        0,
        datetime.now().strftime("%Y-%m-%d")
    )

    transid_entry.focus()


def select_transaction(event):
    selected = trans_tree.focus()

    if not selected:
        return

    values = trans_tree.item(
        selected,
        "values"
    )

    transid_entry.delete(0, "end")
    vehicle_entry.delete(0, "end")
    product_entry.delete(0, "end")
    litres_entry.delete(0, "end")
    debit_entry.delete(0, "end")
    credit_entry.delete(0, "end")
    date_entry.delete(0, "end")

    date_entry.insert(0, values[1])
    transid_entry.insert(0, values[2])
    vehicle_entry.insert(0, values[3])
    product_entry.insert(0, values[4])
    litres_entry.insert(0, values[5])
    debit_entry.insert(0, values[6])
    credit_entry.insert(0, values[7])


# =========================================================
# EXPORT PDF
# =========================================================

def export_customer_pdf():
    global selected_customer

    if selected_customer is None:
        messagebox.showerror(
            "Error",
            "Select a customer first"
        )
        return

    from_date = from_date_entry.get_date()
    to_date = to_date_entry.get_date()

    customer_name = customer_title.cget("text")

    default_name = f"{customer_name}_{from_date}_to_{to_date}.pdf"

    file_name = filedialog.asksaveasfilename(
        defaultextension=".pdf",
        initialfile=default_name,
        filetypes=[("PDF Files", "*.pdf")],
        title="Save PDF"
    )

    if not file_name:
        return

    cursor.execute("""
    SELECT
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
    AND trans_date BETWEEN %s AND %s
    ORDER BY trans_date ASC, id ASC
    """, (
        selected_customer,
        from_date,
        to_date
    ))

    data = cursor.fetchall()

    if not data:
        messagebox.showerror(
            "Error",
            "No transactions found"
        )
        return

    pdf = SimpleDocTemplate(file_name)
    elements = []
    styles = getSampleStyleSheet()

    title = Paragraph(
        f"<b>AA ENTERPRISES</b><br/>"
        f"{customer_name}<br/>"
        f"From {from_date} To {to_date}",
        styles["Title"]
    )

    elements.append(title)
    elements.append(Spacer(1, 15))

    table_data = [[
        "Date",
        "Trans ID",
        "Vehicle",
        "Product",
        "Litres",
        "Debit",
        "Credit",
        "Balance"
    ]]

    total_debit = 0.0
    total_credit = 0.0
    last_balance = 0.0

    for row in data:
        debit = float(row[5] or 0)
        credit = float(row[6] or 0)
        balance = float(row[7] or 0)

        total_debit += debit
        total_credit += credit
        last_balance = balance

        table_data.append([
            str(row[0]),
            str(row[1]),
            str(row[2]),
            str(row[3]),
            str(row[4]),
            str(round(debit, 2)),
            str(round(credit, 2)),
            str(round(balance, 2))
        ])

    table_data.append([
        "",
        "",
        "",
        "TOTAL",
        "",
        str(round(total_debit, 2)),
        str(round(total_credit, 2)),
        str(round(last_balance, 2))
    ])

    table = Table(table_data)

    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BACKGROUND", (0, 1), (-1, -2), colors.whitesmoke),
        ("BACKGROUND", (0, -1), (-1, -1), colors.lightgrey),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER")
    ]))

    elements.append(table)
    pdf.build(elements)

    messagebox.showinfo(
        "Success",
        f"PDF Saved\n{file_name}"
    )


# =========================================================
# IMPORT EXCEL
# =========================================================

def import_transactions():

    global selected_customer

    if selected_customer is None:

        messagebox.showerror(
            "Error",
            "Select Customer First"
        )

        return

    file_path = filedialog.askopenfilename(
        title="Select Excel File",
        filetypes=[("Excel Files", "*.xlsx")]
    )

    if not file_path:
        return

    try:

        # READ EXCEL
        # Your Excel header is on the second visible row, so header=1 is needed
        df = pd.read_excel(
            file_path,
            header=1
        )

        # CLEAN COLUMN NAMES
        df.columns = (
            df.columns
            .astype(str)
            .str.strip()
            .str.upper()
        )

        # RENAME COLUMNS TO STANDARD NAMES
        df.rename(columns={

            "TRANS.ID": "TRANS_ID",
            "TRANS ID": "TRANS_ID",
            "TRANS_ID": "TRANS_ID",

            "DATE": "DATE",
            "VEHICLE": "VEHICLE",
            "PRODUCT": "PRODUCT",
            "LITRES": "LITRES",
            "DEBIT": "DEBIT",
            "CREDIT": "CREDIT",
            "BALANCE": "BALANCE"

        }, inplace=True)

        # CHECK DATE COLUMN
        if "DATE" not in df.columns:

            messagebox.showerror(
                "Error",
                f"Missing Column: DATE\n\nDetected Columns:\n{list(df.columns)}"
            )

            return

        inserted_count = 0
        skipped_count = 0

        last_valid_date = None

        for _, row in df.iterrows():

            # -------------------------------
            # DATE HANDLING
            # -------------------------------

            if pd.notna(row.get("DATE")):

                try:
                    trans_date = pd.to_datetime(
                        row.get("DATE"),
                        dayfirst=True
                    ).date()

                    last_valid_date = trans_date

                except Exception:
                    skipped_count += 1
                    continue

            else:

                # For DISCOUNT rows where date is blank,
                # use previous transaction date
                if last_valid_date is None:
                    skipped_count += 1
                    continue

                trans_date = last_valid_date

            # -------------------------------
            # READ VALUES
            # -------------------------------

            trans_id = ""

            if pd.notna(row.get("TRANS_ID")):
                trans_id = str(row.get("TRANS_ID")).strip()

            vehicle = ""

            if pd.notna(row.get("VEHICLE")):
                vehicle = str(row.get("VEHICLE")).strip()

            product = ""

            if pd.notna(row.get("PRODUCT")):
                product = str(row.get("PRODUCT")).strip()

            litres = 0.0

            if pd.notna(row.get("LITRES")):

                litres_value = str(row.get("LITRES")).replace(",", "").strip()

                if litres_value != "":
                    litres = float(litres_value)

            debit = 0.0

            if pd.notna(row.get("DEBIT")):

                debit_value = str(row.get("DEBIT")).replace(",", "").strip()

                if debit_value != "":
                    debit = float(debit_value)

            credit = 0.0

            if pd.notna(row.get("CREDIT")):

                credit_value = str(row.get("CREDIT")).replace(",", "").strip()

                if credit_value != "":
                    credit = float(credit_value)

            # -------------------------------
            # SKIP EMPTY ROWS
            # -------------------------------

            if (
                trans_id == ""
                and vehicle == ""
                and product == ""
                and litres == 0
                and debit == 0
                and credit == 0
            ):

                skipped_count += 1
                continue

            # -------------------------------
            # HANDLE DISCOUNT ROWS
            # -------------------------------

            if "DISCOUNT" in trans_id.upper():

                vehicle = "DISCOUNT"
                product = "DISCOUNT"
                litres = 0.0

            # -------------------------------
            # CHECK DUPLICATE
            # -------------------------------

            cursor.execute("""
            SELECT id
            FROM ledger_transactions
            WHERE customer_id=%s
            AND trans_date=%s
            AND trans_id=%s
            AND vehicle=%s
            AND product=%s
            AND debit=%s
            AND credit=%s
            LIMIT 1
            """, (
                selected_customer,
                trans_date,
                trans_id,
                vehicle,
                product,
                debit,
                credit
            ))

            exists = cursor.fetchone()

            if exists:

                skipped_count += 1
                continue

            # -------------------------------
            # INSERT TRANSACTION
            # -------------------------------

            cursor.execute("""
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
                trans_id,
                vehicle,
                product,
                litres,
                debit,
                credit,
                0
            ))

            inserted_count += 1

        conn.commit()

        # RECALCULATE BALANCE
        recalculate_balances(selected_customer)

        # RELOAD TRANSACTIONS
        load_transactions(selected_customer)

        messagebox.showinfo(
            "Success",
            f"Transactions Imported Successfully\n\nInserted: {inserted_count}\nSkipped: {skipped_count}"
        )

    except Exception as e:

        messagebox.showerror(
            "Import Error",
            str(e)
        )


# =========================================================
# LEFT FRAME
# =========================================================

left_frame = ctk.CTkFrame(
    app,
    width=350
)

left_frame.pack(
    side="left",
    fill="y",
    padx=10,
    pady=10
)

title = ctk.CTkLabel(
    left_frame,
    text="SALES",
    font=("Arial", 28, "bold")
)

title.pack(pady=20)

customer_name_entry = ctk.CTkEntry(
    left_frame,
    placeholder_text="Customer Name",
    width=250
)

customer_name_entry.pack(pady=10)

phone_entry = ctk.CTkEntry(
    left_frame,
    placeholder_text="Phone Number",
    width=250
)

phone_entry.pack(pady=10)

add_customer_btn = ctk.CTkButton(
    left_frame,
    text="Add Customer",
    command=add_customer,
    width=250,
    height=40
)

add_customer_btn.pack(pady=5)

update_customer_btn = ctk.CTkButton(
    left_frame,
    text="Update Customer",
    command=update_customer,
    width=250,
    height=40
)

update_customer_btn.pack(pady=5)

delete_customer_btn = ctk.CTkButton(
    left_frame,
    text="Delete Customer",
    command=delete_customer,
    width=250,
    height=40,
    fg_color="red"
)

delete_customer_btn.pack(pady=5)


# =========================================================
# CUSTOMER TABLE
# =========================================================

customer_columns = (
    "ID",
    "CUSTOMER",
    "PHONE"
)

customer_tree = ttk.Treeview(
    left_frame,
    columns=customer_columns,
    show="headings",
    height=22
)

for col in customer_columns:
    customer_tree.heading(col, text=col)

    if col == "ID":
        customer_tree.column(
            col,
            width=0,
            stretch=False
        )
    else:
        customer_tree.column(
            col,
            width=150,
            anchor="center"
        )

customer_tree.pack(
    fill="both",
    expand=True,
    pady=10
)

customer_tree.bind(
    "<<TreeviewSelect>>",
    select_customer
)


# =========================================================
# RIGHT FRAME
# =========================================================

right_frame = ctk.CTkFrame(app)

right_frame.pack(
    side="right",
    fill="both",
    expand=True,
    padx=10,
    pady=10
)

customer_title = ctk.CTkLabel(
    right_frame,
    text="Select Customer",
    font=("Arial", 28, "bold")
)

customer_title.pack(pady=20)

export_pdf_btn = ctk.CTkButton(
    right_frame,
    text="Export PDF",
    command=export_customer_pdf,
    width=200,
    height=40
)

export_pdf_btn.pack(pady=5)

import_btn = ctk.CTkButton(
    right_frame,
    text="Import Excel",
    command=import_transactions,
    width=200,
    height=40
)

import_btn.pack(pady=5)


# =========================================================
# TRANSACTION FORM
# =========================================================

form_frame = ctk.CTkFrame(right_frame)

form_frame.pack(fill="x", padx=10)

date_entry = ctk.CTkEntry(
    form_frame,
    placeholder_text="YYYY-MM-DD"
)

date_entry.grid(row=0, column=0, padx=5, pady=5)

date_entry.insert(
    0,
    datetime.now().strftime("%Y-%m-%d")
)

transid_entry = ctk.CTkEntry(
    form_frame,
    placeholder_text="Transaction ID"
)

transid_entry.grid(row=0, column=1, padx=5)

vehicle_entry = ctk.CTkEntry(
    form_frame,
    placeholder_text="Vehicle"
)

vehicle_entry.grid(row=0, column=2, padx=5)

product_entry = ctk.CTkEntry(
    form_frame,
    placeholder_text="Product"
)

product_entry.grid(row=0, column=3, padx=5)

litres_entry = ctk.CTkEntry(
    form_frame,
    placeholder_text="Litres"
)

litres_entry.grid(row=1, column=0, padx=5, pady=5)

debit_entry = ctk.CTkEntry(
    form_frame,
    placeholder_text="Debit"
)

debit_entry.grid(row=1, column=1, padx=5)

credit_entry = ctk.CTkEntry(
    form_frame,
    placeholder_text="Credit"
)

credit_entry.grid(row=1, column=2, padx=5)

from_date_label = ctk.CTkLabel(
    form_frame,
    text="From Date"
)

from_date_label.grid(row=2, column=0, padx=5, pady=5)

from_date_entry = DateEntry(
    form_frame,
    width=18,
    date_pattern="yyyy-mm-dd"
)

from_date_entry.grid(row=2, column=1, padx=5, pady=5)

to_date_label = ctk.CTkLabel(
    form_frame,
    text="To Date"
)

to_date_label.grid(row=2, column=2, padx=5, pady=5)

to_date_entry = DateEntry(
    form_frame,
    width=18,
    date_pattern="yyyy-mm-dd"
)

to_date_entry.grid(row=2, column=3, padx=5, pady=5)


# =========================================================
# TRANSACTION BUTTONS
# =========================================================

add_trans_btn = ctk.CTkButton(
    right_frame,
    text="Add Transaction",
    command=add_transaction,
    width=200,
    height=40
)

add_trans_btn.pack(pady=5)

update_trans_btn = ctk.CTkButton(
    right_frame,
    text="Update Transaction",
    command=update_transaction,
    width=200,
    height=40
)

update_trans_btn.pack(pady=5)

delete_trans_btn = ctk.CTkButton(
    right_frame,
    text="Delete Transaction",
    command=delete_transaction,
    width=200,
    height=40,
    fg_color="red"
)

delete_trans_btn.pack(pady=5)

delete_selected_btn = ctk.CTkButton(
    right_frame,
    text="Delete Selected",
    command=delete_selected_transactions,
    width=200,
    height=40,
    fg_color="darkred"
)

delete_selected_btn.pack(pady=5)


# =========================================================
# TRANSACTION TABLE
# =========================================================

trans_columns = (
    "DB_ID",
    "DATE",
    "TRANS.ID",
    "VEHICLE",
    "PRODUCT",
    "LITRES",
    "DEBIT",
    "CREDIT",
    "BALANCE"
)

trans_tree = ttk.Treeview(
    right_frame,
    columns=trans_columns,
    show="headings",
    height=20,
    selectmode="extended"
)

for col in trans_columns:
    trans_tree.heading(col, text=col)

    if col == "DB_ID":
        trans_tree.column(
            col,
            width=0,
            stretch=False
        )
    else:
        trans_tree.column(
            col,
            width=120,
            anchor="center"
        )

trans_tree.pack(
    fill="both",
    expand=True,
    padx=10,
    pady=10
)

trans_tree.bind(
    "<<TreeviewSelect>>",
    select_transaction
)


# =========================================================
# INITIAL LOAD
# =========================================================

load_customers()


# =========================================================
# RUN APP
# =========================================================

app.mainloop()