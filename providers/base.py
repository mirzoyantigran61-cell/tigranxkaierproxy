from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict


class PaymentProvider(ABC):
    def __init__(self, config: Dict):
        self.config = config

    @abstractmethod
    def create_payment(self, order_id: str, amount: float, currency: str, **kwargs) -> Dict:
        ...

    @abstractmethod
    def get_payment_status(self, payment_id: str) -> Dict:
        ...

    @abstractmethod
    def verify_webhook(self, payload: Dict, headers: Dict) -> bool:
        ...

    def refund(self, payment_id: str, amount: float) -> Dict:
        return {"status": "error", "message": "refund not implemented"}

    def cancel_payment(self, payment_id: str) -> Dict:
        return {"status": "error", "message": "cancel not implemented"}

    def _is_configured(self) -> bool:
        return bool(self.config.get("enabled"))

    def _err(self, msg: str) -> Dict:
        return {"status": "error", "message": msg}
