from __future__ import annotations

import httpx


class RpcError(RuntimeError):
    pass


class RpcClient:
    def __init__(self, url: str, timeout: float = 30.0):
        self.url = url
        self.timeout = timeout

    async def call(self, method: str, params: list):
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    self.url,
                    json=payload,
                )
            except httpx.HTTPError as exc:
                raise RpcError(
                    f"{method}: HTTP request failed: "
                    f"{type(exc).__name__}: {exc}"
                ) from exc

            # Keep the provider's response body so that HTTP 4xx/5xx
            # errors expose the actual JSON-RPC/provider message.
            try:
                body = response.json()
            except ValueError:
                body = None

            if response.status_code >= 400:
                if isinstance(body, dict) and "error" in body:
                    raise RpcError(
                        f"{method}: HTTP {response.status_code}: "
                        f"{body['error']}"
                    )

                # Do not expose the RPC URL/API key.
                text = response.text.strip()
                if len(text) > 1000:
                    text = text[:1000] + "..."

                raise RpcError(
                    f"{method}: HTTP {response.status_code}: "
                    f"{text or 'empty response body'}"
                )

        if not isinstance(body, dict):
            raise RpcError(
                f"{method}: invalid JSON-RPC response"
            )

        if "error" in body:
            raise RpcError(
                f"{method}: {body['error']}"
            )

        if "result" not in body:
            raise RpcError(
                f"{method}: response has neither "
                f"'result' nor 'error'"
            )

        return body["result"]