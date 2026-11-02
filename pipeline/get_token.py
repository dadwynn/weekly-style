"""One-time helper: approve the app on your store and print a long-lived Admin API token.

    python get_token.py your-store.myshopify.com

Use this when the app is in a different organization from the store (custom
distribution), where the client-credentials login is refused (shop_not_permitted).
Add http://localhost:3456/callback as a redirect URL on the app first.
Put the printed token in the SHOPIFY_ADMIN_TOKEN GitHub secret.
"""
from __future__ import annotations

import getpass
import hashlib
import hmac
import os
import re
import secrets
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qsl, urlencode, urlsplit

import requests

PORT = 3456
REDIRECT_URI = f"http://localhost:{PORT}/callback"
SCOPES = "write_content"
SHOP_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9\-]*\.myshopify\.com$")


def _wait_for_callback() -> dict:
    received: dict = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            url = urlsplit(self.path)
            if url.path != "/callback":
                self.send_response(404)
                self.end_headers()
                return
            received.update(parse_qsl(url.query))
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<p>Approved. You can close this tab and go back to the terminal.</p>")

        def log_message(self, *args):
            pass

    server = HTTPServer(("localhost", PORT), Handler)
    while not received:
        server.handle_request()
    server.server_close()
    return received


def _valid_hmac(params: dict, secret: str) -> bool:
    message = "&".join(f"{k}={v}" for k, v in sorted(params.items()) if k != "hmac")
    digest = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, params.get("hmac", ""))


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    shop = sys.argv[1].strip().removeprefix("https://").removeprefix("http://").rstrip("/")
    if not SHOP_RE.match(shop):
        raise SystemExit("Pass the store's myshopify address, e.g. my-shop.myshopify.com")

    client_id = os.environ.get("SHOPIFY_CLIENT_ID") or input("Client ID: ").strip()
    client_secret = os.environ.get("SHOPIFY_CLIENT_SECRET") or getpass.getpass("Client secret (hidden): ").strip()

    state = secrets.token_urlsafe(16)
    authorize_url = f"https://{shop}/admin/oauth/authorize?" + urlencode({
        "client_id": client_id, "scope": SCOPES, "redirect_uri": REDIRECT_URI, "state": state,
    })
    print(f"\nOpening your browser to approve the app. If it doesn't open, visit:\n{authorize_url}\n")
    webbrowser.open(authorize_url)

    params = _wait_for_callback()
    if params.get("error"):
        raise SystemExit(f"Shopify returned an error: {params}")
    if params.get("state") != state:
        raise SystemExit("State mismatch - try again.")
    if params.get("shop") != shop:
        raise SystemExit(f"Callback came from {params.get('shop')}, expected {shop}.")
    if not _valid_hmac(params, client_secret):
        raise SystemExit("HMAC check failed - is the client secret correct?")

    resp = requests.post(
        f"https://{shop}/admin/oauth/access_token",
        data={"client_id": client_id, "client_secret": client_secret, "code": params["code"]},
        timeout=30,
    )
    if not resp.ok:
        raise SystemExit(f"Token exchange failed ({resp.status_code}): {resp.text[:500]}")
    body = resp.json()
    if "expires_in" in body:
        print(f"Warning: this token expires in {body['expires_in']}s; tell Claude so it can add refresh support.")

    print(f"Granted scopes: {body.get('scope')}")
    print("\nAdmin API token (copy into the SHOPIFY_ADMIN_TOKEN GitHub secret; keep it private):\n")
    print(body["access_token"])


if __name__ == "__main__":
    main()
