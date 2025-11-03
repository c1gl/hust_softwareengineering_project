from flask import Flask, request, jsonify, send_from_directory
import requests
import json
import os

app = Flask(__name__)

# ==============================
# 🔧 百度千帆 API 配置
# ==============================
API_URL = "https://qianfan.baidubce.com/v2/app/conversation/runs"
CONVERSATION_URL = "https://qianfan.baidubce.com/v2/app/conversation"
APP_ID = "6a089ea4-d070-4767-9691-01d3a6eec360"
AUTH_TOKEN = "Bearer bce-v3/ALTAK-FMqAnjeWnlyS3xyKFhGN5/163c8cfc9714843633db8e543f0a02478108fe93"

# ==============================
# 🗂️ 用户数据存储文件
# ==============================
USER_FILE = os.path.join(os.path.dirname(__file__), "users.json")


def load_users():
    if not os.path.exists(USER_FILE):
        return {}
    try:
        with open(USER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def save_users(users):
    with open(USER_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


# ==============================
# 💬 千帆对话封装
# ==============================
def create_conversation():
    try:
        payload = json.dumps({"app_id": APP_ID}, ensure_ascii=False)
        headers = {'Content-Type': 'application/json', 'Authorization': AUTH_TOKEN}
        response = requests.post(CONVERSATION_URL, headers=headers, data=payload.encode("utf-8"))
        response.encoding = "utf-8"
        result = response.json()
        conversation_id = result.get("conversation_id")
        return conversation_id
    except Exception as e:
        print(f"❌ 创建会话失败: {e}")
        return None


# ==============================
# 🌐 路由定义
# ==============================
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


# ==============================
# 👤 注册接口
# ==============================
@app.route('/api/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if not username or not password:
        return jsonify({"success": False, "message": "用户名和密码不能为空"}), 400

    users = load_users()
    if username in users:
        return jsonify({"success": False, "message": "用户名已存在"}), 400

    users[username] = {"password": password, "conversations": []}
    save_users(users)
    return jsonify({"success": True, "message": "注册成功，请重新登录"})


# ==============================
# 🔑 登录接口
# ==============================
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    users = load_users()
    if username not in users or users[username]["password"] != password:
        return jsonify({"success": False, "message": "用户名或密码错误"}), 401

    return jsonify({"success": True, "message": "登录成功"})


# ==============================
# 💬 聊天接口 + 保存记录
# ==============================
@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        username = data.get("username", "").strip()
        query = data.get("query", "").strip()
        conversation_id = data.get("conversation_id")

        if not username or not query:
            return jsonify({"error": "用户名和内容不能为空"}), 400

        users = load_users()
        if username not in users:
            return jsonify({"error": "用户未登录"}), 403

        if not conversation_id:
            conversation_id = create_conversation()
            if not conversation_id:
                return jsonify({"error": "创建会话失败"}), 500

        payload = json.dumps({
            "app_id": APP_ID,
            "query": query,
            "conversation_id": conversation_id,
            "stream": False
        }, ensure_ascii=False)

        headers = {'Content-Type': 'application/json', 'Authorization': AUTH_TOKEN}
        resp = requests.post(API_URL, headers=headers, data=payload.encode("utf-8"))
        resp.encoding = "utf-8"
        result = resp.json()

        answer_raw = result.get("answer", "")
        try:
            answer_parsed = json.loads(answer_raw)
            reply_text = answer_parsed.get("result", "")
        except Exception:
            reply_text = answer_raw or "（未解析到回答）"

        # ✅ 保存对话到用户记录
        user_data = users[username]
        conversations = user_data.setdefault("conversations", [])

        # 如果是新会话则创建记录
        conv = next((c for c in conversations if c["conversation_id"] == conversation_id), None)
        if not conv:
            conv = {
                "conversation_id": conversation_id,
                "first_question": query,
                "messages": []
            }
            conversations.append(conv)

        conv["messages"].append({"role": "user", "content": query})
        conv["messages"].append({"role": "bot", "content": reply_text})
        save_users(users)

        return jsonify({
            "reply": reply_text,
            "conversation_id": conversation_id
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==============================
# 📜 获取用户的历史对话列表
# ==============================
@app.route('/api/history/<username>', methods=['GET'])
def get_history(username):
    users = load_users()
    if username not in users:
        return jsonify([])
    conversations = users[username].get("conversations", [])
    # 只返回简要信息（会话ID + 第一条问题）
    return jsonify([
        {"conversation_id": c["conversation_id"], "first_question": c["first_question"]}
        for c in conversations
    ])


# ==============================
# 📜 获取单个会话的完整记录
# ==============================
@app.route('/api/conversation/<username>/<conversation_id>', methods=['GET'])
def get_conversation(username, conversation_id):
    users = load_users()
    if username not in users:
        return jsonify({"error": "用户不存在"}), 404

    conversations = users[username].get("conversations", [])
    conv = next((c for c in conversations if c["conversation_id"] == conversation_id), None)
    if not conv:
        return jsonify({"error": "会话不存在"}), 404

    return jsonify(conv["messages"])


# ==============================
# 🚀 启动服务
# ==============================
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)
