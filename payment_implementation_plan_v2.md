# 咖啡点单系统支付功能实施方案

## 项目概述
为现有咖啡点单系统添加支付功能，支持模拟支付和微信支付两种方式。分两个阶段实施，第一阶段实现模拟支付功能，第二阶段集成真实微信支付。

## 当前状态跟踪

### ✅ 已完成
1. **数据库扩展** (order_db.py)
   - 添加支付相关字段：`payment_status`, `payment_amount`, `payment_method`, `payment_time`, `payment_transaction_id`
   - 实现支付状态管理方法
   - 确保数据库向后兼容

2. **主应用逻辑** (app.py)
   - 新增支付相关路由
   - 金额计算逻辑
   - 模拟支付流程

3. **前端页面开发**
   - 支付页面 (payment.html)
   - 首页下单文案更新
   - 支付成功页面支付信息展示

### 🔄 进行中
1. **微信支付 Native 扫码支付方案准备**
   - 使用微信支付 Native 下单接口获取 `code_url`
   - 支付页展示真实微信支付二维码
   - 使用公网 HTTPS 回调地址接收微信支付通知
   - 通过回调验签/解密后更新订单为已支付

## 数据库架构

### 新增字段说明
| 字段名 | 类型 | 说明 | 示例值 |
|--------|------|------|--------|
| `payment_status` | 字符串 | 支付状态 | `pending`, `paid`, `failed`, `canceled` |
| `payment_amount` | 整数 | 支付金额(分) | `1500` (表示15.00元) |
| `payment_method` | 字符串 | 支付方式 | `simulated`, `wechat_pay`, `alipay` |
| `payment_time` | 字符串 | 支付完成时间 | `2026-05-08 10:30:45` |
| `payment_transaction_id` | 字符串 | 交易ID | `SIM-1715149845-a1b2c3` |

### 关键数据库方法
```python
# order_db.py 中已实现的方法
- update_payment_status(order_id, status, method, transaction_id)
- get_payment_status(order_id) -> dict
- get_order_by_id(order_id) -> dict
- get_orders_by_payment_status(status) -> list
- get_next_order_id() -> int
- _ensure_standard_fields()  # 自动兼容性处理
```

## 支付流程设计

### 核心流程
```
用户访问主页 (index.html)
    ↓
选择咖啡杯数并提交
    ↓
POST /order → 创建待支付订单 (payment_status='pending')
    ↓
重定向到支付页面 /payment/<order_id>
    ↓
在支付页面选择支付方式 (模拟支付 / 微信支付)
    ↓
模拟支付: POST /payment/confirm → 更新支付状态 (payment_status='paid')
微信支付: 微信回调 /payment/callback/wechatpay → 更新支付状态 (payment_status='paid')
    ↓
重定向到成功页面 /order/success
    ↓
后台系统只处理已支付的订单 (payment_status='paid')
```

### 金额计算规则
- 单价: 15元/杯 (可配置)
- 计算: `总金额(元) = 杯数 × 15`
- 微信支付单位: `支付金额(分) = 总金额(元) × 100`

## API接口设计

### 主API路由
| 方法 | 路径 | 功能 | 参数 |
|------|------|------|------|
| GET | `/` | 主页 | - |
| POST | `/order` | 创建订单 | `cups` |
| GET | `/payment/<order_id>` | 支付页面 | - |
| POST | `/payment/confirm` | 确认模拟支付 | `order_id`, `payment_method` |
| POST | `/payment/wechat/create` | 创建微信 Native 支付订单 | `order_id` |
| GET | `/api/payment/status/<order_id>` | 查询支付状态 | - |
| GET | `/order/success` | 支付成功页 | - |
| POST | `/payment/callback/wechatpay` | 微信支付回调 | 微信支付通知 |

### 响应格式
```json
{
  "order_id": "ORDER-001",
  "cups": 2,
  "amount": 3000,
  "payment_status": "paid",
  "payment_method": "simulated"
}
```

## 模拟支付实现细节

### 工作流
1. **订单创建**
   - 计算总金额: `cups × 15 × 100`
   - 设置: `payment_status: 'pending'`, `payment_method: 'simulated'`

2. **支付页面显示**
   - 生成模拟二维码
   - 显示"模拟支付"按钮
   - 实时状态轮询

3. **支付确认**
   - 生成模拟交易ID: `SIM-{timestamp}-{random}`
   - 设置: `payment_status: 'paid'`, `payment_time: now`
   - 返回成功响应

4. **状态验证**
   - 生产系统只处理 `payment_status='paid'` 的订单
   - 制作开始前验证支付状态

## 微信支付 Native 扫码支付设计

### 适用方式
- 第一版采用 **微信支付 Native 扫码支付**。
- 用户在普通浏览器打开点单页面，下单后支付页展示微信支付二维码。
- 用户使用微信扫码支付；支付完成后，微信服务器通过 `notify_url` 通知本地服务。
- 页面继续轮询 `/api/payment/status/<order_id>`，订单变为 `paid` 后跳转成功页。

### 需要准备的微信支付资料
以下资料用于本地 `.env` 或服务器环境变量配置，不应提交到 GitHub，也不要写死在代码中。

```env
WECHAT_APP_ID=公众号或小程序AppID
WECHAT_MCH_ID=微信支付商户号
WECHAT_SERIAL_NO=商户API证书序列号
WECHAT_API_V3_KEY=32位APIv3密钥
WECHAT_PRIVATE_KEY_PATH=certs/apiclient_key.pem
WECHAT_NOTIFY_URL=https://xxxx.cpolar.top/payment/callback/wechatpay
WECHAT_PAY_DESCRIPTION=领志科技咖啡
```

证书文件建议放置：

```text
certs/apiclient_key.pem
```

并确保 `.gitignore` 包含：

```gitignore
.env
certs/
```

### cpolar 回调地址说明
- 测试阶段可以使用 cpolar 提供的 HTTPS 公网地址作为 `WECHAT_NOTIFY_URL`。
- 回调地址必须是微信服务器可访问的完整 HTTPS 地址，例如：

```text
https://xxxx.cpolar.top/payment/callback/wechatpay
```

- 本地 Flask 服务需要保持运行，并监听 `0.0.0.0:5000`。
- 如果 cpolar 域名变化，需要同步更新环境变量或微信支付下单参数中的 `notify_url`。
- 正式部署建议使用固定域名和正式 HTTPS 证书。

### 微信支付工作流
```
用户提交订单
    ↓
POST /order 创建 pending 订单
    ↓
GET /payment/<order_id> 展示支付页
    ↓
POST /payment/wechat/create 调用微信 Native 下单
    ↓
微信返回 code_url
    ↓
支付页根据 code_url 展示二维码
    ↓
用户微信扫码支付
    ↓
微信服务器 POST /payment/callback/wechatpay
    ↓
服务端验签并使用 APIv3 密钥解密通知
    ↓
确认金额、商户订单号、交易状态
    ↓
update_payment_status(..., 'paid', 'wechat_pay', transaction_id)
    ↓
前端轮询到 paid 后跳转 /order/success
```

### 回调安全要求
1. 验证微信支付通知签名，确认通知确实来自微信支付。
2. 使用 `WECHAT_API_V3_KEY` 解密回调中的 `resource`。
3. 校验回调中的商户订单号、支付金额、商户号和交易状态。
4. 回调处理必须幂等：重复通知同一订单时，不应重复进入制作队列或重复修改异常状态。
5. 只有校验通过后，才允许把订单更新为 `payment_status='paid'`。

## 前端页面设计

### 1. 支付页面 (payment.html)
```
┌─────────────────────────────────┐
│    订单信息                      │
│   订单号: ORDER-123456          │
│   数量: 2杯                     │
│   总金额: 30.00元               │
├─────────────────────────────────┤
│    [模拟支付二维码]              │
│    (此处显示模拟的二维码图片)     │
│    或显示微信 Native 支付二维码    │
├─────────────────────────────────┤
│   支付方式: [模拟支付]          │
│                                  │
│   [ 模拟支付按钮 ]              │
│                                  │
│   支付状态: 等待支付...         │
└─────────────────────────────────┘
```

### 2. 成功页面更新 (success.html)
```
┌─────────────────────────────────┐
│    支付成功 😊                   │
│                                  │
│   订单号: ORDER-123456          │
│   支付金额: 30.00元             │
│   支付方式: 模拟支付             │
│   交易ID: SIM-1715149845-a1b2c3 │
│   支付时间: 2026-05-08 10:30:45 │
│                                  │
│   [返回首页] [查看订单]          │
└─────────────────────────────────┘
```

### 3. 主页更新 (index.html)
- 更新表单提交逻辑
- 添加支付说明文本
- 修改提交按钮文案

## 技术实现清单

### 文件修改清单

#### 已完成修改
✅ `order_db.py` - 数据库扩展和支付方法
✅ `app.py` - 模拟支付路由和状态查询逻辑
✅ `templates/payment.html` - 模拟支付页面
✅ `templates/index.html` - 首页下单文案更新
✅ `templates/success.html` - 支付成功信息展示

#### 待修改/创建
🔲 `wechat_pay.py` - 微信支付 Native 下单、签名、回调解密封装
🔲 `.env` - 微信支付本地配置（不提交 Git）
🔲 `certs/apiclient_key.pem` - 商户 API 证书私钥（不提交 Git）
🔲 `app.py` - 接入真实微信 Native 下单路由和回调处理
🔲 `templates/payment.html` - 增加微信支付二维码展示
🔲 `requirements.txt` - 如需要，增加二维码生成、环境变量读取、加密签名依赖

### 关键代码片段

#### 金额计算函数
```python
def calculate_payment_amount(cups, price_per_cup=15):
    """计算支付金额（元转分）"""
    yuan = cups * price_per_cup  # 元
    fen = int(yuan * 100)        # 分（微信支付单位）
    return fen
```

#### 支付状态验证
```python
def validate_payment_status(order_id):
    """验证订单是否已支付"""
    payment_info = order_db.get_payment_status(order_id)
    if not payment_info:
        return False, "订单不存在"
    if payment_info['payment_status'] != 'paid':
        return False, f"订单未支付（当前状态: {payment_info['payment_status']}）"
    return True, "订单已支付"
```

#### 模拟支付交易ID生成
```python
def generate_simulated_transaction_id():
    """生成模拟交易ID"""
    import time, random, string
    timestamp = int(time.time())
    random_str = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
    return f"SIM-{timestamp}-{random_str}"
```

## 部署步骤

### 阶段一：模拟支付 (预计1-2天)
1. **环境准备**
   - 备份 `orders.csv` 数据库文件
   - 检查Python依赖环境

2. **代码实施**
   - 完成 `app.py` 路由修改
   - 创建 `payment.html` 页面
   - 更新现有模板文件
   - 添加样式和图片资源

3. **集成测试**
   - 测试完整支付流程
   - 验证数据库字段更新
   - 测试页面跳转
   - 验证金额计算正确性

4. **部署上线**
   - 部署代码到测试环境
   - 运行测试用例
   - 部署到生产环境
   - 监控日志和错误

### 阶段二：微信支付 Native 扫码支付
1. **资料准备**
   - 准备 `WECHAT_APP_ID`
   - 准备 `WECHAT_MCH_ID`
   - 准备 `WECHAT_SERIAL_NO`
   - 准备 `WECHAT_API_V3_KEY`
   - 准备 `certs/apiclient_key.pem`
   - 准备 cpolar HTTPS 回调地址 `WECHAT_NOTIFY_URL`

2. **配置安全**
   - 创建 `.env` 保存微信支付配置
   - `.gitignore` 忽略 `.env` 和 `certs/`
   - 确认证书和密钥不进入 GitHub

3. **代码实施**
   - 新建微信支付客户端封装
   - 实现 Native 下单接口并获取 `code_url`
   - 支付页面展示真实微信支付二维码
   - 实现微信支付回调验签、解密和订单更新
   - 保留模拟支付用于本地测试和故障排查

4. **联调测试**
   - 使用 cpolar HTTPS 地址接收微信支付回调
   - 测试真实扫码支付
   - 验证支付金额、订单号、交易号写入 `orders.csv`
   - 验证重复回调不会重复处理

5. **正式部署**
   - 替换为固定 HTTPS 域名
   - 更新微信支付回调地址
   - 完成生产环境小额支付测试

## 测试方案

### 功能测试用例
1. **下单流程测试**
   - 输入1杯咖啡，验证金额计算正确
   - 输入10杯（最大值），验证处理正常
   - 输入0或负数，验证错误处理

2. **支付流程测试**
   - 正常支付流程：下单 → 支付 → 成功
   - 支付页面刷新，验证状态保持
   - 多次点击支付按钮，防止重复支付
   - 微信支付扫码后，页面轮询能自动跳转成功页
   - 微信支付回调重复通知时，订单状态保持正确

3. **数据一致性测试**
   - 验证CSV数据库字段完整
   - 测试大量并发下单
   - 重启服务，验证数据持久化

### 性能测试
- 模拟100个用户同时支付
- 验证页面响应时间 < 2秒
- 数据库写入性能测试

### 异常测试
- 网络中断时的支付处理
- 浏览器关闭后的状态恢复
- 支付超时处理机制

## 风险控制

### 技术风险
1. **数据兼容性风险**
   - 控制: 使用 `_ensure_standard_fields()` 自动处理
   - 缓解: 部署前备份，测试恢复流程

2. **并发风险**
   - 控制: 数据库操作使用线程锁
   - 监控: 添加并发访问日志

3. **状态不一致风险**
   - 控制: 支付状态验证机制
   - 监控: 添加数据一致性检查

4. **微信支付回调安全风险**
   - 控制: 回调验签、APIv3 解密、金额校验、订单号校验
   - 缓解: 回调接口只在校验通过后更新订单状态

5. **cpolar 临时域名变化风险**
   - 控制: 测试阶段每次启动前确认 `WECHAT_NOTIFY_URL`
   - 缓解: 正式环境使用固定域名和 HTTPS

### 操作风险
1. **部署风险**
   - 控制: 分阶段部署，有回滚计划
   - 缓解: 保留旧版本代码，快速回滚

2. **监控缺失风险**
   - 控制: 添加支付成功率监控
   - 缓解: 日志记录所有支付操作

## 后续扩展计划

### 短期改进 (1个月内)
- 添加支付宝支付支持
- 实现支付失败重试机制
- 添加支付统计分析页面
- 支持优惠券和折扣功能

### 中期完善 (3个月内)
- 重构支付处理为插件架构
- 添加对账功能
- 集成短信/邮件支付提醒
- 支持会员储值支付

### 长期规划 (6个月+)
- 多门店支付分账
- 支付风控系统
- 支持信用卡支付
- 国际化支付支持

## 文档和维护

### 部署文档
```
1. 克隆代码仓库
2. 安装依赖: pip install -r requirements.txt
3. 配置环境变量(微信支付阶段必需)
4. 启动服务: python app.py
5. 访问应用: http://localhost:5000
```

### 微信支付配置文件示例
```env
WECHAT_APP_ID=
WECHAT_MCH_ID=
WECHAT_SERIAL_NO=
WECHAT_API_V3_KEY=
WECHAT_PRIVATE_KEY_PATH=certs/apiclient_key.pem
WECHAT_NOTIFY_URL=https://xxxx.cpolar.top/payment/callback/wechatpay
WECHAT_PAY_DESCRIPTION=领志科技咖啡
```

### API文档
```
支付状态码说明:
- pending: 待支付
- paid: 已支付
- failed: 支付失败
- canceled: 已取消

错误代码:
- 400: 参数错误
- 404: 订单不存在
- 409: 订单状态不允操作
- 500: 服务器内部错误
```

### 运维监控
- 支付成功率: > 99%
- 平均支付时间: < 30秒
- 系统可用性: > 99.9%
- 错误日志监控: 实时告警

---
**文档版本**: v2.0  
**最后更新**: 2026-05-08  
**负责人**: 咖啡点单系统开发团队