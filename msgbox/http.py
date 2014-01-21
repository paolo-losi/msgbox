import time
import urllib2
from Queue import Queue, Empty
from functools import partial
from threading import Thread, Lock

import tornado.httpserver
import tornado.ioloop
from tornado.web import HTTPError, RequestHandler, Application, asynchronous

from msgbox import logger
from msgbox.sim import sim_manager, TxSmsReq


ioloop = tornado.ioloop.IOLoop.instance()


# application/x-www-form-urlencoded
# params:
#   key:      "asds7878"      (optional)
#   receiver: "+393482222222"
#   sender:   "+393481111111"
#   imsi:     "21312123232"
#   text:     "sms text"

class MTHandler(RequestHandler):

    @asynchronous
    def post(self):
        sender   = self.get_argument('sender', None)
        receiver = self.get_argument('receiver')
        text     = self.get_argument('text')
        imsi     = self.get_argument('imsi', None)
        key      = self.get_argument('key', None)

        if not ((sender is None) ^ (imsi is None)):
            err_msg = 'Use either "sender" or "imsi" params'
            raise HTTPError(400, err_msg)

        sim_manager.send(TxSmsReq(sender, receiver, text, imsi, key,
                                  callback=self.reply_callback))

    def reply_callback(self, response_dict):
        ioloop.add_callback(partial(self.handle_reply, response_dict))

    def handle_reply(self, response_dict):
        log_method = logger.warn if response_dict['status'] == 'ERROR' else \
                     logger.info
        log_method(response_dict['desc'])
        self.write(response_dict)
        self.finish()


class HTTPServerManager(object):

    def __init__(self, port=8888):
        app = Application([
            (r"/send_sms", MTHandler),
        ])
        self.port = port
        self.http_server = tornado.httpserver.HTTPServer(app)

    def start(self):
        logger.info('http listening on port %s', self.port)
        self.http_server.listen(self.port)

    def stop(self):
        self.http_server.stop()


http_server_manager = HTTPServerManager()


# ~~~~~~~~ HTTP Client Manager ~~~~~~~~

class HTTPClientManagerStoppingError(Exception): pass


class HTTPClientManager(object):

    N_WORKERS = 10

    def __init__(self):
        self.active = False
        self.workers = []
        self.queue = Queue()
        self.mutex = Lock()

    def start(self):
        self.active = True
        for i in xrange(self.N_WORKERS):
            thread = Thread(name='HttpClient %d' % i, target=self._work)
            self.workers.append(thread)
            thread.start()

    def stop(self):
        with self.mutex:
            self.active = False

    def _work(self):
        while self.active or not self.queue.empty:
            try:
                msg_dict = self.queue.get(timeout=2)
            except Empty:
                continue
            url = msg_dict.pop('url')
            for attempt in xrange(3):
                try:
                    urllib2.urlopen(url, msg_dict, timeout=20)
                    logger.error('forwarded sms - sender=%s receiver=%s',
                                     msg_dict['sender'], msg_dict['receiver'])
                    break
                except Exception, e:
                    logger.error('error while sending msg', exc_info=True)
                time.sleep(10)
            else:
                logger.error('giving up sending message %s', msg_dict,
                                                             exc_info=1)

    def enqueue(self, rx_sms):
        with self.mutex:
            if self.active:
                self.queue.put(rx_sms)
            else:
                raise HTTPClientManagerStoppingError()


http_client_manager = HTTPClientManager()

