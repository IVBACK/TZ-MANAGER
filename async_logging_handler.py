import logging
import concurrent.futures

class AsyncLoggingHandler(logging.Handler):
    def __init__(self, level, handler):
        super().__init__(level)
        self.handler = handler
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

    def emit(self, record):
        self.executor.submit(self._emit, record)

    def _emit(self, record):
        self.handler.emit(record)