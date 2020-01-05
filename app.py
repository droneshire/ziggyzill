import flask
import os
import rq

import worker
from src.zillow_scraper import ZillowScraperGsheets
from src.zillow_scraper import scrape_zillow_zipcode

app = flask.Flask(__name__)
app.config.from_object(os.environ['APP_SETTINGS'])

worker_queue = rq.Queue(connection=worker.connection)


@app.route('/')
def ecf():
    return flask.jsonify(message='Check out https://www.engineeredcashflow.com',
                         status='OK')


@app.route('/<zipcode>/<email>')
def ecf_zipcode(zipcode, email):
    # worker_queue.enqueue(scrape_zillow_zipcode, zipcode=zipcode, email=email)
    scrape_zillow_zipcode(zipcode, email)
    return flask.jsonify(zipcode=zipcode,
                         email=email,
                         status='PROCESSING_REQUEST')


if __name__ == '__main__':
    app.run()
