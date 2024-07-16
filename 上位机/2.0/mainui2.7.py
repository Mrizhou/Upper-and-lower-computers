import sys
import socket
import json
import time
import logging
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl, pyqtSlot, QObject, pyqtSignal, QTimer, QThread
from PyQt6.QtWebChannel import QWebChannel
from PyQt6 import uic

from handle2_2 import HandleTask
from headingholdtask2_4 import headingholdtask


def angle_string_to_float(angle_string):
    """将角度字符串转换为浮点数。"""
    sign = 1
    if angle_string[0] in "+-":
        if angle_string[0] == "-":
            sign = -1
        angle_string = angle_string[1:]

    integer_part, decimal_part = map(int, angle_string[:-1].split("."))
    angle_float = sign * (integer_part + decimal_part / (10 ** len(str(decimal_part))))
    return angle_float


class CoordinateReceiver(QObject):
    """接收和处理坐标信号的类。"""

    coordinates_received = pyqtSignal(float, float)
    mark_point_received = pyqtSignal(float, float)
    clear_all = pyqtSignal()

    @pyqtSlot(float, float)
    def receiveCoordinates(self, lat, lng):
        print(f"接收到的坐标：纬度 {lat}, 经度 {lng}")
        self.coordinates_received.emit(lat, lng)

    @pyqtSlot(float, float)
    def receiveMarkPoint(self, lat, lng):
        print(f"标记点：纬度 {lat}, 经度 {lng}")
        self.mark_point_received.emit(lat, lng)

    @pyqtSlot()
    def clearAll(self):
        self.clear_all.emit()


class MainUI:
    """应用程序的主UI类。"""

    def __init__(self):
        self.ui = uic.loadUi("上位机ui.ui")
        self.initUI()  # 初始化UI组件，包括WebEngineView
        self.ui.show()
        self.data_recv = {
            "Lsend": None,
            "Rsend": None,
            "longitude": 0.0,
            "latitude": 0.0,
            "compass": "+0.0°",
        }
        self.data_send = {
            "Lsend": 7.5,
            "Rsend": 7.5,
        }
        self.gear = 0
        self.task_obj = {
            "compass": 0.0,
            "latitude": 0.0,
            "longitude": 0.0,
            "mark_latitude": 0.0,
            "mark_longitude": 0.0,
            "start_longitude": 0.0,
            "start_latitude": 0.0,
            "end_longitude": 0.0,
            "end_latitude": 0.0,
        }
        self.load_socket()
        self.recv = Receivedata(self.upper_socket)
        self.recv.data_received.connect(self.handle_data)
        self.timer_1 = QTimer()
        self.DisplayData()
        self.ui.CONNECT.clicked.connect(self.connect_lower)
        self.ui.CONNECT_2.clicked.connect(self.disconnect_lower)
        self.ui.MODEL_3.clicked.connect(self.model_choose)
        self.ui.GEAR_3.clicked.connect(self.gear_choose)

        # 轨迹模式标志
        self.track_mode = False

    def initUI(self):
        """初始化UI组件。"""
        self.webView = QWebEngineView()
        self.webView.setUrl(QUrl("http://127.0.0.1:5000"))

        self.coord_receiver = CoordinateReceiver()
        self.coord_receiver.coordinates_received.connect(self.updateTrack)
        self.coord_receiver.mark_point_received.connect(self.updateTrack)
        self.coord_receiver.clear_all.connect(self.clearAll)

        self.channel = QWebChannel()
        self.webView.page().setWebChannel(self.channel)
        self.channel.registerObject("pywebview", self.coord_receiver)

        layout = QVBoxLayout(self.ui.map)
        layout.addWidget(self.webView)
        self.ui.map.setLayout(layout)

    def updateTrack(self, lat, lng):
        """更新任务点"""
        if hasattr(self, "tas2") and self.tas2:
            self.task_obj["mark_latitude"] = lat
            self.task_obj["mark_longitude"] = lng
        if hasattr(self, "tas3") and self.tas3:
            self.task_obj["start_longitude"] = self.task_obj["end_longitude"]
            self.task_obj["start_latitude"] = self.task_obj["end_latitude"]
            self.task_obj["end_longitude"] = lng
            self.task_obj["end_latitude"] = lat
            self.ui.start_longitude_2.setText(str(self.task_obj["start_longitude"]))
            self.ui.start_latitude_2.setText(str(self.task_obj["start_latitude"]))
            self.ui.end_longitude_2.setText(str(self.task_obj["end_longitude"]))
            self.ui.end_latitude_2.setText(str(self.task_obj["end_latitude"]))

    def clearAll(self):
        """清除所有标记。"""
        self.webView.page().runJavaScript("window.pywebview.clearAll();")

    def load_socket(self):
        """加载并绑定套接字。"""
        ip = ("", 1207)
        self.upper_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.upper_socket.bind(ip)

    def connect_lower(self):
        """连接下位机并开始接收数据。"""
        current_time = time.strftime("%Y%m%d_%H%M%S")
        log_filename = f"gps_data_{current_time}.log"

        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)

        logging.basicConfig(
            filename=log_filename,
            level=logging.INFO,
            format="%(asctime)s - %(message)s",
            filemode="w",
        )
        self.logger = logging.getLogger()

        self.ip_lower = self.ui.IP_2.text()
        self.port = int(self.ui.PORT_2.text())
        self.ui.CONNECT.setEnabled(False)
        self.ui.IP_2.setEnabled(False)
        self.ui.PORT_2.setEnabled(False)
        data_send = json.dumps(self.data_send)
        try:
            self.upper_socket.sendto(data_send.encode("utf-8"), (self.ip_lower, self.port))
        except Exception as e:
            print(f"连接下位机时出错：{e}")
        self.recv.start()

    def disconnect_lower(self):
        """断开与下位机的连接。"""
        self.ui.CONNECT.setEnabled(True)
        self.ui.IP_2.setEnabled(True)
        self.ui.PORT_2.setEnabled(True)
        if hasattr(self, "recv") and self.recv:
            self.recv.stop()
            self.recv.wait(2000)
            self.recv = None
            self.recv = Receivedata(self.upper_socket)

        logging.shutdown()

    def handle_data(self, data):
        """处理从下位机接收到的数据。"""
        recv_msg = json.loads(data[0].decode("utf-8"))
        self.data_recv["Rsend"] = recv_msg["Rsend"]
        self.data_recv["Lsend"] = recv_msg["Lsend"]
        self.data_recv["longitude"] = recv_msg["longitude"]
        self.data_recv["latitude"] = recv_msg["latitude"]
        self.data_recv["compass"] = recv_msg["compass"]

        if self.track_mode:
            self.updateTrack(self.data_recv["latitude"], self.data_recv["longitude"])

        self.logger.info(
            f"Latitude: {self.data_recv['latitude']:.6f}, "
            f"Longitude: {self.data_recv['longitude']:.6f}, "
            f"Lsend: {self.data_recv['Lsend']}, "
            f"Rsend: {self.data_recv['Rsend']}, "
            f"Compass: {self.data_recv['compass']}"
        )
        self.logger.handlers[0].flush()

        self.webView.page().runJavaScript(
            f"window.pywebview.updateCurrentLocation({self.data_recv['latitude']:.6f}, {self.data_recv['longitude']:.6f});"
        )

    def DisplayData(self):
        """定时显示数据。"""
        self.timer_1.timeout.connect(self.on_timeout1)
        self.timer_1.start(10)

    def model_choose(self):
        """根据用户输入选择并启动相应的模式。"""
        if hasattr(self, "tas") and self.tas:
            self.tas.terminate()
            self.tas.wait()
            self.tas = None
        if hasattr(self, "tas2") and self.tas2:
            self.tas2.terminate()
            self.tas2.wait()
            self.tas2 = None
        if hasattr(self, "tas3") and self.tas3:
            self.tas3.terminate()
            self.tas3.wait()
            self.tas3 = None

        self.task_obj["compass"] = angle_string_to_float(self.data_recv["compass"])
        self.task_obj["latitude"] = self.data_recv["latitude"]
        self.task_obj["longitude"] = self.data_recv["longitude"]

        if self.ui.MODEL_2.currentText() == "遥控":
            self.dov = HandleTask()
            self.dov.data_send.connect(self.task_normal)
            self.dov.start()
        elif self.ui.MODEL_2.currentText() == "航向保持":
            self.task_obj["obj"] = float(self.ui.compass_obj.text()) if self.ui.compass_obj.text() else 0.0
            self.task_obj["mode"] = "航向保持"
            self.tas = headingholdtask()
            self.tas.data_send.connect(self.task_normal)
            self.tas.update_data.emit(self.task_obj)
            self.tas.start()
        elif self.ui.MODEL_2.currentText() == "目标跟踪":
            self.task_obj["mode"] = "目标跟踪"
            self.tas2 = headingholdtask()
            self.tas2.data_send.connect(self.task_normal)
            self.tas2.update_data.emit(self.task_obj)
            self.tas2.start()
        elif self.ui.MODEL_2.currentText() == "路径跟踪":
            self.task_obj["start_longitude"] = (
                float(self.ui.start_longitude_2.text()) if self.ui.start_longitude_2.text() else 0.0
            )
            self.task_obj["start_latitude"] = (
                float(self.ui.start_latitude_2.text()) if self.ui.start_latitude_2.text() else 0.0
            )
            self.task_obj["end_longitude"] = (
                float(self.ui.end_longitude_2.text()) if self.ui.end_longitude_2.text() else 0.0
            )
            self.task_obj["end_latitude"] = (
                float(self.ui.end_latitude_2.text()) if self.ui.end_latitude_2.text() else 0.0
            )
            self.task_obj["mode"] = "路径跟踪"
            self.tas3 = headingholdtask()
            self.tas3.data_send.connect(self.task_normal)
            self.tas3.update_data.emit(self.task_obj)
            self.tas3.start()

    def on_timeout1(self):
        """定时更新显示并发送数据。"""
        self.ui.Lsend_2.setText(str(self.data_recv["Lsend"]))
        self.ui.Rsend_2.setText(str(self.data_recv["Rsend"]))
        self.ui.longitude_2.setText(f"{self.data_recv['longitude']:.6f}")
        self.ui.latitude_2.setText(f"{self.data_recv['latitude']:.6f}")
        self.ui.compass_2.setText(str(self.data_recv["compass"]))
        data_send = json.dumps(self.data_send)
        if hasattr(self, "upper_socket") and not self.ui.CONNECT.isEnabled():
            try:
                self.upper_socket.sendto(data_send.encode("utf-8"), (self.ip_lower, self.port))
            except Exception as e:
                print(f"发送数据时出错：{e}")

        if hasattr(self, "tas") and self.tas:
            self.task_obj["compass"] = angle_string_to_float(self.data_recv["compass"])
            self.task_obj["latitude"] = self.data_recv["latitude"]
            self.task_obj["longitude"] = self.data_recv["longitude"]
            self.tas.update_data.emit(self.task_obj)
            self.tas.start()

        if hasattr(self, "tas2") and self.tas2 and self.task_obj:
            self.task_obj["compass"] = angle_string_to_float(self.data_recv["compass"])
            self.task_obj["latitude"] = self.data_recv["latitude"]
            self.task_obj["longitude"] = self.data_recv["longitude"]
            self.tas2.update_data.emit(self.task_obj)
            self.tas2.start()

        if hasattr(self, "tas3") and self.tas3 and self.task_obj:
            self.task_obj["compass"] = angle_string_to_float(self.data_recv["compass"])
            self.task_obj["latitude"] = self.data_recv["latitude"]
            self.task_obj["longitude"] = self.data_recv["longitude"]
            self.tas3.update_data.emit(self.task_obj)
            self.tas3.start()

    def gear_choose(self):
        """根据用户选择选择档位。"""
        self.gear = int(self.ui.GEAR_2.currentText())

    def task_normal(self, data):
        """处理正常任务数据。"""
        self.data_send["Rsend"] = data["Rsend"] * self.gear + 7.5
        self.data_send["Lsend"] = data["Lsend"] * self.gear + 7.5

    def __del__(self):
        """析构函数以释放资源。"""
        try:
            if self.recv:
                self.recv.stop()
                self.recv.wait(2000)
            if hasattr(self, "upper_socket") and self.upper_socket:
                self.upper_socket.close()
        except Exception as e:
            print(f"析构函数中出错：{e}")
        finally:
            logging.shutdown()


class Receivedata(QThread):
    """从下位机接收数据的类。"""

    data_received = pyqtSignal(object)

    def __init__(self, up_socket):
        super().__init__()
        self.up_socket = up_socket
        self.is_running = True
        self.recv_data = None

    def run(self):
        """运行数据接收循环。"""
        self.startReceiveData()

    def startReceiveData(self):
        """开始接收数据。"""
        while self.is_running:
            try:
                self.recv_data = self.up_socket.recvfrom(1024)
                self.data_received.emit(self.recv_data)
            except ConnectionResetError:
                self.is_running = False
                break
            except OSError as e:
                print(f"Receivedata中出错：{e}")

    def stop(self):
        """停止接收数据。"""
        self.is_running = False


if __name__ == "__main__":
    app = QApplication(sys.argv)
    mainWin = MainUI()
    try:
        sys.exit(app.exec())
    finally:
        logging.shutdown()
