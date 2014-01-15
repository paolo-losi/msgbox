import time
import logging
logging.basicConfig(level=logging.INFO,
                    format='[%(levelname)1.1s %(asctime)s] '
                           '%(threadName)-20s '
                           '%(name)-10s %(message)s')

from msgbox.manager import SerialPortManager, StopActor
from msgbox import logger


serial_manager = SerialPortManager()
serial_manager.start()
time.sleep(100)
serial_manager.send(StopActor())
logger.info("StopActor sent")
