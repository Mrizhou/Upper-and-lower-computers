from PyQt6.QtCore import QThread, pyqtSignal


class headingholdtask(QThread):
    """
    航向保持

    """

    data_send = pyqtSignal(dict)
    update_data = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.current_data = {"compass": 0, "obj": 0, "Es": 0}
        self.update_data.connect(self.on_update_data)
        self.data = {"Rsend": 0, "Lsend": 0}

    def run(self):
        ship = ShipSimulation(
            self.current_data["obj"],
            self.current_data["compass"],
            self.current_data["Es"],
        )
        ship_control_data = ship.heading_control()
        self.data["Rsend"], self.data["Lsend"] = [
            round(x - 1, 1) for x in ship_control_data[:2]
        ]

        self.data["Es"] = self.current_data["Es"]
        self.data_send.emit(self.data)

    def on_update_data(self, new_data):
        self.current_data["compass"] = new_data["compass"]
        self.current_data["obj"] = new_data["obj"]
        self.current_data["Es"] = new_data["Es"]


class ShipSimulation:
    def __init__(self, obj, compass, Es):
        self.Es = Es
        self.E = 0
        self.obj = obj
        self.compass = compass
        self.Kp = 0.7
        self.Kd = 0.5
        self.zengliang = 0
        self.Lpwm = 0
        self.Rpwm = 0

    def heading_control(self):
        self.obj = (self.obj + 180) % 360
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
