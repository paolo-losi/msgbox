from functools import partial

import tornado.httpserver
import tornado.ioloop
from tornado.web import HTTPError, RequestHandler, Application, asynchronous

from msgbox import logger
from msgbox.sim import sim_manager, TxSms


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

        sim_manager.send(TxSms(sender, receiver, text, imsi, key,
                               callback=self.reply_callback))

    def reply_callback(self, response_dict):
        ioloop.add_callback(partial(self.handle_reply, response_dict))

    def handle_reply(self, response_dict):
        log_method = logger.warn if response_dict['status'] == 'ERROR' else \
                     logger.info
        log_method(response_dict['desc'])
        self.write(response_dict)
        self.finish()


class HTTPManager(object):

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


http_manager = HTTPManager()
