from flask import Flask, render_template, request, redirect
import sqlite3
from matching_claims import matching_bp

app = Flask(__name__)
app.register_blueprint(matching_bp)

def get_db_connection():
    conn = sqlite3.connect("lost_found.db")
    conn.row_factory = sqlite3.Row
    return conn


@app.route("/")
def home():
    return "MMU Lost & Found System"


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


if __name__ == "__main__":
    app.run(debug=True)
    