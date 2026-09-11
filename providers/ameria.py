"""
AmeriaBank vPOS 3.0 Provider
Официальная документация:
http://smednc.am/media/2019/10/28/9be76c171b016739edbf3f1b3c19cfc85a33e030.pdf
"""
from __future__ import annotations

import logging
from typing import Dict

import requests

from providers.base import PaymentProvider

log = logging.getLogger("ameria-provider")


class AmeriaProvider(PaymentProvider):
    SANDBOX_BASE = "https://servicestest.ameriabank.am/VPOS"
    PRODUCTION_BASE = "https://services.ameriabank.am/VPOS"

    def __init__(self, config: Dict):
        super().__init__(config)
        self.test_mode = bool(config.get("test_mode", True))

    @property
    def base_url(self) -> str:
        return self.SANDBOX_BASE if self.test_mode else self.PRODUCTION_BASE

    def create_payment(self, order_id: str, amount: float, currency: str, **kwargs) -> Dict:
        if not self._is_configured():
            return self._err("Ameriabank payments are not configured")

        client_id = self.config.get("merchant_id") or self.config.get("ClientID")
        username = self.config.get("username") or self.config.get("Username")
        password = self.config.get("password") or self.config.get("Password")
        if not all([client_id, username, password]):
            return self._err("Ameriabank credentials incomplete")

        payload = {
            "ClientID": client_id,
            "Username": username,
            "Password": password,
            "Currency": currency,
            "Description": kwargs.get("description", f"Order {order_id}"),
            "OrderID": order_id,
            "Amount": amount,
            "BackURL": kwargs.get("back_url", ""),
        }
        try:
            r = requests.post(f"{self.base_url}/api/VPOS/InitPayment", json=payload, timeout=15)
            data = r.json() if r.content else {}
        except requests.Timeout:
            return self._err("Ameriabank timeout")
        except requests.RequestException as exc:
            log.exception("Ameria InitPayment failed")
            return self._err(f"Ameriabank request failed: {exc}")

        if r.status_code != 200:
            return self._err(f"Ameriabank HTTP {r.status_code}")

        payment_id = data.get("PaymentID")
        if str(data.get("ResponseCode")) != "1":
            return self._err(f"Ameriabank rejected: {data.get('ResponseMessage', 'unknown')}")

        payment_url = f"{self.base_url}/Payments/Pay?id={payment_id}&lang=en"
        return {"status": "pending", "payment_id": payment_id, "payment_url": payment_url}

    def get_payment_status(self, payment_id: str) -> Dict:
        if not self._is_configured():
            return self._err("Ameriabank payments are not configured")

        username = self.config.get("username") or self.config.get("Username")
        password = self.config.get("password") or self.config.get("Password")
        payload = {"PaymentID": payment_id, "Username": username, "Password": password}

        try:
            r = requests.post(f"{self.base_url}/api/VPOS/GetPaymentDetails", json=payload, timeout=15)
            data = r.json() if r.content else {}
        except Exception as exc:
            return self._err(f"Ameriabank status request failed: {exc}")

        payment_state = str(data.get("PaymentState", "")).upper()
        order_status = str(data.get("OrderStatus", ""))
        if payment_state == "DEPOSITED" or order_status == "2":
            return {"status": "paid", "transaction_id": data.get("rrn") or data.get("MDOrderID", ""), "raw": data}
        elif payment_state in ("PENDING", "APPROVED"):
            return {"status": "pending", "raw": data}
        else:
            return {"status": "failed", "raw": data}

    def verify_webhook(self, payload: Dict, headers: Dict) -> bool:
        if not self._is_configured():
            return False
        order_id = payload.get("OrderID") or payload.get("order_id")
        payment_id = payload.get("PaymentID") or payload.get("payment_id")
        if not order_id or not payment_id:
            return False
        status = self.get_payment_status(payment_id)
        return status.get("status") == "paid"
