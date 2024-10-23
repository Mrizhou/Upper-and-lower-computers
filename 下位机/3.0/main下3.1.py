from PyQt6.QtWidgets import QApplication
import sys
from PyQt6 import uic
import socket
import serial.tools.list_ports
from PyQt6.QtCore import QTimer, QThread, pyqtSignal
import pynmea2
import json
from shipcontrol31 import shipcontrol
import logging
from datetime import datetime


class LowerMachine:
    def __init__(self):
        self.setup_ui()  # 设置UI
        self.initialize_data()  # 初始化数据
        self.lower_socket = None
        self.load_socket()  # 加载网络套接字
        self.initialize_serial_ports()  # 初始化串口
        self.heading_task = shipcontrol()  # 初始化航向保持任务对象
        self.heading_task.data_send.connect(self.on_data_send)  # 连接数据发送信号
        self.initialize_timer()  # 初始化定时器
        self.connect_signals()  # 连接UI信号

    def setup_ui(self):
        # 加载UI文件并显示
        self.ui = uic.loadUi("下位机ui.ui")
        self.ui.show()

    def initialize_data(self):
        # 初始化无人船数据
        self.data = {
            "Lsend": 7.4,
            "Rsend": 7.4,
            "longitude": 0,
            "latitude": 0,
            "compass": 0,
            "mode": None,
            "track_num": 0,
        }
        # 初始化任务对象
        self.task_obj = {
            "Lsend": 7.4,
            "Rsend": 7.4,
            "compass": 0.0,
            "latitude": 0.0,
            "longitude": 0.0,
            "mark_latitude": 0.0,
            "mark_longitude": 0.0,
            "mark_compass": 0.0,
            "mode": None,
            "track_num": 0,
            "path_points": [],
            "gear": 1,
        }
        self.speed = 0
        self.recv = None  # 初始化接收线程对象

    def load_socket(self):
        try:
            # 获取本地主机IP并创建UDP套接字
            self.ip_lower = socket.gethostbyname(socket.gethostname())
            self.ip = (self.ip_lower, 1207)
            self.lower_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.lower_socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)
            self.lower_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
            self.lower_socket.bind(self.ip)
            # 创建接收数据线程并连接数据接收信号
            self.recv = Receivedata(self.lower_socket)
            self.recv.data_received.connect(self.handle_data)
        except socket.error as e:
            print(f"网络接口初始化错误: {e}")

    def initialize_serial_ports(self):
        # 初始化四个串口对象
        self.ser = [None] * 4

    def initialize_timer(self):
        # 初始化定时器，每30ms执行一次任务
        self.timer = QTimer()
        self.timer.timeout.connect(self.on_timeout)
        self.timer.start(30)

    def connect_signals(self):
        # 连接UI中的信号和槽函数
        self.ui.load_com.clicked.connect(self.load_com)
        self.ui.checkBox_1.clicked.connect(lambda: self.connect_com(0, self.ui.comboBox_1, self.ui.checkBox_1))
        self.ui.checkBox_2.clicked.connect(lambda: self.connect_com(1, self.ui.comboBox_2, self.ui.checkBox_2))
        self.ui.checkBox_3.clicked.connect(lambda: self.connect_com(2, self.ui.comboBox_3, self.ui.checkBox_3))
        self.ui.checkBox_4.clicked.connect(lambda: self.connect_com(3, self.ui.comboBox_4, self.ui.checkBox_4))
        self.ui.checkBox_5.clicked.connect(self.connect_upper)

    def load_com(self):
        try:
            # 获取各个串口选择框当前选中的索引
            current_indices = [
                self.ui.comboBox_1.currentIndex(),
                self.ui.comboBox_2.currentIndex(),
                self.ui.comboBox_3.currentIndex(),
                self.ui.comboBox_4.currentIndex(),
            ]

            # 获取可用的串口列表
            ports_list = list(serial.tools.list_ports.comports())

            # 获取所有串口选择框
            combo_boxes = [
                self.ui.comboBox_1,
                self.ui.comboBox_2,
                self.ui.comboBox_3,
                self.ui.comboBox_4,
            ]

            # 清空并重新填充串口选择框
            for combo_box in combo_boxes:
                combo_box.clear()
                for port in ports_list:
                    combo_box.addItem(port.device)

            # 恢复各个选择框的当前选中项
            for combo_box, index in zip(combo_boxes, current_indices):
                combo_box.setCurrentIndex(index)
        except Exception as e:
            print(f"串口加载错误: {e}")

    def connect_upper(self):
        # 生成带时间戳的日志文件名
        current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"device_data_log_{current_time}.txt"
        # 配置日志，增加毫秒精度
        logging.basicConfig(
            filename=log_filename,
            level=logging.INFO,
            format="%(asctime)s.%(msecs)03d - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        self.log_file = log_filename  # 保存日志文件名
        if self.ui.checkBox_5.isChecked():
            try:
                # 启动接收数据线程
                if self.recv:
                    self.recv.start()
            except OSError as e:
                print(f"绑定套接子时发生错误：{e}")
        else:
            try:
                # 停止接收数据线程
                if self.recv:
                    self.recv.stop()
                    self.recv.wait(2000)
                    self.recv = None
                self.recv = Receivedata(self.lower_socket)
            except Exception as e:
                print(f"连接上住机时发生错误：{e}")

    def handle_data(self, data):
        try:
            # 解析接收到的JSON数据
            recv_msg = json.loads(data[0].decode("utf-8"))
            address_upper = data[1]
            # 保存上位机的IP和端口信息
            self.ip_upper = address_upper[0]
            self.port = address_upper[1]
            # 更新任务对象
            self.task_obj.update(recv_msg)
            # 将更新后的任务对象发送给航向保持任务
            self.heading_task.update_data.emit(self.task_obj)
        except json.JSONDecodeError as e:
            print(f"数据解析错误: {e}")
        except KeyError as e:
            print(f"数据中缺少必要的键: {e}")
        except Exception as e:
            print(f"处理上住机数据时发生未知错误: {e}")

    def connect_com(self, index, combo_box, check_box):
        if check_box.isChecked():
            # 打开串口连接
            com_port = combo_box.currentText()
            try:
                self.ser[index] = serial.Serial(
                    port=com_port,
                    baudrate=9600,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=0.5,
                )
            except serial.SerialException as e:
                print(f"连接串口 {com_port} 失败: {e}")
        else:
            # 关闭串口连接
            try:
                if self.ser[index]:
                    self.ser[index].close()
                    self.ser[index] = None
            except serial.SerialException as e:
                print(f"关闭串口 {com_port} 失败: {e}")

    def on_timeout(self):
        try:
            # 定时执行的任务，包括更新UI和发送/接收数据
            self.heading_task.start()
            self.send_serial_data()
            self.read_gps_data()
            self.read_compass_data()
            self.send_socket_data()
            # 日志记录
            if self.log_file:  # 确保日志文件名已设置
                logging.info(
                    f"GPS: ({self.task_obj['latitude']:.6f}, {self.task_obj['longitude']:.6f}), "
                    f"Lsend: {self.task_obj['Lsend']:.1f}, Rsend: {self.task_obj['Rsend']:.1f}, "
                    f"Compass: {self.task_obj['compass']:.1f}, "
                    f"Mark GPS: ({self.task_obj['mark_latitude']:.6f}, {self.task_obj['mark_longitude']:.6f}), "
                    f"Mark Compass: {self.task_obj['mark_compass']:.1f}, "
                    f"Mode: {self.task_obj['mode']}, "
                    f"Track Number: {self.task_obj['track_num']}, "
                    f"Path Points: {self.task_obj['path_points']}, "
                    f"Gear: {self.task_obj['gear']},"
                    f"Speed:{self.speed}"
                )

        except Exception as e:
            print(f"执行任务时发生未知错误: {e}")

    def update_ui(self):
        # 更新UI中的Lsend和Rsend显示
        self.ui.Lsend_2.setText(f"{self.data['Lsend']:.1f}")
        self.ui.Rsend_2.setText(f"{self.data['Rsend']:.1f}")

    def send_serial_data(self):
        # 发送Lsend和Rsend到串口0和1
        try:
            if self.ser[0]:
                l_do = f"D0{self.ui.Lsend_2.text()}".encode("utf-8")
                self.ser[0].write(l_do)
            if self.ser[1]:
                r_do = f"D0{self.ui.Rsend_2.text()}".encode("utf-8")
                self.ser[1].write(r_do)
        except:
            pass

    def read_gps_data(self):
        try:
            # 从串口2读取GPS数据并解析
            if self.ser[2]:
                data = self.ser[2].read_all().decode("utf-8")
                if data:
                    msg = pynmea2.parse(data)
                    self.ui.latitude_2.setText(str(msg.latitude))
                    self.ui.longitude_2.setText(str(msg.longitude))
                    self.data["latitude"] = msg.latitude
                    self.data["longitude"] = msg.longitude
                    self.task_obj["latitude"] = msg.latitude
                    self.task_obj["longitude"] = msg.longitude
                    # 获取速度信息（单位为节）
                    speed_in_knots = msg.spd_over_grnd
                    # 将速度从节转换为米每秒，并保留6位小数
                    self.speed = round(float(speed_in_knots) * 0.514444, 6)
                    self.heading_task.update_data.emit(self.task_obj)
        except (serial.SerialException, pynmea2.ParseError) as e:
            print(f"GPS数据解析错误: {e}")

    def read_compass_data(self):
        try:
            # 从串口3读取罗盘数据并解析
            if self.ser[3]:
                data = self.ser[3].read_all().hex()
                if data:
                    msg1 = data[8:14]
                    if len(msg1) == 6:
                        sign = "-" if msg1[0] == "1" else "+"
                        integer_part = int(msg1[1:4])
                        decimal_part = int(msg1[4:6])
                        compass_value = f"{sign}{integer_part}.{decimal_part:02d}°"
                        self.ui.compass_2.setText(compass_value)
                        self.data["compass"] = compass_value
                        self.task_obj["compass"] = float(f"{integer_part}.{decimal_part:02d}")
                        self.heading_task.update_data.emit(self.task_obj)
        except (serial.SerialException, ValueError) as e:
            print(f"罗盘数据解析错误: {e}")

    def send_socket_data(self):
        # 发送数据到上位机
        if self.recv and self.recv.recv_data:
            try:
                send_data = json.dumps(self.data)
                self.lower_socket.sendto(send_data.encode("utf-8"), (self.ip_upper, self.port))
            except (socket.error, TypeError) as e:
                print(f"数据发送错误: {e}")

    def on_data_send(self, data):
        # 接收 shipcontrol 发送的数据，并更新到下位机发送的数据中
        keys_to_update = keys_to_update = [
            "Lsend",
            "Rsend",
            "longitude",
            "latitude",
            "compass",
            "mode",
            "track_num",
            "mark_latitude",
            "mark_longitude",
            "mark_compass",
            "path_points",
        ]
        for key in keys_to_update:
            if key in data:
                self.data[key] = data[key]
        # 更新UI
        self.task_obj.update(data)
        self.update_ui()

    def __del__(self):
        # 析构函数，关闭所有资源
        try:
            if self.recv:
                self.recv.stop()
                self.recv.wait(2000)
            if self.lower_socket:
                self.lower_socket.close()
        except Exception as e:
            print(f"析构函数错误: {e}")


class Receivedata(QThread):
    data_received = pyqtSignal(object)  # 定义数据接收信号

    def __init__(self, lower_socket):
        super().__init__()
        self.lower_socket = lower_socket
        self.is_running = True
        self.recv_data = None

    def run(self):
        # 启动接收数据的循环
        self.startReceiveData()

    def startReceiveData(self):
        # 接收数据的主循环
        while self.is_running and not self.lower_socket._closed:
            try:
                self.recv_data = self.lower_socket.recvfrom(1024)
                self.data_received.emit(self.recv_data)  # 发射接收到的数据
            except ConnectionResetError:
                self.is_running = False
                break
            except OSError as e:
                print(f"网络接收数据错误: {e}")

    def stop(self):
        # 停止接收数据
        self.is_running = False


if __name__ == "__main__":
    app = QApplication(sys.argv)
    try:
        mainWin = LowerMachine()
        sys.exit(app.exec())
    except Exception as e:
        print(f"主程序错误: {e}")
