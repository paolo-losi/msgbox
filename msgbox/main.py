import logging
import tornado.ioloop

from msgbox import logger
from msgbox.http import http_server_manager, http_client_manager
from msgbox.serial import serial_manager
from msgbox.sim import sim_manager


logging.basicConfig(level=logging.INFO,
                    format='[%(levelname)1.1s %(asctime)s] '
                           '%(name)-15s '
                           '%(threadName)-20s '
                           '%(message)s')


def stop_ioloop():
    http_client_manager.stop()
    ioloop = tornado.ioloop.IOLoop.instance()
    ioloop.add_callback(ioloop.stop)


def main():
    http_client_manager.start()
    sim_manager.start()
    serial_manager.start()
    http_server_manager.start()
    try:
        tornado.ioloop.IOLoop.instance().start()
    except KeyboardInterrupt:
        pass
    except Exception:
        logger.error('error trapped', exc_info=True)
    finally:
        logger.info("shutting down ...")
        http_server_manager.stop()
        serial_manager.stop()
        sim_manager.stop(stop_ioloop)


if __name__ == '__main__':
    main()
