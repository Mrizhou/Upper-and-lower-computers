from PyQt6.QtCore import QThread, pyqtSignal
from pyproj import Geod
import math


class shipcontrol(QThread):
    data_send = pyqtSignal(dict)  # 用于发送控制数据的信号
    update_data = pyqtSignal(dict)  # 用于接收更新数据信号

    def __init__(self):
        super().__init__()
        # 初始化当前数据，包括船的位置、目标位置、模式等
        self.default_value = 7.4  # 初始化默认值
        self.update_data.connect(self.on_update_data)  # 连接更新数据信号
        self.data = self.initialize_data()  # 初始化控制信号数据
        self.previous_E = 0  # 前一时刻的误差，用于微分控制
        self.geod = Geod(ellps="WGS84")  # 使用WGS84椎球体计算地理距离
        self.stop_distance = 2  # 停止距离
        self.slowdown_distance = 5  # 减速距离
        self.mode_function = self.handle_none_mode  # 初始化模式处理函数

    def initialize_data(self):
        # 初始化控制信号数据
        return {
            "compass": 0,
            "latitude": 0.0,
            "longitude": 0.0,
            "mark_latitude": 0.0,
            "mark_longitude": 0.0,
            "mark_compass": 0.0,
            "mode": None,
            "path_points": [],
            "track_num": 0,
            "Rsend": self.default_value,
            "Lsend": self.default_value,
        }

    def run(self):
        # 直接调用已设置的模式处理函数
        self.mode_function()

    def track_target(self):
        # 计算当前船的位置到目标位置的航向角和距离
        obj, _, distance = self.calculate_geod(
            self.data["longitude"],
            self.data["latitude"],
            self.data["mark_longitude"],
            self.data["mark_latitude"],
        )
        if obj < 0:
            obj += 360

        # 如果距离小于停止距离，停止所有动作
        if distance < self.stop_distance:
            self.data = self.initialize_data()  # 初始化控制信号数据
            self.send_control_signals(self.default_value, self.default_value)
        else:
            # 使用船的模拟类计算控制信号
            ship = ShipSimulation(
                obj,
                self.data["compass"],
                self.previous_E,
            )
            ship_control_data = ship.heading_control()
            # 根据距离调整速度，越接近目标速度越小
            scale_factor = self.calculate_scale_factor(distance)
            rsend, lsend = [
                round((x - 0.5) * scale_factor * self.data.get("gear", 1), 1) + self.default_value
                for x in ship_control_data[:2]
            ]
            self.previous_E = ship.E  # 更新前一时刻的误差
            self.send_control_signals(rsend, lsend)

    def hold_heading(self):
        # 使用船的模拟类保持航向
        ship = ShipSimulation(
            self.data["mark_compass"],
            self.data["compass"],
            self.previous_E,
        )
        ship_control_data = ship.heading_control()
        rsend = round((ship_control_data[0] - 0.5) * self.data.get("gear", 1), 1) + self.default_value
        lsend = round((ship_control_data[1] - 0.5) * self.data.get("gear", 1), 1) + self.default_value
        self.previous_E = ship.E  # 更新前一时刻的误差
        self.send_control_signals(rsend, lsend)

    def track_path(self):
        # 如果当前路径点索引已达路径终点，停止运动
        if self.data["track_num"] + 1 >= len(self.data["path_points"]):
            self.data = self.initialize_data()  # 初始化控制信号数据
            self.send_control_signals(self.default_value, self.default_value)
            return

        if self.data["track_num"] == 0 and len(self.data["path_points"]) == 1:
            self.data["mark_longitude"] = self.data["path_points"][0][0]
            self.data["mark_latitude"] = self.data["path_points"][0][1]
            self.track_target()
            return

        # 获取当前路径段的起点和终点
        start_point = self.data["path_points"][self.data["track_num"]]
        end_point = self.data["path_points"][self.data["track_num"] + 1]

        # 计算起点到终点的航向角
        az12, _, _ = self.calculate_geod(start_point[0], start_point[1], end_point[0], end_point[1])

        # 计算起点到当前船的位置的航向角和距离
        az1t, _, dist1t = self.calculate_geod(
            start_point[0], start_point[1], self.data["longitude"], self.data["latitude"]
        )

        # 计算终点到当前船的位置的距离
        _, _, dist2t = self.calculate_geod(end_point[0], end_point[1], self.data["longitude"], self.data["latitude"])

        # 计算当前船到路径的垂直距离
        angle_diff_rad = math.radians(az1t - az12)
        distance_to_line = math.sin(angle_diff_rad) * dist1t

        # 计算应调整的航向角
        beta = math.atan(-distance_to_line / 3.2)
        obj = az12 + math.degrees(beta)
        obj = obj % 360
        if obj < 0:
            obj += 360

        # 使用船的模拟类计算控制信号
        ship = ShipSimulation(
            obj,
            self.data["compass"],
            self.previous_E,
        )

        ship_control_data = ship.heading_control()

        # 如果到达终点，切换到下一个路径点
        if dist2t < self.stop_distance:
            self.data["track_num"] += 1
            rsend = 7.4
            lsend = 7.4
        else:
            # 根据距离调整速度，越接近目标速度越小
            scale_factor = self.calculate_scale_factor(dist2t)
            rsend = round((ship_control_data[0] - 0.5) * self.data["gear"] * scale_factor, 1) + self.default_value
            lsend = round((ship_control_data[1] - 0.5) * self.data["gear"] * scale_factor, 1) + self.default_value
            self.data["track_num"] = self.data["track_num"]

        self.previous_E = ship.E  # 更新前一时刻的误差
        self.send_control_signals(rsend, lsend)

    def manual_input(self):
        # 直接使用输入的数据作为控制信号
        self.send_control_signals(self.data["Rsend"], self.data["Lsend"])

    def remote_control(self):
        # 直接使用遥控的数据作为控制信号
        self.send_control_signals(self.data["Rsend"], self.data["Lsend"])

    def handle_none_mode(self):
        # 处理 mode 为 None 的情况，例如停止所有动作
        self.send_control_signals(self.default_value, self.default_value)

    def calculate_geod(self, start_lon, start_lat, end_lon, end_lat):
        # 计算两个地理坐标之间的航向角和距离
        return self.geod.inv(start_lon, start_lat, end_lon, end_lat)

    def calculate_scale_factor(self, distance):
        # 根据距离计算减速因子，越接近目标速度越小
        if distance < self.stop_distance:
            return 0
        elif distance < self.slowdown_distance:
            return max(0.1, (distance - self.stop_distance) / (self.slowdown_distance - self.stop_distance))
        return 1

    def send_control_signals(self, rsend, lsend):
        # 更新控制信号并发送
        self.update_control_signals(rsend, lsend)
        self.data_send.emit(self.data)

    def update_control_signals(self, rsend, lsend):
        # 更新控制信号
        self.data["Rsend"] = rsend
        self.data["Lsend"] = lsend

    def on_update_data(self, new_data):
        # 更新当前数据并设置模式处理函数
        self.previous_E = 0
        self.data = self.initialize_data()
        self.data.update(new_data)
        self.mode_function = {
            "目标跟踪": self.track_target,
            "航向保持": self.hold_heading,
            "路径跟踪": self.track_path,
            "输入": self.manual_input,
            "遥控": self.remote_control,
            None: self.handle_none_mode,
        }.get(self.data["mode"], self.handle_none_mode)


class ShipSimulation:
    def __init__(self, obj, compass, Es):
        self.Es = Es  # 前一时刻的误差
        self.E = 0  # 当前的误差
        self.obj = obj  # 目标航向角
        self.compass = compass  # 当前航向角
        self.Kp = 0.05  # 比例系数
        self.Kd = 0.01  # 微分系数
        self.zengliang = 0  # 增量控制量
        self.Lpwm = 0  # 左艇PWM信号
        self.Rpwm = 0  # 右艇PWM信号

    def heading_control(self):
        # 计算误差，并确保误差在 -180 到 180 度之间
        self.E = self.compass - self.obj
        if self.E > 180:
            self.E -= 360
        elif self.E < -180:
            self.E += 360

        # 计算增量控制量
        self.zengliang = self.Kp * self.E + self.Kd * (self.E - self.Es)
        self.Es = self.E

        # 计算左右艇的PWM信号
        self.Lpwm = self.zengliang / 2
        self.Rpwm = -self.zengliang / 2

        # 保证PWM信号在 -0.5 到 0.5 之间，并处理小于一定值的死区
        self.Lpwm = self.constrain_pwm(self.Lpwm)
        self.Rpwm = self.constrain_pwm(self.Rpwm)

        return self.Rpwm, self.Lpwm, self.Es

    def constrain_pwm(self, pwm_value):
        # 限制PWM信号的范围，并处理死区
        if pwm_value > 0.5:
            return 0.5
        elif pwm_value < -0.5:
            return -0.5
        elif 0.02 < abs(pwm_value) < 0.1:
            return 0.1 if pwm_value > 0 else -0.1
        return pwm_value
