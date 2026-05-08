# 咖啡点单系统支付功能实现计划

## 当前进展状态
✅ **已完成**：
1. 扩展了order_db.py数据库，添加了支付字段
2. 添加了支付相关的方法：update_payment_status, get_payment_status等
3. 修改了数据库兼容性检查

🚧 **进行中**：
1. 修改app.py路由和逻辑
2. 创建支付相关HTML模板

## 数据模型扩展（已实现）
### CSV数据库新字段
已添加到 `order_db.py`:
- `payment_status` - 支付状态：`pending`, `paid`, `failed`, `canceled`
- `payment_amount` - 支付金额（整数，以分为单位，微信支付用）
- `payment_method` - 支付方式：`simulated`, `wechat_pay`, `alipay`
- `payment_time` - 支付完成时间（UTC格式）
- `payment_transaction_id` - 支付交易ID

### 新增关键方法
1. `update_payment_status()` - 更新订单支付状态
2. `get_payment_status()` - 获取订单支付信息
3. `get_order_by_id()` - 通过ID获取完整订单信息
4. `get_orders_by_payment_status()` - 按支付状态筛选订单
5. `_ensure_payment_fields()` - 确保数据库兼容性

## 新支付流程设计
### 流程图
```
主页(index.html)选择杯数 → POST /order (创建待支付订单，状态：payment_status=pending)
      ↓
跳转支付页面(payment.html)显示订单详情和支付二维码
      ↓
用户扫码/模拟支付 → POST /payment/confirm
      ↓
支付成功 → 更新payment_status=paid → 重定向到success.html
      ↓
制作系统只处理payment_status=paid的订单
```

### 后端路由设计（app.py）
1. **主页路由**：`/` → 保持不变，但表单提交到新逻辑
2. **下单路由**：`/order` (POST) → 修改：创建待支付订单，计算金额，重定向到支付页面
3. **支付页面**：`/payment/<order_id>` (GET) → 显示订单详情、支付金额、支付二维码
4. **支付确认**：`/payment/confirm` (POST) → 模拟支付逻辑，更新支付状态
5. **支付状态查询**：`/api/payment/status/<order_id>` (GET) → 轮询支付状态
6. **成功页面**：`/order/success` → 更新显示支付信息

## 核心代码实现
### 金额计算逻辑
```python
# app.py中
def calculate_payment_amount(cups, price_per_cup=15):
    """计算支付金额（元转分）"""
    yuan = cups * price_per_cup  # 元
    fen = int(yuan * 100)        # 分（微信支付单位）
    return fen

# 每杯咖啡价格可配置，默认15元/杯
```

### 模拟支付流程
1. 用户提交订单 → 创建 `payment_status: pending` 的订单
2. 跳转到支付页面 → 显示模拟二维码和"模拟支付"按钮
3. 点击"模拟支付" → 生成模拟交易ID：`SIM-{timestamp}-{random}`
4. 更新 `payment_status: paid`, `payment_method: simulated`
5. 跳转到成功页面

### 支付安全验证
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

## 前端页面设计
### 1. 支付页面 (payment.html)
- 显示订单号、杯数、总金额
- 显示支付二维码（模拟）
- "模拟支付"按钮
- 支付状态轮询显示

### 2. 成功页面更新 (success.html)
- 显示支付状态：已支付/未支付
- 显示支付方式：模拟支付/微信支付
- 显示交易ID
- 显示支付时间

### 3. 主页更新 (index.html)
- 表单提交逻辑更新
- 说明文字更新：告知需要支付

## 集成微信支付（预留）
### 接口设计
```python
# 微信支付处理类（预留）
class WechatPayHandler:
    def create_payment(self, order_id, amount, description):
        """调用微信支付统一下单API"""
        pass
    
    def verify_callback(self, request_data):
        """验证微信支付回调"""
        pass
    
    def check_payment_status(self, transaction_id):
        """查询支付状态"""
        pass

# 支付工厂模式
def get_payment_handler(method='simulated'):
    if method == 'wechatpay':
        return WechatPayHandler()
    else:
        return SimulatedPayHandler()  # 默认模拟支付
```

### 回调处理
预留路由：`/payment/callback/wechatpay`
- 接收微信支付异步通知
- 验证签名
- 更新订单支付状态

## 数据兼容性和迁移
### 现有订单处理
```python
# order_db.py 中的方法
def _ensure_payment_fields(self):
    """确保CSV文件包含所有支付相关字段"""
    # 自动为现有订单添加默认支付状态
    # 现有订单 payment_status = 'pending'（待支付）
    # 这样不会影响已有订单
```

### 制作系统兼容性
现有的制作系统（如咖啡机控制）需要：
1. 修改：只处理 `payment_status='paid'` 的订单
2. 添加支付状态检查：开始制作前验证已支付

## 测试方案
### 测试场景
1. **正常支付流程**：下单 → 支付 → 成功
2. **支付失败处理**：支付失败时的重试机制
3. **并发支付测试**：多个用户同时下单支付
4. **数据一致性**：验证CSV数据库字段完整性

### 测试数据
- 模拟不同杯数：1杯、5杯、10杯（上限）
- 验证金额计算：15元/杯 × 杯数
- 验证状态流转：pending → paid → processing → completed

## 部署步骤
### 第一阶段：模拟支付
1. 修改 `order_db.py` - ✅ 已完成
2. 修改 `app.py` 路由 - 🚧 进行中
3. 创建支付页面模板 - ❌ 待完成
4. 更新现有模板 - ❌ 待完成
5. 测试完整流程 - ❌ 待完成

### 第二阶段：微信支付集成
1. 申请微信支付商户号
2. 配置API密钥和回调域名
3. 实现 `WechatPayHandler` 类
4. 替换模拟支付逻辑
5. 生产环境测试

## 关键文件路径
- `order_db.py` - 数据库扩展（已修改）
- `app.py` - 路由和逻辑（修改中）
- `templates/payment.html` - 支付页面（待创建）
- `templates/index.html` - 主页表单（待更新）
- `templates/success.html` - 成功页面（待更新）

## 风险和控制
### 技术风险
1. **数据库兼容性**：已通过 `_ensure_payment_fields()` 自动处理
2. **支付状态同步**：使用唯一transaction_id跟踪交易
3. **并发支付**：使用线程锁保护共享资源

### 操作风险
1. **数据备份**：部署前备份orders.csv文件
2. **回滚计划**：保留旧版本代码备份
3. **监控指标**：支付成功率、平均支付时间

## 下一步工作
### 立即执行（阶段一）
1. 完成app.py路由修改
2. 创建payment.html支付页面
3. 更新index.html表单提交
4. 测试模拟支付完整流程

### 后续扩展（阶段二）
1. 集成微信支付SDK
2. 配置生产环境密钥
3. 添加支付对账功能
4. 支持支付宝等其他支付方式

---
**最后更新**：2026-05-08  
**当前版本**：v1.0 - 模拟支付框架