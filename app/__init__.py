import asyncio
import logging
import os
from flask import Flask

logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s: %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-prod')

import data_management
data_management.init_db()

from app.auth import auth
app.register_blueprint(auth)

from app.stripe_routes import payments, load_stripe_config
load_stripe_config(app)
app.register_blueprint(payments)

from app import routes
