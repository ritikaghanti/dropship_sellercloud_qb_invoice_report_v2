# order_invoice_matcher_test.py (compat with refactored df_creator)
from dropship_db import DropshipDb
from invoice import QbInvoice
from quickbooks_db import QuickBooksDb
from df_creator import DfCreator

d_db = DropshipDb()
d_order = d_db.get_specific_invoice_ready_orders("1631644-1706956", 1)
invoice_csv_headers = d_db.get_invoice_csv_headers()

qb_db = QuickBooksDb()
current_refresh_token = qb_db.get_refresh_token()
api = QbInvoice(current_refresh_token)
if api.client.refresh_token != current_refresh_token:
    qb_db.update_refresh_token(api.client.refresh_token)

for dropshipper_info, dropshipper_data in d_order.items():
    df_creator = DfCreator(invoice_csv_headers, dropshipper_data)
    for order in dropshipper_data["orders"]:
        invoice = api.check_exist(order["order_id"])
        if invoice:
            order = df_creator._order_invoice_matcher(order, invoice)
