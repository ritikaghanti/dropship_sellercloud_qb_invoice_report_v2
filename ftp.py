# ftp.py
from __future__ import annotations
import os
from typing import List, Tuple
from kramer_functions import FTPFileManager

"""
FTP uploader for invoice CSVs using Kramer Functions.

- Uses `kramer_functions.FTPFileManager()` — credentials are resolved by that library
  (Key Vault dashed secrets or env vars like DROPSHIP_FTP_HOST/USER/PASS).
- Mirrors each file to:
    /dropshipper_logs/invoice_logs/<ftp_folder>/<filename>
    /dropshipper/<ftp_folder>/invoices/<filename>
- Supports TEST mode:
    - Set INVOICE_TEST_MODE=1 to force uploads into "test_customer" folder
- Supports DRY RUN:
    - Set DRY_RUN=1 to print intended uploads without touching the network

You can also call this file as a script to run a quick self-test (see bottom).
"""


def _bool_env(name: str, default: bool = False) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "on"}


class FTPManager:
    def __init__(self) -> None:
        """
        We rely on Kramer FTPFileManager to resolve credentials.
        If creds are missing or invalid, constructor or upload will raise;
        we catch and log in upload_files to avoid crashing test runs.
        """
        # Lazily instantiate in upload_files so test runs with DRY_RUN don’t require creds.
        self._ftp: FTPFileManager | None = None

        # Behavior flags (can be overridden per-call)
        self.default_test_mode = _bool_env("INVOICE_TEST_MODE", False)
        self.default_dry_run = _bool_env("DRY_RUN", False)

    # ------------------------- public API -------------------------

    def upload_files(
        self,
        all_paths: List[str],
        *,
        test_mode: bool | None = None,
        dry_run: bool | None = None,
    ) -> None:
        """
        Upload local files to two remote destinations per file.
        If test_mode=True (or INVOICE_TEST_MODE=1), forces ftp_folder to 'test_customer'.
        If dry_run=True (or DRY_RUN=1), prints what would happen and exits without network calls.
        """
        if not all_paths:
            print("[FTP] No files to upload.")
            return

        test_mode = self.default_test_mode if test_mode is None else test_mode
        dry_run = self.default_dry_run if dry_run is None else dry_run

        # Prepare (maybe) the FTP client only if we will actually upload
        if not dry_run and self._ftp is None:
            try:
                self._ftp = FTPFileManager()
            except Exception as e:
                # Don’t hard-fail; allow tests to proceed without network
                print(f"[FTP] Unable to initialize FTP client: {e}")
                print("[FTP] Falling back to DRY RUN behavior for this call.")
                dry_run = True

        for path in all_paths:
            ftp_folder, filename = self._path_decomposer(path)
            if test_mode:
                ftp_folder = "test_customer"

            remote_paths = self._build_remote_paths(ftp_folder, filename)

            if dry_run:
                print(f"[FTP:DRY_RUN] Would upload '{path}' to:")
                for rp in remote_paths:
                    print(f"  - {rp}")
                continue

            # Real upload
            try:
                assert self._ftp is not None, "FTP client not initialized"
                for rp in remote_paths:
                    self._ftp.upload_file(path, rp)
                print(f"[FTP] Uploaded '{path}' to {len(remote_paths)} destinations.")
            except Exception as e:
                # Log and continue with other files
                print(f"[FTP] Error uploading '{path}': {e}")

        # Close the session if we opened it
        try:
            if self._ftp is not None:
                self._ftp.close()
        except Exception:
            pass
        finally:
            self._ftp = None

    # ------------------------- helpers -------------------------

    def _path_decomposer(self, local_path: str) -> Tuple[str, str]:
        """
        Expect local files under tmp/<ftp_folder>/<timestamp>/<filename>.
        Returns (ftp_folder, filename). Gracefully handles unexpected shapes.
        """
        norm = local_path.replace("\\", "/")
        parts = norm.split("/")

        filename = parts[-1] if parts else os.path.basename(local_path)

        # Prefer second element after 'tmp' if present
        ftp_folder = "unknown"
        if "tmp" in parts:
            idx = parts.index("tmp")
            if idx + 1 < len(parts):
                ftp_folder = parts[idx + 1]
        elif len(parts) > 1:
            # Fallback: second segment of path
            ftp_folder = parts[1]

        return ftp_folder, filename

    def _build_remote_paths(self, ftp_folder: str, filename: str) -> List[str]:
        """
        Two mirrored destinations per business rules.
        Absolute paths are preferred by most FTP servers; keep leading slash.
        """
        return [
            f"/dropshipper_logs/invoice_logs/{ftp_folder}/{filename}",
            f"/dropshipper/{ftp_folder}/invoices/{filename}",
        ]


# ------------------------- self-test -------------------------
if __name__ == "__main__":
    """
    Quick local test:
      - Creates a dummy file if it doesn't exist.
      - Runs in DRY RUN if DRY_RUN=1 (default), so no network is touched.
      - Set INVOICE_TEST_MODE=1 to force test_customer folder.

    Usage (PowerShell):
      $env:DRY_RUN = "1"
      $env:INVOICE_TEST_MODE = "1"
      python ftp.py
    """
    dummy_dir = os.path.join("tmp", "my_partner", "20250101_000000")
    os.makedirs(dummy_dir, exist_ok=True)
    dummy_file = os.path.join(dummy_dir, "Invoice_01012025.csv")
    if not os.path.exists(dummy_file):
        with open(dummy_file, "w", encoding="utf-8") as fh:
            fh.write("col1,col2\nval1,val2\n")

    fm = FTPManager()
    fm.upload_files([dummy_file])  # honors DRY_RUN and INVOICE_TEST_MODE env vars
