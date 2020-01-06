import flask
import os
import rq
import rq_dashboard
from decouple import config

import worker
from src.zillow_scraper import ZillowScraperGsheets
from src.zillow_scraper import scrape_zillow_zipcode


def check_auth(username, password):
    """This function is called to check if a username password combination is valid."""
    return username == app.config.get("RQ_DASHBOARD_USERNAME") and \
        password == app.config.get("RQ_DASHBOARD_PASSWORD")


def authenticate():
    """Sends a 401 response that enables basic auth."""
    return flask.Response(
        'Could not verify your access level for that URL.\n'
        'You have to login with proper credentials', 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'}
    )


def basic_auth():
    """Ensure basic authorization."""
    auth = flask.request.authorization
    if not auth or not check_auth(auth.username, auth.password):
        return authenticate()


app = flask.Flask(__name__)
app.config.from_object(rq_dashboard.default_settings)

app.config['RQ_DASHBOARD_USERNAME'] = config('RQ_DASHBOARD_USERNAME', '')
app.config['RQ_DASHBOARD_PASSWORD'] = config('RQ_DASHBOARD_PASSWORD', '')
app.config['REDIS_URL'] = config('REDIS_URL', 'localhost')

rq_dashboard.blueprint.before_request(basic_auth)
app.register_blueprint(rq_dashboard.blueprint, url_prefix="/rq")

worker_queue = rq.Queue(connection=worker.connection, is_async=True)


@app.route('/')
def ecf():
    return flask.jsonify(
        message='Check out https://www.engineeredcashflow.com',
        status='OK')


@app.route('/<zipcode>/<email>')
def ecf_zipcode(zipcode, email):
    worker_queue.enqueue(
        scrape_zillow_zipcode,
        job_timeout='3m',
        description='Scraping zipcode {} for {}'.format(
            zipcode, email),
        args=(zipcode, email))
    return flask.jsonify(zipcode=zipcode,
                         email=email,
                         status='PROCESSING_REQUEST')


if __name__ == '__main__':
    app.run()
