import logging
import logging.handlers

_LOG_FMT = '%(asctime)s %(levelname)s [%(filename)s:%(lineno)d] %(message)s'

logger = logging.getLogger('i3-workspace-groups')

def init_logger(name: str) -> None:
    syslog_handler = logging.handlers.SysLogHandler(address='/dev/log')
    stdout_handler = logging.StreamHandler()
    stdout_formatter = logging.Formatter(_LOG_FMT)
    stdout_handler.setFormatter(stdout_formatter)
    syslog_formatter = logging.Formatter('{}: {}'.format(name, _LOG_FMT))
    syslog_formatter.ident = name
    syslog_handler.setFormatter(syslog_formatter)
    logger.addHandler(syslog_handler)
    logger.addHandler(stdout_handler)
