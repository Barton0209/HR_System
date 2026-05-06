"""
Middleware для rate limiting и безопасности
"""
import time
from collections import defaultdict
from typing import Dict, Callable
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware для ограничения количества запросов (rate limiting).
    Ограничивает количество запросов от одного IP в минуту.
    """
    
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        # Хранилище: IP -> список временных меток запросов
        self.request_history: Dict[str, list] = defaultdict(list)
    
    async def dispatch(self, request: Request, call_next: Callable):
        # Получаем IP клиента
        client_ip = request.client.host if request.client else "unknown"
        
        # Пропускаем health check endpoints без ограничений
        if request.url.path in ["/health", "/health/live", "/health/ready", "/metrics"]:
            return await call_next(request)
        
        current_time = time.time()
        window_start = current_time - 60  # Окно в 60 секунд
        
        # Очищаем старые записи за пределами окна
        self.request_history[client_ip] = [
            ts for ts in self.request_history[client_ip]
            if ts > window_start
        ]
        
        # Проверяем лимит
        if len(self.request_history[client_ip]) >= self.requests_per_minute:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Слишком много запросов",
                    "retry_after": int(60 - (current_time - self.request_history[client_ip][0]))
                },
                headers={"Retry-After": str(int(60 - (current_time - self.request_history[client_ip][0])))}
            )
        
        # Записываем текущий запрос
        self.request_history[client_ip].append(current_time)
        
        # Продолжаем обработку запроса
        response = await call_next(request)
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware для добавления заголовков безопасности.
    """
    
    async def dispatch(self, request: Request, call_next: Callable):
        response = await call_next(request)
        
        # Добавляем заголовки безопасности
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # Для HTTPS в production раскомментировать:
        # response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return response
