# main.py
from datetime import datetime
from dropship_db import DropshipDb
from quickbooks_db import QuickBooksDb
from invoice import QbInvoice
from df_creator import DfCreator
from ftp import FTPManager
from file_handler import FileHandler
from email_helper import EmailHelper
from process_logger import ProcessLogger
from seller_cloud_data import get_sellercloud_data


def main():
    logger = ProcessLogger("dropship_sellercloud_qn_invoice_report")

    try:
        d_db = DropshipDb()
        qb_db = QuickBooksDb()
        ftp = FTPManager()
        emailer = EmailHelper(test_recipient="rghanti@krameramerica.com")

        invoice_csv_headers = d_db.get_invoice_csv_headers()
        orders_ready_to_invoice = d_db.get_invoice_ready_orders()
        if not orders_ready_to_invoice:
            print("No orders ready to invoice.")
            return
        orders_ready_to_invoice, sc_errors = get_sellercloud_data(
            orders_ready_to_invoice
        )

        # QuickBooks API client
        current_refresh_token = qb_db.get_refresh_token()
        api = QbInvoice(current_refresh_token)
        if api.client.refresh_token != current_refresh_token:
            qb_db.update_refresh_token(api.client.refresh_token)

        unable_to_invoice = {}
        already_invoiced = {}
        file_paths = []

        for dropshipper_info, dropshipper_data in orders_ready_to_invoice.items():
            df_creator = DfCreator(invoice_csv_headers, dropshipper_data)
            fh = FileHandler(datetime.now())
            ftp_folder_name = dropshipper_data["ftp_folder_name"]

            for order in dropshipper_data["orders"]:
                invoice = api.check_exist(order["order_id"])
                if invoice:
                    already_invoiced.setdefault(dropshipper_info, []).append(
                        order["purchase_order_number"]
                    )
                    continue

                # invoice_id = api.create(order)
                invoice_id = "TEST_ONLY_NO_QB"
                if not invoice_id:
                    unable_to_invoice.setdefault(dropshipper_info, []).append(
                        order["purchase_order_number"]
                    )
                    continue

                success = df_creator.populate_df(order)
                if not success:
                    unable_to_invoice.setdefault(dropshipper_info, []).append(
                        order["purchase_order_number"]
                    )
                    continue

                # d_db.save_invoice_id(order["purchase_order_number"], invoice_id)

            file_path = fh.save_data_to_file(df_creator.to_dataframe(), ftp_folder_name)
            if file_path:
                file_paths.append(file_path)

        if file_paths:
            ftp.upload_files(file_paths, test_mode=True)

            # 🔁 Combine SellerCloud enrichment errors into the same email:
        if unable_to_invoice or already_invoiced:
            # send_error_report(unable_to_invoice, already_invoiced)
            emailer.send_error_report(
                orders_unable_to_invoice=unable_to_invoice,
                orders_already_invoiced=already_invoiced,
            )
        logger.log_success("Completed successfully")

    except Exception as e:
        logger.log_error(str(e))
        raise


if __name__ == "__main__":
    main()
