from PyQt6.QtWidgets import QApplication
import sys
from PyQt6 import uic
import socket
import serial.tools.list_ports
from PyQt6.QtCore import QTimer, QThread, pyqtSignal
import pynmea2
import json
import time


class Main_ui:
    """
    主窗口初始化

    """

    def __init__(self):
        self.ui = uic.loadUi("下位机ui.ui")
        self.ui.show()
        self.load_com()
        self.data = {
            "Lsend": 7.5,
            "Rsend": 7.5,
            "longitude": 0,
            "latitude": 0,
            "compass": 0,
        }
        self.load_socket()
        self.recv = Receivedata(self.lower_socket)
        self.recv.data_received.connect(self.handle_data)
        self.ser_1 = None
        self.ser_2 = None
        self.ser_3 = None
        self.timer_1 = QTimer()
        self.timer_2 = QTimer()
        self.timer_3 = QTimer()
        self.timer_4 = QTimer()
        self.timer_5 = QTimer()
        self.DisplayDuty()
        self.ui.checkBox_1.clicked.connect(self.connect_com1)
        self.ui.checkBox_2.clicked.connect(self.connect_com2)
        self.ui.checkBox_3.clicked.connect(self.connect_com3)
        self.ui.checkBox_4.clicked.connect(self.connect_com4)
        self.ui.checkBox_5.clicked.connect(self.connect_upper)

    # 加载com口
    def load_com(self):
        ports_list = list(serial.tools.list_ports.comports())
        for i in range(len(ports_list)):
            comport = list(ports_list[i])
            comport_number = comport[0]
            self.ui.comboBox_1.addItem(comport_number)
            self.ui.comboBox_2.addItem(comport_number)
            self.ui.comboBox_3.addItem(comport_number)
            self.ui.comboBox_4.addItem(comport_number)
            self.ui.comboBox_1.setCurrentIndex(-1)
            self.ui.comboBox_2.setCurrentIndex(-1)
            self.ui.comboBox_3.setCurrentIndex(-1)
            self.ui.comboBox_4.setCurrentIndex(-1)

    def load_socket(self):
        self.ip_lower = socket.gethostbyname(socket.gethostname())
        self.ip = (self.ip_lower, 1207)
        self.lower_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.lower_socket.bind(self.ip)

    def connect_upper(self):
        if self.ui.checkBox_5.isChecked():
            try:
                self.recv.start()
            except OSError as e:
                print(f"绑定套接字时发生错误：{e}")
        else:
            if hasattr(self, "recv") and self.recv:
                self.recv.stop()
                self.recv.wait(2000)  # 等待接收线程结束，最多等待2秒
                self.recv = None  # 置为None，表示已经停止
            self.recv = Receivedata(self.lower_socket)

    def handle_data(self, data):
        recv_msg = json.loads(data[0].decode("utf-8"))
        self.data["Rsend"] = recv_msg["Rsend"]
        self.data["Lsend"] = recv_msg["Lsend"]
        address_upper = data[1]
        self.ip_upper = address_upper[0]
        self.port = address_upper[1]

    def connect_com1(self):
        self.timer_1.stop()
        if self.ui.checkBox_1.isChecked():
            self.timer_1.timeout.connect(self.on_timeout1)
            com_1 = self.ui.comboBox_1.currentText()
            try:
                self.ser_1 = serial.Serial(
                    port=com_1,
                    baudrate=9600,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=0.5,
                )
                self.timer_1.start(10)
            except serial.SerialException as e:
                print(f"Failed to connect to serial port: {str(e)}")
        else:
            try:
                self.ser_1.close()
            except:
                pass

    def on_timeout1(self):
        try:
            l_do = "D0" + str(self.ui.Lsend_2.text())
            l_do = l_do.encode("utf-8")
            self.ser_1.write(l_do)
        except Exception as e:
            print(e)

    def connect_com2(self):
        self.timer_2.stop()
        if self.ui.checkBox_2.isChecked():
            self.timer_2.timeout.connect(self.on_timeout2)
            com_2 = self.ui.comboBox_2.currentText()
            try:
                self.ser_2 = serial.Serial(
                    port=com_2,
                    baudrate=9600,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=0.5,
                )
                self.timer_2.start(10)
            except serial.SerialException as e:
                print(f"Failed to connect to serial port: {str(e)}")
        else:
            try:
                self.ser_2.close()
            except Exception as e:
                pass

    def on_timeout2(self):
        try:
            r_do = "D0" + str(self.ui.Rsend_2.text())
            r_do = r_do.encode("utf-8")
            self.ser_2.write(r_do)
        except Exception as e:
            print(e)

    # 经纬度显示
    def connect_com3(self):
        self.timer_3.stop()
        if self.ui.checkBox_3.isChecked():
            self.timer_3.timeout.connect(self.on_timeout3)
            com_3 = self.ui.comboBox_3.currentText()
            try:
                self.ser_3 = serial.Serial(
                    port=com_3,
                    baudrate=9600,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=0.5,
                )
                self.timer_3.start(10)
            except serial.SerialException as e:
                print(f"Failed to connect to serial port: {str(e)}")

        else:
            try:
                self.ser_3.close()
            except:
                pass

    def on_timeout3(self):
        try:
            data = self.ser_3.read_all().decode("utf-8")
            if data:
                msg = pynmea2.parse(data)
                self.ui.latitude_2.setText(str(msg.latitude))
                self.ui.longitude_2.setText(str(msg.longitude))
                self.data["latitude"] = msg.latitude
                self.data["longitude"] = msg.longitude
        except:
            pass

    # 罗盘显示
    def connect_com4(self):
        self.timer_4.stop()
        if self.ui.checkBox_4.isChecked():
            self.timer_4.timeout.connect(self.on_timeout4)
            com_4 = self.ui.comboBox_4.currentText()
            try:
                self.ser_4 = serial.Serial(
                    port=com_4,
                    baudrate=9600,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=0.5,
                )
                self.timer_4.start(10)
            except serial.SerialException as e:
                print(f"Failed to connect to serial port: {str(e)}")

        else:
            try:
                self.ser_4.close()
            except:
                pass

    def on_timeout4(self):
        try:
            data = self.ser_4.read_all().hex()
            if data:
                msg1 = data[8:14]
                if len(msg1) == 6:
                    if msg1[0] == "1":
                        sign = "-"
                    else:
                        sign = "+"
                integer_part = int(msg1[1:4])
                decimal_part = int(msg1[4:6])
                compass_value = f"{sign}{integer_part}.{decimal_part:02d}°"
                self.ui.compass_2.setText(compass_value)
                self.data["compass"] = compass_value
        except:
            pass

    # 显示左右占空比
    def DisplayDuty(self):
        self.timer_5.timeout.connect(self.on_timeout5)
        self.timer_5.start(10)

    def on_timeout5(self):
        print(self.data)
        self.ui.Lsend_2.setText("7.5")
        self.ui.Rsend_2.setText("7.5")
        try:
            self.ui.Lsend_2.setText(str(self.data["Lsend"]))
            self.ui.Rsend_2.setText(str(self.data["Rsend"]))
            if self.recv and self.recv.recv_data:
                send_data = json.dumps(self.data)
                print(self.data)
                self.lower_socket.sendto(
                    send_data.encode("utf-8"), (self.ip_upper, self.port)
                )

        except Exception as e:
            print(f"Error in on_timeout5: {e}")

    # 在析构函数中释放资源
    def __del__(self):
        try:
            if self.recv:
                self.recv.stop()
                self.recv.wait(2000)
            if hasattr(self, "lower_socket") and self.lower_socket:
                self.lower_socket.close()
        except Exception as e:
            print(f"Error in destructor: {e}")


class Receivedata(QThread):
    """
    接受上位机信息

    """

    data_received = pyqtSignal(object)

    def __init__(self, lower_socket):
        super().__init__()
        self.lower_socket = lower_socket
        self.is_running = True
        self.recv_data = None

    def run(self):
        self.startReceiveData()

    def startReceiveData(self):
        while self.is_running and not self.lower_socket._closed:
            try:
                self.recv_data = self.lower_socket.recvfrom(1024)
                self.data_received.emit(self.recv_data)  # 触发信号
            except ConnectionResetError as reason:
                self.is_running = False
                break
            except OSError as e:
                print(e)

    def stop(self):
        self.is_running = False


if __name__ == "__main__":
    app = QApplication(sys.argv)
    mainWin = Main_ui()
    sys.exit(app.exec())
