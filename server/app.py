# server/app.py
"""本地被测服务：用户模块（基线）+ 支付与对账（对账模块改造）。

两份流水（本地 / 渠道）初始完全一致；POST /reconcile/manipulate 支持对任一侧
做丢弃、改金额、重复记账三种操纵，制造脏数据供对账差异用例练习。
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


# ---------------------------------------------------------------- 支付与对账

# 业务码约定：3001 流水中找不到指定支付单
PAYMENTS = {}        # payment_id -> 支付单记录
LOCAL_LEDGER = []    # 平台本地流水
CHANNEL_LEDGER = []  # 渠道流水
_payment_seq = 1000


@app.post("/payments")
def create_payment():
    """支付成功：返回 payment_id，本地与渠道流水各记一笔（初始一致）"""
    global _payment_seq
    body = request.get_json(silent=True) or {}
    order_id = body.get("order_id")
    amount = body.get("amount")
    if not order_id or not isinstance(amount, (int, float)) or isinstance(amount, bool) or amount <= 0:
        return make_resp(1, "支付参数非法：order_id 必填，amount 必须大于 0"), 400

    _payment_seq += 1
    payment_id = f"PAY-{_payment_seq}"
    entry = {"payment_id": payment_id, "order_id": order_id, "amount": amount}
    PAYMENTS[payment_id] = entry
    LOCAL_LEDGER.append(dict(entry))
    CHANNEL_LEDGER.append(dict(entry))
    return make_resp(0, "支付成功", dict(entry)), 200


@app.get("/reconcile/local")
def reconcile_local():
    """平台本地流水"""
    return jsonify(LOCAL_LEDGER), 200


@app.get("/reconcile/channel")
def reconcile_channel():
    """渠道流水"""
    return jsonify(CHANNEL_LEDGER), 200


@app.post("/reconcile/manipulate")
def reconcile_manipulate():
    """操纵流水制造脏数据：drop（丢弃）/ bump_amount（改金额）/ duplicate（重复入账）

    真实项目里这些差异来自渠道掉单、金额分/元单位错位、回调重试重复入账；
    测试里用显式操纵把三类差异可控地造出来。
    """
    body = request.get_json(silent=True) or {}
    side = body.get("side")
    op = body.get("op")
    payment_id = body.get("payment_id")
    if side not in ("local", "channel"):
        return make_resp(1, "side 必须是 local 或 channel"), 400
    if op not in ("drop", "bump_amount", "duplicate"):
        return make_resp(1, "op 必须是 drop / bump_amount / duplicate"), 400
    amount = body.get("amount")
    if op == "bump_amount" and (
        not isinstance(amount, (int, float)) or isinstance(amount, bool) or amount <= 0
    ):
        return make_resp(1, "bump_amount 需要合法的 amount"), 400

    ledger = LOCAL_LEDGER if side == "local" else CHANNEL_LEDGER
    index = next((i for i, e in enumerate(ledger) if e["payment_id"] == payment_id), None)
    if index is None:
        return make_resp(3001, "流水中找不到该支付单"), 404

    entry = ledger[index]
    if op == "drop":
        ledger.pop(index)
    elif op == "bump_amount":
        entry["amount"] = amount
    elif op == "duplicate":
        ledger.append(dict(entry))
    return make_resp(0, f"已对 {side} 流水执行 {op}", {"payment_id": payment_id}), 200


@app.post("/reconcile/reset")
def reconcile_reset():
    """清空支付与两份流水：对账用例用它做前后隔离"""
    PAYMENTS.clear()
    LOCAL_LEDGER.clear()
    CHANNEL_LEDGER.clear()
    return make_resp(0, "流水已清空"), 200
