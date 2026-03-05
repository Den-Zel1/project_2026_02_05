from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
from jose import jwt

from starlette.responses import RedirectResponse

from config import settings, PUBLIC_URLS


class PrintMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        url= request.url.components.path
        if url not in PUBLIC_URLS:
            try:
                token = request.cookies.get("access_token")
                payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
                username = payload.get("sub")

            except Exception as e:
                print(type(e))
                return RedirectResponse(url="/login", status_code=302)
            else:
                response = await call_next(request)
        else:
            response = await call_next(request)
        return response

