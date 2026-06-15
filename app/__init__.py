import asyncio
import logging
import os
from flask import Flask

logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['DB_PATH'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bless.db')
app.config['MASTER_DB_PATH'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'master.db')
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', os.urandom(24))

import data_management
data_management.init_db(app.config['DB_PATH'])

from app.master_db import init_master_db
init_master_db(app.config['MASTER_DB_PATH'])

from apscheduler.schedulers.background import BackgroundScheduler
from app.master_sync import run_full_sync
from lularoe_scraper import BlessScraper


def _run_bless_scrape():
    db_path = app.config['DB_PATH']
    try:
        asyncio.run(BlessScraper(db_path).run())
    except Exception:
        logger.exception("Bless scrape failed")


_scheduler = BackgroundScheduler(daemon=True)
_scheduler.add_job(
    func=lambda: run_full_sync(app.config['DB_PATH'], app.config['MASTER_DB_PATH']),
    trigger='interval',
    hours=6,
    id='master_sync',
    replace_existing=True,
)
_scheduler.add_job(
    func=_run_bless_scrape,
    trigger='interval',
    hours=6,
    id='bless_scrape',
    replace_existing=True,
)
_scheduler.start()

from app.stripe_routes import payments, load_stripe_config
load_stripe_config(app)
app.register_blueprint(payments)

from app import routes
