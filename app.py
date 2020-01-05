import flask
import os
import rq

import worker
from src.zillow_scraper import ZillowScraperGsheets

app = flask.Flask(__name__)
app.config.from_object(os.environ['APP_SETTINGS'])

worker_queue = rq.Queue(connection=worker.connection)


@app.route('/')
def ecf():
    return flask.jsonify(message='Check out www.engineeredcashflow.com',
                         status='OK')


@app.route('/<zipcode>/<email>')
def ecf_zipcode(zipcode, email):
    status = True
    worker_queue.enqueue(scrape_zillow_zipcode, zipcode=zipcode, email=email)
    return flask.jsonify(zipcode=zipcode, status='PROCESSING_REQUEST')


if __name__ == '__main__':
    app.run()
