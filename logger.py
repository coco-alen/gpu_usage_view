import logging
from rich.logging import RichHandler
from config import log_level

logging.basicConfig(
    level=log_level, format="| %(name)s ===>> %(message)s", datefmt="%X", handlers=[RichHandler()]
    )

logger = logging.getLogger("GpuWatcher")

if __name__ == "__main__":
    logger.debug("Debug message")
    logger.info("Hello, World!")
    logger.warning("Warning message")
    logger.error("Error message")
    logger.critical("Critical message")