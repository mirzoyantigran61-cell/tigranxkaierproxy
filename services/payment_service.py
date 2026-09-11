"""
Payment Service — orchestrates providers.
"""
from __future__ import annotations

import logging
import secrets
import time
from typing import Dict

from config import Config
from providers.ameria import AmeriaProvider
from providers.fastbank import FastBankProvider
from providers.cis import CISProvider
from providers.kazakhstan import KazakhstanProvider

log = logging.getLogger("payment-service")


class PaymentService:
    def __init__(self, firebase_service):
        self.firebase = firebase_service

    def _get_provider(self, name: str, config: Dict):
        name = name.lower()
        providers = {
            "ameria": AmeriaProvider,
            "fastbank": FastBankProvider,
            "cis": CISProvider,
            "kazakhstan": KazakhstanProvider,
        }
        cls = providers.get(name)
        return cls(config) if cls else None

    def create_order(self, user_id: str, provider_name: str, product_id: str) -> Dict:
        product = self.firebase.get_product(product_id)
        if not product:
            return {"status": "error", "message": "invalid product"}

        amount = product["price"]
        currency = product["currency"]
        order_id = f"order_{secrets.token_hex(8)}"

        self.firebase.create_payment(order_id, {
            "user_id": user_id,
            "provider": provider_name,
            "product_id": product_id,
            "amount": amount,
            "currency": currency,
            "status": "created",
            "created_at": int(time.time()),
            "updated_at": int(time.time()),
            "payment_id": "",
            "transaction_id": "",
            "paid_at": 0,
            "webhook_processed": False,
        })

        provider_cfg = dict(self.firebase.get_config().get(provider_name.upper(), {}))
        provider_cfg.update(self._env_secrets_for(provider_name))

        provider = self._get_provider(provider_name, provider_cfg)
        if not provider:
            return {"status": "error", "message": "unknown provider"}

        result = provider.create_payment(
            order_id, amount, currency,
            description=f"Purchase {product_id}",
            back_url=f"{Config.PROXY_VER_ADDR}panel",
        )
        if result.get("status") == "error":
            return result

        if result.get("payment_id"):
            self.firebase.update_payment(order_id, {
                "payment_id": result["payment_id"],
                "status": "pending",
            })

        return {
            "status": "success",
            "order_id": order_id,
            "payment_url": result.get("payment_url"),
        }

    def _env_secrets_for(self, provider_name: str) -> Dict:
        name = provider_name.upper()
        mapping = {
            "AMERIA": ["MERCHANT_ID", "USERNAME", "PASSWORD", "TERMINAL_ID"],
            "FASTBANK": ["MERCHANT_ID", "USERNAME", "PASSWORD", "API_KEY", "SECRET", "WEBHOOK_SECRET"],
            "CIS": ["MERCHANT_ID", "API_KEY", "SECRET"],
            "KAZAKHSTAN": ["MERCHANT_ID", "API_KEY", "SECRET"],
        }
        out = {}
        for key in mapping.get(name, []):
            val = getattr(Config, f"{name}_{key}", "")
            if val:
                out[key.lower()] = val
        return out

    def verify_and_activate(self, provider_name: str, payload: Dict, headers: Dict) -> Dict:
        provider_cfg = dict(self.firebase.get_config().get(provider_name.upper(), {}))
        provider_cfg.update(self._env_secrets_for(provider_name))
        provider = self._get_provider(provider_name, provider_cfg)
        if not provider:
            return {"status": "error", "message": "unknown provider"}

        if not provider.verify_webhook(payload, headers):
            return {"status": "error", "message": "invalid signature"}

        order_id = payload.get("OrderID") or payload.get("order_id")
        payment_id = payload.get("PaymentID") or payload.get("payment_id")
        if not order_id or not payment_id:
            return {"status": "error", "message": "missing order_id or payment_id"}

        order = self.firebase.get_payment(order_id)
        if not order:
            return {"status": "error", "message": "order not found"}
        if order.get("provider") != provider_name.lower():
            return {"status": "error", "message": "provider mismatch"}
        if order.get("payment_id") and order["payment_id"] != payment_id:
            return {"status": "error", "message": "payment_id mismatch"}

        status = provider.get_payment_status(payment_id)
        if status.get("status") != "paid":
            return {"status": "error", "message": "payment not confirmed"}

        self.firebase.update_payment(order_id, {
            "status": "paid",
            "paid_at": int(time.time()),
            "webhook_processed": True,
            "transaction_id": status.get("transaction_id", ""),
        })

        self.activate_purchase(
            order["user_id"], order["product_id"], order_id,
            order.get("amount"), order.get("currency")
        )
        return {"status": "success"}

    def activate_purchase(self, user_id: str, product_id: str, order_id: str, amount=None, currency=None) -> bool:
        existing = self.firebase.get_entitlement(user_id, product_id)
        if existing and existing.get("order_id") == order_id and existing.get("active"):
            return True

        product = self.firebase.get_product(product_id) or {}
        duration_days = int(product.get("duration", 30))
        expires_at = int(time.time()) + duration_days * 86400

        self.firebase.set_entitlement(user_id, product_id, {
            "active": True,
            "order_id": order_id,
            "activated_at": int(time.time()),
            "expires_at": expires_at,
            "amount": amount,
            "currency": currency,
        })
        return True
