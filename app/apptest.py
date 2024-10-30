from flask import Flask, render_template
import gmail

app = Flask(__name__)


@app.route('/')
def index():
    # # Generate example metrics (replace with data_management calls)
    summary = gmail.gmail_creds()
    metric1 = summary[0]
    metric2 = summary[1]
    metric3 = summary[2]

    #
    return render_template("index.html", metric1=metric1, metric2=metric2, metric3=metric3)

@app.route("/success")
def success():
    return render_template("success.html")


@app.route("/cancel")
def cancelled():
    return render_template("cancel.html")




if __name__ == '__main__':
    app.run(debug=True)
