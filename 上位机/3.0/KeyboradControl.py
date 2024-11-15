import pygame
from PyQt6.QtCore import QThread, pyqtSignal


class KeyboardControlTask(QThread):
    data_send = pyqtSignal(dict)  # 用于发送控制数据的信号
    update_data = pyqtSignal(float)  # 用于接收更新数据信号

    def __init__(self):
        super().__init__()
        pygame.init()
        pygame.display.set_mode((400, 300))
        self.update_data.connect(self.on_update_data)  # 连接更新数据信号
        self.is_running = True
        self.l_do = 0.0
        self.r_do = 0.0
        self.speed_step = 0.1
        self.max_speed = -2.4
        self.min_speed = 2.4

    def run(self):
        clock = pygame.time.Clock()
        while self.is_running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.stop()
                    return

            # 获取按键状态
            keys = pygame.key.get_pressed()
            self.handle_key_events(keys)

            # 发射信号传递数据
            self.data_send.emit({"Lsend": self.l_do, "Rsend": self.r_do})

            # 控制帧率
            clock.tick(10)

    def on_update_data(self, new_data):
        self.speed_step = round(0.1 * new_data, 1)

    def handle_key_events(self, keys):
        # 前进和后退控制
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            self.l_do = max(self.l_do - self.speed_step, self.max_speed)
            self.r_do = max(self.r_do - self.speed_step, self.max_speed)
        elif keys[pygame.K_s] or keys[pygame.K_DOWN]:
            self.l_do = min(self.l_do + self.speed_step, self.min_speed)
            self.r_do = min(self.r_do + self.speed_step, self.min_speed)

        # 左转和右转控制
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            self.l_do = min(self.l_do + self.speed_step, self.min_speed)
            self.r_do = max(self.r_do - self.speed_step, self.max_speed)
        elif keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            self.l_do = max(self.l_do - self.speed_step, self.max_speed)
            self.r_do = min(self.r_do + self.speed_step, self.min_speed)

        if keys[pygame.K_p]:
            self.l_do = 0
            self.r_do = 0

    def stop(self):
        self.is_running = False
        pygame.quit()
