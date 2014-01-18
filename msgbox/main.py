import time
import logging
logging.basicConfig(level=logging.INFO,
                    format='[%(levelname)1.1s %(asctime)s] '
                           '%(threadName)-20s '
                           '%(name)-10s %(message)s')

from msgbox import logger
from msgbox.manager import SerialPortManager, StopActor
from msgbox.web import start_web


def main():
    serial_manager = SerialPortManager()
    serial_manager.start()
    try:
        start_web()
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("shutting down ...")
        serial_manager.send(StopActor())


if __name__ == '__main__':
    main()
