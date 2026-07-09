from flask import Flask, render_template, jsonify, request
import json    ##Import Flask tools (app + html + json + request)

app = Flask(__name__) ##Create Flask app


# Main Page
@app.route("/")  ##Home URL
def home():
    return render_template("index.html") ##Open index.html


# GET
@app.route("/api/products", methods=["GET"])    ##GET API for products
def get_products():   ##Get products function
    page = int(request.args.get("page", 1)) ##Get page number (default = 1)
    limit = int(request.args.get("limit", 10)) ##el limit 10 
    category = request.args.get("category") ##Get selected category
    search = request.args.get("search", "").lower()   #Get search text + lowercase

    start = (page - 1) * limit      #elpage eeli hia 0 -1 *10= 
    end = start + limit

    with open("products.json", "r") as file:       ##Open JSON file (Read mode)
        products = json.load(file)

    # Filter by category
    if category:
        products = [  #Create filtered list
            product for product in products
            if product.get("category") == category #Keep same category only
        ]

    # Filter by search
    if search: #Check search text
        products = [
            product for product in products
            if search in product.get("title", "").lower() #(Case-insensitive).
        ]
###big o optmaztion 
    return jsonify(products[start:end])

if __name__ == "__main__":
    app.run(debug=True)
    

    