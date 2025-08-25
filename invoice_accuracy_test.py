# invoice_accuracy_test.py (minor tidy)
from quickbooks_db import QuickBooksDb
from dropship_db import DropshipDb
from invoice import QbInvoice
from datetime import datetime, timedelta
from decimal_rounding import round_to_decimal
from tqdm import tqdm
import sys

# Check invoices from N days ago
DAYS_AGO = 2

d_db = DropshipDb()
invoiced_orders = d_db.get_invoiced_orders(datetime.now() - timedelta(days=DAYS_AGO))

if not invoiced_orders:
    print("There are no invoiced orders")
    d_db.close()
    sys.exit(0)

qb_db = QuickBooksDb()
current_refresh_token = qb_db.get_refresh_token()
api = QbInvoice(current_refresh_token)

if api.client.refresh_token != current_refresh_token:
    qb_db.update_refresh_token(api.client.refresh_token)

incorrect_subtotal_orders = []
invoice_not_found_orders = []

for order_id, subtotal in tqdm(
    invoiced_orders.items(), desc="Checking invoice accuracy"
):
    invoice = api.check_exist(order_id)
    if invoice:
        if invoice.TotalAmt != round_to_decimal(subtotal):
            incorrect_subtotal_orders.append(order_id)
    else:
        invoice_not_found_orders.append(order_id)

print("\nIncorrect subtotal orders:")
print(
    "\nNone"
    if not incorrect_subtotal_orders
    else "\n" + "\n".join("\t" + x for x in incorrect_subtotal_orders)
)

print("\n\nInvoices not found:")
print(
    "\nNone\n"
    if not invoice_not_found_orders
    else "\n" + "\n".join("\t" + x for x in invoice_not_found_orders)
)

d_db.close()
qb_db.close()
