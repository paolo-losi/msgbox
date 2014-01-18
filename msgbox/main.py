import logging
logging.basicConfig(level=logging.INFO,
                    format='[%(levelname)1.1s %(asctime)s] '
                           '%(threadName)-20s '
                           '%(name)-10s %(message)s')

from msgbox import logger
from msgbox.serial import serial_manager
from msgbox.sim import sim_manager
from msgbox.web import start_web


def main():
    sim_manager.start()
    serial_manager.start()
    try:
        start_web()
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("shutting down ...")
        serial_manager.stop()
        sim_manager.stop()


if __name__ == '__main__':
    main()
