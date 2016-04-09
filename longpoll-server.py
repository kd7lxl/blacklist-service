#!/usr/bin/env python

from gevent import monkey
monkey.patch_all()

import gevent
from gevent import pywsgi
from gevent import queue
import redis


def process_messages(body):
    server = redis.Redis(host='localhost', port=6379, db=0)
    client = server.pubsub()
    client.subscribe('blacklist')
    while True:
        message = client.get_message(timeout=900.0)
        if message is None:
            # timeout - send something valid but benign, such as a TESTNET address
            body.put("192.0.2.0")
            body.put("192.0.2.0")
            break
        elif message['type'] == 'message':
            # Send it twice: once for the data, second for the content-length. WTF
            body.put("%s" % message['data'])
            body.put("%s" % message['data'])
            break
    body.put(StopIteration)


def handle(environ, start_response):
    start_response('200 OK', [
        ('Content-Type', 'text/plain'),
        ('Connection', 'close'),
    ])
    body = queue.Queue()
    gevent.spawn(process_messages, body)
    return body


server = pywsgi.WSGIServer(('127.0.0.1', 1234), handle)
print "Serving on http://127.0.0.1:1234..."
try:
    server.serve_forever()
except KeyboardInterrupt:
    server.stop()
