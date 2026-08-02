from flask import Flask, render_template, jsonify, request, session, redirect
import sqlite3
import os
from auth import auth
import cv2                                         
from auth import auth, decode_base64_image          
from hand_gesture.hand_recognition import HandGestureProcessor   


app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "devices.db")


def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


app.secret_key = "your_secret_key"
app.register_blueprint(auth)
hand_processor = HandGestureProcessor()

@app.route("/")
def home():

    if "user_id" not in session:
        return redirect("/login")

    return render_template("index.html")

    
# GET
@app.route("/api/products", methods=["GET"])
def get_products():

    try:
        page = int(request.args.get("page", 1))
    except ValueError:
        page = 1
    page = max(page, 1)

    try:
        limit = int(request.args.get("limit", 10))
    except ValueError:
        limit = 10
    limit = max(limit, 1)

    category = request.args.get("category", "").strip()
    search = request.args.get("search", "").strip().lower()

    start = (page - 1) * limit
    end = start + limit

    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT
                rowid AS id,
                name AS title,
                img AS src,
                description,
                tags AS category,
                quantity,
                price,
                createdAt
            FROM devices
        """)
        products = [dict(row) for row in cur.fetchall()]
    finally:
        conn.close()

    if category:
        products = [
            product for product in products
            if category.lower() in (product.get("category") or "").lower()
        ]

    if search:
        products = [
            product for product in products
            if search in (product.get("title") or "").lower()
        ]

    return jsonify(products[start:end])

@app.route("/api/hand-command", methods=["POST"])
def hand_command():
    data = request.get_json()

    if not data or "image" not in data:
        return jsonify({"command": "NONE"}), 400

    try:
        rgb_image = decode_base64_image(data["image"])
    except Exception:
        return jsonify({"command": "NONE"}), 400

    frame = cv2.cvtColor(rgb_image, cv2.COLOR_RGB2BGR)
    _, result = hand_processor.process_frame(frame, draw=False)

    return jsonify(result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
    app.run(debug=True)