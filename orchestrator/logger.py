import structlog, logging

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = structlog.get_logger()
