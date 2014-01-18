import tornado.web
import tornado.httpserver

# application/x-www-form-urlencoded
# params:
#   key:      "asds7878"      (optional)
#   receiver: "+393482222222"
#   sender:   "+393481111111" (or use "dev" instead)
#   dev:      "/dev/ttyUSB0"  (or use "sender" instead)
#   text:     "sms text"

class MTHandler(tornado.web.RequestHandler):

    def post(self):
        self.write("Hello, world")


class HTTPManager(object):

    def __init__(self):
        app = tornado.web.Application([
            (r"/send_sms", MTHandler),
        ])
        self.http_server = tornado.httpserver.HTTPServer(app)

    def start(self):
        self.http_server.listen(8888)

    def stop(self):
        self.http_server.stop()


http_manager = HTTPManager()
