from PyQt6.QtWidgets import QApplication
import sys
from PyQt6 import uic
import socket
import serial.tools.list_ports
from PyQt6.QtCore import QTimer
import pynmea2
import json
from PyQt6.QtCore import QThread


def string_to_dict(s):
    return json.loads(s)


class Main_ui:
    """
    主窗口初始化

    """

    def __init__(self):
        self.ui = uic.loadUi("下位机ui.ui")
        self.ui.show()
        self.load_com()
        self.ser_1 = None
        self.ser_2 = None
        self.ser_3 = None
        self.recv = None
        self.recv_msg = None
        self.timer_1 = QTimer()
        self.timer_2 = QTimer()
        self.timer_3 = QTimer()
        self.timer_4 = QTimer()
        self.timer_5 = QTimer()
        self.recv = Receivedata()
        self.ui.checkBox_1.clicked.connect(self.connect_com1)
        self.ui.checkBox_2.clicked.connect(self.connect_com2)
        self.ui.checkBox_3.clicked.connect(self.connect_com3)
        self.ui.checkBox_4.clicked.connect(self.connect_com4)
        self.ui.checkBox_5.clicked.connect(self.connect_com5)

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
                self.timer_1.start(100)
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
                self.timer_2.start(100)
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
                self.timer_3.start(100)
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
        except:
            pass

    # 罗盘显示
    def connect_com4(self):
        self.timer_4.stop()

    def on_timeout4(self):
        com_4 = self.ui.currentText()

    # 接收上位机信息
    def connect_com5(self):
        self.timer_5.stop()
        if self.ui.checkBox_5.isChecked():
            self.recv.is_running = True
            self.timer_5.timeout.connect(self.on_timeout5)
            self.timer_5.start(100)

    def on_timeout5(self):
        try:
            self.recv.start()
            if self.recv.recv_msg:
                self.ui.Lsend_2.setText(str(self.recv.recv_msg["Lsend"]))
                self.ui.Rsend_2.setText(str(self.recv.recv_msg["Rsend"]))
        except:
            print(2)


class Receivedata(QThread):
    """
    接收下位机信息
    """

    def __init__(self):
        super().__init__()
        self.ip_lower = None
        self.ip_upper = None
        self.get_local_ip()
        self.recv_msg = None
        self.is_running = True

    def run(self):
        self.startReceiveData()

    def get_local_ip(self):
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        self.ip_lower = (ip, 1207)
        self.lower_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.lower_socket.bind(self.ip_lower)

    def startReceiveData(self):
        while self.is_running:
            try:
                recv_data = self.lower_socket.recvfrom(1024)
                self.recv_msg = string_to_dict(recv_data[0].decode("utf-8"))
                self.ip_upper = recv_data[1]
            except ConnectionResetError as reason:
                self.is_running = False
                break


if __name__ == "__main__":
    app = QApplication(sys.argv)
    mainWin = Main_ui()
    sys.exit(app.exec())
