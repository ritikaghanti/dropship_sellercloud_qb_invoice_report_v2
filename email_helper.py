# email_helper.py
from __future__ import annotations
from typing import Dict, List, Iterable, Optional
from kramer_functions import GmailNotifier, AzureSecrets


class EmailHelper:
    """
    Thin wrapper over Kramer Functions GmailNotifier.
    - Optional test_recipient to force all emails to go to a single address (safe testing).
    - Fallback default recipient (IT) from Azure Key Vault (secret: 'email-address-it-department').
    - send_error_report() to format the classic invoice error summary.
    """

    def __init__(self, test_recipient: Optional[str] = None) -> None:
        self.notifier = GmailNotifier()
        self.secrets = AzureSecrets()
        self.default_it_email = self._get_secret_safe("email-address-it-department")
        self.test_recipient = test_recipient  # e.g., "rghanti@krameramerica.com"

    def send_error_report(
        self,
        orders_unable_to_invoice: Optional[Dict[str, List[str]]] = None,
        orders_already_invoiced: Optional[Dict[str, List[str]]] = None,
        *,
        recipients: Optional[Iterable[str]] = None,
        subject: str = "Dropshipper Invoice Error Report",
    ) -> None:
        """Build and send the classic error report (monospaced)."""
        lines: List[str] = []

        if orders_unable_to_invoice:
            lines.append("There was an Error when trying to invoice these orders:")
            for code, orders in orders_unable_to_invoice.items():
                lines.append(f"  {code}:")
                for po in orders or []:
                    lines.append(f"    {po}")
            lines.append("")

        if orders_already_invoiced:
            lines.append("These orders were previously invoiced:")
            for code, orders in orders_already_invoiced.items():
                lines.append(f"  {code}:")
                for po in orders or []:
                    lines.append(f"    {po}")
            lines.append("")

        if not lines:
            lines = ["No errors to report."]

        html = "<pre>\n" + "\n".join(lines) + "</pre>"
        body = "\n".join(lines)

        to_list = self._resolve_recipients(recipients)
        if not to_list:
            return  # nothing to send

        self.notifier.send_notification(
            subject=subject,
            body=body,
            recipients=list(to_list),
            html_body=html,
            machine_info=True,
            discord_notification=False,
        )

    # ------------------------- Helpers -------------------------

    def _resolve_recipients(self, recipients: Optional[Iterable[str]]) -> List[str]:
        """If test_recipient is set, always send only to that address."""
        if self.test_recipient:
            return [self.test_recipient]
        if recipients:
            return list(recipients)
        return [self.default_it_email] if self.default_it_email else []

    def _get_secret_safe(self, name: str) -> Optional[str]:
        try:
            return self.secrets.get_secret(name, required=False)
        except Exception:
            return None


__all__ = ["EmailHelper"]
