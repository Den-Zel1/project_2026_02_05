import logging
from datetime import datetime

from elasticsearch import Elasticsearch


class ElasticsearchHandler(logging.Handler):
    def __init__(self, hosts: list[str] | None = None, index: str = "fastapi-logs", level: int = logging.DEBUG):
        super().__init__(level=level)
        self.es = Elasticsearch(hosts or ["http://elasticsearch:9200"])
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

            self.es.index(index=self.index, document=doc)
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
