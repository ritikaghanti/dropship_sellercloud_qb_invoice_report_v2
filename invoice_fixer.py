# invoice_fixer.py (kept; safer CSV reads)
import pandas as pd
from invoice import QbInvoice
from quickbooks_db import QuickBooksDb
from quickbooks.objects import Invoice

qb_db = QuickBooksDb()
current_refresh_token = qb_db.get_refresh_token()
api = QbInvoice(current_refresh_token)
if api.client.refresh_token != current_refresh_token:
    qb_db.update_refresh_token(api.client.refresh_token)


def df_reader(file_path):
    for enc in ("utf-8", "ISO-8859-1", "cp1252"):
        try:
            return pd.read_csv(file_path, dtype=str, encoding=enc)
        except UnicodeDecodeError:
            continue
    print(f"Error reading the file: could not decode {file_path}")
    return None


def fix_invoices():
    folder = "C:\\Users\\Alfredo\\Downloads\\invoices that need fixing\\"
    files = ["Invoice_01052024.csv", "Invoice_01082024.csv", "Invoice_01092024.csv"]

    what_is = "UPS Ground"
    what_needs_to_be = "FEDEX Ground HD"
    email_sent_status = []

    not_change_this = ["AAG1629506-1704718", "AAG1631212-1706505", "AAG1631404-1706705"]

    all_invoices_ids = []

    for file in files:
        df = df_reader(folder + file)
        if df is None:
            continue
        df = df.dropna()
        all_invoices_ids.extend(df["Invoice Number"].unique().tolist())

    for id in all_invoices_ids:
        if id in not_change_this:
            continue
        invs = Invoice.filter(DocNumber=id, qb=api.client)
        if not invs:
            continue
        invoice = invs[0]
        if getattr(invoice, "EmailStatus", "") == "EmailSent":
            email_sent_status.append(id)
        if (
            invoice.ShipMethodRef.name == what_is
            and invoice.ShipMethodRef.value == what_is
        ):
            invoice.ShipMethodRef.name = what_needs_to_be
            invoice.ShipMethodRef.value = what_needs_to_be
            invoice.save(qb=api.client)
