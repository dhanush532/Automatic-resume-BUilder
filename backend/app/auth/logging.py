import logging


class RedactAuthQuery(logging.Filter):
    def filter(self, record):
        # Uvicorn access args: client, method, full path, HTTP version, status.
        if isinstance(record.args, tuple) and len(record.args) == 5:
            values = list(record.args)
            if isinstance(values[2], str) and "/auth/" in values[2] and "?" in values[2]:
                values[2] = values[2].split("?", 1)[0] + "?[redacted]"
                record.args = tuple(values)
        return True


def protect_auth_logs():
    logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(item, RedactAuthQuery) for item in logger.filters):
        logger.addFilter(RedactAuthQuery())
