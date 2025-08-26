# seller_cloud_data.py
from __future__ import annotations

from typing import Dict, List, Tuple, Optional
import traceback

from seller_cloud_api import SellerCloudAPI

DropshipperKey = Tuple[str, str]  # (dropshipper_code, ftp_folder_name)
SC_OP_GET_ORDERS = "GET_ORDERS"


def _enrich_order_with_sc(order: dict, sellercloud_order: dict) -> bool:
    """
    Mutate `order` with totals and per-item prices from SellerCloud. Returns True on success.

    Expected SellerCloud shape (minimal):
      sellercloud_order["TotalInfo"]["Tax"|"GrandTotal"]
      sellercloud_order["OrderItems"]: List[{"ProductIDOriginal", "LineTotal"}]
    """
    try:
        order["tax"] = sellercloud_order["TotalInfo"]["Tax"]
        order["subtotal"] = sellercloud_order["TotalInfo"]["GrandTotal"]

        sc_items = sellercloud_order.get("OrderItems", []) or []
        id_to_line_total = {
            item.get("ProductIDOriginal"): item.get("LineTotal") for item in sc_items
        }

        new_items: List[Tuple[str, int, float]] = []
        for sku, qty, *rest in order.get("items", []):
            if not sku:
                return False
            try:
                qty_i = int(qty or 0)
            except Exception:
                qty_i = 0
            line_total = id_to_line_total.get(sku)
            if line_total is None or qty_i <= 0:
                return False
            unit_price = float(line_total) / float(qty_i)
            new_items.append((sku, qty_i, unit_price))

        order["items"] = new_items
        return True
    except Exception:
        return False


def get_sellercloud_data(
    ready_to_invoice_orders: Dict[DropshipperKey, Dict[str, object]],
    *,
    sc_api: Optional[SellerCloudAPI] = None,
) -> Tuple[Dict[DropshipperKey, Dict[str, object]], Dict[str, List[str]]]:
    """
    Enrich ready-to-invoice orders with financial data from SellerCloud.

    - Attaches order-level tax and subtotal
    - Rewrites each item tuple (sku, qty) -> (sku, qty, unit_price)
    - Drops orders with missing/mismatched SKUs or failed API fetches
    - Removes dropshipper buckets that end up empty

    Returns:
        (enriched_orders, sc_errors)

        sc_errors: Dict[str, List[str]]
          - "not_found_in_sc": list of PO numbers where GET failed (non-200)
          - "item_mismatch":   list of PO numbers where SKU/qty mismatch or missing
          - "unexpected_error": list of PO numbers where an exception occurred
    """
    sc_api = sc_api or SellerCloudAPI()
    sc_errors: Dict[str, List[str]] = {
        "not_found_in_sc": [],
        "item_mismatch": [],
        "unexpected_error": [],
    }

    # Iterate over a copy so we can modify the original safely
    for ds_key, ds_data in list(ready_to_invoice_orders.items()):
        original_orders: List[dict] = list(ds_data.get("orders", []))
        kept_orders: List[dict] = []

        for order in original_orders:
            po_number = order.get("purchase_order_number")
            sc_id = order.get("sellercloud_order_id")

            try:
                response = sc_api.execute(
                    {"url_args": {"order_id": sc_id}}, SC_OP_GET_ORDERS
                )
                if getattr(response, "status_code", None) != 200:
                    sc_errors["not_found_in_sc"].append(po_number)
                    continue

                sc_order = response.json()
                if not _enrich_order_with_sc(order, sc_order):
                    sc_errors["item_mismatch"].append(po_number)
                    continue

                kept_orders.append(order)

            except Exception:
                # Keep trace for local logs if you like; only PO numbers go to the error list
                # print(traceback.format_exc())
                sc_errors["unexpected_error"].append(po_number)
                continue

        if kept_orders:
            ds_data["orders"] = kept_orders
        else:
            del ready_to_invoice_orders[ds_key]

    return ready_to_invoice_orders, sc_errors
