# HustNetwork

> 本仓库 fork 自 [ywang-wnlo/HustNetwork](https://github.com/ywang-wnlo/HustNetwork)。

## 本 fork 说明

本 fork 主要维护 Windows GUI 打包版本，方便在 Windows 桌面环境下作为托盘程序长期运行。

### 开发说明

本 fork 的 Windows GUI 适配、打包流程调整和部分功能改动使用 Codex + GPT-5.5 辅助完成，相关改动经过本地构建和基础运行验证。

### 主要改动

- 使用 PySide6 提供 Windows GUI 和系统托盘。
- 支持保存配置，密码使用 Windows DPAPI 加密后写入 `config.ini`。
- 支持静默启动：启动后隐藏到托盘并自动开启认证服务。
- 支持当前用户开机自启：在用户 Startup 文件夹创建快捷方式。
- 支持一键创建桌面快捷方式。
- 使用 Nuitka 打包 Windows 可执行程序，降低 PyInstaller 误报概率。

### Windows 使用

从 Release 下载 Windows 压缩包后，先完整解压，再运行：

```text
HustNetwork_GUI.exe
```

不要只复制单个 exe。程序运行需要同目录下的 DLL、PYD、`PySide6` 等依赖文件。

常用设置：

- 勾选“保存配置”：保存账号、加密后的密码和重连参数。
- 勾选“静默启动”：下次启动时不显示窗口，直接隐藏到托盘并开始认证。
- 勾选“开机自启”：当前 Windows 用户登录后自动启动程序。
- 点击“创建快捷方式”：在桌面创建当前程序的快捷方式。

### Windows 打包

推荐使用普通 venv，而不是 conda 环境打包：

```powershell
uv venv --python cpython-3.11.15 .venv
uv pip install --python .\.venv\Scripts\python.exe -r requirements.txt
```

标准 Nuitka 打包命令：

```powershell
.\.venv\Scripts\python.exe -m nuitka `
  --standalone `
  --enable-plugin=pyside6 `
  --windows-console-mode=disable `
  --windows-icon-from-ico=.\icon\network.ico `
  --output-dir=dist_nuitka `
  --output-filename=HustNetwork_GUI.exe `
  --assume-yes-for-downloads `
  HustNetwork_GUI.py
```

UPX 压缩版可以减小体积，但可能增加杀毒软件误报概率：

```powershell
.\.venv\Scripts\python.exe -m nuitka `
  --standalone `
  --enable-plugin=pyside6 `
  --enable-plugin=upx `
  --upx-binary=.\upx.exe `
  --windows-console-mode=disable `
  --windows-icon-from-ico=.\icon\network.ico `
  --output-dir=dist_nuitka_upx `
  --output-filename=HustNetwork_GUI.exe `
  --assume-yes-for-downloads `
  HustNetwork_GUI.py
```

Release 时压缩并上传整个 `HustNetwork_GUI.dist` 目录，不要只上传 exe。

## 原项目说明

已毕业，无环境进行后续适配

## 功能

有库依赖，自动认证华科校园网，并支持断线重连，还有适用于 Window 的 GUI 版本

## 使用

无需在路由器上，任何（通过通过路由器的）接入校园网的设备均可运行

```bash
python3 HustNetwork.py hust-network.conf
python3 HustNetwork_GUI.py
HustNetwork_GUI.exe
```

其中 hust-network.conf 中内容依次为校园网账号和密码

程序需保持一直运行，推荐使用 screen 或者 systemctl 配置成 service 挂在后台

## 其他相关项目推荐

- Rust 二进制文件：https://github.com/black-binary/hust-network-login
- Shell 版本：https://github.com/jyi2ya/hust-network-login-sh
