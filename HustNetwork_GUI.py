#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import sys
import time
import math
import subprocess
import base64

import win32crypt
import requests
from PySide6 import QtCore, QtWidgets, QtGui
import configparser
import rc_icon


DEFAULT_CONFIG = {
    'network': {
        'username': '',
        'password': '',
        'ping_interval': '15',
        'ping_dns1': '202.114.0.242',
        'ping_dns2': '223.5.5.5',
    },
    'normal': {
        'silent_start': 'False',
        'auto_start': 'False',
    },
}


def set_windows_app_id():
    if sys.platform.lower() != 'win32':
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            'HustNetwork.GUI'
        )
    except Exception:
        pass


def encrypt_password(password):
    """使用 Windows DPAPI 加密密码"""
    if not password:
        return ''
    try:
        encrypted = win32crypt.CryptProtectData(password.encode('utf-8'), None, None, None, None, 0)
        return base64.b64encode(encrypted).decode('utf-8')
    except Exception:
        return password


def decrypt_password(encrypted_password):
    """使用 Windows DPAPI 解密密码"""
    if not encrypted_password:
        return ''
    try:
        decoded = base64.b64decode(encrypted_password)
        decrypted = win32crypt.CryptUnprotectData(decoded, None, None, None, 0)
        return decrypted[1].decode('utf-8')
    except Exception:
        return encrypted_password


def get_autostart_path():
    """获取开机自启快捷方式路径"""
    startup_path = os.path.join(
        os.environ['APPDATA'],
        'Microsoft',
        'Windows',
        'Start Menu',
        'Programs',
        'Startup'
    )
    if is_packaged():
        return os.path.join(startup_path, 'HustNetwork_GUI.lnk')
    return os.path.join(startup_path, 'HustNetwork_GUI_DEV.lnk')


def get_desktop_shortcut_path():
    desktop_path = os.path.join(os.environ['USERPROFILE'], 'Desktop')
    if is_packaged():
        return os.path.join(desktop_path, 'HustNetwork_GUI.lnk')
    return os.path.join(desktop_path, 'HustNetwork_GUI_DEV.lnk')


def get_other_autostart_path():
    """获取另一种运行模式的开机自启快捷方式路径"""
    startup_path = os.path.join(
        os.environ['APPDATA'],
        'Microsoft',
        'Windows',
        'Start Menu',
        'Programs',
        'Startup'
    )
    if is_packaged():
        return os.path.join(startup_path, 'HustNetwork_GUI_DEV.lnk')
    return os.path.join(startup_path, 'HustNetwork_GUI.lnk')


def is_packaged():
    return (
        getattr(sys, 'frozen', False)
        or "__compiled__" in globals()
        or os.path.splitext(sys.argv[0])[1].lower() == '.exe'
    )


def get_executable_path():
    if os.path.splitext(sys.argv[0])[1].lower() == '.exe':
        return os.path.abspath(sys.argv[0])
    return sys.executable


def create_shortcut(shortcut_path):
    import win32com.client
    shell = win32com.client.Dispatch('WScript.Shell')
    shortcut = shell.CreateShortCut(shortcut_path)

    if is_packaged():
        target = get_executable_path()
        args = ''
        working_dir = os.path.dirname(target)
    else:
        target = sys.executable
        args = f'"{os.path.abspath(__file__)}"'
        working_dir = os.path.dirname(os.path.abspath(__file__))

    shortcut.Targetpath = target
    shortcut.Arguments = args
    shortcut.WorkingDirectory = working_dir
    shortcut.IconLocation = target
    shortcut.save()


def set_autostart(enable):
    """设置开机自启"""
    shortcut_path = get_autostart_path()
    
    if enable:
        # 创建快捷方式到启动文件夹
        try:
            other_shortcut_path = get_other_autostart_path()
            if os.path.exists(other_shortcut_path):
                os.remove(other_shortcut_path)

            create_shortcut(shortcut_path)
            return True
        except Exception as e:
            print(f"创建开机自启失败: {e}")
            return False
    else:
        # 删除启动文件夹中的快捷方式
        try:
            if os.path.exists(shortcut_path):
                os.remove(shortcut_path)
            other_shortcut_path = get_other_autostart_path()
            if os.path.exists(other_shortcut_path):
                os.remove(other_shortcut_path)
            return True
        except Exception as e:
            print(f"删除开机自启失败: {e}")
            return False


def is_autostart_enabled():
    """检查是否已设置开机自启"""
    return os.path.exists(get_autostart_path())


def create_desktop_shortcut():
    try:
        create_shortcut(get_desktop_shortcut_path())
        return True
    except Exception as e:
        print(f"创建桌面快捷方式失败: {e}")
        return False


class HustNetwork(QtCore.QThread):
    status_signal = QtCore.Signal(str)

    def __init__(self, username='', password='', ping_interval=15, ping_dns1='202.114.0.242', ping_dns2='223.5.5.5', config=None):
        super().__init__()
        if config is None:
            self._username = username
            self._password = password
            self._ping_interval = ping_interval
            self._ping_dns1 = ping_dns1
            self._ping_dns2 = ping_dns2
        else:
            self._username = config.get('network', 'username')
            self._password = config.get('network', 'password')
            self._ping_interval = config.getint('network', 'ping_interval')
            self._ping_dns1 = config.get('network', 'ping_dns1')
            self._ping_dns2 = config.get('network', 'ping_dns2')
        self._auth_url = None
        self._referer = None
        self._origin = None
        # 认证过程中不要走系统代理
        self._proxies = {
            'http': None,
            'https': None,
        }
        self._encrypted_password = None

    def _ping(self, host):
        # 利用 ping 判断网络状态
        if sys.platform.lower() == "win32":
            cmd = f"ping -n 2 -w 1000 {host}"
            creation_flags = subprocess.CREATE_NO_WINDOW
        else:
            cmd = f"ping -c 2 -W 1 {host}"
            creation_flags = 0
        args = cmd.split(' ')
        th = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creation_flags)
        return (th.wait() == 0)

    def _check_status(self):
        # 默认情况依次 ping 校园网 DNS 和 阿里云 DNS
        return self._ping(self._ping_dns1) or self._ping(self._ping_dns2)

    def _get_auth_url(self):
        # 通过 http 的网站进行跳转
        test_url = "http://1.1.1.1"
        response = requests.get(test_url, proxies=self._proxies)
        response.encoding = 'utf8'

        # 获取跳转链接
        href = re.findall(r"href='(.+)'", response.text)
        self._referer = href[0]
        self._origin = self._referer.split("/eportal/")[0]
        self._auth_url = self._origin + "/eportal/InterFace.do?method=login"

    def _password_encrypt(self):
        page_info_url = self._origin + "/eportal/InterFace.do?method=pageInfo"
        data = {
            "queryString": self._referer
        }
        response = requests.post(
            page_info_url, data=data, proxies=self._proxies)
        response.encoding = 'utf8'
        result = response.json()

        self._publicKey_exponent = result["publicKeyExponent"]
        self._publicKey_modulus = result["publicKeyModulus"]
        return result["passwordEncrypt"]

    # 加密的模拟来源于
    # 1. https://blog.csdn.net/Kreeda/article/details/117965385
    # 2. https://www.cnblogs.com/himax/p/python_rsa_no_padding.html
    def _get_encrypted_password(self):
        if self._encrypted_password is None:
            # 加上通用的 mac string
            self._encrypted_password = self._password + ">111111111"
            e = int(self._publicKey_exponent, 16)
            m = int(self._publicKey_modulus, 16)
            # 16进制转10进制
            t = self._encrypted_password.encode('utf-8')
            # 字符串逆向并转换为bytes
            input_nr = int.from_bytes(t, byteorder='big')
            # 将字节转化成int型数字，如果没有标明进制，看做ascii码值
            crypt_nr = pow(input_nr, e, m)
            # 计算x的y次方，如果z在存在，则再对结果进行取模，其结果等效于pow(x,y) %z
            length = math.ceil(m.bit_length() / 8)
            # 取模数的比特长度(二进制长度)，除以8将比特转为字节
            crypt_data = crypt_nr.to_bytes(length, byteorder='big')
            # 将密文转换为bytes存储(8字节)，返回hex(16字节)
            self._encrypted_password = crypt_data.hex()
        return self._encrypted_password

    def _reconnection(self):
        if self._auth_url is None:
            self._get_auth_url()

        # 组成 post 数据
        data = {
            "userId": self._username,
            "password": self._password,
            "service": "",
            "queryString": self._referer.split("jsp?")[1],
            "operatorPwd": "",
            "operatorUserId": "",
            "validcode": "",
            "passwordEncrypt": ""
        }
        if self._password_encrypt():
            data["password"] = self._get_encrypted_password()
            data["passwordEncrypt"] = "true"

        # 校园网认证
        headers = {
            "Host": self._origin.split("://")[1],
            "Origin": self._origin,
            "Referer": self._referer,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.51 Safari/537.36"
        }
        response = requests.post(
            self._auth_url, data=data, headers=headers, proxies=self._proxies)

        # 打印响应状态
        response.encoding = response.apparent_encoding
        result = response.json()
        if result["result"] == 'success':
            self.status_signal.emit("认证成功！")
        else:
            self.status_signal.emit(result["message"])

    def run(self):
        while (True):
            try:
                ping_status = self._check_status()
            except Exception:
                self.status_signal.emit("网络异常！请检查网线接口连接情况")
                time.sleep(5)
                continue
            if not ping_status:
                try:
                    self._reconnection()
                except Exception:
                    self.status_signal.emit("连接失败！")
            else:
                self.status_signal.emit("已认证！")
            time.sleep(self._ping_interval)


class HustNetworkGUI(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.hustNetwork = None
        self.tray_msg = None
        self.config_path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), 'config.ini')

        self.setWindowTitle("华科校园网认证服务")
        self.setWindowIcon(QtGui.QIcon(":/icon/network.png"))
        self.setWindowFlags(QtCore.Qt.WindowType.WindowMinimizeButtonHint |
                            QtCore.Qt.WindowType.WindowCloseButtonHint)

        self.layout = QtWidgets.QFormLayout(self)

        self.username = QtWidgets.QLineEdit()
        self.layout.addRow("校园网账号", self.username)

        self.password = QtWidgets.QLineEdit()
        self.password.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        self.layout.addRow("校园网密码", self.password)

        self.ping_interval = QtWidgets.QLineEdit("15")
        self.layout.addRow("断线重连间隔(s)", self.ping_interval)

        self.ping_dns1 = QtWidgets.QLineEdit("202.114.0.242")
        self.layout.addRow("ping 主机1", self.ping_dns1)
        self.ping_dns2 = QtWidgets.QLineEdit("223.5.5.5")
        self.layout.addRow("ping 主机2", self.ping_dns2)

        self.status = QtWidgets.QLabel("未运行")
        self.layout.addRow("当前状态", self.status)

        self.save_config = QtWidgets.QCheckBox("保存配置")
        self.save_config.setChecked(True)
        self.silent_start = QtWidgets.QCheckBox("静默启动")
        self.silent_start.setChecked(False)
        self.auto_start = QtWidgets.QCheckBox("开机自启")
        self.auto_start.setChecked(is_autostart_enabled())
        self.desktop_shortcut_button = QtWidgets.QPushButton("创建快捷方式")
        self.button = QtWidgets.QPushButton("开启服务")
        self.layout.addRow(self.save_config, self.silent_start)
        self.layout.addRow(self.auto_start, self.desktop_shortcut_button)
        self.layout.addRow(self.button)

        if QtWidgets.QSystemTrayIcon.isSystemTrayAvailable():
            self.create_tray_icon()
            self.tray_icon.show()

        self.button.clicked.connect(self.daemon_toggle)
        self.auto_start.stateChanged.connect(self._on_auto_start_changed)
        self.desktop_shortcut_button.clicked.connect(self._on_create_desktop_shortcut)

        self.config = configparser.ConfigParser()
        self.config.read_dict(DEFAULT_CONFIG)
        if os.path.exists(self.config_path):
            self.config.read(self.config_path)  # 读取配置文件
            self.username.setText(self.config.get('network', 'username', fallback=''))
            encrypted_pwd = self.config.get('network', 'password', fallback='')
            self.password.setText(decrypt_password(encrypted_pwd))
            self.ping_interval.setText(
                self.config.get('network', 'ping_interval', fallback='15'))
            self.ping_dns1.setText(self.config.get('network', 'ping_dns1', fallback='202.114.0.242'))
            self.ping_dns2.setText(self.config.get('network', 'ping_dns2', fallback='223.5.5.5'))
            self.silent_start.setChecked(
                self.config.getboolean('normal', 'silent_start', fallback=False))
            self.auto_start.setChecked(
                self.config.getboolean('normal', 'auto_start', fallback=False))
        else:
            self.save_to_confg_file()

    def tray_icon_activated(self, reason: QtWidgets.QSystemTrayIcon.ActivationReason):
        # 单击、双击均显示主窗口
        if reason == QtWidgets.QSystemTrayIcon.ActivationReason.DoubleClick:
            self.showNormal()
        elif reason == QtWidgets.QSystemTrayIcon.ActivationReason.Trigger:
            self.showNormal()

    def create_tray_icon(self):
        self.show_action = QtGui.QAction("显示", self)
        self.show_action.triggered.connect(self.showNormal)

        self.quit_action = QtGui.QAction("退出", self)
        self.quit_action.triggered.connect(qApp.quit)

        self.tray_icon_menu = QtWidgets.QMenu(self)
        self.tray_icon_menu.addAction(self.show_action)
        self.tray_icon_menu.addSeparator()
        self.tray_icon_menu.addAction(self.quit_action)

        self.tray_icon = QtWidgets.QSystemTrayIcon(
            QtGui.QIcon(":/icon/network.png"), self)
        self.tray_icon.setContextMenu(self.tray_icon_menu)
        self.tray_icon.setToolTip("华科校园网认证服务")

        self.tray_icon.activated.connect(self.tray_icon_activated)

    def closeEvent(self, event):
        # 服务运行后关闭时隐藏
        if not event.spontaneous() or not self.isVisible():
            return
        if self.hustNetwork and QtWidgets.QSystemTrayIcon.isSystemTrayAvailable() and self.tray_icon.isVisible():
            self.hide()
            self.tray_info("隐藏至系统托盘")
            event.ignore()

    def changeEvent(self, event):
        # 服务运行后最小化时隐藏
        if self.hustNetwork and self.windowState() == QtCore.Qt.WindowState.WindowMinimized:
            self.hide()
            self.tray_info("隐藏至系统托盘")
        QtWidgets.QWidget.changeEvent(self, event)

    @QtCore.Slot()
    def set_status(self, string: str):
        self.status.setText(string)

    @QtCore.Slot()
    def tray_info(self, string: str):
        if self.tray_msg != string:
            self.tray_msg = string
            self.tray_icon.showMessage("华科校园网认证服务", string)

    def save_to_confg_file(self):
        if self.save_config.isChecked():
            self.config['network'] = {
                'username': self.username.text(),
                'password': encrypt_password(self.password.text()),
                'ping_interval': self.ping_interval.text(),
                'ping_dns1': self.ping_dns1.text(),
                'ping_dns2': self.ping_dns2.text()}
            self.config['normal'] = {
                'silent_start': str(self.silent_start.isChecked()),
                'auto_start': str(self.auto_start.isChecked())}
            with open(self.config_path, 'w') as f:
                self.config.write(f)

    def start_auth_daemon(self):
        if self.save_config.isChecked():
            self.hustNetwork = HustNetwork(config=self.config)
        else:
            self.hustNetwork = HustNetwork(
                self.username.text(), self.password.text(), int(self.ping_interval.text()),
                self.ping_dns1.text(), self.ping_dns2.text())
        self.hustNetwork.status_signal.connect(self.set_status)
        self.hustNetwork.status_signal.connect(self.tray_info)
        self.hustNetwork.start()

    @QtCore.Slot()
    def _on_auto_start_changed(self, state):
        enable = state == QtCore.Qt.CheckState.Checked.value
        set_autostart(enable)
        self.save_to_confg_file()

    @QtCore.Slot()
    def _on_create_desktop_shortcut(self):
        if create_desktop_shortcut():
            self.tray_info("已创建桌面快捷方式")
        else:
            QtWidgets.QMessageBox.warning(self, "华科校园网认证服务", "创建桌面快捷方式失败")

    @QtCore.Slot()
    def daemon_toggle(self):
        if self.hustNetwork is None:
            self.save_to_confg_file()
            # 处理开机自启设置
            set_autostart(self.auto_start.isChecked())
            self.set_status("认证中...")
            self.start_auth_daemon()
            self.button.setText("停止服务")
        else:
            self.hustNetwork.terminate()
            self.hustNetwork.wait()
            del self.hustNetwork
            self.hustNetwork = None
            self.set_status("未运行")
            self.button.setText("开启服务")


if __name__ == "__main__":
    import ctypes
    set_windows_app_id()
    app = QtWidgets.QApplication(sys.argv)
    app.setWindowIcon(QtGui.QIcon(":/icon/network.png"))
    
    mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "HustNetwork_GUI_SingleInstance")
    if ctypes.windll.kernel32.GetLastError() == 183:
        QtWidgets.QMessageBox.warning(None, "华科校园网认证服务", "程序已在运行中！")
        sys.exit(0)

    if not QtWidgets.QSystemTrayIcon.isSystemTrayAvailable():
        QtWidgets.QMessageBox.critical(
            None, "华科校园网认证服务", "该系统上不支持隐藏至系统托盘\n如需断线重连功能，认证完成后请勿关闭本程序")

    widget = HustNetworkGUI()
    widget.resize(250, 200)
    if widget.silent_start.isChecked():
        widget.hide()
        widget.daemon_toggle()
    else:
        widget.show()

    sys.exit(app.exec())
