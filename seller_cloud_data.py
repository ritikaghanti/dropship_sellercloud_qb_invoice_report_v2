# seller_cloud_data.py
from __future__ import annotations

from typing import Dict, List, Tuple, Optional, TYPE_CHECKING, Protocol, Any
import traceback

from seller_cloud_api import SellerCloudAPI

# Optional Kramer Functions imports — safe to run without them at runtime
try:
    from kramer_functions import AzureSecrets, GmailNotifier  # type: ignore
except Exception:  # pragma: no cover
    AzureSecrets = None  # type: ignore
    GmailNotifier = None  # type: ignore

# ---- Typing support ---------------------------------------------------------
if TYPE_CHECKING:
    # For static type checking when Kramer Functions is installed
    from kramer_functions import GmailNotifier as GmailNotifierType  # type: ignore
else:
    # Fallback type for hints when Kramer isn't present at runtime
    class GmailNotifierType(Protocol):  # minimal compatible interface
        def send(self, *args, **kwargs) -> None: ...


# Structural notifier protocol so hints always reference a *type*
class NotifierProto(Protocol):
    def send(self, *args, **kwargs) -> None: ...


DropshipperKey = Tuple[str, str]  # (dropshipper_code, ftp_folder_name)
SC_OP_GET_ORDERS = "GET_ORDERS"


# ---- Notifier Helpers -------------------------------------------------------
def _build_notifier(notifier: Optional[NotifierProto]) -> Optional[NotifierProto]:
    """
    Return the given notifier or try to create a GmailNotifier from Kramer Functions.
    This function never raises; returns None on failure/missing deps.
    """
    if notifier is not None:
        return notifier

    # If Kramer isn't available, there's nothing to build
    if GmailNotifier is None:
        return None

    # Optionally hydrate defaults from Key Vault (not required)
    defaults: Dict[str, Any] = {}
    if AzureSecrets is not None:
        try:
            secrets = AzureSecrets()
            # recipients: comma/semicolon-separated -> list[str]
            try:
                to_raw = secrets.get_secret("INVOICE_NOTIFIER_TO")
                if to_raw:
                    defaults["default_recipients"] = [
                        s.strip()
                        for s in str(to_raw).replace(";", ",").split(",")
                        if s.strip()
                    ]
            except Exception:
                pass
            try:
                frm = secrets.get_secret("INVOICE_NOTIFIER_FROM")
                if frm:
                    defaults["default_sender"] = frm
            except Exception:
                pass
        except Exception:
            # Secrets are optional; ignore failures
            pass

    # Instantiate, tolerating constructor signature differences
    try:
        return GmailNotifier(**defaults)  # type: ignore[misc,call-arg]
    except TypeError:
        try:
            return GmailNotifier()  # type: ignore[misc]
        except Exception:
            traceback.print_exc()
            return None
    except Exception:
        traceback.print_exc()
        return None


def _notify(notifier: Optional[NotifierProto], subject: str, body: str) -> None:
    """
    Best-effort notification. Supports various .send(...) signatures:
    - send(subject=..., html_body=...)  (Kramer Email/Gmail pattern)
    - send(subject=..., body=...)       (alt signature)
    - send(subject, body)               (positional)
    Swallows all exceptions (logging/alerts shouldn't break the pipeline).
    """
    if notifier is None:
        return
    try:
        # Try common Kramer-style kwargs first
        try:
            notifier.send(subject=subject, html_body=f"<pre>{body}</pre>")
            return
        except TypeError:
            pass

        # Try alternative kwarg name
        try:
            notifier.send(subject=subject, body=body)
            return
        except TypeError:
            pass

        # Fall back to positional
        notifier.send(subject, body)  # type: ignore[misc]
    except Exception:
        # Last resort: ignore notifier errors
        pass


# ---- SellerCloud Enrichment -------------------------------------------------
def _enrich_order_with_sc(order: dict, sc_order: dict) -> bool:
    try:
        totals = sc_order.get("TotalInfo") or {}
        order["tax"] = float(totals.get("Tax") or 0.0)
        order["subtotal"] = float(
            totals.get("GrandTotal") or 0.0
        )  # GrandTotal = items + tax + shipping

        sc_items = sc_order.get("OrderItems") or []
        # Build (sku -> (line_total, qty))
        id_to_totals = {
            (it.get("ProductIDOriginal") or it.get("SKU") or it.get("ProductSKU")): (
                float(it.get("LineTotal") or 0.0),
                int(it.get("Qty") or it.get("Quantity") or 0),
            )
            for it in sc_items
        }

        new_items = []
        for sku, qty, *_ in order.get("items", []):
            line_total, sc_qty = id_to_totals.get(sku, (0.0, 0))
            q = qty or sc_qty or 0
            if q <= 0:
                return False  # can’t compute unit price
            unit_cost = line_total / q  # <-- 3-decimal kept later in DfCreator
            new_items.append((sku, qty or q, unit_cost))

        order["items"] = new_items
        return True
    except Exception:
        return False


def _fetch_sc_order(sc_api: SellerCloudAPI, sc_id: Any) -> Optional[dict]:
    """
    Fetch a SellerCloud order by ID using either the new or legacy execute signature.
    Returns parsed JSON dict on success, or None on failure.
    """
    try:
        # Preferred (new) signature: execute(action, data={...})
        resp = sc_api.execute(SC_OP_GET_ORDERS, data={"url_args": {"order_id": sc_id}})
    except TypeError:
        # Legacy fallback: execute(data, action)
        resp = sc_api.execute({"url_args": {"order_id": sc_id}}, SC_OP_GET_ORDERS)
    except Exception:
        return None

    if not resp or getattr(resp, "status_code", None) != 200:
        return None

    try:
        return resp.json()
    except Exception:
        return None


def get_sellercloud_data(
    ready_to_invoice_orders: Dict[DropshipperKey, Dict[str, Any]],
    *,
    sc_api: Optional[SellerCloudAPI] = None,
    notifier: Optional[NotifierProto] = None,
) -> Dict[DropshipperKey, Dict[str, Any]]:
    """
    Enrich ready-to-invoice orders with financial data from SellerCloud.

    - Attaches order-level `tax` and `subtotal`
    - Rewrites each item tuple (sku, qty) -> (sku, qty, unit_price)
    - Drops orders with missing/mismatched SKUs or failed API fetches
    - Removes dropshipper buckets that end up empty

    Dependencies can be injected (sc_api, notifier) for testability; if omitted,
    they will be created with sensible defaults.
    """
    sc_api = sc_api or SellerCloudAPI()
    notifier = _build_notifier(notifier)

    # Work over a snapshot of keys so we can mutate the source dict safely
    for ds_key in list(ready_to_invoice_orders.keys()):
        ds_data = ready_to_invoice_orders.get(ds_key) or {}
        original_orders: List[dict] = list(ds_data.get("orders") or [])
        kept_orders: List[dict] = []

        for order in original_orders:
            order_id = order.get("purchase_order_number") or order.get("order_id")
            sc_id = order.get("sellercloud_order_id")

            try:
                sc_order = _fetch_sc_order(sc_api, sc_id)
                if not sc_order:
                    _notify(
                        notifier,
                        subject=f"SellerCloud fetch failed for order {order_id}",
                        body=(
                            f"Could not retrieve SellerCloud data for PO {order_id} (SC id: {sc_id}). "
                            "No invoice will be created for this order."
                        ),
                    )
                    continue

                if not _enrich_order_with_sc(order, sc_order):
                    order_skus = ", ".join(
                        str(sku) for sku, *_ in order.get("items", [])
                    )
                    _notify(
                        notifier,
                        subject=f"Item mismatch on order {order_id}",
                        body=(
                            f"One or more SKUs ({order_skus}) were not found or had invalid data in SellerCloud. "
                            f"No invoice will be created for this order."
                        ),
                    )
                    continue

                kept_orders.append(order)

            except Exception as e:
                _notify(
                    notifier,
                    subject=f"Unable to get price data from SellerCloud for order {order_id}",
                    body=(
                        "An unexpected error occurred while enriching the order. "
                        "No invoice will be created for this order.\n\n"
                        f"Error: {e}\n\n{traceback.format_exc()}"
                    ),
                )
                continue

        # Replace orders with only the ones we kept; drop ds bucket if empty
        if kept_orders:
            ds_data["orders"] = kept_orders
        else:
            # Remove empty dropshipper bucket
            ready_to_invoice_orders.pop(ds_key, None)

    return ready_to_invoice_orders
