# file_handler.py (kept for legacy local writes)
from __future__ import annotations
import os
from datetime import datetime


class FileHandler:
    DATE_FORMAT = "%m%d%Y"
    TIME_FORMAT = "%H%M%S"
    BASE_DIRECTORY = "tmp"

    def __init__(self, report_date: datetime):
        self.report_date = report_date

    def save_data_to_file(self, invoice_data_df, ftp_folder_name: str):
        if invoice_data_df.empty:
            return False
        directory_path = self._create_directory_structure(ftp_folder_name)
        date_str = self.report_date.strftime(self.DATE_FORMAT)
        file_path = os.path.join(directory_path, f"Invoice_{date_str}.csv")
        invoice_data_df.to_csv(file_path, index=False)
        return file_path

    def _create_directory_structure(self, ftp_folder_name: str) -> str:
        datetime_str = self.report_date.strftime(
            f"{self.DATE_FORMAT}_{self.TIME_FORMAT}"
        )
        dir_path = os.path.join(self.BASE_DIRECTORY, ftp_folder_name, datetime_str)
        os.makedirs(dir_path, exist_ok=True)
        return dir_path
