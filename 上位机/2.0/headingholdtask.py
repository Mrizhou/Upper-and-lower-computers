from PyQt6.QtCore import QThread, pyqtSignal
import logging

logging.basicConfig(level=logging.INFO)


class headingholdtask(QThread):
    """
    航向保持任务类
    """

    data_send = pyqtSignal(dict)
    update_data = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.current_data = {"compass": 0, "obj": 0, "Es": 0}
        self.is_running = True

    def run(self):
        """
        运行航向保持任务
        """
        while self.is_running:
            self.update_data.connect(self.update_task_obj)

    def update_task_obj(self, task_obj):
        """
        更新任务对象
        """
        self.current_data = task_obj
        self.run_task()

    def run_task(self):
        """
        执行航向保持控制，并发送数据信号
        """
        Kp = 0.5
        Es = self.current_data["Es"]
        obj = self.current_data["obj"]
        compass = self.current_data["compass"]
        E = compass - obj
        Es += E

        Lsend = Kp * E
        Rsend = -Kp * E
        self.data_send.emit({"Lsend": Lsend, "Rsend": Rsend, "Es": Es})

        logging.info("Task data: Lsend=%s, Rsend=%s, Es=%s", Lsend, Rsend, Es)

    def stop(self):
        """
        停止任务
        """
        self.is_running = False
