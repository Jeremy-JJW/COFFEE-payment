# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

这是一个咖啡自动制作系统的点单与支付系统，使用Python Flask开发，主要功能包括：
1. 触摸屏点单界面（前端使用HTML/CSS/JS）
2. 虎皮椒微信支付集成（支持二维码扫码支付）
3. 咖啡制作队列管理与硬件控制（通过串口和IO板卡控制咖啡机、机械臂等设备）
4. 订单数据库管理（使用CSV文件存储订单状态）

## 系统架构

### 前端与后端
- **`app.py`** - Flask主应用，包含所有HTTP路由
- **`templates/`** - HTML模板目录，包含点单、支付、成功页面
- **`static/`** - 静态资源目录（图片、CSS、JavaScript）

### 支付系统
- **`hupijiao_pay.py`** - 虎皮椒支付客户端（主要实现）
- **`hupijiao-v3-python.py`** - 虎皮椒V3版原始参考实现
- 支付流程：生成支付二维码 → 用户手机扫码 → 虎皮椒异步回调 → 更新订单状态

### 订单与数据库
- **`order_db.py`** - 订单数据库管理（CSV文件读写，支持线程安全操作）
- 订单字段：`order_id`, `cups`, `payment_amount`, `payment_status`, `payment_method`, `transaction_id`, `payment_time`

### 硬件控制
- **`mainio_IN11_monitor.py`** - 咖啡制作主控制器（多线程监控订单队列并控制硬件）
- **`coffee_machine.py`** - 咖啡机串口通信控制
- **`yanmeng_io_reader.py`** - 岩獴IO板卡控制（控制机械臂、传感器等）
- **`start_work.py`** - 独立设备开机程序

## 环境配置

1. **Python环境**：使用virtualenv（`.venv/`目录）
2. **环境变量**：支付配置通过`.env`文件设置（参考`.env.example`）
   ```
   XUNHUPAY_APPID=your_hupijiao_appid
   XUNHUPAY_APPSECRET=your_hupijiao_appsecret
   XUNHUPAY_PUBLIC_BASE_URL=https://your-public-https-domain.example
   XUNHUPAY_GATEWAY=https://api.xunhupay.com/payment/do.html
   XUNHUPAY_PAYMENT=wechat
   XUNHUPAY_TITLE=领志科技咖啡
   ENABLE_SIMULATED_PAYMENT=false
   ```
3. **硬件要求**：岩獴IO板卡、COM口连接的咖啡机

## 开发与运行命令

### 启动Web服务器（点单系统）
```bash
python app.py
```
- 访问：`http://localhost:5000` 或 `http://<局域网IP>:5000`
- 支持局域网内其他设备访问

### 启动咖啡制作系统
```bash
python mainio_IN11_monitor.py
```
- 启动后自动监控订单队列，处理已支付订单
- 需要连接岩獴IO板卡和咖啡机

### 设备开机程序（仅用于设备完全断电后）
```bash
python start_work.py
```
- 发送3秒开机信号到机械臂和咖啡机

### 启动完整系统（推荐）
同时运行上述两个服务：
1. 一个终端运行 `python app.py`
2. 另一个终端运行 `python mainio_IN11_monitor.py`

## 支付流程说明

### 正常支付流程
1. 用户访问首页 (`/`) → 选择杯数 → 点击"提交订单并支付"
2. 跳转到支付页面 (`/payment/<order_id>`)
3. 触摸屏展示虎皮椒支付二维码
4. 用户用手机微信扫描二维码并支付
5. 虎皮椒异步回调到 `/payment/callback/xunhupay`
6. 支付成功后更新订单状态为 `paid`
7. 前端通过轮询检测到支付完成后跳转到成功页面

### 模拟支付（开发测试时可用）
设置环境变量 `ENABLE_SIMULATED_PAYMENT=true` 可启用模拟支付，不调用真实虎皮椒接口。

## 订单状态流转

```
待支付 (pending) → 已支付 (paid) → 制作中 (status=0) → 已完成 (status=2)
```

- 生产程序 (`mainio_IN11_monitor.py`) 只处理 `payment_status='paid'` 且 `status=0` 的订单
- 制作过程中更新 `completed_cups` 字段跟踪进度

## 重要约定

1. **支付回调**：虎皮椒支付成功后通过 `POST /payment/callback/xunhupay` 通知系统
2. **金额单位**：内部存储使用"分"（整数），显示时除以100转换为"元"
3. **线程安全**：订单数据库操作使用 `threading.Lock()` 确保线程安全
4. **硬件连接**：咖啡制作系统需要岩獴IO板卡和串口连接的咖啡机

## 相关文件位置

- **计划文件**：存储在 `.cursor/plans/` 目录中
- **环境配置**：`.env` 文件（敏感信息不提交到Git）
- **日志文件**：`Coffee_machine2.log`（咖啡制作系统日志）
- **订单数据**：`orders.csv`（订单数据库）

## 支付集成要点

1. **虎皮椒配置**：需要注册虎皮椒商户账号，获取 `appid` 和 `appsecret`
2. **公网访问**：需要公网HTTPS域名供虎皮椒回调使用（通过 `XUNHUPAY_PUBLIC_BASE_URL` 配置）
3. **二维码展示**：支付页面显示虎皮椒生成的支付二维码，用户手机扫码支付
4. **回调验证**：支付回调需要进行签名验证、金额校验和幂等处理