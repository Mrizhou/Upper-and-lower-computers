from PyQt6.QtCore import QThread, pyqtSignal
from pyproj import Geod


class headingholdtask(QThread):
    """
    航向保持和目标跟踪
    """

    data_send = pyqtSignal(dict)
    update_data = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.current_data = {
            "compass": 0,
            "latitude": 0.0,
            "longitude": 0.0,
            "mark_latitude": 0.0,
            "mark_longitude": 0.0,
            "mode": "航向保持",  # 默认模式为航向保持
        }
        self.update_data.connect(self.on_update_data)
        self.data = {"Rsend": 0, "Lsend": 0}
        self.previous_E = 0  # 初始化 previous_E 为 0
        self.geod = Geod(ellps="WGS84")
        self.stop_distance = 0.5  # 定义停止的距离阈值，单位为米
        self.slowdown_distance = 5  # 定义减速的距离阈值，单位为米

    def run(self):
        if self.current_data["mode"] == "目标跟踪":
            self.track_target()
        elif self.current_data["mode"] == "航向保持":
            self.hold_heading()

    def track_target(self):
        # 计算期望航向角
        obj, _, distance = self.geod.inv(
            self.current_data["longitude"],
            self.current_data["latitude"],
            self.current_data["mark_longitude"],
            self.current_data["mark_latitude"],
        )
        if obj < 0:
            obj += 360

        # 检查距离是否接近目标位置
        if distance < self.stop_distance:
            self.data["Rsend"] = 0
            self.data["Lsend"] = 0
        else:
            ship = ShipSimulation(
                obj,
                self.current_data["compass"],
                self.previous_E,
            )
            ship_control_data = ship.heading_control()
            if distance < self.slowdown_distance:
                scale_factor = max(
                    0.1, (distance - self.stop_distance) / (self.slowdown_distance - self.stop_distance)
                )  # 距离越小，速度越慢，最小为0.1倍速
            else:
                scale_factor = 1  # 正常速度
            self.data["Rsend"], self.data["Lsend"] = [round((x - 1) * scale_factor, 1) for x in ship_control_data[:2]]

            # 更新Es
            self.previous_E = ship.E  # 更新上一时刻的E

        self.data_send.emit(self.data)

    def hold_heading(self):
        ship = ShipSimulation(
            self.current_data["obj"],
            self.current_data["compass"],
            self.previous_E,
        )
        ship_control_data = ship.heading_control()
        self.data["Lsend"], self.data["Rsend"] = [round(x - 1, 1) for x in ship_control_data[:2]]

        # 更新Es
        self.previous_E = ship.E  # 更新上一时刻的E

        self.data_send.emit(self.data)

    def on_update_data(self, new_data):
        self.current_data["compass"] = new_data["compass"]
        self.current_data["latitude"] = new_data["latitude"]
        self.current_data["longitude"] = new_data["longitude"]
        self.current_data["mark_latitude"] = new_data["mark_latitude"]
        self.current_data["mark_longitude"] = new_data["mark_longitude"]
        self.current_data["mode"] = new_data.get("mode", "航向保持")
        if self.current_data["mode"] == "航向保持":
            self.current_data["obj"] = new_data["obj"]


class ShipSimulation:
    def __init__(self, obj, compass, Es):
        self.Es = Es
        self.E = 0
        self.obj = obj
        self.compass = compass
        self.Kp = 0.5
        self.Kd = 0.2
        self.zengliang = 0
        self.Lpwm = 0
        self.Rpwm = 0

    def heading_control(self):
        self.E = self.compass - self.obj
        if self.E > 180:
            self.E -= 360
        elif self.E < -180:
            self.E += 360
        self.zengliang = self.Kp * self.E + self.Kd * (self.E - self.Es)
        self.Es = self.E
        self.Lpwm = self.zengliang / 2
        self.Rpwm = -self.zengliang / 2
        if self.Lpwm > 0.5:
            self.Lpwm = 0.5
        if self.Lpwm < -0.5:
            self.Lpwm = -0.5
        if self.Rpwm > 0.5:
            self.Rpwm = 0.5
        if self.Rpwm < -0.5:
            self.Rpwm = -0.5
        return self.Lpwm, self.Rpwm, self.Es
