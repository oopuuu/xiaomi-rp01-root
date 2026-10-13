#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小米路由器 root 密码计算器 (用户名 root)
适用: 小米 BE3600 Pro 网线版 (RP01) 固件 1.0.67
      —— 以及所有 mkxqimage 内含同一盐值的小米机型

【使用前提】仅用于找回【你自己拥有的设备】的 root 密码。
SN 可以直接推导出设备的 root 密码，因此不要把 SN 或算出的密码分享给他人，
也不要对不属于你的设备使用本工具。

算法来源与验证:
  1) 固件 /bin/mkxqimage 内含字符串 "d44fb0960aa0-a5e6-4a30-250f-6d2df50a"
  2) mkxqimage -I 通过 `nvram get SN` 取序列号, 输出 8 位密码
  3) 本算法与"在 qemu 中真实运行固件自带 mkxqimage -I"的结果
     对 14 组不同 SN 逐一比对, 14/14 完全一致
  4) 并在 RP01 真机上, 与路由器自身执行 `mkxqimage -I` 的输出
     逐字符一致（且该密码经 crypt 验证即为 /etc/shadow 中 root 的明文）

用法:
    python3 calc_root_pwd.py 12345/A1B2C3D4E5F6
    python3 calc_root_pwd.py --selftest
"""

from __future__ import print_function

import sys
import hashlib

# 固件 /bin/mkxqimage 中的原始盐
SALT_RAW = "d44fb0960aa0-a5e6-4a30-250f-6d2df50a"
# 实际参与哈希的是"按 '-' 分段后反转"的盐
SALT = "-".join(reversed(SALT_RAW.split("-")))   # 6d2df50a-250f-4a30-a5e6-d44fb0960aa0


def root_pwd(sn):
    """由设备序列号 SN 计算 root 密码(8位)。SN 中的 '/' 必须保留。"""
    if sys.version_info[0] < 3:
        if isinstance(sn, unicode):
            sn = sn.encode("utf-8")
        raw = str(sn) + SALT
    else:
        if isinstance(sn, str):
            raw = (sn + SALT).encode("utf-8")
        else:
            raw = sn + SALT.encode("utf-8")
    return hashlib.md5(raw).hexdigest()[:8]


# ---- 自测样本: 左侧为 SN, 右侧为在 qemu 中真实执行
#      `mkxqimage -I`(注入该 SN)得到的输出 ----
SELFTEST = {
    "":                     "8a6b71bb",
    "a":                    "09c1df40",
    "b":                    "d5b672c8",
    "c":                    "5962111a",
    "aa":                   "1b24ec19",
    "ab":                   "c29bad13",
    "ba":                   "582df6b0",
    "0":                    "fc07eefb",
    "1":                    "49c5beb1",
    "01":                   "8757a5f5",
    "10":                   "99cbd03d",
    "12345/A1B2C3D4E5F6":   "71499649",
    "12345/A1B2C3D4E5F7":   "604ba36d",
    "12346/A1B2C3D4E5F6":   "068cdd41",
}


def selftest():
    ok = 0
    for sn, expect in SELFTEST.items():
        got = root_pwd(sn)
        flag = "OK " if got == expect else "FAIL"
        if got == expect:
            ok += 1
        print("  [{0}] SN={1!r:22} 期望={2}  实得={3}".format(flag, sn, expect, got))
    print("\n  自测结果: {0}/{1}".format(ok, len(SELFTEST)))
    return 0 if ok == len(SELFTEST) else 1


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        print("提示: SN 中的 '/' 是 SN 的一部分, 不要漏掉。")
        return 2
    if args[0] in ("--selftest", "-t"):
        print("自测: 与固件 mkxqimage -I 实测输出比对")
        return selftest()

    sn = args[0].strip()
    if "/" not in sn:
        print("[!] 警告: SN '{0}' 不含 '/', 请确认是否为完整序列号。".format(sn))
        print("    小米路由器的 SN 形如 12345/A1B2C3D4E5F6。\n")
    pwd = root_pwd(sn)
    print("SN      : {0}".format(sn))
    print("用户名  : root")
    print("密码    : {0}".format(pwd))
    print("\n登录:  ssh -o HostKeyAlgorithms=+ssh-rsa -o PubkeyAcceptedAlgorithms=+ssh-rsa \\")
    print("           -o StrictHostKeyChecking=no root@192.168.31.1")
    print("       然后 root / {0}".format(pwd))
    return 0


if __name__ == "__main__":
    sys.exit(main())
