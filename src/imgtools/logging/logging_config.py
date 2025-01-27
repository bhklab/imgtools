import logging.config
import os
from pathlib import Path
from typing import Dict, List

import structlog
from structlog.processors import CallsiteParameter, CallsiteParameterAdder
from structlog.typing import Processor

from imgtools.logging.processors import (
    CallPrettifier,
    ESTTimeStamper,
    PathPrettifier,
)

VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
DEFAULT_LOG_LEVEL = "WARNING"


class LoggingManager:
    """
    Manages the configuration and initialization of a structured logger.

    This class provides flexible options for configuring log levels, formats,
    and output destinations.

    Parameters
    ----------
    name : str
        Name of the logger instance.

    Attributes
    ----------
    name : str
        Name of the logger instance.
    base_dir : Path
        Base directory for path prettification.
                    i.e if base_dir is /home/user/project and logs include a path like /home/user/project/data/file.txt
                    then the path will be prettified to data/file.txt
    level : str
        Log level for the logger.


    Methods
    -------
    get_logger()
        Retrieve the configured logger instance.
    configure_logging(level=None)
        Dynamically adjust logging settings.

    Raises
    ------
    ValueError
        If an invalid log level is provided.
    RuntimeError
        If the log directory or file cannot be created.

    Examples
    --------
    Initialize with default settings:
        >>> manager = LoggingManager(name="mypackage")
        >>> logger = manager.get_logger()
        >>> logger.info("Info message")
    """

    def __init__(
        self,
        name: str,
        base_dir: Path | None = None,
    ) -> None:
        self.name = name
        self.base_dir = base_dir or Path.cwd()
        self.level = self.env_level
        self._initialize_logger()

    @property
    def env_level(self) -> str:
        return os.environ.get(
            f"{self.name}_LOG_LEVEL".upper(), DEFAULT_LOG_LEVEL
        ).upper()

    @property
    def base_logging_config(self) -> Dict:
        """
        Create the basic logging configuration settings.

        Returns
        -------
        dict
            Base logging configuration.
        """
        return {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "console": {
                    "()": structlog.stdlib.ProcessorFormatter,
                    "processors": [
                        CallPrettifier(concise=True),
                        structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                        structlog.dev.ConsoleRenderer(
                            exception_formatter=structlog.dev.RichTracebackFormatter(
                                width=-1, show_locals=False
                            ),
                        ),
                    ],
                    "foreign_pre_chain": self.pre_chain,
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "console",
                },
            },
            "loggers": {
                self.name: {
                    "handlers": ["console"],
                    "level": self.level,
                    "propagate": False,
                },
            },
        }

    @property
    def pre_chain(self) -> List[Processor]:
        return [
            structlog.stdlib.add_log_level,
            ESTTimeStamper(),
            structlog.stdlib.add_logger_name,
            structlog.stdlib.PositionalArgumentsFormatter(),
            CallsiteParameterAdder(
                [
                    CallsiteParameter.MODULE,
                    CallsiteParameter.FUNC_NAME,
                    CallsiteParameter.LINENO,
                ]
            ),
            PathPrettifier(base_dir=self.base_dir),
            structlog.stdlib.ExtraAdder(),
            structlog.processors.StackInfoRenderer(),
        ]

    def _initialize_logger(self) -> None:
        """
        Initialize the logger with the current configuration.
        """

        logging.config.dictConfig(self.base_logging_config)
        structlog.configure(
            processors=[
                *self.pre_chain,
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

    def get_logger(self) -> structlog.stdlib.BoundLogger:
        """
        Retrieve the logger instance.

        Returns
        -------
        structlog.stdlib.BoundLogger
            Configured logger instance.
        """
        return structlog.get_logger(self.name)

    def configure_logging(
        self, level: str = DEFAULT_LOG_LEVEL
    ) -> structlog.stdlib.BoundLogger:
        """
        Dynamically adjust logging settings.

        Parameters
        ----------
        level : str, optional
                        Set the log level.

        Returns
        -------
        structlog.stdlib.BoundLogger
                        Updated logger instance.

        Raises
        ------
        ValueError
                        If an invalid log level is specified.
        """
        level_upper = level.upper()
        if level_upper not in VALID_LOG_LEVELS:
            msg = f"Invalid logging level: {level}"
            raise ValueError(msg)

        # Store the old level for logging the change
        old_level = self.level
        self.level = level_upper

        self._initialize_logger()
        logger = self.get_logger()

        # Log the level change
        if old_level != self.level:
            logger.info(
                "Log level changed", old_level=old_level, new_level=self.level
            )

        return logger
