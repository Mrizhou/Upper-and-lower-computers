import sys
import socket
import json
import time
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QTableWidgetItem, QMessageBox
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtCore import QUrl, pyqtSlot, QObject, pyqtSignal, QTimer, QThread, QMutex, QMutexLocker
from PyQt6.QtWebChannel import QWebChannel
from PyQt6 import uic
from handle22 import HandleTask
from KeyboradControl import KeyboardControlTask


# 工具函数
def angle_string_to_float(angle_string):
    # 将角度字符串转换为浮点数
    sign = 1
    if angle_string[0] in "+-":
        if angle_string[0] == "-":
            sign = -1
        angle_string = angle_string[1:]
    integer_part, decimal_part = map(int, angle_string[:-1].split("."))
    angle_float = sign * (integer_part + decimal_part / (10 ** len(str(decimal_part))))
    return angle_float


class CoordinateReceiver(QObject):
    is_clearing = False  # 标志变量
    # 用于接收和发送坐标的信号
    coordinates_received = pyqtSignal(float, float)
    mark_point_received = pyqtSignal(float, float)
    clear_all = pyqtSignal()

    @pyqtSlot(float, float)
    def receiveCoordinates(self, lat, lng):
        # 接收坐标并发出信号
        print(f"接收到的坐标：纬度 {lat}, 经度 {lng}")
        self.coordinates_received.emit(lat, lng)

    @pyqtSlot(float, float)
    def receiveMarkPoint(self, lat, lng):
        # 接收标记点并发出信号
        print(f"标记点：纬度 {lat}, 经度 {lng}")
        self.mark_point_received.emit(lat, lng)

    @pyqtSlot()
    def clearAll(self):
        if self.is_clearing:
            return  # 如果正在清除，直接返回
        self.is_clearing = True  # 设置为正在清除

        print("清除所有标记点信号触发")
        self.clear_all.emit()

        self.is_clearing = False  # 清除完成后恢复标志


class MainUI:
    def __init__(self):
        # 加载用户界面文件
        self.ui = uic.loadUi("上位机ui.ui")
        # 初始化用户界面、变量和信号连接
        self.initUI()
        self.ui.show()
        self.initVariables()
        self.initConnections()

    def initUI(self):
        # 初始化地图视图，将其直接绑定到 map 小部件
        self.webView = QWebEngineView(self.ui.map)
        self.webView.setUrl(QUrl("http://127.0.0.1:5000"))

        # 设置 webView 的大小和位置，完全符合 map 小部件的定义
        self.webView.setGeometry(10, 0, self.ui.map.width(), self.ui.map.height())

        # 设置 WebChannel 与 JavaScript 进行交互
        self.channel = QWebChannel()
        self.coord_receiver = CoordinateReceiver()
        self.channel.registerObject("pywebview", self.coord_receiver)
        self.webView.page().setWebChannel(self.channel)

    def initVariables(self):
        # 初始化变量
        self.data_recv = {
            "Lsend": 7.4,
            "Rsend": 7.4,
            "longitude": 0,
            "latitude": 0,
            "compass": 0,
            "mode": None,
            "track_num": 0,
        }
        self.data_send = {
            "mark_latitude": 0.0,
            "mark_longitude": 0.0,
            "mark_compass": 0.0,
            "mode": None,
            "path_points": [],
            "gear": 1,
            "track_num": 0,
        }

        # 创建 UDP 套接字用于与下位机通信
        self.upper_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.upper_socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)
        self.upper_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)

        self.upper_socket.bind(("", 619))
        # 创建数据接收线程
        self.recv = Receivedata(self.upper_socket)
        # 创建定时器
        self.timer_1 = QTimer()

    def initConnections(self):
        # 初始化信号与槽的连接
        self.recv.data_received.connect(self.handle_data)
        self.timer_1.timeout.connect(self.on_timeout1)
        self.timer_1.start(100)

        self.ui.CONNECT.clicked.connect(self.connect_lower)
        self.ui.CONNECT_2.clicked.connect(self.disconnect_lower)
        self.ui.MODEL_3.clicked.connect(self.model_choose)
        self.ui.GEAR_3.clicked.connect(self.gear_choose)

        self.coord_receiver.mark_point_received.connect(self.updateTrack)
        self.coord_receiver.clear_all.connect(self.clearAll)

    def connect_lower(self):
        # 连接下位机
        self.ip_lower = self.ui.IP_2.text()
        self.port = int(self.ui.PORT_2.text())
        self.disableConnectUI()
        data_send = json.dumps(self.data_send)
        try:
            # 发送初始数据以建立连接
            self.upper_socket.sendto(data_send.encode("utf-8"), (self.ip_lower, self.port))
        except Exception as e:
            print(f"连接下位机时出错：{e}")
        # 启动接收数据线程
        self.recv.start()

    def disconnect_lower(self):
        # 断开与下位机的连接
        self.enableConnectUI()
        if hasattr(self, "recv") and self.recv:
            self.recv.stop()
            self.recv.wait(2000)
            self.recv = Receivedata(self.upper_socket)

    def disableConnectUI(self):
        # 禁用连接按钮，防止重复连接
        self.ui.CONNECT.setEnabled(False)
        self.ui.IP_2.setEnabled(False)
        self.ui.PORT_2.setEnabled(False)

    def enableConnectUI(self):
        # 启用连接按钮
        self.ui.CONNECT.setEnabled(True)
        self.ui.IP_2.setEnabled(True)
        self.ui.PORT_2.setEnabled(True)

    def handle_data(self, data):
        # 处理接收到的数据
        recv_msg = json.loads(data[0].decode("utf-8"))
        self.data_recv.update(recv_msg)
        # 在地图上更新当前位置
        self.webView.page().runJavaScript(
            f"window.pywebview.updateCurrentLocation({self.data_recv['latitude']:.6f}, {self.data_recv['longitude']:.6f});"
        )

    def updateTrack(self, lat, lng):
        # 更新轨迹表格和路径点
        current_row_count = self.ui.GPS_task.rowCount()
        self.ui.GPS_task.insertRow(current_row_count)
        self.ui.GPS_task.setItem(current_row_count, 0, QTableWidgetItem(str(lng)))
        self.ui.GPS_task.setItem(current_row_count, 1, QTableWidgetItem(str(lat)))
        # 只在标记点接收时添加到 path_points 中
        self.data_send["path_points"].append((lng, lat))

    def clearAll(self):
        # 清除所有地图上的标记
        self.webView.page().runJavaScript("window.pywebview.clearAll();")

        # 清空 GPS_task 表格
        self.ui.GPS_task.setRowCount(0)

    def on_timeout1(self):
        # 定时更新显示数据并发送数据
        self.updateDisplayData()

    def updateDisplayData(self):
        # 更新用户界面显示的数据
        self.ui.Lsend_2.setText(f"{self.data_recv['Lsend']:.1f}")
        self.ui.Rsend_2.setText(f"{self.data_recv['Rsend']:.1f}")
        self.ui.longitude_2.setText(f"{self.data_recv['longitude']:.6f}")
        self.ui.latitude_2.setText(f"{self.data_recv['latitude']:.6f}")
        self.ui.compass_2.setText(str(self.data_recv["compass"]))
        # 更新起点和终点的经纬度显示
        track_num = self.data_recv.get("track_num", 0)

        if len(self.data_send["path_points"]) > track_num + 1:
            # 更新起点
            start_lng, start_lat = self.data_send["path_points"][track_num]
            self.ui.start_longitude_2.setText(str(start_lng))
            self.ui.start_latitude_2.setText(str(start_lat))

            # 更新终点
            end_lng, end_lat = self.data_send["path_points"][track_num + 1]
            self.ui.end_longitude_2.setText(str(end_lng))
            self.ui.end_latitude_2.setText(str(end_lat))
        else:
            # 如果path_points不够，则显示空或默认值
            self.ui.start_longitude_2.setText("0")
            self.ui.start_latitude_2.setText("0")
            self.ui.end_longitude_2.setText("0")
            self.ui.end_latitude_2.setText("0")

    def model_choose(self):
        if hasattr(self, "dov") and self.dov:
            self.dov.stop()
            self.dov.terminate()
            self.dov.wait()
            self.dov = None
        if hasattr(self, "dov1") and self.dov1:
            self.dov1.stop()
            self.dov1.terminate()
            self.dov1.wait()
            self.dov1 = None
        # 从 UI 中获取 MODEL_2 的当前选定值
        selected_mode = self.ui.MODEL_2.currentText()

        # 更新 data_send 中的 mode
        self.data_send["mode"] = selected_mode

        # 更新 data_send 中的 mark_compass, mark_latitude 和 mark_longitude
        try:
            mark_compass = float(self.ui.compass_obj_2.text())
            mark_latitude = float(self.ui.end_latitude_2.text())
            mark_longitude = float(self.ui.end_longitude_2.text())
        except ValueError:
            mark_compass = 0
            mark_latitude = 0
            mark_longitude = 0

        self.data_send.update(
            {
                "mark_compass": mark_compass,
                "mark_latitude": mark_latitude,
                "mark_longitude": mark_longitude,
                # 保持 gear 不变
                "track_num": 0,
            }
        )

        if self.ui.MODEL_2.currentText() == "遥控":
            self.dov = HandleTask()
            self.dov.data_send.connect(self.task_normal)
            self.dov.start()
        elif self.ui.MODEL_2.currentText() == "键盘":
            self.dov1 = KeyboardControlTask()
            self.dov1.data_send.connect(self.task_normal)
            self.dov1.start()
        elif self.ui.MODEL_2.currentText() == "输入":
            Lsend = self.ui.Lsend_4.text()
            Rsend = self.ui.Rsend_4.text()
            if self.validate_send_values(Lsend, Rsend):
                self.data_send["Lsend"] = float(Lsend)
                self.data_send["Rsend"] = float(Rsend)
            else:
                QMessageBox.warning(self.ui, "输入不合法", "Lsend 和 Rsend 必须在 4.9 到 9.8 之间，且小数点后一位。")
                self.ui.Lsend_4.setText("7.4")
                self.ui.Rsend_4.setText("7.4")
                self.data_send["Lsend"] = 7.4
                self.data_send["Rsend"] = 7.4
        # 确认模式已更新
        print(f"模式更新为：{selected_mode}")

        data_send = json.dumps(self.data_send)
        if not self.ui.CONNECT.isEnabled():
            try:
                self.upper_socket.sendto(data_send.encode("utf-8"), (self.ip_lower, self.port))
            except Exception as e:
                print(f"发送数据时出错：{e}")
        print(self.data_send)

    def validate_send_values(self, Lsend, Rsend):
        try:
            Lsend = float(Lsend)
            Rsend = float(Rsend)
            if (
                4.9 <= Lsend <= 9.8
                and 4.9 <= Rsend <= 9.8
                and len(str(Lsend).split(".")[1]) == 1
                and len(str(Rsend).split(".")[1]) == 1
            ):
                return True
        except ValueError:
            return False
        return False

    def task_normal(self, data):
        if hasattr(self, "dov") and self.dov:
            self.data_send["Rsend"] = round(max(4.9, min(data["Rsend"] * self.data_send["gear"] + 7.4, 9.8)), 1)
            self.data_send["Lsend"] = round(max(4.9, min(data["Lsend"] * self.data_send["gear"] + 7.4, 9.8)), 1)
        if hasattr(self, "dov1") and self.dov1:
            self.data_send["Rsend"] = round(max(4.9, min(data["Rsend"] + 7.4, 9.8)), 1)
            self.data_send["Lsend"] = round(max(4.9, min(data["Lsend"] + 7.4, 9.8)), 1)
        print(self.data_send)

    def gear_choose(self):
        # 选择档位
        self.data_send["gear"] = float(self.ui.GEAR_2.currentText())
        if hasattr(self, "dov1") and self.dov1:
            self.dov1.update_data.emit(self.data_send["gear"])

    def __del__(self):
        # 析构函数，关闭接收线程和套接字
        try:
            if hasattr(self, "recv") and self.recv:
                self.recv.stop()
                self.recv.wait(2000)
            if hasattr(self, "upper_socket") and self.upper_socket:
                self.upper_socket.close()
        except Exception as e:
            print(f"析构函数中出错：{e}")


class Receivedata(QThread):
    # 数据接收线程类
    data_received = pyqtSignal(object)

    def __init__(self, up_socket):
        super().__init__()
        self.up_socket = up_socket
        self.is_running = True
        self.mutex = QMutex()

    def run(self):
        # 启动接收数据线程
        while self.is_running:
            try:
                with QMutexLocker(self.mutex):
                    recv_data = self.up_socket.recvfrom(1024)
                    self.data_received.emit(recv_data)
            except ConnectionResetError:
                self.is_running = False
                break
            except OSError as e:
                print(f"接收数据时出错：{e}")

    def stop(self):
        # 停止接收数据
        with QMutexLocker(self.mutex):
            self.is_running = False


if __name__ == "__main__":
    # 主程序入口
    app = QApplication(sys.argv)
    mainWin = MainUI()
    sys.exit(app.exec())
