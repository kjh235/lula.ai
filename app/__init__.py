import os
from flask import Flask

app = Flask(__name__)
app.config['DB_PATH'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bless.db')
app.config['MASTER_DB_PATH'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'master.db')

import data_management
data_management.init_db(app.config['DB_PATH'])

from app.master_db import init_master_db
init_master_db(app.config['MASTER_DB_PATH'])

from apscheduler.schedulers.background import BackgroundScheduler
from app.master_sync import run_full_sync

_scheduler = BackgroundScheduler(daemon=True)
_scheduler.add_job(
    func=lambda: run_full_sync(app.config['DB_PATH'], app.config['MASTER_DB_PATH']),
    trigger='interval',
    hours=6,
    id='master_sync',
    replace_existing=True,
)
_scheduler.start()

from app.stripe_routes import payments, load_stripe_config
load_stripe_config(app)
app.register_blueprint(payments)

from app import routes
