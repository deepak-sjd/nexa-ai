import logging
import sys


def configure_logging(debug: bool = False) -> None:
    """
    Configure application-wide logging.

    Called once at startup from main.py. Replaces ad-hoc
    print() statements with structured, leveled logging that
    can be redirected/aggregated in production.
    """

    level = logging.DEBUG if debug else logging.INFO

    formatter = logging.Formatter(
        fmt=(
            "%(asctime)s | %(levelname)-8s | "
            "%(name)s | %(message)s"
        ),
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Avoid duplicate handlers on reload (uvicorn --reload
    # re-imports modules).
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Quiet noisy third-party loggers unless we're debugging.
    logging.getLogger("httpx").setLevel(
        logging.WARNING if not debug else logging.DEBUG
    )
    logging.getLogger("google_genai").setLevel(
        logging.WARNING if not debug else logging.DEBUG
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)