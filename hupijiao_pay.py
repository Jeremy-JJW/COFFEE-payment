# *-* coding: UTF-8 *-*

import base64
import hashlib
import hmac
import os
import time
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from urllib.parse import urlencode, unquote_plus

import requests

try:
    import qrcode
except ImportError:  # pragma: no cover - only used when dependency is missing
    qrcode = None


class HupijiaoError(Exception):
    """Raised when the Hupijiao payment request cannot be completed."""


def load_local_env(filename=".env"):
    if not os.path.exists(filename):
        return

    with open(filename, "r", encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_local_env()

_last_trade_timestamp_ms = 0


@dataclass
class HupijiaoConfig:
    appid: str
    appsecret: str
    public_base_url: str
    gateway: str = "https://api.xunhupay.com/payment/do.html"
    payment: str = "wechat"
    title: str = "领志科技咖啡"
    timeout: int = 15

    @classmethod
    def from_env(cls, public_base_url=None, require_public_base_url=True):
        appid = os.getenv("XUNHUPAY_APPID", "").strip()
        appsecret = os.getenv("XUNHUPAY_APPSECRET", "").strip()
        env_public_base_url = os.getenv("XUNHUPAY_PUBLIC_BASE_URL", "").strip().rstrip("/")
        public_base_url = (env_public_base_url or (public_base_url or "")).strip().rstrip("/")
        if not appid or not appsecret or (require_public_base_url and not public_base_url):
            raise HupijiaoError(
                "虎皮椒支付配置缺失，请设置 XUNHUPAY_APPID、"
                "XUNHUPAY_APPSECRET、XUNHUPAY_PUBLIC_BASE_URL"
            )

        return cls(
            appid=appid,
            appsecret=appsecret,
            public_base_url=public_base_url,
            gateway=os.getenv("XUNHUPAY_GATEWAY", cls.gateway).strip() or cls.gateway,
            payment=os.getenv("XUNHUPAY_PAYMENT", cls.payment).strip() or cls.payment,
            title=os.getenv("XUNHUPAY_TITLE", cls.title).strip() or cls.title,
            timeout=int(os.getenv("XUNHUPAY_TIMEOUT", str(cls.timeout))),
        )

    @property
    def notify_url(self):
        return f"{self.public_base_url}/payment/callback/xunhupay"

    def return_url(self, order_id):
        return f"{self.public_base_url}/order/success?order_id={order_id}"

    def callback_url(self, order_id):
        return f"{self.public_base_url}/payment/{order_id}"


def sign(params, appsecret):
    items = [
        (key, str(value))
        for key, value in params.items()
        if key != "hash" and value not in (None, "")
    ]
    items.sort(key=lambda item: item[0])
    raw = unquote_plus(urlencode(items))
    return hashlib.md5((raw + appsecret).encode("utf-8")).hexdigest()


def verify_sign(params, appsecret):
    received = str(params.get("hash", "")).lower()
    expected = sign(params, appsecret).lower()
    return bool(received) and hmac.compare_digest(received, expected)


def cents_to_yuan(cents):
    yuan = (Decimal(int(cents)) / Decimal("100")).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )
    return format(yuan, "f")


def yuan_to_cents(yuan):
    amount = Decimal(str(yuan)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return int(amount * 100)


def trade_order_id(order_id):
    global _last_trade_timestamp_ms
    timestamp_ms = int(time.time() * 1000)
    if timestamp_ms <= _last_trade_timestamp_ms:
        timestamp_ms = _last_trade_timestamp_ms + 1
    _last_trade_timestamp_ms = timestamp_ms
    return f"coffee_{int(order_id)}_{timestamp_ms}"


def parse_trade_order_id(value):
    raw = str(value or "")
    if raw.startswith("coffee_"):
        parts = raw.split("_")
        if len(parts) >= 2:
            raw = parts[1]
    return int(raw)


def qr_data_uri(pay_url):
    if not pay_url or qrcode is None:
        return ""

    image = qrcode.make(pay_url)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


class HupijiaoClient:
    def __init__(self, config=None, public_base_url=None):
        self.config = config or HupijiaoConfig.from_env(public_base_url=public_base_url)

    def create_payment(self, order):
        order_id = int(order["order_id"])
        payload = {
            "version": "1.1",
            "lang": "zh-cn",
            "plugins": "flask",
            "appid": self.config.appid,
            "trade_order_id": trade_order_id(order_id),
            "payment": self.config.payment,
            "is_app": "Y",
            "total_fee": cents_to_yuan(order["payment_amount"]),
            "title": f"{self.config.title} {order['cups']}杯",
            "description": "",
            "time": str(int(time.time())),
            "notify_url": self.config.notify_url,
            "return_url": self.config.return_url(order_id),
            "callback_url": self.config.callback_url(order_id),
            "nonce_str": f"{int(time.time())}{order_id}",
        }
        payload["hash"] = sign(payload, self.config.appsecret)

        try:
            response = requests.post(
                self.config.gateway,
                data=payload,
                headers={"Referer": self.config.public_base_url + "/"},
                timeout=self.config.timeout,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            raise HupijiaoError(f"虎皮椒支付请求失败: {exc}") from exc
        except ValueError as exc:
            raise HupijiaoError("虎皮椒返回内容不是有效 JSON") from exc

        errcode = str(data.get("errcode", data.get("code", "0")))
        if errcode not in ("0", "200"):
            message = data.get("errmsg") or data.get("message") or data.get("msg") or data
            raise HupijiaoError(f"虎皮椒创建支付订单失败: {message}")

        qr_image = data.get("url_qrcode") or data.get("qrcode") or data.get("qr_code") or ""
        pay_url = data.get("url") or qr_image
        if not pay_url:
            raise HupijiaoError("虎皮椒返回中没有支付二维码或支付链接")

        return {
            "raw": data,
            "pay_url": pay_url,
            "qr_image": qr_image,
            "qr_data_uri": "" if qr_image else qr_data_uri(pay_url),
        }
