from flask import Flask, render_template, jsonify, request
import json
app = Flask(__name__)
# elmain paagee 
@app.route("/")
def home():
    return render_template("index.html")
# GET
@app.route("/api/products", methods=["GET"])
def get_products():
    with open("products.json", "r") as file:
        products = json.load(file)
    return jsonify(products)
# POST
@app.route("/api/products", methods=["POST"])
def add_product():

    new_product = request.json
    with open("products.json", "r") as file:
        products = json.load(file)
    products.append(new_product)
    with open("products.json", "w") as file:
        json.dump(products, file, indent=4)
    return jsonify({"message":"Product Added"}),201
if __name__ == "__main__":
    app.run(debug=True)