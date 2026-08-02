from flask import Blueprint, render_template, request, redirect, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import cv2
import face_recognition
import json
import numpy as np
import base64

auth = Blueprint("auth", __name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "devices.db")


def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_face_encoding_column():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(users)")
    columns = [row["name"] for row in cur.fetchall()]
    if "face_encoding" not in columns:
        cur.execute("ALTER TABLE users ADD COLUMN face_encoding TEXT")
        conn.commit()
        print("✅ The face_encoding column has been added to the users table")
    conn.close()


ensure_face_encoding_column()  


def capture_and_encode_face():
   
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        return None

    while True:
        ret, frame = cap.read()

        if not ret:
            break

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb)

        cv2.imshow("Capture Face - Press SPACE", frame)
        key = cv2.waitKey(1)

        if key == 32:
            if len(face_locations) != 1:
                cap.release()
                cv2.destroyAllWindows()
                return None

            encoding = face_recognition.face_encodings(rgb, face_locations)[0]
            cap.release()
            cv2.destroyAllWindows()
            return json.dumps(encoding.tolist())

        if key == 27:
            break

    cap.release()
    cv2.destroyAllWindows()
    return None


def decode_base64_image(base64_string):
    header, encoded = base64_string.split(",", 1)
    binary_data = base64.b64decode(encoded)
    np_arr = np.frombuffer(binary_data, dtype=np.uint8)
    image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    return rgb_image


@auth.route("/api/detect-face", methods=["POST"])
def detect_face():
    data = request.get_json()

    if not data or "image" not in data:
        return jsonify({"success": False, "message": "No image received"}), 400

    try:
        rgb_image = decode_base64_image(data["image"])
    except Exception:
        return jsonify({"success": False, "message": "Invalid image"}), 400

    face_locations = face_recognition.face_locations(rgb_image)

    if len(face_locations) != 1:
        return jsonify({
            "success": False,
"message": "Make sure only one face is clearly visible to the camera."        })

    encoding = face_recognition.face_encodings(rgb_image, face_locations)[0]

    return jsonify({
        "success": True,
        "encoding": encoding.tolist()
    })


@auth.route("/api/face-login", methods=["POST"])
def face_login():
    data = request.get_json()

    if not data or "image" not in data:
        return jsonify({"success": False, "message": "No image received"}), 400

    try:
        rgb_image = decode_base64_image(data["image"])
    except Exception:
        return jsonify({"success": False, "message": "Invalid image"}), 400

    face_locations = face_recognition.face_locations(rgb_image)

    if len(face_locations) != 1:
        return jsonify({"success": False, "message": "Only one face must be clearly visible to the camera"})

    unknown_encoding = face_recognition.face_encodings(rgb_image, face_locations)[0]

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, username, face_encoding FROM users WHERE face_encoding IS NOT NULL")
    users = cur.fetchall()
    conn.close()

    best_user = None
    best_distance = 1.0

    for user in users:
        try:
            known_encoding = np.array(json.loads(user["face_encoding"]))
        except Exception:
            continue

        distance = face_recognition.face_distance([known_encoding], unknown_encoding)[0]

        if distance < best_distance:
            best_distance = distance
            best_user = user

    TOLERANCE = 0.6

    if best_user is not None and best_distance <= TOLERANCE:
        session["user_id"] = best_user["id"]
        session["username"] = best_user["username"]
        return jsonify({"success": True, "redirect": "/"})

        return jsonify({"success": False, "message": "Face not recognized; try manual entry."})

@auth.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form["username"].strip()
        email = request.form["email"].strip()
        password = request.form["password"]
        face_encoding = request.form.get("face_encoding", "").strip()   

        if len(password) < 8:
            flash("Password must be at least 8 characters long.", "error")
            return render_template("register.html")

        conn = get_db()
        cur = conn.cursor()

        cur.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cur.fetchone():
            conn.close()
            flash("Username already exists.", "error")
            return render_template("register.html")

        cur.execute("SELECT id FROM users WHERE email = ?", (email,))
        if cur.fetchone():
            conn.close()
            flash("Email already exists.", "error")
            return render_template("register.html")

        hashed_password = generate_password_hash(password)

        cur.execute("""
            INSERT INTO users (username, email, password, face_encoding)
            VALUES (?, ?, ?, ?)
        """, (username, email, hashed_password, face_encoding if face_encoding else None))   

        conn.commit()
        conn.close()

        flash("Account created successfully!", "success")
        return redirect("/login")

    return render_template("register.html")


@auth.route("/test-camera")
def test_camera():

    face_encoding = capture_and_encode_face()

    if face_encoding is None:
        return "No face detected"

    return "Face captured successfully!"


@auth.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"].strip()
        password = request.form["password"]

        conn = get_db()
        cur = conn.cursor()

        cur.execute("SELECT * FROM users WHERE email = ?", (email,))
        user = cur.fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect("/")

        flash("Invalid email or password.", "error")

    return render_template("login.html")


@auth.route("/logout")
def logout():
    session.clear()
    return redirect("/login")