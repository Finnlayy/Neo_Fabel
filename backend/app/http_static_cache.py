"""Cache-Control for FastAPI static mounts when clients hit :8000 directly."""

from __future__ import annotations

from starlette.types import ASGIApp, Message, Receive, Scope, Send

_STATIC_CACHE = b"private, max-age=300"


class StaticCacheMiddleware:
    """Attach short private cache headers to /static/* responses."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope.get("path", "").startswith("/static/"):
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                if not any(name.lower() == b"cache-control" for name, _ in headers):
                    headers.append((b"cache-control", _STATIC_CACHE))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)
