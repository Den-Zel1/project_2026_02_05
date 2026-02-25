from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
import time


class PrintMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 🟡 ВХОДЯЩИЙ ЗАПРОС
        print("\n" + "=" * 50)
        print("🔵 ПОЛУЧЕН ЗАПРОС:")
        print(f"📌 Метод: {request.method}")
        print(f"📍 URL: {request.url.path}")
        print(f"🔍 Параметры: {dict(request.query_params)}")

        # Засекаем время
        start_time = time.time()

        # 🔄 Обрабатываем запрос
        response = await call_next(request)

        # 🟢 ИСХОДЯЩИЙ ОТВЕТ
        process_time = time.time() - start_time
        print(f"✅ ОТВЕТ: Статус {response.status_code}")
        print(f"⏱️ Время: {process_time:.3f} сек")
        print("=" * 50 + "\n")

        return response