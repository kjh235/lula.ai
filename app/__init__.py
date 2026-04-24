import os
from flask import Flask

app = Flask(__name__)
app.config['DB_PATH'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'bless.db')

from app import routes
