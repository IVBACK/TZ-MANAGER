import logging
from logging.handlers import RotatingFileHandler
from colorlog import ColoredFormatter
from async_logging_handler import AsyncLoggingHandler

class LoggerManager:
    ALERT_LEVEL = 35
    RESOLVED_LEVEL = 25

    def __init__(self, log_file):
        # Initialize and configure logger
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.setup_custom_levels()
        self.set_up_file_logging(log_file)
        self.set_up_console_logging()

    def setup_custom_levels(self):
        logging.addLevelName(self.ALERT_LEVEL, 'ALERT')
        logging.addLevelName(self.RESOLVED_LEVEL, 'RESOLVED')
        logging.Logger.alert = self.alert
        logging.Logger.resolved = self.resolved

    def alert(self, message, *args, **kwargs):
        if self.logger.isEnabledFor(self.ALERT_LEVEL):
            self.logger._log(self.ALERT_LEVEL, message, args, **kwargs)

    def resolved(self, message, *args, **kwargs):
        if self.logger.isEnabledFor(self.RESOLVED_LEVEL):
            self.logger._log(self.RESOLVED_LEVEL, message, args, **kwargs)

    def set_up_file_logging(self, log_file):
        log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', datefmt="%Y-%m-%d %H:%M:%S")
        log_handler = RotatingFileHandler(log_file, mode='a', maxBytes=5*1024*1024, backupCount=2, encoding=None, delay=0)
        log_handler.setFormatter(log_formatter)
        async_log_handler = AsyncLoggingHandler(logging.INFO, log_handler)
        self.logger.addHandler(async_log_handler)

    def set_up_console_logging(self):
        # Creating a console handler
        console_handler = logging.StreamHandler()

        # Setting the log level for the console handler
        console_handler.setLevel(logging.INFO)  # or any other level you prefer

        # Creating a formatter with colors
        color_formatter = ColoredFormatter(
            "%(log_color)s%(asctime)s - %(levelname)s - %(message)s%(reset)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
                'ALERT': 'red,bg_white',  # Assuming ALERT is a custom level you have defined
                'RESOLVED': 'blue',       # Assuming RESOLVED is a custom level you have defined
            }
        )

        # Applying the formatter to the console handler
        console_handler.setFormatter(color_formatter)

        # Adding the console handler to the logger
        self.logger.addHandler(console_handler)
