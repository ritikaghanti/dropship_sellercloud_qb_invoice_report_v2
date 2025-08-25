# email_helper.py
from __future__ import annotations
from typing import Dict, List, Iterable, Optional
from kramer_functions import GmailNotifier, AzureSecrets


class Emailer:
    """
    Thin wrapper over Kramer Functions GmailNotifier.
    - Pulls a default IT recipient from Key Vault (optional).
    - Lets you force a single test recipient for safe runs.
    """

    def __init__(self, test_recipient: Optional[str] = None) -> None:
        self.notifier = GmailNotifier()
        self.secrets = AzureSecrets()
        # Optional default IT address, stored in Key Vault (change the name to your vault’s key)
        self.default_it_email = self._get_secret_safe("email-address-it-department")
        self.test_recipient = test_recipient  # e.g., "rghanti@krameramerica.com"

    # ---- public API -----------------------------------------------------

    def send_plain(
        self,
        subject: str,
        body: str,
        recipients: Optional[Iterable[str]] = None,
        *,
        reply_to: Optional[str] = None,
        machine_info: bool = True,
        discord_notification: bool = False,
    ) -> None:
        """Send a plain-text email via Kramer notifier."""
        to_list = self._resolve_recipients(recipients)
        if not to_list:
            # Fallback: if nothing provided and no IT email, drop the send
            return
        self.notifier.send_notification(
            subject=subject,
            body=body,
            recipients=list(to_list),
            html_body=None,
            reply_to=reply_to,
            machine_info=machine_info,
            discord_notification=discord_notification,
        )

    def send_html(
        self,
        subject: str,
        html_body: str,
        recipients: Optional[Iterable[str]] = None,
        *,
        text_fallback: str = "",
        reply_to: Optional[str] = None,
        machine_info: bool = True,
        discord_notification: bool = False,
    ) -> None:
        """Send an HTML email (with optional plain text fallback)."""
        to_list = self._resolve_recipients(recipients)
        if not to_list:
            return
        self.notifier.send_notification(
            subject=subject,
            body=text_fallback or "See HTML version.",
            recipients=list(to_list),
            html_body=html_body,
            reply_to=reply_to,
            machine_info=machine_info,
            discord_notification=discord_notification,
        )

    def send_error_report(
        self,
        orders_unable_to_invoice: Optional[Dict[str, List[str]]] = None,
        orders_already_invoiced: Optional[Dict[str, List[str]]] = None,
        *,
        recipients: Optional[Iterable[str]] = None,
        subject: str = "Dropshipper Invoice Error Report",
    ) -> None:
        """Builds and sends the classic error report."""
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

        # Pre block keeps monospaced / aligned formatting
        try:
            self.send_html(
                subject=subject,
                html_body=html,
                recipients=recipients,
                text_fallback=body,
                machine_info=True,
                discord_notification=False,
            )
        except Exception:
            pass

    # ---- helpers --------------------------------------------------------

    def _resolve_recipients(self, recipients: Optional[Iterable[str]]) -> List[str]:
        """If test_recipient is set, always send only to that address."""
        if self.test_recipient:
            return [self.test_recipient]
        if recipients:
            return list(recipients)
        # fallback to default IT email if present
        return [self.default_it_email] if self.default_it_email else []

    def _get_secret_safe(self, name: str) -> Optional[str]:
        try:
            return self.secrets.get_secret(name, required=False)
        except Exception:
            return None

    # Backward-compat: allow imports of EmailHelper and a module-level send_error_report()


class EmailHelper(Emailer):
    pass


def send_error_report(
    orders_unable_to_invoice: Optional[Dict[str, List[str]]] = None,
    orders_already_invoiced: Optional[Dict[str, List[str]]] = None,
    *,
    recipients: Optional[Iterable[str]] = None,
    subject: str = "Dropshipper Invoice Error Report",
) -> None:
    """Convenience wrapper for legacy code paths."""
    Emailer().send_error_report(
        orders_unable_to_invoice=orders_unable_to_invoice,
        orders_already_invoiced=orders_already_invoiced,
        recipients=recipients,
        subject=subject,
    )


__all__ = ["Emailer", "EmailHelper", "send_error_report"]
