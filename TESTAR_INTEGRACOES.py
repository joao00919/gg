"""Teste local da integração ZYNEX.

Preencha as variáveis abaixo ou defina-as no ambiente e execute:
    python TESTAR_INTEGRACOES.py
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.request

BOT_URL = os.getenv("BOT_URL", "https://zynexsales.camposcloud.app").rstrip("/")
TRANSCRIPT_URL = os.getenv("TRANSCRIPT_URL", "https://SUBDOMINIO-TRANSCRIPTS.camposcloud.app").rstrip("/")
SALES_BOT_API_KEY = os.getenv("SALES_BOT_API_KEY", "")
MANAGER_APPLICATION_ID = os.getenv("MANAGER_APPLICATION_ID", "")


def get_json(url: str, headers: dict[str, str] | None = None) -> tuple[int, dict]:
    request = urllib.request.Request(url, headers=headers or {}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {"raw": raw}
        return exc.code, data


def signed_headers(secret: str, method: str, path: str, body: str = "") -> dict[str, str]:
    timestamp = str(int(time.time() * 1000))
    material = f"{timestamp}.{method.upper()}.{path}.{body}".encode("utf-8")
    digest = hmac.new(secret.encode("utf-8"), material, hashlib.sha256).digest()
    signature = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return {
        "x-api-key": secret,
        "x-timestamp": timestamp,
        "x-signature": signature,
    }


def show(name: str, status: int, data: dict) -> None:
    ok = 200 <= status < 300
    print(f"[{'OK' if ok else 'ERRO'}] {name}: HTTP {status}")
    print(json.dumps(data, ensure_ascii=False, indent=2))
    print()


def main() -> None:
    status, data = get_json(f"{BOT_URL}/health")
    show("Saúde do bot", status, data)

    if "SUBDOMINIO-TRANSCRIPTS" not in TRANSCRIPT_URL:
        status, data = get_json(f"{TRANSCRIPT_URL}/health")
        show("Saúde da API de transcripts", status, data)
    else:
        print("[PULAR] Preencha TRANSCRIPT_URL para testar a API de transcripts.\n")

    if SALES_BOT_API_KEY and MANAGER_APPLICATION_ID:
        path = f"/internal/v1/applications/{MANAGER_APPLICATION_ID}/status"
        headers = signed_headers(SALES_BOT_API_KEY, "GET", path)
        status, data = get_json(f"{BOT_URL}{path}", headers=headers)
        show("API privada do bot", status, data)
    else:
        print("[PULAR] Defina SALES_BOT_API_KEY e MANAGER_APPLICATION_ID para testar a API privada.\n")


if __name__ == "__main__":
    main()
