# server/app.py
"""本地被测服务：用户模块（基线）+ 商品 / 购物车 / 订单 / 库存（电商同构改造）。

所有状态放在 Flask 进程内存里，只为练习断言设计，不模拟真实存储。
库存账遵循守恒关系：initial_stock == deducted + stock（deducted 为净扣减，
取消订单回滚时 deducted 相应减回）。
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


# ---------------------------------------------------------------- 商品 / 库存

# 业务码约定（对齐国内网关风格：HTTP 层反映传输问题，业务成败看 code）
# 2001 库存不足 / 2002 商品不存在 / 2003 参数非法（数量 / 价格）/ 2004 订单不存在 / 2005 订单已取消
GOODS = {}          # goods_id -> 商品库存账（含 stock / initial_stock / deducted）
GOOD_JOURNAL = {}   # goods_id -> [{"op": "deduct"/"rollback", "order_id":.., "quantity":..}]
_goods_seq = 1000


def _bad_request(message: str):
    return make_resp(1, message), 400


@app.post("/goods")
def create_goods():
    """建商品：name / price / stock，返回 goods_id"""
    global _goods_seq
    body = request.get_json(silent=True) or {}
    name = body.get("name")
    price = body.get("price")
    stock = body.get("stock")
    if not name or not isinstance(price, (int, float)) or isinstance(price, bool) or price <= 0:
        return _bad_request("商品参数非法：name 必填，price 必须大于 0")
    if not isinstance(stock, int) or isinstance(stock, bool) or stock < 0:
        return _bad_request("商品参数非法：stock 必须是不小于 0 的整数")

    _goods_seq += 1
    goods_id = _goods_seq
    GOODS[goods_id] = {
        "goods_id": goods_id,
        "name": name,
        "price": price,
        "stock": stock,
        "initial_stock": stock,
        "deducted": 0,
    }
    GOOD_JOURNAL[goods_id] = []
    return make_resp(0, "商品已创建", dict(GOODS[goods_id])), 200


@app.delete("/goods/<int:goods_id>")
def delete_goods(goods_id: int):
    """删除商品（造数工厂 teardown 用）：连同流水一起清掉"""
    if goods_id not in GOODS:
        return make_resp(2002, "商品不存在"), 404
    GOODS.pop(goods_id)
    GOOD_JOURNAL.pop(goods_id, None)
    return make_resp(0, "商品已删除", {"goods_id": goods_id}), 200


@app.get("/inventory/<int:goods_id>")
def get_inventory(goods_id: int):
    """库存账查询：守恒断言的数据源（initial_stock == deducted + stock）"""
    if goods_id not in GOODS:
        return make_resp(2002, "商品不存在"), 404
    goods = GOODS[goods_id]
    return jsonify(
        {
            "goods_id": goods_id,
            "stock": goods["stock"],
            "initial_stock": goods["initial_stock"],
            "deducted": goods["deducted"],
        }
    ), 200


@app.get("/inventory/<int:goods_id>/journal")
def get_inventory_journal(goods_id: int):
    """库存流水：每笔扣减 / 回滚一条，供流水与订单一一对应的核对"""
    if goods_id not in GOODS:
        return make_resp(2002, "商品不存在"), 404
    return jsonify(GOOD_JOURNAL[goods_id]), 200


# ---------------------------------------------------------------- 购物车

CARTS = {}  # (user_id, goods_id) -> 累加后的数量


@app.post("/cart/items")
def add_cart_item():
    body = request.get_json(silent=True) or {}
    user_id = body.get("user_id")
    goods_id = body.get("goods_id")
    quantity = body.get("quantity")
    if not user_id or goods_id is None or quantity is None:
        return _bad_request("加购参数非法：user_id / goods_id / quantity 必填")
    if goods_id not in GOODS:
        return make_resp(2002, "商品不存在"), 404
    if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
        return _bad_request("加购数量必须是不小于 1 的整数")

    key = (user_id, goods_id)
    CARTS[key] = CARTS.get(key, 0) + quantity
    return make_resp(
        0,
        "已加入购物车",
        {"user_id": user_id, "goods_id": goods_id, "quantity": quantity, "cart_total": CARTS[key]},
    ), 200


# ---------------------------------------------------------------- 订单

ORDERS = {}      # order_id -> 订单记录
_order_seq = 5000


@app.post("/orders")
def create_order():
    """下单：内部扣库存；库存不足返回业务码 2001（HTTP 仍为 200，成败看业务码）"""
    global _order_seq
    body = request.get_json(silent=True) or {}
    user_id = body.get("user_id")
    goods_id = body.get("goods_id")
    quantity = body.get("quantity")
    if not user_id or goods_id is None or quantity is None:
        return _bad_request("下单参数非法：user_id / goods_id / quantity 必填")
    if goods_id not in GOODS:
        return make_resp(2002, "商品不存在"), 404
    if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
        return _bad_request("下单数量必须是不小于 1 的整数")

    goods = GOODS[goods_id]
    if goods["stock"] < quantity:
        # 业务失败：不扣库存、不记流水，避免"少卖"（扣了账没货）
        return make_resp(2001, "库存不足", {}), 200

    _order_seq += 1
    order_id = _order_seq
    goods["stock"] -= quantity
    goods["deducted"] += quantity
    GOOD_JOURNAL[goods_id].append({"op": "deduct", "order_id": order_id, "quantity": quantity})
    ORDERS[order_id] = {
        "order_id": order_id,
        "user_id": user_id,
        "goods_id": goods_id,
        "quantity": quantity,
        "status": "created",
    }
    return make_resp(0, "下单成功", dict(ORDERS[order_id])), 200


@app.post("/orders/<int:order_id>/cancel")
def cancel_order(order_id: int):
    """取消订单：回滚库存并记一条 rollback 流水；重复取消返回业务码 2005"""
    if order_id not in ORDERS:
        return make_resp(2004, "订单不存在"), 404
    order = ORDERS[order_id]
    if order["status"] == "canceled":
        return make_resp(2005, "订单已取消，勿重复取消", {}), 200

    order["status"] = "canceled"
    goods = GOODS[order["goods_id"]]
    goods["stock"] += order["quantity"]
    goods["deducted"] -= order["quantity"]
    GOOD_JOURNAL[order["goods_id"]].append(
        {"op": "rollback", "order_id": order_id, "quantity": order["quantity"]}
    )
    return make_resp(0, "订单已取消", {"order_id": order_id, "status": "canceled"}), 200
