# process_logger.py (adds .log_success/.log_error/.log_info)
import pyodbc
from config import db_config, create_connection_string
import time


class ProcessLogger:
    def __init__(self, process_name):
        self.connection_string = create_connection_string(db_config["ProcessLogs"])
        self.connection = pyodbc.connect(self.connection_string)
        self.cursor = self.connection.cursor()
        self.process_name = process_name
        self.start_time = time.perf_counter()

    def log_process(self, status, error_code=None):
        allowed = ["success", "failed", "info"]
        if status not in allowed:
            raise ValueError(f"Invalid status: {status}. Allowed: {allowed}")
        duration = time.perf_counter() - self.start_time
        if error_code is not None:
            self.cursor.execute(
                "INSERT INTO ActivityLogs (process_id, status, duration, error_code) "
                "VALUES ((SELECT process_id FROM Processes WHERE process_name = ?), ?, ?, ?)",
                self.process_name,
                status,
                duration,
                error_code,
            )
        else:
            self.cursor.execute(
                "INSERT INTO ActivityLogs (process_id, status, duration) "
                "VALUES ((SELECT process_id FROM Processes WHERE process_name = ?), ?, ?)",
                self.process_name,
                status,
                duration,
            )
        self.connection.commit()

    # Convenience wrappers
    def log_success(self, msg: str = ""):
        self.log_process("success", msg or None)

    def log_error(self, msg: str = ""):
        self.log_process("failed", msg or None)

    def log_info(self, msg: str = ""):
        self.log_process("info", msg or None)
