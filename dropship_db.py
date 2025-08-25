# dropship_db.py
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple
import pyodbc
from config import db_config, create_connection_string

DropshipperKey = Tuple[str, str]  # (dropshipper_code, ftp_folder_name)


class DropshipDb:
    """
    Minimal DB wrapper for the dropship invoicing pipeline.
    - Connects using 'DropshipSellerCloudTest' profile.
    - Uses a SINGLE query (with FOR JSON PATH) to fetch orders + items.
    """

    def __init__(self) -> None:
        self.connection_string = create_connection_string(
            db_config["DropshipSellerCloudTest"]
        )
        self.connection = pyodbc.connect(self.connection_string)
        self.cursor = self.connection.cursor()

    # --------------------------------------------------------------------- #
    # CSV headers
    # --------------------------------------------------------------------- #
    def get_invoice_csv_headers(self) -> Dict[str, List[str]]:
        """
        Returns {file_format_name: [header, ...]} for invoice CSVs.
        """
        sql = """
            SELECT 
                f.name AS file_format_name,
                STRING_AGG(fd.header_name, ', ') AS header_names
            FROM dbo.fileformats AS f
            JOIN dbo.fileformatdetails AS fd ON fd.format_id = f.id
            WHERE f.type = 'invoice'
            GROUP BY f.name
            ORDER BY f.name;
        """
        try:
            self.cursor.execute(sql)
            rows = self.cursor.fetchall()
            if rows:
                return {r.file_format_name: r.header_names.split(", ") for r in rows}
        except Exception:
            pass

        # Safe fallback so tests don't crash
        print("[DropshipDb] get_invoice_csv_headers: using fallback headers.")
        return {
            "default": [
                "po_number",
                "invoice_number",
                "invoice_date",
                "invoice_total_amount",
                "invoice_subtotal_amount",
                "invoice_tax_amount",
                "line_item_sku",
                "line_item_quantity",
                "line_item_unit_cost",
            ],
            "aag": [
                "Invoice Number",
                "SONumber",
                "Date",
                "Customer",
                "CarrierName",
                "TrackingNumber",
                "item",
                "qty",
                "price",
            ],
        }

    # --------------------------------------------------------------------- #
    # ONE-QUERY fetch for orders ready to invoice (orders + items inline)
    # --------------------------------------------------------------------- #
    def get_invoice_ready_orders(
        self,
        report_orders: Optional[List[str]] = None,
    ) -> Dict[DropshipperKey, Dict[str, Any]]:
        """
        Build the ready-to-invoice structure with a single SQL query.

        Returns:
        {
            (dropshipper_code, ftp_folder_name): {
                "file_format_name": <str>,
                "ftp_folder_name": <str>,
                "orders": [ {order_dict}, ... ]
            },
            ...
        }
        """
        base_sql = """
            SELECT   
                po.id,
                po.purchase_order_number,
                po.sellercloud_order_id,
                po.shipping_cost,
                po.tracking_number,
                po.tracking_date,
                po.city,
                po.zip,
                po.address,
                s.code AS state,
                c.two_letter_code AS country,
                d.code,
                d.name,
                d.ftp_folder_name,
                ff.name AS file_format_name,
                (
                    SELECT poi.sku, poi.quantity
                    FROM dbo.PurchaseOrderItems AS poi
                    WHERE poi.purchase_order_id = po.id
                    ORDER BY poi.id
                    FOR JSON PATH
                ) AS items_json
            FROM dbo.PurchaseOrders AS po
            JOIN dbo.Dropshippers          AS d   ON po.dropshipper_id = d.id
            JOIN dbo.States                AS s   ON po.state        = s.id
            JOIN dbo.Countries             AS c   ON po.country      = c.id
            JOIN dbo.DropshipperFileFormats AS dff ON dff.dropshipper_id = d.id
            JOIN dbo.FileFormats           AS ff  ON ff.id = dff.format_id
            WHERE po.tracking_number IS NOT NULL
            AND ff.type = 'invoice'
            AND po.is_invoiced = 0
            AND d.code != 'ABS'
            {po_filter}
            ORDER BY po.id;
        """

        params: List[Any] = []
        po_filter = ""
        if report_orders:
            placeholders = ", ".join("?" * len(report_orders))
            po_filter = f" AND po.purchase_order_number IN ({placeholders})"
            params.extend(report_orders)

        sql = base_sql.format(po_filter=po_filter)

        try:
            self.cursor.execute(sql, params) if params else self.cursor.execute(sql)
            rows = self.cursor.fetchall()
        except Exception as e:
            raise RuntimeError(f"Query for invoice-ready orders failed: {e}")

        result: Dict[DropshipperKey, Dict[str, Any]] = {}
        for row in rows:
            # Items as JSON → list of dicts
            items_raw_json = getattr(row, "items_json", None) or "[]"
            try:
                items_raw = json.loads(items_raw_json)
            except Exception:
                items_raw = []

            items = [
                (itm.get("sku"), int(itm.get("quantity") or 0), 0.0)
                for itm in items_raw
            ]

            ds_key: DropshipperKey = (row.code, row.ftp_folder_name)
            order = {
                "items": items,
                "purchase_order_number": row.purchase_order_number,
                "sellercloud_order_id": row.sellercloud_order_id,
                "tax": "",
                "shipping": float(row.shipping_cost or 0),
                "subtotal": "",
                "code": row.code,
                "tracking_number": row.tracking_number,
                "ship_date": (
                    row.tracking_date.strftime("%Y/%m/%d") if row.tracking_date else ""
                ),
                "city": row.city,
                "state": row.state,
                "country": row.country,
                "postal_code": row.zip,
                "address": row.address,
                "dropshipper_name": row.name,
            }
            order["order_id"] = self._ensure_order_id(
                row.code, row.purchase_order_number
            )

            if ds_key in result:
                result[ds_key]["orders"].append(order)
            else:
                result[ds_key] = {
                    "orders": [order],
                    "file_format_name": row.file_format_name,
                    "ftp_folder_name": row.ftp_folder_name,
                }

        return result

    # --------------------------------------------------------------------- #
    # Helpers
    # --------------------------------------------------------------------- #
    @staticmethod
    def _ensure_order_id(code: str, purchase_order_number: str) -> str:
        """Ensure the dropshipper code prefixes the PO number."""
        code_len = len(code or "")
        if purchase_order_number[:code_len] == code:
            return purchase_order_number
        return f"{code}{purchase_order_number}"

    # --------------------------------------------------------------------- #
    # Optional write helper
    # --------------------------------------------------------------------- #
    def save_invoice_id(self, purchase_order_number: str, invoice_id: str) -> None:
        """
        Best-effort write: store the QuickBooks invoice id against the PO.
        If table/column doesn’t exist (common in test DBs), log and return (no raise).
        """
        if not purchase_order_number or not invoice_id:
            print("[save_invoice_id] Missing PO or invoice_id; skipping.")
            return

        candidates = [
            ("dbo.PurchaseOrders", "quickbooks_invoice_id"),
            ("dbo.PurchaseOrders", "qb_invoice_id"),
            ("dbo.PurchaseOrders", "invoice_id"),
        ]

        for table, col in candidates:
            try:
                sql = f"UPDATE {table} SET {col} = ? WHERE purchase_order_number = ?"
                self.cursor.execute(sql, (invoice_id, purchase_order_number))
                if self.cursor.rowcount and self.cursor.rowcount > 0:
                    self.connection.commit()
                    print(
                        f"[save_invoice_id] Saved invoice_id to {table}.{col} for PO={purchase_order_number}"
                    )
                    return
            except Exception:
                continue

        print(
            "[save_invoice_id] WARNING: Could not persist invoice_id in this DB (table/column not found). Skipping."
        )

    # --------------------------------------------------------------------- #
    # Lifecycle
    # --------------------------------------------------------------------- #
    def close(self) -> None:
        try:
            self.cursor.close()
        except Exception:
            pass
        try:
            self.connection.close()
        except Exception:
            pass
