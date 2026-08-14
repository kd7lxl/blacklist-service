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
    try:
        client.subscribe('blacklist')
        yield "# longpoll begin\n"
        with gevent.Timeout(60, False):
            for i in xrange(100):
                message = client.get_message(timeout=4.0)
                if message is None:
                    yield "# longpoll wait\n"
                elif message['type'] == 'message':
                    yield message['data'] + "\n"
                    break
                else:
                    yield "# longpoll timeout\n"
    finally:
        client.close()
        server.connection_pool.disconnect()


bind = ('0.0.0.0', 1234)
server = pywsgi.WSGIServer(bind, handle)
print "Serving on http://%s:%d..." % bind
try:
    server.serve_forever()
except KeyboardInterrupt:
    server.stop()
