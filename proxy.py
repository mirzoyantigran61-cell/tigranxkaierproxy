"""
Proxy blueprint — перехват игрового трафика и подмена verAddr.
Без функций обхода защит/античита — только транспорт.
"""
from __future__ import annotations

import json as _json
import logging

import requests
from flask import Blueprint, Response, jsonify, request
from urllib.parse import urljoin

from config import Config

log = logging.getLogger("proxy")

proxy_bp = Blueprint("proxy", __name__)

HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host", "content-length",
}

_http = requests.Session()


def _filtered_request_headers():
    out = {}
    for k, v in request.headers.items():
        if k.lower() in HOP_BY_HOP:
            continue
        out[k] = v
    return out


def _filtered_response_headers(resp):
    out = []
    for k, v in resp.headers.items():
        if k.lower() in HOP_BY_HOP or k.lower() == "content-length":
            continue
        out.append((k, v))
    return out


def _reverse_proxy(path: str):
    target = urljoin(Config.UPSTREAM_BASE_URL, path)
    raw_body = request.get_data(cache=False)
    try:
        upstream = _http.request(
            method=request.method,
            url=target,
            params=request.args,
            headers=_filtered_request_headers(),
            data=raw_body if raw_body else None,
            timeout=(5, 20),
            allow_redirects=False,
            stream=True,
        )
        body = b"" if request.method == "HEAD" else upstream.raw.read(decode_content=False)
        response = Response(response=body, status=upstream.status_code,
                            headers=_filtered_response_headers(upstream))

        if upstream.headers.get("content-type", "").startswith("application/json"):
            try:
                data = _json.loads(body)
                if isinstance(data, dict) and "verAddr" in data:
                    data["code"] = 0
                    data["verAddr"] = Config.PROXY_VER_ADDR
                    if "abhotupdate_cdn_url" in data:
                        data["abhotupdate_cdn_url"] = Config.PROXY_VER_ADDR + "hotpatchs/"
                    new_body = _json.dumps(data).encode("utf-8")
                    response.set_data(new_body)
                    response.headers["Content-Length"] = str(len(new_body))
            except Exception:
                pass

        return response
    except requests.Timeout:
        return jsonify({"status": "error", "message": "upstream timeout"}), 504
    except requests.RequestException as exc:
        log.exception("Proxy error")
        return jsonify({"status": "error", "message": "upstream failed", "detail": str(exc)}), 502


@proxy_bp.route("/proxy/<path:path>",
                methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
def reverse_proxy_named(path: str):
    return _reverse_proxy(path)


@proxy_bp.route("/<path:path>",
                methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
def catch_all(path: str):
    if path.startswith(("panel", "api", "health", "static", "verify")):
        return jsonify({"error": "Not found"}), 404
    return _reverse_proxy(path)
