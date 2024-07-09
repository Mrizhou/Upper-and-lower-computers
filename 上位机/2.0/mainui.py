import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl, pyqtSlot, QObject, pyqtSignal
from PyQt6.QtWebChannel import QWebChannel
from PyQt6 import uic
import socket
from PyQt6.QtCore import QTimer, QThread
import json
from handle import HandleTask
from headingholdtask import headingholdtask


def angle_string_to_float(angle_string):
    sign = 1
    if angle_string[0] in "+-":
        if angle_string[0] == "-":
            sign = -1
        angle_string = angle_string[1:]

    parts = angle_string[:-1].split(".")
    integer_part = int(parts[0])
    decimal_part = int(parts[1])
    angle_float = sign * (integer_part + decimal_part / (10 ** len(parts[1])))
    return angle_float


class CoordinateReceiver(QObject):
    coordinates_received = pyqtSignal(float, float)

    @pyqtSlot(float, float)
    def receiveCoordinates(self, lat, lng):
        self.coordinates_received.emit(lat, lng)


class Main_ui:
    """
    主窗口初始化
    """

    def __init__(self):
        self.ui = uic.loadUi("上位机ui.ui")
        self.initUI()  # 初始化UI组件，包括WebEngineView
        self.ui.show()
        self.data_recv = {
            "Lsend": None,
            "Rsend": None,
            "longitude": 0,
            "latitude": 0,
            "compass": "+0.0°",
        }
        self.data_send = {
            "Lsend": 7.5,
            "Rsend": 7.5,
        }
        self.gear = 0
        self.load_socket()
        self.recv = Receivedata(self.upper_socket)
        self.recv.data_received.connect(self.handle_data)
        self.timer_1 = QTimer()
        self.DisplayData()
        self.ui.CONNECT.clicked.connect(self.connect_lower)
        self.ui.CONNECT_2.clicked.connect(self.disconnect_lower)
        self.ui.MODEL_3.clicked.connect(self.model_choose)
        self.ui.GEAR_3.clicked.connect(self.gear_choose)

    def initUI(self):
        # 创建 QWebEngineView 实例
        self.webView = QWebEngineView()
        self.webView.setUrl(QUrl("http://127.0.0.1:5000"))

        # 创建 CoordinateReceiver 实例
        self.coord_receiver = CoordinateReceiver()
        self.coord_receiver.coordinates_received.connect(self.handle_coordinates)

        # 创建 QWebChannel 并将其与 QWebEngineView 关联
        self.channel = QWebChannel()
        self.webView.page().setWebChannel(self.channel)
        self.channel.registerObject("pywebview", self.coord_receiver)

        # 将 QWebEngineView 添加到 map 容器中
        layout = QVBoxLayout(self.ui.map)
        layout.addWidget(self.webView)
        self.ui.map.setLayout(layout)

    def handle_coordinates(self, lat, lng):
        print(f"Handling coordinates: Latitude {lat}, Longitude {lng}")
        # 在这里处理接收到的经纬度信息

    def load_socket(self):
        ip = ("", 1207)
        self.upper_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.upper_socket.bind(ip)

    def connect_lower(self):
        self.ip_lower = self.ui.IP_2.text()
        self.port = int(self.ui.PORT_2.text())
        self.ui.CONNECT.setEnabled(False)
        self.ui.IP_2.setEnabled(False)
        self.ui.PORT_2.setEnabled(False)
        data_send = json.dumps(self.data_send)
        try:
            self.upper_socket.sendto(
                data_send.encode("utf-8"), (self.ip_lower, self.port)
            )
        except Exception as e:
            pass
        self.recv.start()

    def disconnect_lower(self):
        self.ui.CONNECT.setEnabled(True)
        self.ui.IP_2.setEnabled(True)
        self.ui.PORT_2.setEnabled(True)
        if hasattr(self, "recv") and self.recv:
            self.recv.stop()
            self.recv.wait(2000)
            self.recv = None
            self.recv = Receivedata(self.upper_socket)

    def handle_data(self, data):
        recv_msg = json.loads(data[0].decode("utf-8"))
        print(recv_msg)
        self.data_recv["Rsend"] = recv_msg["Rsend"]
        self.data_recv["Lsend"] = recv_msg["Lsend"]
        self.data_recv["longitude"] = recv_msg["longitude"]
        self.data_recv["latitude"] = recv_msg["latitude"]
        self.data_recv["compass"] = recv_msg["compass"]

    def DisplayData(self):
        self.timer_1.timeout.connect(self.on_timeout1)
        self.timer_1.start(100)

    def on_timeout1(self):
        self.ui.Lsend_2.setText(str(self.data_recv["Lsend"]))
        self.ui.Rsend_2.setText(str(self.data_recv["Rsend"]))
        self.ui.longitude_2.setText(str(self.data_recv["longitude"]))
        self.ui.latitude_2.setText(str(self.data_recv["latitude"]))
        self.ui.compass_2.setText(str(self.data_recv["compass"]))
        data_send = json.dumps(self.data_send)
        try:
            self.upper_socket.sendto(
                data_send.encode("utf-8"), (self.ip_lower, self.port)
            )
        except Exception as e:
            pass
        if hasattr(self, "tas") and self.tas:
            self.task_obj["compass"] = angle_string_to_float(self.data_recv["compass"])
            self.tas.update_data.emit(self.task_obj)
            print(self.task_obj)
            self.tas.start()

    def model_choose(self):
        if self.ui.MODEL_2.currentText() == "遥控":
            self.dov = HandleTask()
            self.dov.data_send.connect(self.task_normal)
            self.dov.start()
        elif self.ui.MODEL_2.currentText() == "任务":
            self.task_obj = {}
            self.task_obj["compass"] = angle_string_to_float(self.data_recv["compass"])
            self.task_obj["obj"] = float(self.ui.compass_obj.text())
            self.task_obj["Es"] = 0
            self.tas = headingholdtask()
            self.tas.data_send.connect(self.task_normal)
            self.tas.start()

    def gear_choose(self):
        self.gear = int(self.ui.GEAR_2.currentText())

    def task_normal(self, data):
        self.data_send["Rsend"] = data["Rsend"] * self.gear + 7.5
        self.data_send["Lsend"] = data["Lsend"] * self.gear + 7.5
        if hasattr(self, "tas") and self.tas:
            self.task_obj["Es"] = data["Es"]

    # 在析构函数中释放资源
    def __del__(self):
        try:
            if self.recv:
                self.recv.stop()
                self.recv.wait(2000)
            if hasattr(self, "lower_socket") and self.upper_socket:
                self.upper_socket.close()
        except Exception as e:
            print(f"Error in destructor: {e}")


class Receivedata(QThread):
    """
    接受下位机信息
    """

    data_received = pyqtSignal(object)

    def __init__(self, up_socket):
        super().__init__()
        self.up_socket = up_socket
        self.is_running = True
        self.recv_data = None

    def run(self):
        self.startReceiveData()

    def startReceiveData(self):
        while self.is_running:
            try:
                self.recv_data = self.up_socket.recvfrom(1024)
                self.data_received.emit(self.recv_data)
            except ConnectionResetError:
                self.is_running = False
                break
            except OSError as e:
                print(f"Error in Receivedata: {e}")

    def stop(self):
        self.is_running = False


if __name__ == "__main__":
    app = QApplication(sys.argv)
    mainWin = Main_ui()
    sys.exit(app.exec())
