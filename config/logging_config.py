"""
Logging Configuration

Sets up structured logging for the entire application.
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from loguru import logger


def setup_logging(
    log_dir: Path = None,
    level: str = "INFO",
    enable_file_logging: bool = True
):
    """
    Configure logging for the application

    Args:
        log_dir: Directory to store log files
        level: Logging level (DEBUG, INFO, WARNING, ERROR)
        enable_file_logging: Whether to write logs to files
    """

    # Remove default logger
    logger.remove()

    # Console logging with color
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=level,
        colorize=True
    )

    if enable_file_logging:
        if log_dir is None:
            log_dir = Path(__file__).parent.parent / "logs"

        log_dir.mkdir(parents=True, exist_ok=True)

        # General application log (rotates daily)
        logger.add(
            log_dir / "app_{time:YYYY-MM-DD}.log",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            level=level,
            rotation="00:00",  # Rotate at midnight
            retention="30 days",  # Keep 30 days of logs
            compression="zip"  # Compress old logs
        )

        # Error log (separate file for errors)
        logger.add(
            log_dir / "errors_{time:YYYY-MM-DD}.log",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}\n{exception}",
            level="ERROR",
            rotation="00:00",
            retention="90 days",
            compression="zip"
        )

        # Agent decisions log (track all agent recommendations)
        logger.add(
            log_dir / "agent_decisions_{time:YYYY-MM-DD}.log",
            format="{time:YYYY-MM-DD HH:mm:ss} | {extra[agent]} | {message}",
            level="INFO",
            rotation="00:00",
            retention="1 year",
            compression="zip",
            filter=lambda record: "agent" in record["extra"]
        )

        # Performance log (track API calls, execution time)
        logger.add(
            log_dir / "performance_{time:YYYY-MM-DD}.log",
            format="{time:YYYY-MM-DD HH:mm:ss} | {extra[operation]} | {message}",
            level="DEBUG",
            rotation="00:00",
            retention="7 days",
            filter=lambda record: "operation" in record["extra"]
        )

    return logger


def log_agent_decision(
    agent_name: str,
    decision: str,
    symbol: str = None,
    confidence: float = None,
    reasoning: str = None
):
    """Log agent decision with structured format"""

    message = f"Decision: {decision}"
    if symbol:
        message += f" | Symbol: {symbol}"
    if confidence is not None:
        message += f" | Confidence: {confidence:.2%}"
    if reasoning:
        message += f" | Reasoning: {reasoning}"

    logger.bind(agent=agent_name).info(message)


def log_performance(operation: str, duration_ms: float, success: bool = True):
    """Log performance metrics"""

    status = "SUCCESS" if success else "FAILED"
    logger.bind(operation=operation).debug(
        f"{status} | Duration: {duration_ms:.2f}ms"
    )


if __name__ == "__main__":
    # Test logging setup
    setup_logging(level="DEBUG")

    logger.info("Application started")
    logger.debug("Debug message")
    logger.warning("Warning message")
    logger.error("Error message")

    # Test agent decision logging
    log_agent_decision(
        agent_name="portfolio_optimizer",
        decision="BUY",
        symbol="AAPL",
        confidence=0.85,
        reasoning="Strong fundamentals, oversold technically"
    )

    # Test performance logging
    log_performance("data_fetch", 150.5, success=True)
