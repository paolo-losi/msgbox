import tornado.ioloop
import tornado.web

# application/x-www-form-urlencoded
# params:
#   receiver: "+393482222222"
#   sender:   "+393481111111" (or use "dev" instead)
#   dev:      "/dev/ttyUSB0"  (or use "sender" instead)
#   text:     "sms text"

class MTHandler(tornado.web.RequestHandler):

    def post(self):
        self.write("Hello, world")


application = tornado.web.Application([
    (r"/send_sms", MTHandler),
])


def start_web():
    application.listen(8888)
    tornado.ioloop.IOLoop.instance().start()
