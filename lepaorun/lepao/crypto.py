# -*- coding: utf-8 -*-
# --- license notice ---
# License: MIT (see LICENSE)
# --- end license notice ---
"""lepao.crypto —— 乐跑协议核心算法（AES-128-CBC + SignMD5）

算法来源: 小程序 wxapkg 反编译（乐跑/逆向分析.md），2026-09-07 安卓真机抓包逐字节验证。
"""
import base64
import hashlib
import random

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

AES_KEY = b"Wet2C8d34f62ndi3"
AES_IV = b"K6iv85jBD8jgf32D"
SIGN_KEY = "rDJiNB9j7vD2"


def encrypt_data(plaintext: str) -> str:
    """AES-128-CBC + PKCS7 → base64"""
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    ct = cipher.encrypt(pad(plaintext.encode("utf-8"), 16))
    return base64.b64encode(ct).decode()


def decrypt_data(data_b64: str) -> str:
    """base64 → AES-128-CBC 解密 → UTF-8 明文"""
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    pt = unpad(cipher.decrypt(base64.b64decode(data_b64)), 16)
    return pt.decode("utf-8")


def sign_md5(params: dict, secret: str = SIGN_KEY) -> str:
    """SignMD5: 按键升序拼接 k+v, 末尾拼 secret, 整体 MD5"""
    concat = "".join(f"{k}{params[k]}" for k in sorted(params.keys()))
    return hashlib.md5((concat + secret).encode("utf-8")).hexdigest()


def random6() -> str:
    """6 位随机数字（与小程序 random6 一致）"""
    return str(int(1e6 * random.random()) + 1e6)[1:7]
