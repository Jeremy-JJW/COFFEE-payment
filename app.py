from flask import Flask, request, redirect, url_for, render_template, jsonify
from threading import Lock
import datetime
import socket
from order_db import order_db  # 导入订单数据库

# app = Flask(__name__)
app = Flask(__name__, static_folder='static')

# 全局变量保存订单信息（线程安全）
next_order_id = order_db.get_next_order_id()  # 新增：订单ID计数器
order_lock = Lock() 
last_order_time = None
order_history = []

 
# 获取本机IP地址和当前时间（保持不变）
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"


def get_current_time():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # return datetime.datetime.now()


# 支付相关辅助函数
def generate_payment_token():
    """生成支付唯一标识"""
    import hashlib
    import secrets
    token = hashlib.md5(str(secrets.randbits(128)).encode()).hexdigest()[:16]
    return token

def calculate_payment_amount(cups, price_per_cup=15):
    """计算支付金额（元转分）"""
    yuan = cups * price_per_cup  # 元
    fen = int(yuan * 100)        # 分
    return fen

def generate_transaction_id():
    """生成模拟交易ID"""
    import time
    import random
    timestamp = int(time.time())
    random_str = ''.join(random.choices('0123456789ABCDEF', k=6))
    return f"SIM-{timestamp}-{random_str}"

def validate_payment_status(order_id):
    """验证订单是否已支付"""
    payment_info = order_db.get_payment_status(order_id)
    if not payment_info:
        return False, "订单不存在"
    if payment_info['payment_status'] != 'paid':
        return False, f"订单未支付（当前状态: {payment_info['payment_status']}）"
    return True, "订单已支付"

def create_production_order(order_id):
    """支付成功后创建制作订单"""
    order = order_db.get_order_by_id(order_id)
    if not order:
        return False, "订单不存在"

    # 检查是否已支付
    if order['payment_status'] != 'paid':
        return False, "订单未支付，无法开始制作"

    # 更新订单状态为待处理（status=0）
    # 这里直接使用数据库的更新方法
    # 由于现有代码使用status字段，我们确保它为0
    return True, "订单已准备好制作"


# 主页 - 展示订单表单 00000
@app.route('/')
def order_page():
    # 处理可能的错误消息
    error_message = request.args.get('error', '')

    # 获取本机IP地址
    ip_address = get_local_ip()

    # 获取当前时间
    current_time = get_current_time()

    # 从数据库中获取待处理订单总杯数
    pending_cups = order_db.count_pending_cups()
    making_orders = []
    for order in order_db.get_pending_orders():
        cups = order.get('cups', 0)
        completed_cups = order.get('completed_cups', 0)
        progress_percent = round((completed_cups / cups) * 100) if cups else 0
        making_orders.append({
            **order,
            'progress_percent': progress_percent
        })

    return render_template(
        'index.html',
        ip_address=ip_address,
        current_time=current_time,
        error=error_message,
        pending_cups=pending_cups,
        making_orders=making_orders
    )


@app.route('/api/order_status')
def api_order_status():
    """首页轮询：返回待制作总杯数（与 CSV 中 status=0 的订单一致）"""
    pending_cups = order_db.count_pending_cups()
    return jsonify(success=True, pending_cups=pending_cups)
 

# 下单处理 网页上点击下单后提交表单首先在这里处理  11111
@app.route('/order', methods=['POST'])
def place_order():
    global next_order_id, last_order_time, order_history

    # 获取杯子数量
    cups = request.form.get('cups')
    try:
        cups = int(cups)
        if cups < 1 or cups > 10:
            raise ValueError("杯数超出范围")
    except:
        # 重定向回主页并显示错误消息
        return redirect(url_for('order_page', error="请输入有效的杯数（1-10）"))

    # 计算支付金额
    payment_amount = calculate_payment_amount(cups)

    # 加锁处理全局变量
    with order_lock:
        # 生成订单信息
        order_id = next_order_id
        next_order_id += 1
        now = datetime.datetime.now()
        last_order_time = now

        # 记录订单到内存历史中
        order_history.append({
            "id": order_id,
            "time": now.strftime("%Y-%m-%d %H:%M:%S"),
            "cups": cups,
            "amount": payment_amount / 100  # 显示为元
        })

        # 将订单提交到数据库（创建待支付订单）
        order_db.add_order(order_id, cups, payment_amount)

    print(f"订单 #{order_id}：{cups}杯咖啡 (金额: ¥{payment_amount/100:.2f})")

    # 跳转到支付页面（不再是直接成功页面）
    return redirect(url_for('payment_page', order_id=order_id))


@app.route('/payment/<int:order_id>')
def payment_page(order_id):
    """显示模拟支付页面"""
    order = order_db.get_order_by_id(order_id)
    if not order:
        return redirect(url_for('order_page', error="订单不存在，请重新下单"))

    if order['payment_status'] == 'paid':
        return redirect(url_for('order_success', order_id=order_id))

    return render_template(
        'payment.html',
        order=order,
        amount_yuan=order['payment_amount'] / 100,
        error=request.args.get('error', ''),
        current_time=get_current_time()
    )


@app.route('/payment/confirm', methods=['POST'])
def confirm_payment():
    """模拟支付确认"""
    order_id = request.form.get('order_id')
    payment_method = request.form.get('payment_method', 'simulated')

    try:
        order_id = int(order_id)
    except (TypeError, ValueError):
        return redirect(url_for('order_page', error="支付订单号无效，请重新下单"))

    order = order_db.get_order_by_id(order_id)
    if not order:
        return redirect(url_for('order_page', error="订单不存在，请重新下单"))

    if order['payment_status'] == 'paid':
        return redirect(url_for('order_success', order_id=order_id))

    transaction_id = generate_transaction_id()
    if not order_db.update_payment_status(order_id, 'paid', payment_method, transaction_id):
        return redirect(url_for('payment_page', order_id=order_id, error="支付失败，请重试"))

    print(f"订单 #{order_id} 模拟支付成功，交易号: {transaction_id}")
    return redirect(url_for('order_success', order_id=order_id))


@app.route('/api/payment/status/<int:order_id>')
def api_payment_status(order_id):
    """查询订单支付状态"""
    payment_info = order_db.get_payment_status(order_id)
    if not payment_info:
        return jsonify(success=False, error="订单不存在"), 404
    return jsonify(success=True, **payment_info)


@app.route('/payment/callback/wechatpay', methods=['POST'])
def wechatpay_callback():
    """微信支付回调预留接口"""
    return jsonify(success=False, message="微信支付暂未启用"), 501


# 订单成功页面  22222
@app.route('/order/success')
def order_success():
    order_id = request.args.get('order_id')
    order = None
    if order_id:
        order = order_db.get_order_by_id(order_id)
        if not order:
            return redirect(url_for('order_page', error="订单不存在，请重新下单"))
        if order['payment_status'] != 'paid':
            return redirect(url_for('payment_page', order_id=order_id))

    cups = order['cups'] if order else request.args.get('cups', '0')
    current_time = get_current_time()
    return render_template(
        'success.html',
        cups=cups,
        order=order,
        amount_yuan=(order['payment_amount'] / 100) if order else 0,
        current_time=current_time
    )


# 订单明细页面
@app.route('/orders')
def order_details():
    # 计算已完成的总杯数
    total_cups = sum(order['cups'] for order in order_history)

    # 从数据库获取最新状态信息
    pending_orders = order_db.get_pending_orders()
    pending_cups = order_db.count_pending_cups()
    completed_orders_count = len(order_history) - len(pending_orders)

    return render_template(
        'orders.html',
        total_cups=total_cups,
        pending_cups=pending_cups,
        order_count=len(order_history),
        completed_orders_count=completed_orders_count,
        orders=order_history,
        pending_orders=pending_orders,
        current_time=get_current_time()
    )


if __name__ == '__main__':
    # 获取本机在局域网中的IP
    ip = get_local_ip()
    print(f" * 本地访问: http://127.0.0.1:5000")
    print(f" * 其他设备访问: http://{ip}:5000")

    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True
    )









