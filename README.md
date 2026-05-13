# Cursor_coffee
这个是cursor中开发coffee项目的github备份库

**项目介绍见 CLAUDE.md**

已改的程序

    1.虎皮椒id
    
    2.异常关闭先关闭连接

## 总览流程图

### 代码进化历程

```mermaid
flowchart LR
    A["阶段 0：无支付系统"] --> B["阶段 1：模拟支付"]
    B --> C["阶段 2：虎皮椒真实支付"]

    A1["/order 下单后直接写入 orders.csv"] --> A2["生产程序读取 status=0 订单"]
    A2 --> A3["机械臂、咖啡机、落杯器开始制作"]

    B1["扩展 orders.csv 支付字段"] --> B2["新增 /payment 页面"]
    B2 --> B3["/payment/confirm 模拟支付"]
    B3 --> B4["payment_status=pending/paid"]
    B4 --> B5["生产程序只读取 paid 订单"]

    C1["新增 hupijiao_pay.py"] --> C2["调用虎皮椒下单接口"]
    C2 --> C3["支付页显示微信二维码"]
    C3 --> C4["/payment/callback/xunhupay 接收回调"]
    C4 --> C5["验签、校验金额、幂等处理"]
    C5 --> C6["真实付款成功后改为 paid"]

    A --> A1
    B --> B1
    C --> C1
```

这张图表达的是代码能力的递进关系：一开始只有“下单和制作”，后来加了“支付状态”作为制作门槛，最后把模拟支付入口替换为虎皮椒真实微信扫码支付。

### 一个订单的完整流程与技术栈

```mermaid
flowchart TD
    U["用户 / 触摸屏"] --> FE["templates/index.html<br>HTML + CSS + JavaScript"]
    FE -->|"POST /order"| APP["app.py<br>Flask 路由"]
    APP -->|"计算金额<br>calculate_payment_amount()"| CSV1["orders.csv<br>payment_status=pending"]
    APP -->|"redirect"| PAY["templates/payment.html<br>支付页"]

    PAY -->|"服务端创建支付"| HPCLIENT["hupijiao_pay.py<br>requests + MD5签名 + Decimal金额转换"]
    HPCLIENT -->|"POST payment/do.html"| HUPI["虎皮椒支付平台<br>微信扫码支付"]
    HUPI -->|"返回 pay_url / qrcode"| PAY
    PAY -->|"展示二维码"| WX["用户微信扫码付款"]

    WX --> HUPI
    HUPI -->|"POST /payment/callback/xunhupay"| CALLBACK["app.py 回调接口<br>verify_sign + appid校验 + 金额校验"]
    CALLBACK -->|"update_payment_status()"| CSV2["orders.csv<br>payment_status=paid<br>写入交易号和支付时间"]

    PAY -->|"每 3 秒 fetch<br>/api/payment/status/order_id"| STATUS["app.py 状态接口<br>JSON 返回支付状态"]
    STATUS --> CSV2
    STATUS -->|"paid"| SUCCESS["templates/success.html<br>支付成功页"]

    CSV2 --> PROD["mainio_IN11_monitor.py<br>生产队列线程"]
    PROD -->|"get_next_pending_order()<br>只取 paid + status=0"| DB["order_db.py<br>CSV读写 + threading.Lock"]
    PROD --> IO["yanmeng_io_reader.py<br>岩獴IO板卡"]
    PROD --> COFFEE["coffee_machine.py<br>pyserial 串口控制咖啡机"]
    IO --> MACHINE["机械臂 / 落杯器 / 传感器"]
    COFFEE --> MACHINE
    MACHINE --> DONE["制作完成<br>completed_cups增加<br>status最终变为2"]
```
