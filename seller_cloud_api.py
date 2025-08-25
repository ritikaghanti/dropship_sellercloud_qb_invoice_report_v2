# seller_cloud_api.py
from __future__ import annotations

from typing import Optional, Dict, Any
import requests
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from kramer_functions import AzureSecrets


class SellerCloudAPI:
    """
    Lightweight SellerCloud client using Kramer Functions (AzureSecrets).

    - Auth: Username/Password -> POST /token
    - Base URL: https://krameramerica.api.sellercloud.us/rest/api/
    - Methods:
        * get_order(order_id) -> Response
        * execute(data, action, **kwargs)  # small adapter to ease migration
    """

    BASE_URL = "https://krameramerica.api.sellercloud.us/rest/api/"

    def __init__(
        self,
        *,
        username_secret: str = "sc-username-dan",
        password_secret: str = "sc-password-dan",
        timeout: int = 30,
        max_retries: int = 3,
    ) -> None:
        self.timeout = timeout

        # --- secrets via Kramer Functions (short, safe error) ---
        try:
            secrets = AzureSecrets()
            self.username = secrets.get_secret(username_secret)
            self.password = secrets.get_secret(password_secret)
        except Exception:
            # keep message short so your ActivityLogs.error_code won't overflow
            raise RuntimeError("Missing SellerCloud username/password secrets in KV.")

        # --- auth token + session ---
        self.access_token = self._get_token(self.username, self.password, timeout)
        self.session = self._create_session(self.access_token, max_retries)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def get_order(self, order_id: str) -> requests.Response:
        """
        GET a single order by ID from SellerCloud.
        Example: GET /Orders/{order_id}
        """
        url = f"{self.BASE_URL}Orders/{order_id}"
        return self.session.get(url, timeout=self.timeout)

    def execute(
        self,
        data: Optional[Dict[str, Any]],
        action: str,
        **kwargs: Any,
    ) -> Optional[requests.Response]:
        """
        Small adapter so existing code that calls `execute(..., action)` keeps working.

        Supported:
          - "GET_ORDER" or "GET_ORDERS": expects data={"url_args": {"order_id": "<id>"}}
        """
        data = data or {}
        url_args = data.get("url_args") or {}

        if action in {"GET_ORDER", "GET_ORDERS"}:
            order_id = url_args.get("order_id")
            if not order_id:
                raise ValueError("GET_ORDER(S) requires url_args['order_id']")
            return self.get_order(str(order_id))

        raise ValueError(f"Unsupported SellerCloud action: {action}")

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _get_token(self, username: str, password: str, timeout: int) -> str:
        """
        POST /token with Username/Password and return access_token.
        """
        url = f"{self.BASE_URL}token"
        payload = {"Username": username, "Password": password}
        try:
            resp = requests.post(url, json=payload, timeout=timeout)
        except requests.RequestException:
            raise RuntimeError("SellerCloud token request failed (network).")

        if resp.status_code != 200:
            # keep error short
            raise RuntimeError("SellerCloud token request failed (HTTP).")

        try:
            token = resp.json().get("access_token")
        except Exception:
            token = None

        if not token:
            raise RuntimeError("SellerCloud token response missing access_token.")
        return token

    def _create_session(self, token: str, max_retries: int) -> Session:
        """
        Session with Authorization + basic retry policy on idempotent GETs.
        """
        s = requests.Session()
        s.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
        )

        retry = Retry(
            total=max_retries,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),  # we only retry GETs
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        s.mount("https://", adapter)
        s.mount("http://", adapter)
        return s
