import argparse
import logging
import tornado.ioloop

from msgbox import logger
from msgbox.http import http_server_manager, http_client_manager
from msgbox.serial import SerialPortManager
from msgbox.sim import sim_manager


parser = argparse.ArgumentParser()
parser.add_argument("--debug",    help="log at debug level",
                                  action='store_true')
parser.add_argument("--usb-only", help="manage usb modems only",
                                  action='store_true')


def stop_ioloop():
    http_client_manager.stop()
    ioloop = tornado.ioloop.IOLoop.instance()
    ioloop.add_callback(ioloop.stop)


def main():
    args = parser.parse_args()

    level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=level,
                        format='[%(levelname)1.1s %(asctime)s] '
                               #'%(name)-15s '
                               '%(threadName)-20s '
                               '%(message)s')


    serial_manager = SerialPortManager(args.usb_only)

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
