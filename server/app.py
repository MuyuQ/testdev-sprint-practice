# server/app.py
"""本地被测服务：用户模块（基线）+ App 下单与支付回调（移动端配套接口回归）。

端上行为用三个请求头标识（X-Device-Id / X-App-Version / X-Channel）：
缺失返回业务码 4001，伪造（不在支持列表 / 格式非法）返回业务码 4002。
支付回调可能丢失（simulate=lost 模拟网络丢失）；补偿任务负责主动补账，幂等——
每笔订单只补一次，迟到的回调不重复记账。
"""
from flask import Flask, jsonify, request

app = Flask(__name__)

# ---------------------------------------------------------------- 用户模块（main 基线保留）

# 模拟账号库：只有 valid_user / valid_pass 能登录成功
VALID_USERS = {"valid_user": "valid_pass"}


def make_resp(code: int, message: str, data=None):
    """统一响应结构：业务码 + 提示 + 数据，和真实项目保持同构"""
    return jsonify({"code": code, "message": message, "data": data or {}})


@app.post("/auth/login")
def login():
    body = request.get_json(silent=True) or {}
    # 缺参：400
    if not body.get("username") or not body.get("password"):
        return make_resp(1, "用户名或密码不能为空"), 400
    # 账号或密码错误：401
    if VALID_USERS.get(body["username"]) != body["password"]:
        return make_resp(1, "用户名或密码错误"), 401
    # 登录成功：200 + token
    return make_resp(0, "登录成功", {"token": f"fake-token-{body['username']}"}), 200


@app.get("/users/<int:user_id>")
def get_user(user_id: int):
    if user_id != 1:
        return make_resp(1, "用户不存在"), 404
    return make_resp(0, "ok", {"id": 1, "name": "张三"}), 200


# ---------------------------------------------------------------- App 下单与回调

# 业务码约定：4001 端上请求头缺失 / 4002 端上身份校验失败 / 4003 订单不存在
REQUIRED_DEVICE_HEADERS = ("X-Device-Id", "X-App-Version", "X-Channel")
# 端上身份白名单：模拟真实后端的版本与渠道校验
SUPPORTED_APP_VERSIONS = {"3.2.0", "3.1.0"}
SUPPORTED_CHANNELS = {"huawei", "xiaomi", "appstore"}

APP_ORDERS = {}    # order_id -> 订单记录（含 status / paid_via / compensated）
CALLBACK_LOG = []  # 到账审计流水：每笔订单最多一条，区分 callback / compensation
_app_order_seq = 9000


def _device_headers():
    """取出三个端上请求头（缺失为 None）"""
    return {name: request.headers.get(name) for name in REQUIRED_DEVICE_HEADERS}


def _validate_device_headers():
    """校验端上身份：缺失 → (4001, 400)，伪造 → (4002, 403)；通过返回 None"""
    headers = _device_headers()
    missing = [name for name, value in headers.items() if not value]
    if missing:
        return make_resp(4001, f"缺少端上必填请求头：{', '.join(missing)}"), 400
    if (
        not headers["X-Device-Id"].startswith("dev-")
        or headers["X-App-Version"] not in SUPPORTED_APP_VERSIONS
        or headers["X-Channel"] not in SUPPORTED_CHANNELS
    ):
        return make_resp(4002, "端上身份校验失败，请求已拒绝"), 403
    return None


@app.post("/app/order")
def app_order():
    """App 下单：先校验三个端上请求头，再落订单（状态 created，待回调 / 补偿）"""
    global _app_order_seq
    rejected = _validate_device_headers()
    if rejected is not None:
        return rejected

    body = request.get_json(silent=True) or {}
    user_id = body.get("user_id")
    amount = body.get("amount")
    if not user_id or not isinstance(amount, (int, float)) or isinstance(amount, bool) or amount <= 0:
        return make_resp(1, "下单参数非法：user_id 必填，amount 必须大于 0"), 400

    _app_order_seq += 1
    order_id = _app_order_seq
    APP_ORDERS[order_id] = {
        "order_id": order_id,
        "user_id": user_id,
        "amount": amount,
        "status": "created",
        "paid_via": None,
        "compensated": False,
    }
    return make_resp(0, "下单成功", {"order_id": order_id, "status": "created"}), 200


@app.get("/app/orders/<int:order_id>")
def get_app_order(order_id: int):
    """订单查询：补偿断言的数据源"""
    if order_id not in APP_ORDERS:
        return make_resp(4003, "订单不存在"), 404
    return jsonify(APP_ORDERS[order_id]), 200


@app.get("/app/callback-log")
def get_callback_log():
    """到账审计流水：断言"只补一次"用"""
    return jsonify(CALLBACK_LOG), 200


@app.post("/app/callback")
def app_callback():
    """支付回调。simulate=lost 模拟回调在网络中丢失（服务端什么都没收到）；
    正常回调把订单置为 paid；重复回调不重复记账。"""
    body = request.get_json(silent=True) or {}
    order_id = body.get("order_id")
    if not isinstance(order_id, int) or order_id not in APP_ORDERS:
        return make_resp(4003, "订单不存在"), 404

    if body.get("simulate") == "lost":
        # 回调在网络里丢了：服务端没收到，订单状态保持 created
        return make_resp(0, "回调已模拟丢失（服务端未收到）", {"order_id": order_id, "received": False, "duplicate": False}), 200

    order = APP_ORDERS[order_id]
    if order["status"] == "paid":
        # 迟到 / 重放的回调：已记账，不再重复入账
        return make_resp(0, "订单已支付，回调不重复记账", {"order_id": order_id, "received": True, "duplicate": True}), 200

    order["status"] = "paid"
    order["paid_via"] = "callback"
    CALLBACK_LOG.append({"order_id": order_id, "via": "callback"})
    return make_resp(0, "回调处理完成", {"order_id": order_id, "received": True, "duplicate": False}), 200


@app.post("/app/compensation")
def app_compensation():
    """补偿任务：主动补账所有未支付订单。幂等——已支付订单不再触碰，
    每笔订单只补一次（迟到回调也只判重，见 /app/callback-log 审计）。"""
    compensated = []
    for order_id in sorted(APP_ORDERS):
        order = APP_ORDERS[order_id]
        if order["status"] == "paid":
            continue
        order["status"] = "paid"
        order["paid_via"] = "compensation"
        order["compensated"] = True
        CALLBACK_LOG.append({"order_id": order_id, "via": "compensation"})
        compensated.append(order_id)
    return make_resp(0, "补偿任务执行完成", {"compensated": compensated, "count": len(compensated)}), 200


@app.post("/app/reset")
def app_reset():
    """清空订单与审计流水：用例间隔离用"""
    APP_ORDERS.clear()
    CALLBACK_LOG.clear()
    return make_resp(0, "App 状态已清空"), 200
