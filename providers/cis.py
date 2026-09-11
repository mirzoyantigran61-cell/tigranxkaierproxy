"""
CIS Provider — универсальный провайдер для банков СНГ.
WAITING FOR PROVIDER DOCUMENTATION
"""
from __future__ import annotations

from typing import Dict

from providers.base import PaymentProvider


class CISProvider(PaymentProvider):
    API_BASE_URL = "PASTE_OFFICIAL_CIS_API_URL_HERE"

    def create_payment(self, order_id: str, amount: float, currency: str, **kwargs) -> Dict:
        if not self._is_configured():
            return self._err("CIS payments are not configured")
        return self._err("CISProvider not implemented")

    def get_payment_status(self, payment_id: str) -> Dict:
        return self._err("CISProvider not implemented")

    def verify_webhook(self, payload: Dict, headers: Dict) -> bool:
        return False
