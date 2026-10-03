from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import os
import threading
import webbrowser
from werkzeug.utils import secure_filename
from werkzeug.serving import is_running_from_reloader

from matching_claims import matching_bp


app = Flask(__name__)

# Register Member 3 matching system
app.register_blueprint(matching_bp)


# Database
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "lost_found.db")


# Upload folder for found item images
UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# Connect to database
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# =========================
# DASHBOARD
# =========================

@app.route("/")
def dashboard():
    return render_template("dashboard.html")


# =========================
# YOUR LOST ITEM SYSTEM
# =========================

@app.route("/lost-items")
def lost_items():

    conn = get_db_connection()

    items = conn.execute(
        "SELECT * FROM lost_items"
    ).fetchall()

    conn.close()

    return render_template("lost_items.html", items=items)


@app.route("/report-lost", methods=["GET", "POST"])
def report_lost():

    if request.method == "POST":

        item_name = request.form["item_name"]
        description = request.form["description"]
        category = request.form["category"]
        location = request.form["location"]
        date = request.form["date"]

        conn = get_db_connection()

        conn.execute("""
            INSERT INTO lost_items
            (item_name, description, category, location, date, image, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            item_name,
            description,
            category,
            location,
            date,
            "",
            "Lost"
        ))

        conn.commit()
        conn.close()

        return redirect("/lost-items")

    return render_template("report_lost.html")


@app.route("/delete-lost/<int:item_id>")
def delete_lost(item_id):

    conn = get_db_connection()

    conn.execute(
        "DELETE FROM lost_items WHERE id = ?",
        (item_id,)
    )

    conn.commit()
    conn.close()

    return redirect("/lost-items")


@app.route("/edit-lost/<int:item_id>", methods=["GET", "POST"])
def edit_lost(item_id):

    conn = get_db_connection()

    if request.method == "POST":

        item_name = request.form["item_name"]
        description = request.form["description"]
        category = request.form["category"]
        location = request.form["location"]
        date = request.form["date"]

        conn.execute("""
            UPDATE lost_items
            SET item_name = ?,
                description = ?,
                category = ?,
                location = ?,
                date = ?
            WHERE id = ?
        """, (
            item_name,
            description,
            category,
            location,
            date,
            item_id
        ))

        conn.commit()
        conn.close()

        return redirect("/lost-items")

    item = conn.execute(
        "SELECT * FROM lost_items WHERE id = ?",
        (item_id,)
    ).fetchone()

    conn.close()

    return render_template("edit_lost.html", item=item)


# =========================
# HAMRESH FOUND ITEM SYSTEM
# =========================

@app.route("/report")
def report_item():
    return render_template("report.html")


@app.route("/found/add", methods=["POST"])
def add_found_item():

    item_name = request.form["item_name"]
    description = request.form["description"]
    category = request.form["category"]
    location = request.form["location"]
    date = request.form["date"]

    image = request.files.get("image")

    image_filename = ""

    if image and image.filename:

        image_filename = secure_filename(image.filename)

        image.save(
            os.path.join(
                app.config["UPLOAD_FOLDER"],
                image_filename
            )
        )

    connection = get_db_connection()

    connection.execute("""
        INSERT INTO found_items
        (item_name, description, category, location, date, image, status)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        item_name,
        description,
        category,
        location,
        date,
        image_filename,
        "Found"
    ))

    connection.commit()
    connection.close()

    return redirect(url_for("found_items"))


@app.route("/found")
def found_items():

    search = request.args.get("search", "")
    category = request.args.get("category", "")
    location = request.args.get("location", "")

    connection = get_db_connection()

    query = """
        SELECT * FROM found_items
        WHERE 1=1
    """

    parameters = []

    if search:

        query += """
            AND (
                item_name LIKE ?
                OR description LIKE ?
            )
        """

        parameters.extend([
            "%" + search + "%",
            "%" + search + "%"
        ])

    if category:

        query += " AND category = ?"

        parameters.append(category)

    if location:

        query += " AND location LIKE ?"

        parameters.append(
            "%" + location + "%"
        )

    query += " ORDER BY id DESC"

    items = connection.execute(
        query,
        parameters
    ).fetchall()

    connection.close()

    return render_template(
        "found.html",
        items=items,
        search=search,
        category=category,
        location=location
    )


# =========================
# SEARCH FOUND ITEMS
# =========================

@app.route("/search")
def search_items():

    search = request.args.get("search", "")
    category = request.args.get("category", "")
    location = request.args.get("location", "")

    connection = get_db_connection()

    query = """
        SELECT * FROM found_items
        WHERE 1=1
    """

    parameters = []

    if search:

        query += """
            AND (
                item_name LIKE ?
                OR description LIKE ?
            )
        """

        parameters.extend([
            "%" + search + "%",
            "%" + search + "%"
        ])

    if category:

        query += " AND category = ?"

        parameters.append(category)

    if location:

        query += " AND location LIKE ?"

        parameters.append(
            "%" + location + "%"
        )

    query += " ORDER BY id DESC"

    items = connection.execute(
        query,
        parameters
    ).fetchall()

    connection.close()

    return render_template(
        "search.html",
        items=items,
        search=search,
        category=category,
        location=location
    )


# =========================
# MANAGE FOUND ITEMS
# =========================

@app.route("/manage")
def manage_items():

    connection = get_db_connection()

    items = connection.execute("""
        SELECT * FROM found_items
        ORDER BY id DESC
    """).fetchall()

    connection.close()

    return render_template(
        "manage.html",
        items=items
    )


@app.route("/found/delete/<int:item_id>", methods=["POST"])
def delete_found_item(item_id):

    connection = get_db_connection()

    item = connection.execute(
        "SELECT image FROM found_items WHERE id = ?",
        (item_id,)
    ).fetchone()

    connection.execute(
        "DELETE FROM found_items WHERE id = ?",
        (item_id,)
    )

    connection.commit()
    connection.close()

    # Delete image from uploads folder
    if item and item["image"]:

        image_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            item["image"]
        )

        if os.path.exists(image_path):
            os.remove(image_path)

    return redirect(url_for("manage_items"))


@app.route("/found/status/<int:item_id>", methods=["POST"])
def update_found_status(item_id):

    new_status = request.form["status"]

    connection = get_db_connection()

    connection.execute(
        """
        UPDATE found_items
        SET status = ?
        WHERE id = ?
        """,
        (
            new_status,
            item_id
        )
    )

    connection.commit()
    connection.close()

    return redirect(url_for("manage_items"))


# =========================
# START FLASK
# =========================

if __name__ == "__main__":
    debug = True
    if not debug or is_running_from_reloader():
        threading.Timer(
            1.0,
            lambda: webbrowser.open("http://127.0.0.1:5000")
        ).start()
    app.run(debug=debug)