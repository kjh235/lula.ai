import logging

logger = logging.getLogger(__name__)


def run_full_sync(*args, **kwargs):
    logger.info("master_sync: no-op (single PostgreSQL DB with row-level isolation)")
    return {"synced_at": None, "tables": {}}
