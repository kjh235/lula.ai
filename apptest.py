from flask import Flask, render_template
import random

app = Flask(__name__)


@app.route('/')
def index():
    # # Generate example metrics (replace with real data)
    # metric1 = random.randint(10, 100)
    # metric2 = random.uniform(1.0, 10.0)
    # metric3 = random.randint(500, 1000)
    #
    # return render_template('index.html', metric1=metric1, metric2=metric2, metric3=metric3)
    return "<p>Hello, World!</p>"
@app.route('/hello')
def hello():
    return 'Hello, World'



if __name__ == '__main__':
    app.run(debug=True)
