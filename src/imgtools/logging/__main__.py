import time
from imgtools.logging import logger
import click
import logging
from tqdm import trange
from tqdm.contrib.logging import logging_redirect_tqdm 


@click.command()
def main():
    """
    Create and configure an example structlog logger.
    """
    logger.debug(
        "This is a debug message",
        context_var1="value1",
        context_var2="value2",
    )
    logger.info(
        "This is an info message",
        user="user123",
        action="info_action",
    )
    logger.warning(
        "This is a warning message",
        file="file.txt",
        line=42,
    )
    logger.error(
        "This is an error message",
        error_code=500,
        module="main_module",
    )
    logger.critical(
        "This is a critical message",
        system="production",
        severity="high",
    )
    logger.fatal(
        "This is a fatal message",
        reason="Unknown",
        attempt=5,
    )

    # To use tqdm with logger,
    # you need to get the logger from base logging instead of structlog
    # which also works as normal
    imgtools_logger = logging.getLogger("imgtools")
    imgtools_logger.info("This is an imgtools logger message", extra={"foo": "bar"})
    imgtools_logger.warning("This is an imgtools logger warning message", extra={"warning": "oh no"})

    with logging_redirect_tqdm([imgtools_logger]):
        for i in trange(4):
            imgtools_logger.info(f"This is a tqdm logger message {i}")
            time.sleep(0.5)
            if i == 3:
                1 / 0


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.exception(e)