import logging
import logging.handlers
import time
from datetime import datetime, timezone
from queue import Queue

from elasticsearch import Elasticsearch


class ExtraFormatter(logging.Formatter):
    """Formatter, который дописывает extra-поля в строку лога."""

    STANDARD_KEYS = {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "message", "taskName",
    }

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        extras = {
            k: v for k, v in record.__dict__.items()
            if k not in self.STANDARD_KEYS and not k.startswith("_")
        }
        if extras:
            pairs = " ".join(f"{k}={v}" for k, v in extras.items())
            return f"{base} | {pairs}"
        return base


class ElasticsearchHandler(logging.Handler):
    """Handler, отправляющий логи в Elasticsearch."""

    STANDARD_KEYS = {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "message", "taskName",
    }

    def __init__(
        self,
        hosts: list[str] | None = None,
        index: str = "fastapi-logs",
        level: int = logging.DEBUG,
        timeout: float = 2.0,
        total_timeout: float = 5.0,
        max_retries: int = 10,
        error_log_interval: float = 300.0,
    ):
        super().__init__(level=level)
        self.request_timeout = timeout
        self.total_timeout = total_timeout
        self.max_retries = max_retries
        self.error_log_interval = error_log_interval
        self._last_error_logged: float = 0
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
                "@timestamp": datetime.now(timezone.utc).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "module": record.module,
                "funcName": record.funcName,
                "lineno": record.lineno,
            }

            for key, value in record.__dict__.items():
                if key not in self.STANDARD_KEYS and not key.startswith("_"):
                    doc[key] = value

            budget = max(0.0, float(self.total_timeout))
            per_try = max(0.001, float(self.request_timeout))
            allowed_retries = max(0, min(self.max_retries, int(budget // per_try) - 1))

            self.es.options(
                request_timeout=min(per_try, budget) if budget > 0 else per_try,
                max_retries=allowed_retries,
                retry_on_timeout=True,
            ).index(index=self.index, document=doc)
        except Exception:
            now = time.monotonic()
            if now - self._last_error_logged > self.error_log_interval:
                self._last_error_logged = now
                logging.getLogger("elasticsearch.handler").warning(
                    "Elasticsearch недоступен, логи не отправляются"
                )


def setup_logging(level: int = logging.DEBUG, log_file: str = "app.log"):
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    formatter = ExtraFormatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    file_handler = logging.handlers.RotatingFileHandler(
        log_file, encoding="utf-8", maxBytes=10 * 1024 * 1024, backupCount=5,
    )
    file_handler.setFormatter(formatter)

    # ES handler в отдельном потоке через QueueHandler/QueueListener
    es_handler = ElasticsearchHandler()
    log_queue: Queue[logging.LogRecord] = Queue(-1)
    queue_handler = logging.handlers.QueueHandler(log_queue)
    queue_listener = logging.handlers.QueueListener(
        log_queue, es_handler, respect_handler_level=True,
    )
    queue_listener.start()

    root_logger.handlers = [console_handler, file_handler, queue_handler]

    # Приглушаем сторонние библиотеки
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("elasticsearch").setLevel(logging.WARNING)
    logging.getLogger("elasticsearch.handler").setLevel(logging.WARNING)

    return queue_listener
