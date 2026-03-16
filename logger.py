import logging
from datetime import datetime

from elasticsearch import Elasticsearch


class ElasticsearchHandler(logging.Handler):
    def __init__(
        self,
        hosts: list[str] | None = None,
        index: str = "fastapi-logs",
        level: int = logging.WARNING,
        timeout: float = 2.0,
        total_timeout: float = 5.0,
        max_retries: int = 10,
    ):
        super().__init__(level=level)
        self.request_timeout = timeout
        self.total_timeout = total_timeout
        self.max_retries = max_retries
        self.es = Elasticsearch(
            hosts or ["http://elasticsearch:9200"],
            request_timeout=timeout,
            retry_on_timeout=True,
            max_retries=max_retries,
        )
        self.index = index

    def emit(self, record: logging.LogRecord) -> None:
        try:
            doc = {
                "@timestamp": datetime.utcnow().isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "module": record.module,
                "funcName": record.funcName,
                "lineno": record.lineno,
            }

            # Пробрасываем extra-поля (request_id, user и т.п.), если есть
            for key, value in record.__dict__.items():
                if key not in {
                    "name",
                    "msg",
                    "args",
                    "levelname",
                    "levelno",
                    "pathname",
                    "filename",
                    "module",
                    "exc_info",
                    "exc_text",
                    "stack_info",
                    "lineno",
                    "funcName",
                    "created",
                    "msecs",
                    "relativeCreated",
                    "thread",
                    "threadName",
                    "processName",
                    "process",
                }:
                    doc[key] = value

            # Жестко ограничиваем суммарное время на попытки/ретраи
            budget = max(0.0, float(self.total_timeout))
            per_try = max(0.001, float(self.request_timeout))
            allowed_retries = max(0, min(self.max_retries, int(budget // per_try) - 1))

            self.es.options(
                request_timeout=min(per_try, budget) if budget > 0 else per_try,
                max_retries=allowed_retries,
                retry_on_timeout=True,
            ).index(index=self.index, document=doc)
        except Exception:
            # Никогда не роняем приложение из‑за проблем с логами
            pass


def setup_logging(level: int = logging.DEBUG, log_file: str = "app.log"):
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)

    es_handler = ElasticsearchHandler()

    root_logger.handlers = [console_handler, file_handler, es_handler]

    # Приглушаем сторонние библиотеки
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("elasticsearch").setLevel(logging.WARNING)
