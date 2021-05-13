import logging
import logging.handlers

_LOG_FMT_STDERR = (
    '%(asctime)s %(levelname)s [%(filename)s:%(lineno)d] %(message)s')
_LOG_FMT_SYSLOG = (
    '%(levelname)s [%(filename)s:%(lineno)d] %(message)s')

logger = logging.getLogger()


def init_logger(name: str) -> None:
    stderr_handler = logging.StreamHandler()
    stderr_formatter = logging.Formatter(_LOG_FMT_STDERR)
    stderr_handler.setFormatter(stderr_formatter)
    logger.addHandler(stderr_handler)
    syslog_handler = logging.handlers.SysLogHandler(address='/dev/log')
    syslog_formatter = logging.Formatter(f'{name}: {_LOG_FMT_SYSLOG}')
    syslog_handler.setFormatter(syslog_formatter)
    logger.addHandler(syslog_handler)
