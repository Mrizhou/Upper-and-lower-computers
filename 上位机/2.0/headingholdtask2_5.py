from PyQt6.QtCore import QThread, pyqtSignal
from pyproj import Geod
import math


from PyQt6.QtCore import QThread, pyqtSignal
from pyproj import Geod
import math


class headingholdtask(QThread):
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
            "mode": "航向保持",
            "path_points": [],  # 增加路径点列表
        }
        self.update_data.connect(self.on_update_data)
        self.data = {"Rsend": 0, "Lsend": 0}
        self.previous_E = 0
        self.geod = Geod(ellps="WGS84")
        self.stop_distance = 2
        self.slowdown_distance = 5
        self.current_path_index = 0  # 当前路径点索引

    def run(self):
        if self.current_data["mode"] == "目标跟踪":
            self.track_target()
        elif self.current_data["mode"] == "航向保持":
            self.hold_heading()
        elif self.current_data["mode"] == "路径跟踪":
            self.track_track()

    def track_target(self):
        # 计算期望航向角
        _, obj, distance = self.geod.inv(
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
                    0.1,
                    (distance - self.stop_distance) / (self.slowdown_distance - self.stop_distance),
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

    def track_track(self):
        if self.current_path_index >= len(self.current_data["path_points"]) - 1:
            # 如果路径点已经到达最后一个，停止运动
            self.data["Rsend"] = 0
            self.data["Lsend"] = 0
            self.data_send.emit(self.data)
            return

        # 获取当前路径段的起点和终点
        start_point = self.current_data["path_points"][self.current_path_index]
        end_point = self.current_data["path_points"][self.current_path_index + 1]

        az12, _, _ = self.geod.inv(
            start_point[0],
            start_point[1],
            end_point[0],
            end_point[1],
        )

        az1t, _, dist1t = self.geod.inv(
            start_point[0],
            start_point[1],
            self.current_data["longitude"],
            self.current_data["latitude"],
        )

        angle_diff_rad = math.radians(az1t - az12)
        distance_to_line = math.sin(angle_diff_rad) * dist1t

        beta = math.atan(-distance_to_line / 3.2)
        obj = az12 + math.degrees(beta)
        obj = obj % 360
        if obj < 0:
            obj += 360

        ship = ShipSimulation(
            obj,
            self.current_data["compass"],
            self.previous_E,
        )

        ship_control_data = ship.heading_control()

        if dist1t < self.stop_distance:
            # 如果到达当前路径点，切换到下一个路径点
            self.current_path_index += 1
        else:
            if dist1t < self.slowdown_distance:
                scale_factor = max(
                    0.1,
                    (dist1t - self.stop_distance) / (self.slowdown_distance - self.stop_distance),
                )  # 距离越小，速度越慢，最小为0.1倍速
            else:
                scale_factor = 1  # 正常速度
            self.data["Rsend"], self.data["Lsend"] = [round((x - 1) * scale_factor, 1) for x in ship_control_data[:2]]
            self.data["current_path_index"] = self.current_path_index

        self.previous_E = ship.E  # 更新上一时刻的E
        self.data_send.emit(self.data)

    def on_update_data(self, new_data):
        self.current_data["compass"] = new_data["compass"]
        self.current_data["latitude"] = new_data["latitude"]
        self.current_data["longitude"] = new_data["longitude"]
        self.current_data["mode"] = new_data.get("mode", "航向保持")
        if self.current_data["mode"] == "航向保持":
            self.current_data["obj"] = new_data["obj"]
        elif self.current_data["mode"] == "目标跟踪":
            self.current_data["mark_latitude"] = new_data["mark_latitude"]
            self.current_data["mark_longitude"] = new_data["mark_longitude"]
        elif self.current_data["mode"] == "路径跟踪":
            self.current_data["path_points"] = new_data["path_points"]


class ShipSimulation:
    def __init__(self, obj, compass, Es):
        self.Es = Es
        self.E = 0
        self.obj = obj
        self.compass = compass
        self.Kp = 0.5
        self.Kd = 0
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
