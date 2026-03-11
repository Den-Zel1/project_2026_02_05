import logging

from fastapi import Request
from jose import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse

from config import settings, PUBLIC_URLS

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        url = request.url.components.path
        if url in PUBLIC_URLS:
            return await call_next(request)

        request_id = getattr(request.state, "request_id", "?")

        try:
            token = request.cookies.get("access_token")
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            username = payload.get("sub")
            request.state.username = username
        except Exception as e:
            logger.warning(
                "Ошибка авторизации: %s — %s, path=%s",
                type(e).__name__, e, url,
                extra={"request_id": request_id, "path": url, "error": str(e)},
            )
            return RedirectResponse(url="/login", status_code=302)

        return await call_next(request)
