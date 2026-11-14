# server/app.py
"""本地被测服务：用户模块（基线）+ 后台管理动作（权限矩阵参数化探测）。

ADMIN_POLICY 模拟真实后端写死在服务里的权限配置；测试期望矩阵在
config/permission-matrix.yaml 里独立维护。两者不一致时回归立刻报错。
服务端按"默认拒绝"设计：矩阵之外的任何角色 / 资源 / 操作一律 403。
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


# ---------------------------------------------------------------- 后台权限

# 业务码约定：4031 权限不足（HTTP 403）
# 服务端策略：模拟真实后端配置，独立于测试期望矩阵（config/permission-matrix.yaml）。
# 注意：这里故意用硬编码而不是读同一份 YAML，否则探测永远自证通过，失去回归价值。
ADMIN_POLICY = {
    "ADMIN": {
        "goods": {"create", "update", "delete"},
        "order": {"cancel", "refund"},
        "config": {"read", "write"},
        "user": {"ban"},
    },
    "OPS": {
        "goods": {"create", "update"},
        "order": {"cancel"},
        "config": {"read"},
    },
    "CS": {
        "goods": {"update"},
    },
}


@app.post("/admin/action")
def admin_action():
    """后台管理动作探测：allow 返回 200，deny（含未知角色/资源/操作）返回 403"""
    body = request.get_json(silent=True) or {}
    role = body.get("role")
    resource = body.get("resource")
    action = body.get("action")
    if not role or not resource or not action:
        return make_resp(1, "参数非法：role / resource / action 必填"), 400

    allowed = action in ADMIN_POLICY.get(role, {}).get(resource, set())
    decision = "allow" if allowed else "deny"
    code = 0 if allowed else 4031
    status = 200 if allowed else 403
    return make_resp(
        code,
        "允许执行" if allowed else "权限不足",
        {"role": role, "resource": resource, "action": action, "decision": decision},
    ), status
