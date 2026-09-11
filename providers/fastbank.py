"""
Fast Bank Provider
⚠️ WAITING FOR BANK DOCUMENTATION ⚠️
"""
from __future__ import annotations

from typing import Dict

from providers.base import PaymentProvider


class FastBankProvider(PaymentProvider):
    SANDBOX_BASE = "PASTE_FASTBANK_SANDBOX_URL_HERE"
    PRODUCTION_BASE = "PASTE_FASTBANK_PRODUCTION_URL_HERE"

    def __init__(self, config: Dict):
        super().__init__(config)
        self.test_mode = bool(config.get("test_mode", True))

    @property
    def base_url(self) -> str:
        return self.SANDBOX_BASE if self.test_mode else self.PRODUCTION_BASE

    def create_payment(self, order_id: str, amount: float, currency: str, **kwargs) -> Dict:
        if not self._is_configured():
            return self._err("Fast Bank payments are not configured")
        return self._err(
            "Fast Bank API integration is not yet implemented. "
            "Please provide official Fast Bank API documentation and credentials."
        )

    def get_payment_status(self, payment_id: str) -> Dict:
        if not self._is_configured():
            return self._err("Fast Bank payments are not configured")
        return self._err("Fast Bank GetPaymentStatus not implemented")

    def verify_webhook(self, payload: Dict, headers: Dict) -> bool:
        return False
