from flask import (
    Flask,
    render_template,
    jsonify,
    request,
    session,
    redirect,
    Response
)

import os
import json
import time
import threading
import logging
from functools import wraps
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import face_recognition
import cv2
import paho.mqtt.client as mqtt

from config import Config
from auth import auth, decode_base64_image
from db import (
    get_db,
    init_db,
    create_order,
    get_order,
    update_order_status,
    get_active_order,
    update_inventory,
)
from hand_gesture.hand_recognition import HandGestureProcessor

# ENVIRONMENT


# CAMERA CONFIGURATION

camera_source = os.getenv("CAMERA_URL", "0")

try:
    camera_source = int(camera_source)
except ValueError:
    pass


CAMERA_RETRY_DELAY = float(
    os.getenv("CAMERA_RETRY_DELAY", "2")
)

MAX_CAMERA_RETRIES = int(
    os.getenv("MAX_CAMERA_RETRIES", "5")
)


# MQTT / HANDOFF CONFIGURATION

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "frigate/events")

PICKUP_ZONE = os.getenv("PICKUP_ZONE", "pickup_zone")
DROPOFF_ZONE = os.getenv("DROPOFF_ZONE", "dropoff_zone")


# FLASK APPLICATION

app = Flask(__name__)
app.config.from_object(Config)

#LIMIT

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["200 per minute"],
    storage_uri="memory://"
)
# LOGGING
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

logger = logging.getLogger(__name__)


# SECURITY CONFIGURATION

SECRET_KEY = os.getenv("SECRET_KEY")

if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY is not configured. "
        "Please add SECRET_KEY to your .env file."
    )


app.config.update(

    # Application secret
    SECRET_KEY=SECRET_KEY,

    # Session Security

    # JavaScript cannot access session cookie
    SESSION_COOKIE_HTTPONLY=True,

    # Only send cookie over HTTPS when enabled
    SESSION_COOKIE_SECURE=(
        os.getenv(
            "SESSION_COOKIE_SECURE",
            "false"
        ).lower() == "true"
    ),

    # Helps protect against CSRF
    SESSION_COOKIE_SAMESITE=os.getenv(
        "SESSION_COOKIE_SAMESITE",
        "Lax"
    ),

    # Refresh session expiration
    SESSION_REFRESH_EACH_REQUEST=True,

    # Request Security

    # Maximum request size.
    # Important because the application receives Base64 images.
    MAX_CONTENT_LENGTH=int(
        os.getenv(
            "MAX_CONTENT_LENGTH_MB",
            "5"
        )
    ) * 1024 * 1024,
)


# SECURITY HEADERS

@app.after_request
def add_security_headers(response):

    # Prevent MIME type sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"

    # Prevent clickjacking
    response.headers["X-Frame-Options"] = "SAMEORIGIN"

    # Control referrer information
    response.headers["Referrer-Policy"] = (
        "strict-origin-when-cross-origin"
    )

    # Limit browser permissions
    response.headers["Permissions-Policy"] = (
        "camera=(self), "
        "microphone=(), "
        "geolocation=()"
    )

    return response


# AUTHENTICATION HELPERS

def is_authenticated():
    """
    Check whether the current user is authenticated.
    """

    return "user_id" in session


def login_required_api(func):
    """
    Protect API endpoints.

    Unauthenticated requests receive HTTP 401.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):

        if not is_authenticated():

            return jsonify({
                "success": False,
                "message": "Authentication required"
            }), 401

        return func(*args, **kwargs)

    return wrapper


def login_required_page(func):
    """
    Protect normal HTML pages.

    Unauthenticated users are redirected to login.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):

        if not is_authenticated():

            return redirect("/login")

        return func(*args, **kwargs)

    return wrapper


# APPLICATION REGISTRATION

app.register_blueprint(auth)


# PRODUCTS CACHE

PRODUCTS_CACHE_TTL = int(
    os.getenv(
        "PRODUCTS_CACHE_TTL",
        "60"
    )
)

_products_catalog = []

_catalog_loaded_at = 0.0

_catalog_lock = threading.Lock()

_hand_lock = threading.Lock()

_hand_processor = None


# MQTT LISTENER (Frigate handoff events)
#
# Runs as a background thread started once at process startup (see
# APPLICATION START at the bottom of this file), not inside a route.
# It stays subscribed for the lifetime of the process and updates
# order status directly through db.py when a relevant zone event
# arrives.

def on_mqtt_connect(client, userdata, flags, reason_code, properties=None):

    if reason_code == 0:

        logger.info(
            "Connected to MQTT broker at %s:%s",
            MQTT_BROKER,
            MQTT_PORT
        )

        client.subscribe(MQTT_TOPIC)

    else:

        logger.error(
            "MQTT connection failed, reason_code=%s",
            reason_code
        )


def on_mqtt_message(client, userdata, msg):

    try:

        payload = json.loads(msg.payload.decode("utf-8"))

    except (json.JSONDecodeError, UnicodeDecodeError):

        logger.warning(
            "Received non-JSON MQTT payload on %s, ignoring",
            msg.topic
        )

        return

    # Only handle a fresh detection, not update/end events,
    # to avoid processing the same zone entry multiple times.
    if payload.get("type") != "new":
        return

    after = payload.get("after", {})

    if after.get("label") != "person":
        return

    zones = after.get("current_zones", [])
    camera = after.get("camera")

    if PICKUP_ZONE in zones:
        _handle_pickup(camera)

    elif DROPOFF_ZONE in zones:
        _handle_arrival(camera)


def _handle_pickup(camera):

    order = get_active_order(status="PENDING")

    if order is None:

        logger.warning(
            "Pickup event on %s but no PENDING order found - ignoring",
            camera
        )

        return

    update_order_status(order["id"], "IN_TRANSIT")

    logger.info(
        "Order %s -> IN_TRANSIT (pickup detected on %s)",
        order["id"],
        camera
    )


def _handle_arrival(camera):

    order = get_active_order(status="IN_TRANSIT")

    if order is None:

        logger.warning(
            "Arrival event on %s but no IN_TRANSIT order found - ignoring",
            camera
        )

        return

    update_order_status(order["id"], "COMPLETED")

    update_inventory(order["device_name"], order["qty"])

    logger.info(
        "Order %s -> COMPLETED, inventory updated (arrival on %s)",
        order["id"],
        camera
    )


def start_mqtt_listener():
    """Blocking call -- must run in its own thread."""

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2
    )

    client.on_connect = on_mqtt_connect
    client.on_message = on_mqtt_message

    try:

        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        client.loop_forever()

    except Exception:

        logger.exception(
            "MQTT listener crashed, handoff tracking is now offline"
        )


# HEALTH CHECK

@app.route(
    "/health",
    methods=["GET"]
)
def health_check():

    try:

        # Test database connection
        with get_db() as conn:

            conn.execute(
                "SELECT 1"
            )

        return jsonify({
            "status": "healthy",
            "database": "connected",
            "camera": "configured"
        }), 200

    except Exception:

        logger.exception(
            "Health check failed"
        )

        return jsonify({
            "status": "unhealthy",
            "database": "unavailable"
        }), 503


# HOME

@app.route("/")
@login_required_page
def home():

    return render_template(
        "index.html"
    )


# HAND GESTURE PROCESSOR

def _get_hand_processor():

    global _hand_processor

    if _hand_processor is None:

        with _hand_lock:

            if _hand_processor is None:

                _hand_processor = HandGestureProcessor()

    return _hand_processor


# LOAD PRODUCTS

def _load_products_catalog():

    global _products_catalog
    global _catalog_loaded_at

    with get_db() as conn:

        cur = conn.cursor()

        cur.execute(
            """
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
            """
        )

        _products_catalog = [
            dict(row)
            for row in cur.fetchall()
        ]

    _catalog_loaded_at = time.time()


# FETCH PRODUCTS

def _fetch_products(
    page,
    limit,
    category,
    search
):

    global _products_catalog

    # Reload cache when expired
    if (
        not _products_catalog
        or
        time.time() - _catalog_loaded_at
        >= PRODUCTS_CACHE_TTL
    ):

        with _catalog_lock:

            if (
                not _products_catalog
                or
                time.time() - _catalog_loaded_at
                >= PRODUCTS_CACHE_TTL
            ):

                _load_products_catalog()

    products = _products_catalog

    # Category filtering

    if category:

        needle = category.lower()

        products = [
            product
            for product in products
            if needle in (
                product.get("category") or ""
            ).lower()
        ]

    # Search filtering

    if search:

        needle = search.lower()

        products = [
            product
            for product in products
            if needle in (
                product.get("title") or ""
            ).lower()
        ]

    # Pagination

    offset = (page - 1) * limit

    return products[
        offset:offset + limit
    ]


# DATABASE INITIALIZATION

init_db()

_load_products_catalog()


# PRODUCTS API

@app.route(
    "/api/products",
    methods=["GET"]
)
@login_required_api
def get_products():

    # Page

    try:

        page = int(
            request.args.get(
                "page",
                1
            )
        )

    except (ValueError, TypeError):

        page = 1

    page = max(page, 1)

    # Limit

    try:

        limit = int(
            request.args.get(
                "limit",
                10
            )
        )

    except (ValueError, TypeError):

        limit = 10

    # Prevent huge responses
    limit = min(
        max(limit, 1),
        100
    )

    # Filters

    category = request.args.get(
        "category",
        ""
    ).strip()

    search = request.args.get(
        "search",
        ""
    ).strip()

    # Fetch

    products = _fetch_products(
        page,
        limit,
        category,
        search
    )

    response = jsonify(products)

    # Private browser caching
    # because products are accessible only to authenticated users.
    response.headers["Cache-Control"] = (
        f"private, max-age={PRODUCTS_CACHE_TTL}"
    )

    return response


# ORDERS API (delivery pickup and handoff)

@app.route(
    "/api/orders",
    methods=["POST"]
)
@login_required_api
@limiter.limit("30 per minute")
def create_order_route():

    data = request.get_json(silent=True) or {}

    device_name = (data.get("device_name") or "").strip()
    qty = data.get("qty")

    if not device_name:

        return jsonify({
            "success": False,
            "message": "device_name is required"
        }), 400

    if not isinstance(qty, int) or qty <= 0:

        return jsonify({
            "success": False,
            "message": "qty must be a positive integer"
        }), 400

    order_id = create_order(device_name, qty)

    logger.info(
        "Order %s created: %s x%s",
        order_id,
        device_name,
        qty
    )

    return jsonify({
        "success": True,
        "order_id": order_id,
        "status": "PENDING"
    }), 201


@app.route(
    "/api/orders/<int:order_id>",
    methods=["GET"]
)
@login_required_api
def get_order_route(order_id):

    order = get_order(order_id)

    if order is None:

        return jsonify({
            "success": False,
            "message": "Order not found"
        }), 404

    return jsonify({
        "success": True,
        "order": order
    })


# HAND COMMAND API
@app.route(
    "/api/hand-command",
    methods=["POST"]
)
@login_required_api
@limiter.limit("30 per minute")
def hand_command():

    # Safely parse JSON
    data = request.get_json(
        silent=True
    )

    if not data or "image" not in data:

        return jsonify({
            "success": False,
            "command": "NONE",
            "message": "Invalid request"
        }), 400

    # Decode image

    try:

        rgb_image = decode_base64_image(
            data["image"]
        )

    except Exception:

        return jsonify({
            "success": False,
            "command": "NONE",
            "message": "Invalid image"
        }), 400

    # Process gesture

    try:

        frame = cv2.cvtColor(
            rgb_image,
            cv2.COLOR_RGB2BGR
        )

        with _hand_lock:

            _, result = (
                _get_hand_processor()
                .process_frame(
                    frame,
                    draw=False
                )
            )

        return jsonify(result)

    except Exception:

        app.logger.exception(
            "Hand gesture processing failed"
        )

        return jsonify({
            "success": False,
            "command": "NONE",
            "message": "Unable to process image"
        }), 500


# CAMERA STREAM

def generate_frames():

    cap = None

    for attempt in range(MAX_CAMERA_RETRIES):

        cap = cv2.VideoCapture(camera_source)

        if cap.isOpened():

            app.logger.info(
                "Camera connected successfully"
            )

            break

        app.logger.warning(
            f"Camera connection attempt "
            f"{attempt + 1}/{MAX_CAMERA_RETRIES} failed"
        )

        if cap:
            cap.release()

        time.sleep(CAMERA_RETRY_DELAY)

    else:

        app.logger.error(
            "Unable to connect to camera "
            "after maximum retries"
        )

        return

    try:

        while True:

            ret, frame = cap.read()

            if not ret:

                app.logger.warning(
                    "Camera frame could not be read"
                )

                break

            ret2, buffer = cv2.imencode(
                ".jpg",
                frame
            )

            if not ret2:
                continue

            frame_bytes = buffer.tobytes()

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n"
                + frame_bytes
                + b"\r\n"
            )

    finally:

        cap.release()

        app.logger.info(
            "Camera resource released"
        )


# VIDEO FEED

@app.route(
    "/video_feed"
)
@login_required_api
def video_feed():

    return Response(
        generate_frames(),
        mimetype=(
            "multipart/x-mixed-replace; "
            "boundary=frame"
        )
    )


# SETTINGS PAGE

@app.route(
    "/settings"
)
@login_required_page
def settings():

    with get_db() as conn:

        cur = conn.cursor()

        cur.execute(
            """
            SELECT face_encoding
            FROM users
            WHERE id = ?
            """,
            (
                session["user_id"],
            )
        )

        face = cur.fetchone()

    face_enabled = bool(
        face
        and
        face["face_encoding"]
    )

    return render_template(
        "settings.html",
        face_enabled=face_enabled
    )


# SAVE FACE

@app.route(
    "/api/settings/face",
    methods=["POST"]
)
@login_required_api
@limiter.limit("10 per minute")
def save_face():

    # Parse request

    data = request.get_json(
        silent=True
    )

    if not data or "image" not in data:

        return jsonify({
            "success": False,
            "message": "No image received"
        }), 400

    # Decode image

    try:

        rgb_image = decode_base64_image(
            data["image"]
        )

        # Detect faces

        face_locations = (
            face_recognition
            .face_locations(
                rgb_image
            )
        )

        if not face_locations:

            return jsonify({
                "success": False,
                "message": "No face detected"
            }), 400

        # Encode face

        encodings = (
            face_recognition
            .face_encodings(
                rgb_image,
                face_locations
            )
        )

        if not encodings:

            return jsonify({
                "success": False,
                "message": "Could not encode face"
            }), 400

        face_encoding = encodings[0]

        # Convert NumPy array to JSON

        face_encoding_json = json.dumps(
            face_encoding.tolist()
        )

        # Save face encoding

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

    except Exception:

        # Log technical details server-side
        app.logger.exception(
            "Face save failed"
        )

        # Do NOT expose internal error
        return jsonify({
            "success": False,
            "message": "Failed to save face"
        }), 500


# ERROR HANDLERS

@app.errorhandler(413)
def request_too_large(error):

    return jsonify({
        "success": False,
        "message": "Request is too large"
    }), 413


@app.errorhandler(401)
def unauthorized(error):

    return jsonify({
        "success": False,
        "message": "Authentication required"
    }), 401


@app.errorhandler(403)
def forbidden(error):

    return jsonify({
        "success": False,
        "message": "Access forbidden"
    }), 403


@app.errorhandler(404)
def not_found(error):

    return jsonify({
        "success": False,
        "message": "Resource not found"
    }), 404


@app.errorhandler(500)
def internal_server_error(error):

    app.logger.exception(
        "Internal server error"
    )

    return jsonify({
        "success": False,
        "message": "Internal server error"
    }), 500


# APPLICATION START

if __name__ == "__main__":

    port = int(
        os.getenv(
            "PORT",
            5000
        )
    )

    # Start the MQTT listener once, in a background thread, before the
    # Flask server starts serving requests. daemon=True so it doesn't
    # block process shutdown.
    mqtt_thread = threading.Thread(
        target=start_mqtt_listener,
        daemon=True
    )
    mqtt_thread.start()

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        threaded=True
    )