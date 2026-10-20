from starlette.responses import JSONResponse


class BodyTooLarge(Exception):
    pass


class ReviewBodyLimit:
    """Bound public review request bodies before multipart spooling or JSON parsing."""

    def __init__(self, app, prefix="/api/v1/review"):
        self.app = app
        self.prefix = prefix

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope.get("path", "").startswith(self.prefix):
            return await self.app(scope, receive, send)
        limit = 3 * 1024 * 1024 + 65536 if scope["path"].endswith("/extract") else 512 * 1024
        size = 0

        async def bounded_receive():
            nonlocal size
            message = await receive()
            size += len(message.get("body", b""))
            if size > limit:
                raise BodyTooLarge
            return message

        # Buffer only up to this limit before parsers can allocate temporary files.
        chunks = []
        try:
            while True:
                message = await bounded_receive()
                if message["type"] == "http.disconnect":
                    return
                chunks.append(message.get("body", b""))
                if not message.get("more_body", False):
                    break
        except BodyTooLarge:
            return await JSONResponse({"detail": "Request is too large. Upload a file smaller than 3 MB or shorten the text."}, status_code=413)(scope, receive, send)
        body = b"".join(chunks)
        consumed = False

        async def replay():
            nonlocal consumed
            if consumed:
                return await receive()
            consumed = True
            return {"type": "http.request", "body": body, "more_body": False}

        await self.app(scope, replay, send)
