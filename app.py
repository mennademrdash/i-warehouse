from flask import Flask, render_template, jsonify, request
import json

app = Flask(__name__)


# Main Page
@app.route("/")
def home():
    return render_template("index.html")


# GET
@app.route("/api/products", methods=["GET"])
def get_products():
    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 10))
    category = request.args.get("category")
    search = request.args.get("search", "").lower()

    start = (page - 1) * limit
    end = start + limit

    with open("products.json", "r") as file:
        products = json.load(file)

    # Filter by category
    if category:
        products = [
            product for product in products
            if product.get("category") == category
        ]

    # Filter by search
    if search:
        products = [
            product for product in products
            if search in product.get("title", "").lower()
        ]

    return jsonify(products[start:end])

if __name__ == "__main__":
    app.run(debug=True)