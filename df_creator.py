# df_creator.py (refactored)
from __future__ import annotations
import io
from typing import Dict, List, Any
import pandas as pd
from decimal_rounding import round_to_decimal


class DfCreator:
    """
    Simpler DataFrame builder for invoice CSVs.
    - Avoids deprecated DataFrame._append by buffering rows
    - Handles both "default" and "aag" formats
    - Tolerates items as (sku, qty) or (sku, qty, unit_cost)
    - Provides CSV bytes via to_csv_bytes()
    - Includes legacy helper `_order_invoice_matcher` used by tests
    """

    def __init__(
        self,
        invoice_csv_headers: Dict[str, List[str]],
        dropshipper_data: Dict[str, Any],
    ):
        self.file_format_name: str = dropshipper_data["file_format_name"]
        self.headers_map = invoice_csv_headers
        if self.file_format_name not in self.headers_map:
            raise ValueError(
                f"Missing CSV headers for format '{self.file_format_name}'"
            )
        self._rows: List[Dict[str, Any]] = []

    # -------- Public API --------
    def populate_df(self, order: Dict[str, Any]) -> bool:
        try:
            fmt = self.file_format_name
            if fmt == "default":
                self._add_default_rows(order)
            elif fmt == "aag":
                self._add_aag_rows(order)
            else:
                self._add_default_rows(order)
            return True
        except Exception as e:
            print(f"Error while populating dataframe rows: {e}")
            return False

    def to_dataframe(self) -> pd.DataFrame:
        df = pd.DataFrame(self._rows)
        cols = self.headers_map[self.file_format_name]
        for c in cols:
            if c not in df.columns:
                df[c] = ""
        df = df[cols]
        return df

    def to_csv_bytes(self) -> bytes:
        df = self.to_dataframe()
        if df.empty:
            return b""
        buf = io.StringIO(newline="")
        df.to_csv(buf, index=False)
        return buf.getvalue().encode("utf-8")

    # -------- Internal builders --------
    def _add_default_rows(self, order: Dict[str, Any]) -> None:
        base = {
            "po_number": order.get("purchase_order_number", ""),
            "invoice_number": order.get("order_id", ""),
            "invoice_date": order.get("ship_date", ""),
            "invoice_total_amount": order.get("subtotal", ""),
            "invoice_subtotal_amount": self._safe_round(
                (order.get("subtotal") or 0) - (order.get("tax") or 0)
            ),
            "invoice_tax_amount": order.get("tax", ""),
        }
        for item in order.get("items", []):
            sku = item[0]
            qty = item[1]
            unit_cost = item[2] if len(item) > 2 else ""
            row = dict(base)
            row.update(
                {
                    "line_item_sku": sku,
                    "line_item_quantity": qty,
                    "line_item_unit_cost": unit_cost,
                }
            )
            self._rows.append(row)

    def _add_aag_rows(self, order: Dict[str, Any]) -> None:
        base = {
            "Invoice Number": order.get("order_id", ""),
            "SONumber": order.get("purchase_order_number", ""),
            "Date": self._normalize_date(order.get("ship_date", "")),
            "Customer": "auto_accessories_garage",
            "CarrierName": "FEDEX_GROUND",
            "TrackingNumber": order.get("tracking_number", ""),
        }

        items = order.get("items", []) or []
        n_items = max(len(items), 1)

        for sku, qty, *rest in items:
            qty = int(qty or 0)
            unit_cost = rest[0] if rest else None
            price_each = self._fallback_item_price(order, n_items, unit_cost)
            # keep 3 decimals
            line_price = float(f"{price_each * max(qty,1):.3f}")
            self._rows.append({**base, "item": sku, "qty": qty, "price": line_price})

        # Taxes and Shipping lines
        self._rows.append(
            {**base, "item": "Taxes", "qty": 1, "price": float(order.get("tax") or 0.0)}
        )
        self._rows.append(
            {
                **base,
                "item": "SHIPPING",
                "qty": 1,
                "price": float(order.get("shipping") or 0.0),
            }
        )

    # inside class DfCreator

    def _normalize_date(self, value: object) -> str:
        """
        Return date in 'YYYY/MM/DD' as required by AAG.
        Accepts:
        - str already in YYYY/MM/DD (returned as-is)
        - str like '7/7/2025' or '07/07/2025'
        - datetime/date objects
        Falls back to str(value) if parsing fails.
        """
        from datetime import datetime, date

        if value is None:
            return ""
        # If it's already a date/datetime
        if isinstance(value, (datetime, date)):
            return value.strftime("%Y/%m/%d")

        s = str(value).strip()
        # Already the desired format?
        try:
            # quick check: parse as desired format
            dt = datetime.strptime(s, "%Y/%m/%d")
            return dt.strftime("%Y/%m/%d")
        except Exception:
            pass

        # Try common m/d/Y formats
        for fmt in ("%m/%d/%Y", "%-m/%-d/%Y", "%m/%-d/%Y", "%-m/%d/%Y"):
            try:
                dt = datetime.strptime(s, fmt)
                return dt.strftime("%Y/%m/%d")
            except Exception:
                continue

        # Last resort: try pandas to_datetime
        try:
            import pandas as pd

            dt = pd.to_datetime(s, errors="raise")
            return dt.strftime("%Y/%m/%d")
        except Exception:
            return s  # give back original string if all else fails

    def _fallback_item_price(
        self, order: Dict[str, Any], n_items: int, unit_cost
    ) -> float:
        # If enrichment provided a unit cost > 0, use it
        try:
            if unit_cost is not None and float(unit_cost) > 0:
                return float(unit_cost)
        except Exception:
            pass
        # Otherwise compute from totals: (subtotal - tax - shipping) / item_count
        subtotal = float(order.get("subtotal") or 0.0)
        tax = float(order.get("tax") or 0.0)
        shipping = float(order.get("shipping") or 0.0)
        base = subtotal - tax - shipping
        return base / max(n_items, 1)

    def _safe_round(self, value: Any) -> Any:
        try:
            return round_to_decimal(value)
        except Exception:
            return value

    # -------- Legacy helper used by order_invoice_matcher_test.py --------
    def _order_invoice_matcher(self, order: Dict[str, Any], invoice) -> Dict[str, Any]:
        order_items = {}
        order["subtotal"] = getattr(invoice, "TotalAmt", order.get("subtotal", 0))
        for line in getattr(invoice, "Line", []) or []:
            if getattr(line, "Description", "") == "Shipping":
                order["shipping"] = line.Amount
            elif getattr(line, "Description", "") == "Taxes":
                order["tax"] = line.Amount
            elif getattr(line, "DetailType", "") == "SalesItemLineDetail":
                order_items[getattr(line, "Description", "")] = line.Amount
        for i in range(len(order.get("items", []))):
            sku, quantity, unit_cost = (
                order["items"][i]
                if len(order["items"][i]) == 3
                else (*order["items"][i], 0)
            )
            order["items"][i] = (sku, quantity, order_items.get(sku, unit_cost))
        return order
