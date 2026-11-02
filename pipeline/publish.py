"""Replace the body of the Shopify `style-tips` page via the Admin GraphQL API."""
from __future__ import annotations

import os

import requests

API_VERSION = os.environ.get("SHOPIFY_API_VERSION", "2026-10")
PAGE_HANDLE = os.environ.get("SHOPIFY_PAGE_HANDLE", "style-tips")


def _access_token(store: str) -> str:
    """Use a static Admin API token if given, else the client-credentials grant
    (apps created in Shopify's Dev Dashboard for your own store)."""
    if token := os.environ.get("SHOPIFY_ADMIN_TOKEN"):
        return token
    resp = requests.post(
        f"https://{store}/admin/oauth/access_token",
        data={
            "grant_type": "client_credentials",
            "client_id": os.environ["SHOPIFY_CLIENT_ID"],
            "client_secret": os.environ["SHOPIFY_CLIENT_SECRET"],
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _graphql(store: str, token: str, query: str, variables: dict) -> dict:
    resp = requests.post(
        f"https://{store}/admin/api/{API_VERSION}/graphql.json",
        json={"query": query, "variables": variables},
        headers={"X-Shopify-Access-Token": token},
        timeout=30,
    )
    resp.raise_for_status()
    body = resp.json()
    if body.get("errors"):
        raise RuntimeError(f"Shopify GraphQL error: {body['errors']}")
    return body["data"]


def publish(body_html: str) -> str:
    # e.g. my-shop.myshopify.com; tolerate a pasted "https://.../" form
    store = os.environ["SHOPIFY_STORE"].strip().removeprefix("https://").removeprefix("http://").rstrip("/")
    token = _access_token(store)

    data = _graphql(store, token,
                    "query($q: String!) { pages(first: 1, query: $q) { nodes { id handle } } }",
                    {"q": f"handle:{PAGE_HANDLE}"})
    nodes = data["pages"]["nodes"]
    if not nodes:
        raise RuntimeError(f"No Shopify page with handle '{PAGE_HANDLE}'. Create it first.")

    result = _graphql(store, token, """
        mutation($id: ID!, $page: PageUpdateInput!) {
          pageUpdate(id: $id, page: $page) { page { id handle } userErrors { field message } }
        }""", {"id": nodes[0]["id"], "page": {"body": body_html}})
    errors = result["pageUpdate"]["userErrors"]
    if errors:
        raise RuntimeError(f"pageUpdate failed: {errors}")
    return f"https://{store}/pages/{PAGE_HANDLE}"
