import tornado.httpserver
from tornado.web import HTTPError, RequestHandler, Application

from msgbox import logger


# application/x-www-form-urlencoded
# params:
#   key:      "asds7878"      (optional)
#   receiver: "+393482222222"
#   sender:   "+393481111111"
#   imsi:     "21312123232"
#   text:     "sms text"

class MTHandler(RequestHandler):

    def post(self):
        text     = self.get_argument('text')
        receiver = self.get_argument('receiver')
        key      = self.get_argument('key', None)

        sender   = self.get_argument('sender', None)
        imsi     = self.get_argument('imsi', None)

        if not ((sender is None) ^ (imsi is None)):
            err_msg = 'Use either "sender" or "imsi" params'
            raise HTTPError(400, err_msg)

        self.write("Hello, world")


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
