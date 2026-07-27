from flask import Flask, render_template, jsonify, request, session, redirect
import sqlite3
import os
from auth import auth

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "devices.db")


def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


app.secret_key = "your_secret_key"
app.register_blueprint(auth)


@app.route("/")
def home():

    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT quantity FROM devices")
        rows = cur.fetchall()
    finally:
        conn.close()

    quantities = [row["quantity"] or 0 for row in rows]
    total_products = len(quantities)

    # Dynamic threshold based on the data itself
    if quantities:
        average_quantity = sum(quantities) / len(quantities)
    else:
        average_quantity = 0

    low_stock_threshold = average_quantity * 0.5 

    available = 0
    low_stock = 0
    out_of_stock = 0

    for quantity in quantities:
        if quantity == 0:
            out_of_stock += 1
        elif quantity <= low_stock_threshold:
            low_stock += 1
        else:
            available += 1

    return render_template(
        "index.html",
        total_products=total_products,
        available=available,
        low_stock=low_stock,
        out_of_stock=out_of_stock,
    )


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


if __name__ == "__main__":
    app.run(debug=True)