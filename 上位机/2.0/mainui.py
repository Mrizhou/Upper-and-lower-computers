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
        self.clock = pygame.time
