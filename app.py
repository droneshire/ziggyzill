import flask 
import os

app = flask.Flask(__name__)
app.config.from_object(os.environ['APP_SETTINGS'])

@app.route('/')
def ecf():
    return "Check out www.engineeredcashflow.com"

@app.route('/<zipcode>')
def ecf_zipcode(zipcode):
    return "Finding data for {}!".format(zipcode)

if __name__ == '__main__':
    app.run()