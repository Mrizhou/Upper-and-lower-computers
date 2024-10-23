import pygame
import math
from PyQt6.QtCore import QThread, pyqtSignal


def convert_to_polar_coordinates(x, y):
    r = math.sqrt(x**2 + y**2)
    theta = math.atan2(y, x)
    return r, theta


def convert_handle_to_dutycycle(x, y):
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
    data_send = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        pygame.init()
        self.clock = pygame.time.Clock()
        self.joysticks = {}
        self.done = False
        self.joystick_count = pygame.joystick.get_count()
        self.is_running = True

    def run(self):
        while self.is_running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.done = True  # 退出循环

                # 处理游戏手柄的热插拔
                if event.type == pygame.JOYDEVICEADDED:
                    joy = pygame.joystick.Joystick(event.device_index)
                    self.joysticks[joy.get_instance_id()] = joy
                    print(f"Joystick {joy.get_instance_id()} connencted")

                if event.type == pygame.JOYDEVICEREMOVED:
                    del self.joysticks[event.instance_id]
                    print(f"Joystick {event.instance_id} disconnected")

            # 初始化 l_do 和 r_do
            l_do = 0
            r_do = 0

            # 遍历所有的游戏手柄
            for joystick in self.joysticks.values():
                axes = joystick.get_numaxes()
                x = joystick.get_axis(0)
                y = -joystick.get_axis(1)

                l_do, r_do = convert_handle_to_dutycycle(x, y)
                print(l_do, r_do)
                data = {"Lsend": l_do, "Rsend": r_do}
                self.data_send.emit(data)

            self.clock.tick(100)

    def stop(self):
        self.is_running = False
        pygame.quit()
