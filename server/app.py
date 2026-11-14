# server/app.py
"""本地被测服务：一个极简用户系统，供自动化用例打真实 HTTP 请求"""
from flask import Flask, jsonify, request

app = Flask(__name__)

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
