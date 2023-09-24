from flask import render_template
from app import app, db
import random

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)

@app.route("/")
def index():
    # Generate example metrics (replace with real data)
    metric1 = random.randint(10, 100)
    metric2 = random.uniform(1.0, 10.0)
    metric3 = random.randint(500, 1000)

    return render_template('index.html', metric1=metric1, metric2=metric2, metric3=metric3)