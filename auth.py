from flask import Blueprint, render_template, request, redirect, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os

auth = Blueprint("auth", __name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.path.join(BASE_DIR, "devices.db")


def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


@auth.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form["username"].strip()
        email = request.form["email"].strip()
        password = request.form["password"]

        # Password validation
        if len(password) < 8:
            flash("Password must be at least 8 characters long.", "error")
            return render_template("register.html")

        conn = get_db()
        cur = conn.cursor()

        # Check username
        cur.execute("SELECT id FROM users WHERE username = ?", (username,))
        if cur.fetchone():
            conn.close()
            flash("Username already exists.", "error")
            return render_template("register.html")

        # Check email
        cur.execute("SELECT id FROM users WHERE email = ?", (email,))
        if cur.fetchone():
            conn.close()
            flash("Email already exists.", "error")
            return render_template("register.html")

        hashed_password = generate_password_hash(password)

        cur.execute("""
            INSERT INTO users (username, email, password)
            VALUES (?, ?, ?)
        """, (username, email, hashed_password))

        conn.commit()
        conn.close()

        flash("Account created successfully!", "success")
        return redirect("/login")

    return render_template("register.html")


@auth.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"].strip()
        password = request.form["password"]

        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        )

        user = cur.fetchone()
        conn.close()

        # Debug
        print("========== LOGIN DEBUG ==========")
        print("Email:", email)
        print("User Found:", user)

        if user:
            print("Password Entered:", password)
            print("Password In Database:", user["password"])
            print("Password Match:", check_password_hash(user["password"], password))

        if user and check_password_hash(user["password"], password):

            session["user_id"] = user["id"]
            session["username"] = user["username"]

            print("Login Success!")
            return redirect("/")

        print("Login Failed!")
        flash("Invalid email or password.", "error")

    return render_template("login.html")


@auth.route("/logout")
def logout():
    session.clear()
    return redirect("/login")