import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl, pyqtSlot, QObject, pyqtSignal
from PyQt6.QtWebChannel import QWebChannel
from PyQt6 import uic
import socket
from PyQt6.QtCore import QTimer, QThread
import json
from handle2_1 import HandleTask
from headingholdtask import headingholdtask
from pyproj import Proj, Transformer
import math

# 使用 EPSG 代码定义转换器，WGS84 (EPSG:4326) 和 UTM Zone 33N (EPSG:32633)
transformer = Transformer.from_crs("EPSG:4326", "EPSG:32633")


def WGS84_to_UTM(lat, lon):
    """
    将WGS84坐标转换为UTM坐标。

    参数:
        lon (float): 经度
        lat (float): 纬度

    返回:
        tuple: (x, y) UTM坐标
    """
    # 转换为 UTM 坐标
    x, y = transformer.transform(lat, lon)  # 注意 lat, lon 顺序
    return x, y


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
    mark_point_received = pyqtSignal(float, float)
    clear_all = pyqtSignal()

    @pyqtSlot(float, float)
    def receiveCoordinates(self, lat, lng):
        print(f"Received coordinates: Latitude {lat}, Longitude {lng}")
        self.coordinates_received.emit(lat, lng)

    @pyqtSlot(float, float)
    def receiveMarkPoint(self, lat, lng):
        print(f"Marked point: Latitude {lat}, Longitude {lng}")
        self.mark_point_received.emit(lat, lng)

    @pyqtSlot()
    def clearAll(self):
        self.clear_all.emit()


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
        self.task_obj = {}
        self.load_socket()
        self.recv = Receivedata(self.upper_socket)
        self.recv.data_received.connect(self.handle_data)
        self.timer_1 = QTimer()
        self.DisplayData()
        self.ui.CONNECT.clicked.connect(self.connect_lower)
        self.ui.CONNECT_2.clicked.connect(self.disconnect_lower)
        self.ui.MODEL_3.clicked.connect(self.model_choose)
        self.ui.GEAR_3.clicked.connect(self.gear_choose)

        # 记录模式开关
        self.track_mode = False

    def initUI(self):
        # 创建 QWebEngineView 实例
        self.webView = QWebEngineView()
        self.webView.setUrl(QUrl("http://127.0.0.1:5000"))

        # 创建 CoordinateReceiver 实例
        self.coord_receiver = CoordinateReceiver()
        self.coord_receiver.coordinates_received.connect(self.updateTrack)
        self.coord_receiver.mark_point_received.connect(self.updateTrack)
        self.coord_receiver.clear_all.connect(self.clearAll)

        # 创建 QWebChannel 并将其与 QWebEngineView 关联
        self.channel = QWebChannel()
        self.webView.page().setWebChannel(self.channel)
        self.channel.registerObject("pywebview", self.coord_receiver)

        # 将 QWebEngineView 添加到 map 容器中
        layout = QVBoxLayout(self.ui.map)
        layout.addWidget(self.webView)
        self.ui.map.setLayout(layout)

    def updateTrack(self, lat, lng):
        self.task_obj["latitude"] = lat
        self.task_obj["longitude"] = lng
        print(f"Handling marked point: Latitude {lat}, Longitude {lng}")

    def clearAll(self):
        self.webView.page().runJavaScript("window.pywebview.clearAll();")

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
        self.data_recv["Rsend"] = recv_msg["Rsend"]
        self.data_recv["Lsend"] = recv_msg["Lsend"]
        self.data_recv["longitude"] = recv_msg["longitude"]
        self.data_recv["latitude"] = recv_msg["latitude"]
        self.data_recv["compass"] = recv_msg["compass"]

        # 如果在轨迹记录模式下，则更新轨迹
        if self.track_mode:
            self.updateTrack(self.data_recv["latitude"], self.data_recv["longitude"])

        # 更新地图中心和当前位置
        self.webView.page().runJavaScript(
            f"window.pywebview.updateCurrentLocation({self.data_recv['latitude']}, {self.data_recv['longitude']});"
        )

    def DisplayData(self):
        self.timer_1.timeout.connect(self.on_timeout1)
        self.timer_1.start(10)

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
        if hasattr(self, "tas2") and self.tas2 and self.task_obj:
            # 获取当前位置的纬度和经度
            current_lat = self.data_recv["latitude"]
            current_lng = self.data_recv["longitude"]

            # 将标记点和当前位置转换为 UTM 坐标系
            mark_x, mark_y = WGS84_to_UTM(
                self.task_obj["latitude"], self.task_obj["longitude"]
            )
            current_x, current_y = WGS84_to_UTM(current_lat, current_lng)

            # 计算与正北方向的差角
            delta_x = mark_x - current_x
            delta_y = mark_y - current_y

            # 避免除零错误
            if delta_x == 0 and delta_y == 0:
                print("The marked point is exactly the same as the current location.")
                self.data_send = {
                    "Lsend": 7.5,
                    "Rsend": 7.5,
                }
            # 计算角度，处理边界情况
            if delta_x == 0:
                if delta_y > 0:
                    bearing = 0  # 正北
                else:
                    bearing = 180  # 正南
            elif delta_y == 0:
                if delta_x > 0:
                    bearing = 90  # 正东
                else:
                    bearing = 270  # 正西
            else:
                angle = math.atan2(delta_y, delta_x)
                bearing = (math.degrees(angle) + 360) % 360
            self.task_obj["obj"] = bearing
            self.task_obj["compass"] = angle_string_to_float(self.data_recv["compass"])
            self.tas2.update_data.emit(self.task_obj)
            self.tas2.start()

    def model_choose(self):
        if self.ui.MODEL_2.currentText() == "遥控":
            self.dov = HandleTask()
            self.dov.data_send.connect(self.task_normal)
            self.dov.start()
        elif self.ui.MODEL_2.currentText() == "航向保持":
            self.task_obj["compass"] = angle_string_to_float(self.data_recv["compass"])
            self.task_obj["obj"] = float(self.ui.compass_obj.text())
            self.task_obj["Es"] = 0
            self.tas = headingholdtask()
            self.tas.data_send.connect(self.task_normal)
            self.tas.start()
        elif self.ui.MODEL_2.currentText() == "目标跟踪":
            self.task_obj["compass"] = angle_string_to_float(self.data_recv["compass"])
            self.task_obj["obj"] = angle_string_to_float(self.data_recv["compass"])
            self.task_obj["Es"] = 0
            self.tas2 = headingholdtask()
            self.tas2.data_send.connect(self.task_normal)
            self.tas2.start()

    def gear_choose(self):
        self.gear = int(self.ui.GEAR_2.currentText())

    def task_normal(self, data):
        self.data_send["Rsend"] = data["Rsend"] * self.gear + 7.5
        self.data_send["Lsend"] = data["Lsend"] * self.gear + 7.5
        if (hasattr(self, "tas") and self.tas) or (hasattr(self, "tas2") and self.tas2):
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
