# =============================
# invoice.py (refactored)
# =============================
from __future__ import annotations
from datetime import datetime
from typing import Any, Dict, Optional

from config import client_secret, qBData
from intuitlib.client import AuthClient
from quickbooks import QuickBooks
from quickbooks.objects import (
    Invoice,
    SalesItemLineDetail,
    SalesItemLine,
    Item,
    Term,
    Class,
    Customer,
)
from quickbooks.objects.base import Ref, Address, EmailAddress


# -------- Helpers --------


def _normalize_date(d: str) -> str:
    """Accepts 'YYYY/MM/DD', 'YYYY-MM-DD', or '%m/%d/%Y' and returns 'YYYY-MM-DD'."""
    if not d:
        return ""
    for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(d, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    # If unknown, return as-is to avoid hard failures
    return d


def _safe_amount(v: Any) -> float:
    try:
        return float(v)
    except Exception:
        return 0.0


class QbInvoice:
    """Thin wrapper around QuickBooks invoice creation.

    Improvements:
    - Caches QBO references (Item/Class/Term/Customer) instead of fetching per line
    - Tolerates items shaped as (sku, qty) or (sku, qty, unit_cost)
    - Normalizes dates; safer numeric handling
    - Returns the created Invoice object on success (not just True)
    """

    # Default IDs used in your original code — keep configurable here
    ITEM_ID = 2  # generic item
    TAX_ITEM_ID = 24  # tax
    SHIPPING_ITEM_ID = 23  # shipping
    CLASS_ID = 1300000000000892596
    TERM_ID = 4

    def __init__(self, current_refresh_token: str):
        self.auth_client = AuthClient(
            client_id=client_secret["client_id"],
            client_secret=client_secret["client_secret"],
            environment=client_secret["environment"],
            redirect_uri=client_secret["redirect_uri"],
        )
        self.client = QuickBooks(
            auth_client=self.auth_client,
            refresh_token=current_refresh_token,
            company_id=qBData["realm_id"],
        )
        # Lazy caches
        self._item_ref: Optional[Ref] = None
        self._tax_ref: Optional[Ref] = None
        self._shipping_ref: Optional[Ref] = None
        self._class_ref: Optional[Ref] = None
        self._term_ref: Optional[Ref] = None
        self._customer_cache: Dict[Any, Ref] = {}

    # -------- Lazy ref getters --------
    def _get_item_ref(self) -> Ref:
        if not self._item_ref:
            self._item_ref = Item.get(self.ITEM_ID, qb=self.client).to_ref()
        return self._item_ref

    def _get_tax_ref(self) -> Ref:
        if not self._tax_ref:
            self._tax_ref = Item.get(self.TAX_ITEM_ID, qb=self.client).to_ref()
        return self._tax_ref

    def _get_shipping_ref(self) -> Ref:
        if not self._shipping_ref:
            self._shipping_ref = Item.get(
                self.SHIPPING_ITEM_ID, qb=self.client
            ).to_ref()
        return self._shipping_ref

    def _get_class_ref(self) -> Ref:
        if not self._class_ref:
            self._class_ref = Class.get(self.CLASS_ID, qb=self.client).to_ref()
        return self._class_ref

    def _get_term_ref(self) -> Ref:
        if not self._term_ref:
            self._term_ref = Term.get(self.TERM_ID, qb=self.client).to_ref()
        return self._term_ref

    def _get_customer_ref(self, customer_id: Any) -> Ref:
        ref = self._customer_cache.get(customer_id)
        if ref:
            return ref
        ref = Customer.get(customer_id, qb=self.client).to_ref()
        self._customer_cache[customer_id] = ref
        return ref

    # -------- Line builders --------
    def _sales_line(
        self,
        *,
        sku: str,
        qty: Any,
        unit_cost: Any,
        item_ref: Ref,
        class_ref: Ref,
        date_iso: str,
    ) -> SalesItemLine:
        qty_val = _safe_amount(qty)
        unit_val = _safe_amount(unit_cost)
        detail = SalesItemLineDetail()
        detail.ServiceDate = date_iso
        detail.UnitPrice = unit_val
        detail.Qty = qty_val
        detail.ItemRef = item_ref
        detail.ClassRef = class_ref

        line = SalesItemLine()
        line.Amount = str(unit_val * qty_val)
        line.DetailType = "SalesItemLineDetail"
        line.Description = sku
        line.SalesItemLineDetail = detail
        return line

    def _single_qty_line(
        self, *, desc: str, amount: Any, item_ref: Ref, class_ref: Ref, date_iso: str
    ) -> SalesItemLine:
        amt = _safe_amount(amount)
        detail = SalesItemLineDetail()
        detail.ServiceDate = date_iso
        detail.UnitPrice = amt
        detail.Qty = 1
        detail.ItemRef = item_ref
        detail.ClassRef = class_ref

        line = SalesItemLine()
        line.Amount = amt
        line.DetailType = "SalesItemLineDetail"
        line.Description = desc
        line.SalesItemLineDetail = detail
        return line

    # -------- Public methods --------
    def create_invoice(
        self, order: Dict[str, Any], vendor_mapping: Dict[str, Dict[str, Any]]
    ):
        """Create and save an invoice in QuickBooks for a single order.
        Returns the created Invoice on success; False on failure.
        """
        try:
            date_iso = _normalize_date(order.get("ship_date", ""))
            ds_name = order.get("dropshipper_name")
            vm = vendor_mapping.get(ds_name) or {}

            item_ref = self._get_item_ref()
            tax_ref = self._get_tax_ref()
            shipping_ref = self._get_shipping_ref()
            class_ref = self._get_class_ref()
            term_ref = self._get_term_ref()

            # Build line items from order lines
            lines: list[SalesItemLine] = []
            for tup in order.get("items", []):
                sku = tup[0]
                qty = tup[1]
                unit_cost = tup[2] if len(tup) > 2 else 0
                lines.append(
                    self._sales_line(
                        sku=sku,
                        qty=qty,
                        unit_cost=unit_cost,
                        item_ref=item_ref,
                        class_ref=class_ref,
                        date_iso=date_iso,
                    )
                )

            # tax + shipping lines
            lines.append(
                self._single_qty_line(
                    desc="Taxes",
                    amount=order.get("tax", 0),
                    item_ref=tax_ref,
                    class_ref=class_ref,
                    date_iso=date_iso,
                )
            )
            lines.append(
                self._single_qty_line(
                    desc="Shipping",
                    amount=order.get("shipping", 0),
                    item_ref=shipping_ref,
                    class_ref=class_ref,
                    date_iso=date_iso,
                )
            )

            # Ship method
            ship_ref = Ref()
            ship_method = vm.get("ship_method", "")
            ship_ref.value = ship_method
            ship_ref.name = ship_method

            # Customer + terms
            customer_id = vm.get("customer_id")
            if not customer_id:
                raise ValueError(
                    f"Missing customer_id for dropshipper '{ds_name}' in vendor_mapping"
                )
            customer_ref = self._get_customer_ref(customer_id)

            invoice = Invoice()
            invoice.CustomerRef = customer_ref
            invoice.SalesTermRef = term_ref
            invoice.TrackingNum = order.get("tracking_number", "")
            invoice.ShipDate = date_iso
            invoice.Line = lines
            invoice.TxnDate = date_iso
            invoice.DocNumber = order.get("order_id", "")

            # Bill-to email (vendor contact)
            email = (vm.get("email") or "").strip()
            if email:
                invoice.BillEmail = EmailAddress()
                invoice.BillEmail.Address = email

            # Ship method + address
            invoice.ShipMethodRef = ship_ref
            invoice.ShipAddr = Address()
            invoice.ShipAddr.City = order.get("city", "")
            invoice.ShipAddr.CountrySubDivisionCode = order.get("state", "")
            invoice.ShipAddr.Country = order.get("country", "")
            invoice.ShipAddr.PostalCode = order.get("postal_code", "")
            invoice.ShipAddr.Line1 = order.get("address", "")

            # Persist
            invoice.save(qb=self.client)
            return invoice

        except Exception as e:
            print(f"Error creating invoice for order {order.get('order_id')}: {e}")
            return False

    def check_exist(self, invoice_number: str):
        try:
            invs = Invoice.filter(DocNumber=invoice_number, qb=self.client)
            return invs[0] if invs else False
        except Exception as e:
            print(f"Error while checking invoice existence: {e}")
            return False

    def delete_invoice(self, invoice: Invoice) -> bool:
        try:
            invoice.delete(qb=self.client)
            return True
        except Exception as e:
            print(f"Error deleting invoice: {e}")
            return False

    def close(self) -> None:
        try:
            self.client.close()
        except Exception:
            pass
