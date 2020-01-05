import os
import redis
import rq 

listen = ['high', 'default', 'low']

redis_url = os.getenv('REDISTOGO_URL', 'redis://localhost:6379')

connection = redis.from_url(redis_url)

if __name__ == '__main__':
    with rq.Connection(connection):
        worker = rq.Worker(map(rq.Queue, listen))
        worker.work()