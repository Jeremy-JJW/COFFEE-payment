# 虎皮椒支付接入方案

##流程




## 目标

在当前咖啡点单系统中接入虎皮椒支付，用于替代或补充现有模拟支付流程，实现真实微信扫码收款。

当前项目已经具备支付基础流程：

```text
用户下单
    ↓
创建 pending 订单
    ↓
进入支付页
    ↓
支付成功后更新 payment_status=paid
    ↓
订单进入咖啡制作队列
```

虎皮椒适合作为第一版真实支付方案，因为它不需要直接对接微信支付官方的商户证书、APIv3 密钥和回调解密流程，接入复杂度更低。

## 虎皮椒方案概述

虎皮椒是第三方聚合支付/个人支付接口平台。项目侧通过虎皮椒接口创建支付订单，虎皮椒返回支付二维码或支付跳转地址。用户支付成功后，虎皮椒服务器回调本项目的 `notify_url`，项目验签成功后将订单标记为已支付。

### 支付网关

```text
正式环境: https://api.xunhupay.com/payment/do.html
备用环境: https://api.dpweixin.com/payment/do.html
```

建议将网关地址配置为环境变量，避免接口域名变化时需要修改代码。

## 需要准备的资料

以下信息需要从虎皮椒后台获取：

```text
虎皮椒 APPID
虎皮椒 AppSecret / 秘钥
支付网关地址
公网 HTTPS 回调地址 notify_url
支付成功跳转地址 return_url
支付失败或取消返回地址 callback_url
```

注意：虎皮椒文档中的 `appid` 是虎皮椒平台的 APPID，不是微信小程序 AppID，也不是微信公众号 AppID。

## 建议配置方式

新建本地 `.env` 保存配置，不要写死在代码中，也不要提交到 GitHub。

```env
XUNHUPAY_APPID=你的虎皮椒appid
XUNHUPAY_APPSECRET=你的虎皮椒appsecret
XUNHUPAY_GATEWAY=https://api.xunhupay.com/payment/do.html
XUNHUPAY_NOTIFY_URL=https://你的cpolar域名/payment/callback/xunhupay
XUNHUPAY_RETURN_BASE_URL=https://你的cpolar域名
XUNHUPAY_PAYMENT=wechat
XUNHUPAY_TITLE=领志科技咖啡
```

`.gitignore` 中应确保包含：

```gitignore
.env
```

## cpolar 地址使用方式

测试阶段可以使用 cpolar 提供的 HTTPS 公网地址。

示例：

```text
notify_url:
https://xxxx.cpolar.top/payment/callback/xunhupay

return_url:
https://xxxx.cpolar.top/order/success?order_id=订单号

callback_url:
https://xxxx.cpolar.top/payment/订单号
```

注意事项：

- 必须使用 HTTPS 地址。
- 本地 Flask 服务需要保持运行。
- 当前 `app.py` 使用 `host='0.0.0.0'` 和 `port=5000`，适合被 cpolar 转发。
- 如果 cpolar 临时域名变化，需要同步更新 `.env` 中的回调地址。

## 接口参数

### 发起支付请求

虎皮椒下单接口使用 POST 请求。

核心参数：

| 参数名 | 说明 | 示例 |
| --- | --- | --- |
| `version` | API 版本 | `1.1` |
| `appid` | 虎皮椒 APPID | 后台获取 |
| `trade_order_id` | 商户订单号 | `coffee_12` |
| `payment` | 支付方式 | `wechat` |
| `total_fee` | 支付金额，单位元 | `15.00` |
| `title` | 商品标题 | `领志科技咖啡` |
| `time` | 当前时间戳 | `1715149845` |
| `notify_url` | 异步回调地址 | `https://xxx/payment/callback/xunhupay` |
| `return_url` | 支付成功后浏览器跳转地址 | `https://xxx/order/success?order_id=12` |
| `callback_url` | 支付失败或取消返回地址 | `https://xxx/payment/12` |
| `nonce_str` | 随机字符串 | 每次请求都不同 |
| `hash` | 签名 | MD5 小写 |

### 签名规则

虎皮椒签名规则：

1. 去掉值为空的参数。
2. 去掉 `hash` 参数。
3. 按参数名 ASCII 码从小到大排序。
4. 拼接为 `key1=value1&key2=value2` 格式。
5. 字符串末尾直接拼接 `AppSecret`，中间没有连接符。
6. 对最终字符串做 MD5，得到 32 位小写 `hash`。

示例伪代码：

```python
def sign(params, appsecret):
    items = sorted(
        (key, value)
        for key, value in params.items()
        if key != "hash" and value not in (None, "")
    )
    raw = "&".join(f"{key}={value}" for key, value in items)
    return md5((raw + appsecret).encode("utf-8")).hexdigest()
```

## 回调处理

支付成功后，虎皮椒会向 `notify_url` 发送 POST 请求。

常见回调参数：

| 参数名 | 说明 |
| --- | --- |
| `trade_order_id` | 商户订单号 |
| `total_fee` | 支付金额 |
| `transaction_id` | 支付平台交易号 |
| `open_order_id` | 虎皮椒内部订单号 |
| `order_title` | 订单标题 |
| `status` | 订单状态，`OD` 表示已支付 |
| `appid` | 虎皮椒 APPID |
| `time` | 时间戳 |
| `nonce_str` | 随机字符串 |
| `hash` | 签名 |

项目收到回调后必须校验：

```text
hash 签名正确
status == OD
appid 等于本项目配置的 XUNHUPAY_APPID
trade_order_id 能对应到本地订单
total_fee 和本地订单金额一致
```

校验通过后，更新订单：

```python
order_db.update_payment_status(
    order_id,
    "paid",
    "xunhupay_wechat",
    transaction_id
)
```

回调接口必须返回：

```text
success
```

如果返回内容不是 `success`，虎皮椒会继续重试回调。

## 与当前项目的集成点

### 需要新增的后端接口

```text
POST /payment/xunhupay/create
```

作用：

- 根据本地订单号读取订单信息。
- 组装虎皮椒下单参数。
- 生成 `hash` 签名。
- 调用虎皮椒支付网关。
- 返回二维码地址或支付跳转地址给前端。

```text
POST /payment/callback/xunhupay
```

作用：

- 接收虎皮椒支付成功回调。
- 验证签名和订单金额。
- 将订单更新为 `payment_status='paid'`。
- 返回 `success`。

### 需要调整的前端页面

当前 `templates/payment.html` 已经有模拟支付页面。后续可以增加：

```text
微信支付按钮
虎皮椒二维码展示区域
正在等待支付提示
支付状态轮询
```

支付页仍然可以复用当前已有的轮询接口：

```text
GET /api/payment/status/<order_id>
```

当接口返回 `payment_status == "paid"` 时跳转：

```text
/order/success?order_id=<order_id>
```

## 推荐支付流程

```text
用户选择杯数
    ↓
POST /order
    ↓
创建本地 pending 订单
    ↓
跳转 /payment/<order_id>
    ↓
用户点击微信支付
    ↓
POST /payment/xunhupay/create
    ↓
服务端调用虎皮椒支付网关
    ↓
前端展示 url_qrcode 或支付链接
    ↓
用户扫码支付
    ↓
虎皮椒回调 /payment/callback/xunhupay
    ↓
服务端验签、校验金额、更新 paid
    ↓
前端轮询发现 paid
    ↓
跳转支付成功页
    ↓
咖啡制作系统处理已支付订单
```

## 与微信支付官方直连对比

| 对比项 | 虎皮椒支付 | 微信支付官方直连 |
| --- | --- | --- |
| 资质要求 | 通常支持个人接入，无需营业执照，具体以平台规则为准 | 通常需要微信支付商户号，涉及商户资质 |
| 接入复杂度 | 较低，主要是 `appid`、`appsecret`、签名和回调 | 较高，需要 APIv3、证书、签名、验签、回调解密 |
| 所需密钥 | 虎皮椒 APPID 和 AppSecret | 商户号、AppID、APIv3 密钥、商户证书私钥、证书序列号 |
| 回调处理 | MD5 签名校验，返回 `success` | 微信支付签名验签、AES-GCM 解密、平台证书处理 |
| 二维码获取 | 虎皮椒返回二维码地址或支付跳转链接 | Native 支付返回 `code_url`，通常需要自己生成二维码 |
| 资金链路 | 经过虎皮椒平台服务 | 直连微信支付官方商户体系 |
| 可控性 | 依赖虎皮椒平台接口和规则 | 可控性更强，官方能力完整 |
| 合规和稳定性 | 需自行确认平台资质、费率、风控、到账规则 | 官方直连更适合正式商业化长期使用 |
| 适合阶段 | 快速验证真实支付、个人项目、小规模测试 | 正式生产、企业经营、长期稳定收款 |

## 风险和注意事项

1. **必须验签**
   - 不能收到回调就直接修改订单状态。
   - 必须校验 `hash`、`status`、`appid`、订单号和金额。

2. **金额必须校验**
   - 回调金额必须和本地订单金额一致。
   - 金额比较时建议统一格式，例如都转换为分再比较。

3. **回调必须幂等**
   - 虎皮椒可能重复回调。
   - 如果订单已经是 `paid`，再次收到同一交易号回调时应直接返回 `success`。

4. **密钥不能提交 GitHub**
   - `.env` 不提交。
   - `AppSecret` 不写死在代码中。

5. **确认平台规则**
   - 正式使用前确认虎皮椒费率、到账时间、退款规则、风控限制和适用场景。

## 结论

虎皮椒支付可以接入当前咖啡点单系统，并且比微信支付官方直连更适合作为第一版真实支付验证方案。

推荐策略：

```text
短期：保留模拟支付，同时接入虎皮椒微信支付，快速跑通真实扫码支付。
长期：如果项目进入正式商业化运营，再评估迁移到微信支付官方直连。
```
