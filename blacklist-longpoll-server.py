#!/usr/bin/env python

import os

from gevent import monkey
monkey.patch_all()

import gevent
from gevent import pywsgi
import redis


def handle(environ, start_response):
    start_response('200 OK', [
        ('Content-Type', 'text/plain'),
        ('Connection', 'close'),
    ])
    server = redis.Redis(host=os.environ.get("REDIS_HOST", "localhost"),
                         port=6379, db=0)
    client = server.pubsub()
    client.subscribe('blacklist')

    yield "# longpoll begin\n"

    for i in xrange(100):
        # Mikrotik 6.39+ times out if no data is received for 5 seconds
        message = client.get_message(timeout=4.0)
        if message is None:
            yield "# longpoll wait\n"
        elif message['type'] == 'message':
            yield message['data'] + "\n"
            break
    else:
        yield "# longpoll timeout\n"
    client.close()


bind = ('0.0.0.0', 1234)
server = pywsgi.WSGIServer(bind, handle)
print "Serving on http://%s:%d..." % bind
try:
    server.serve_forever()
except KeyboardInterrupt:
    server.stop()
