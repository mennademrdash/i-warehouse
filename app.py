from flask import Flask, render_template, jsonify, request, session, redirect, Response
import os
import json
import time
import threading
import face_recognition
import cv2

from auth import auth, decode_base64_image
from db import get_db, init_db
from hand_gesture.hand_recognition import HandGestureProcessor

camera_source = os.getenv("CAMERA_URL", "0")
try:
    camera_source = int(camera_source)
except ValueError:
    pass

app = Flask(__name__)

PRODUCTS_CACHE_TTL = int(os.getenv("PRODUCTS_CACHE_TTL", "60"))
_products_catalog = []
_catalog_loaded_at = 0.0
_catalog_lock = threading.Lock()
_hand_lock = threading.Lock()
_hand_processor = None


app.secret_key = "your_secret_key"
app.register_blueprint(auth)


@app.route("/")
def home():
    if "user_id" not in session:
        return redirect("/login")

    return render_template("index.html")


def _get_hand_processor():
    global _hand_processor
    if _hand_processor is None:
        with _hand_lock:
            if _hand_processor is None:
                _hand_processor = HandGestureProcessor()
    return _hand_processor


def _load_products_catalog():
    global _products_catalog, _catalog_loaded_at
    with get_db() as conn:
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
            ORDER BY rowid
        """)
        _products_catalog = [dict(row) for row in cur.fetchall()]
    _catalog_loaded_at = time.time()


def _fetch_products(page, limit, category, search):
    if not _products_catalog or time.time() - _catalog_loaded_at >= PRODUCTS_CACHE_TTL:
        with _catalog_lock:
            if not _products_catalog or time.time() - _catalog_loaded_at >= PRODUCTS_CACHE_TTL:
                _load_products_catalog()

    products = _products_catalog

    if category:
        needle = category.lower()
        products = [
            product for product in products
            if needle in (product.get("category") or "").lower()
        ]

    if search:
        needle = search.lower()
        products = [
            product for product in products
            if needle in (product.get("title") or "").lower()
        ]

    offset = (page - 1) * limit
    return products[offset:offset + limit]


init_db()
_load_products_catalog()


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
    limit = min(max(limit, 1), 100)

    category = request.args.get("category", "").strip()
    search = request.args.get("search", "").strip()

    products = _fetch_products(page, limit, category, search)
    response = jsonify(products)
    response.headers["Cache-Control"] = f"public, max-age={PRODUCTS_CACHE_TTL}"
    return response

#> API endpoint byesta2bel image mn Frontend.
@app.route("/api/hand-command", methods=["POST"])
def hand_command():
    #By2ra JSON el gay mn JavaScript.
    data = request.get_json()

    if not data or "image" not in data:
        return jsonify({"command": "NONE"}), 400

    try:
        # By7awel Base64 image
        #le image 72e2ya.
        rgb_image = decode_base64_image(data["image"])
    except Exception:
        return jsonify({"command": "NONE"}), 400

    frame = cv2.cvtColor(rgb_image, cv2.COLOR_RGB2BGR)

    with _hand_lock:
        _, result = _get_hand_processor().process_frame(frame, draw=False)

    return jsonify(result)


def generate_frames():
    #Function mas2oola 3an live camera stream.
    cap = cv2.VideoCapture(camera_source)
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        ret2, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        #Da howa elli by5alli el video live.
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

#Lamma el browser yefta7:
@app.route("/video_feed")
# Da format by5alli el browser ye3rd video live frame by frame
def video_feed():
    return Response(generate_frames(),
                     mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route("/settings")
def settings():

    if "user_id" not in session:
        return redirect("/login")

    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT face_encoding FROM users WHERE id = ?",
            (session["user_id"],)
        )
        face = cur.fetchone()

    face_enabled = bool(face and face["face_encoding"])

    return render_template(
        "settings.html",
        face_enabled=face_enabled
    )
@app.route("/api/settings/face", methods=["POST"])
def save_face():

    if "user_id" not in session:
        return jsonify({
            "success": False,
            "message": "Not logged in"
        }), 401

    data = request.get_json()

    if not data or "image" not in data:
        return jsonify({
            "success": False,
            "message": "No image received"
        }), 400

    try:
        rgb_image = decode_base64_image(data["image"])

        face_locations = face_recognition.face_locations(rgb_image)

        if not face_locations:
            return jsonify({
                "success": False,
                "message": "No face detected"
            }), 400

        encodings = face_recognition.face_encodings(
            rgb_image,
            face_locations
        )

        if not encodings:
            return jsonify({
                "success": False,
                "message": "Could not encode face"
            }), 400

        face_encoding = encodings[0]

        # Convert numpy array to JSON string
        face_encoding_json = json.dumps(face_encoding.tolist())

        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE users
                SET face_encoding = ?
                WHERE id = ?
                """,
                (
                    face_encoding_json,
                    session["user_id"]
                )
            )
            conn.commit()

        return jsonify({
            "success": True,
            "message": "Face saved successfully"
        })

    except Exception as e:
        print("Face save error:", e)

        return jsonify({
            "success": False,
            "message": "Failed to save face"
        }), 500
        
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        threaded=True
    )