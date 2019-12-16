import flask 
import os

app = flask.Flask(__name__)
app.config.from_object(os.environ['APP_SETTINGS'])

@app.route('/')
def ecf():
    return flask.jsonify(message='Check out www.engineeredcashflow.com',
                         status='OK')

@app.route('/<zipcode>')
def ecf_zipcode(zipcode):
    return flask.jsonify(zipcode=zipcode)

if __name__ == '__main__':
    app.run()