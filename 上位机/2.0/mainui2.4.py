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
import logging
import time
from pyproj import Geod


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
        current_time = time.strftime("%Y%m%d_%H%M%S")
        log_filename = f"gps_data_{current_time}.log"

        # 移除所有现有的日志处理器
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)

        # 重新配置日志记录器
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

        # 关闭日志记录
        logging.shutdown()

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

        # 保存GPS数据到日志，包含Lsend、Rsend和compass信息
        self.logger.info(
            f"Latitude: {self.data_recv['latitude']:.6f}, "
            f"Longitude: {self.data_recv['longitude']:.6f}, "
            f"Lsend: {self.data_recv['Lsend']}, "
            f"Rsend: {self.data_recv['Rsend']}, "
            f"Compass: {self.data_recv['compass']}"
        )
        self.logger.handlers[0].flush()  # 确保日志内容被刷新到文件

        # 更新地图中心和当前位置
        self.webView.page().runJavaScript(
            f"window.pywebview.updateCurrentLocation({self.data_recv['latitude']}, {self.data_recv['longitude']});"
        )

    def DisplayData(self):
        self.timer_1.timeout.connect(self.on_timeout1)
        self.timer_1.start(10)

    def model_choose(self):
        # 停止当前任务
        if hasattr(self, "tas") and self.tas:
            self.tas.terminate()
            self.tas.wait()
            self.tas = None
        if hasattr(self, "tas2") and self.tas2:
            self.tas2.terminate()
            self.tas2.wait()
            self.tas2 = None

        # 初始化 task_obj，确保所有必要的键都存在
        self.task_obj = {
            "compass": angle_string_to_float(self.data_recv["compass"]),
            "obj": 0,
            "Es": 0,
            "latitude": self.data_recv["latitude"],  # 添加默认值
            "longitude": self.data_recv["longitude"],  # 添加默认值
        }

        # 模式选择
        if self.ui.MODEL_2.currentText() == "遥控":
            self.dov = HandleTask()
            self.dov.data_send.connect(self.task_normal)
            self.dov.start()
        elif self.ui.MODEL_2.currentText() == "航向保持":
            self.task_obj["obj"] = (
                float(self.ui.compass_obj.text()) if self.ui.compass_obj.text() else 0
            )
            self.tas = headingholdtask()
            self.tas.data_send.connect(self.task_normal)
            self.tas.start()
        elif self.ui.MODEL_2.currentText() == "目标跟踪":
            self.task_obj["obj"] = angle_string_to_float(self.data_recv["compass"])
            self.tas2 = headingholdtask()
            self.tas2.data_send.connect(self.task_normal)
            self.tas2.start()

    def on_timeout1(self):
        self.ui.Lsend_2.setText(str(self.data_recv["Lsend"]))
        self.ui.Rsend_2.setText(str(self.data_recv["Rsend"]))
        self.ui.longitude_2.setText(f"{self.data_recv['longitude']:.6f}")
        self.ui.latitude_2.setText(f"{self.data_recv['latitude']:.6f}")
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

            mark_lat = self.task_obj["latitude"]
            mark_lng = self.task_obj["longitude"]

            geod = Geod(ellps="WGS84")

            distance, bearing = geod.inv(current_lng, current_lat, mark_lng, mark_lat)
            if bearing < 0:
                bearing += 360

            self.task_obj["obj"] = bearing
            self.task_obj["compass"] = angle_string_to_float(self.data_recv["compass"])
            self.tas2.update_data.emit(self.task_obj)
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
        finally:
            logging.shutdown()  # 确保在程序关闭时刷新并关闭日志文件


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
    try:
        sys.exit(app.exec())
    finally:
        logging.shutdown()  # 确保在程序关闭时刷新并关闭日志文件
