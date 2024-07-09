import pygame
import math
from PyQt6.QtCore import QThread, pyqtSignal
import logging

logging.basicConfig(level=logging.INFO)


def convert_to_polar_coordinates(x, y):
    """
    将笛卡尔坐标转换为极坐标
    """
    r = math.sqrt(x**2 + y**2)
    theta = math.atan2(y, x)
    return r, theta


def convert_handle_to_dutycycle(x, y):
    """
    将手柄输入转换为占空比
    """
    r, theta = convert_to_polar_coordinates(x, y)
    if r > 1:
        r = 1
    theta = theta - math.pi / 2

    if 0 <= theta < math.pi / 2:
        r_do = r
        l_do = r * math.cos(theta)
    elif -3 * math.pi / 2 <= theta < -math.pi:
        r_do = -r
        l_do = r * math.cos(theta)
    elif -math.pi / 2 <= theta < 0:
        r_do = r * math.cos(theta)
        l_do = r
    elif -math.pi <= theta < -math.pi / 2:
        r_do = r * math.cos(theta)
        l_do = -r

    r_do = -round(r_do, 1)
    l_do = -round(l_do, 1)
    return (l_do, r_do)


class HandleTask(QThread):
    """
    手柄遥控任务类
    """

    data_send = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        pygame.init()
        self.clock = pygame.time.Clock()
        self.done = False
        self.is_running = True

    def run(self):
        """
        运行手柄遥控任务
        """
        while self.is_running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.done = True

                if event.type == pygame.JOYDEVICEADDED:
                    joy = pygame.joystick.Joystick(event.device_index)
                    joy.init()
                    logging.info("Joystick %s connected", joy.get_id())

                if event.type == pygame.JOYDEVICEREMOVED:
                    logging.info("Joystick %s disconnected", event.joy)

            if not self.done:
                self.handle_input()

            self.clock.tick(100)

        pygame.quit()

    def handle_input(self):
        """
        处理手柄输入，发送数据信号
        """
        joystick = pygame.joystick.Joystick(0)
        joystick.init()
        x = joystick.get_axis(0)
        y = -joystick.get_axis(1)
        l_do, r_do = convert_handle_to_dutycycle(x, y)
        logging.info("Joystick input: Lsend=%s, Rsend=%s", l_do, r_do)
        self.data_send.emit({"Lsend": l_do, "Rsend": r_do})
