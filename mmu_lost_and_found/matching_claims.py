from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, current_app
import sqlite3
import os
import re
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename


matching_bp = Blueprint(
    "matching",
    __name__,
    template_folder="matching_templates"
)


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "lost_found.db")


CATEGORIES = [
    "Wallet",
    "Phone",
    "Laptop",
    "Bag",
    "Keys",
    "Student Card",
    "Earphones",
    "Other"
]

LOST_STATUSES = [
    "Lost",
    "Found",
    "Claimed"
]

ALLOWED_IMAGES = {
    "png",
    "jpg",
    "jpeg",
    "gif",
    "webp"
}

EMAIL_PATTERN = re.compile(
    r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
)

MATCH_THRESHOLD = 40


@matching_bp.record_once
def setup(state):

    app = state.app

    if not app.secret_key:
        app.secret_key = "mmu-lost-and-found-dev-key"

    upload_folder = app.config.get("UPLOAD_FOLDER")

    if not upload_folder:
        upload_folder = os.path.join(
            BASE_DIR,
            "static",
            "uploads"
        )

    app.config["UPLOAD_FOLDER"] = upload_folder

    os.makedirs(upload_folder, exist_ok=True)


def get_db():

    connection = sqlite3.connect(DATABASE)

    connection.row_factory = sqlite3.Row

    return connection


def validate_non_empty(*fields):

    for field in fields:

        if field is None or str(field).strip() == "":
            return False

    return True


def is_valid_date(value):

    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True

    except (TypeError, ValueError):
        return False


def save_image(image):

    if not image or not image.filename:
        return ""

    filename = secure_filename(image.filename)

    filename = uuid.uuid4().hex[:8] + "_" + filename

    image.save(
        os.path.join(
            current_app.config["UPLOAD_FOLDER"],
            filename
        )
    )

    return filename


def has_allowed_extension(image):

    if not image or not image.filename:
        return True

    extension = image.filename.rsplit(".", 1)[-1].lower()

    return extension in ALLOWED_IMAGES


def words(text):

    return set(
        re.findall(
            r"[a-z0-9]+",
            text.lower()
        )
    )


def calculate_confidence(lost, found):

    score = 0

    lost_name = lost["item_name"].strip().lower()
    found_name = found["item_name"].strip().lower()

    if lost_name == found_name:

        score += 50

    elif lost_name in found_name or found_name in lost_name:

        score += 35

    else:

        lost_words = words(lost_name)
        found_words = words(found_name)

        if lost_words and found_words:

            shared = len(
                lost_words & found_words
            )

            total = len(
                lost_words | found_words
            )

            score += round(
                30 * shared / total
            )

    if lost["category"] == found["category"]:

        score += 30

    lost_location = lost["location"].strip().lower()
    found_location = found["location"].strip().lower()

    if lost_location == found_location:

        score += 20

    elif lost_location in found_location or found_location in lost_location:

        score += 20

    return score


def find_possible_matches(lost, found_items):

    matches = []

    for found in found_items:

        confidence = calculate_confidence(
            lost,
            found
        )

        if confidence >= MATCH_THRESHOLD:

            matches.append({
                "item": found,
                "confidence": confidence
            })

    matches.sort(
        key=lambda match: match["confidence"],
        reverse=True
    )

    return matches


@matching_bp.route("/overview")
def overview():

    connection = get_db()

    stats = {

        "lost": connection.execute(
            "SELECT COUNT(*) FROM lost_items WHERE status = 'Lost'"
        ).fetchone()[0],

        "found": connection.execute(
            "SELECT COUNT(*) FROM found_items WHERE status = 'Found'"
        ).fetchone()[0],

        "claimed": connection.execute(
            "SELECT COUNT(*) FROM found_items WHERE status = 'Claimed'"
        ).fetchone()[0],

        "pending": connection.execute("""
            SELECT COUNT(*)
            FROM claims
            JOIN found_items
            ON claims.found_item_id = found_items.id
            WHERE claims.status = 'Pending'
        """).fetchone()[0]
    }

    recent = connection.execute("""
        SELECT
            'Lost' AS kind,
            id,
            item_name,
            category,
            location,
            date,
            status
        FROM lost_items

        UNION ALL

        SELECT
            'Found' AS kind,
            id,
            item_name,
            category,
            location,
            date,
            status
        FROM found_items

        ORDER BY date DESC, id DESC

        LIMIT 5
    """).fetchall()

    connection.close()

    return render_template(
        "overview.html",
        stats=stats,
        recent=recent
    )


@matching_bp.route("/lost")
def lost_items():

    search = request.args.get(
        "search",
        ""
    ).strip()

    category = request.args.get(
        "category",
        ""
    )

    location = request.args.get(
        "location",
        ""
    ).strip()

    query = """
        SELECT *
        FROM lost_items
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

    connection = get_db()

    items = connection.execute(
        query,
        parameters
    ).fetchall()

    connection.close()

    return render_template(
        "lost.html",
        items=items,
        search=search,
        category=category,
        location=location,
        categories=CATEGORIES,
        statuses=LOST_STATUSES
    )


@matching_bp.route("/lost/add", methods=["POST"])
def add_lost_item():

    item_name = request.form.get(
        "item_name",
        ""
    ).strip()

    description = request.form.get(
        "description",
        ""
    ).strip()

    category = request.form.get(
        "category",
        ""
    )

    location = request.form.get(
        "location",
        ""
    ).strip()

    date = request.form.get(
        "date",
        ""
    )

    image = request.files.get("image")

    if not validate_non_empty(
        item_name,
        description,
        category,
        location,
        date
    ):

        flash(
            "Please fill in all required fields.",
            "error"
        )

        return redirect(
            url_for("matching.lost_items")
            + "#report"
        )

    if category not in CATEGORIES:

        flash(
            "Please choose a valid category.",
            "error"
        )

        return redirect(
            url_for("matching.lost_items")
            + "#report"
        )

    if not is_valid_date(date):

        flash(
            "Please enter a valid date.",
            "error"
        )

        return redirect(
            url_for("matching.lost_items")
            + "#report"
        )

    if not has_allowed_extension(image):

        flash(
            "Image must be a PNG, JPG, GIF or WEBP file.",
            "error"
        )

        return redirect(
            url_for("matching.lost_items")
            + "#report"
        )

    image_filename = save_image(image)

    connection = get_db()

    connection.execute("""
        INSERT INTO lost_items
        (
            item_name,
            description,
            category,
            location,
            date,
            image,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        item_name,
        description,
        category,
        location,
        date,
        image_filename,
        "Lost"
    ))

    connection.commit()

    connection.close()

    flash(
        "Lost item reported. Check 'Possible Matches' to see if it was found.",
        "success"
    )

    return redirect(
        url_for("matching.lost_items")
    )


@matching_bp.route(
    "/lost/status/<int:item_id>",
    methods=["POST"]
)
def update_lost_status(item_id):

    new_status = request.form.get(
        "status",
        ""
    )

    if new_status not in LOST_STATUSES:

        flash(
            "Invalid status.",
            "error"
        )

        return redirect(
            url_for("matching.lost_items")
        )

    connection = get_db()

    connection.execute(
        """
        UPDATE lost_items
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

    flash(
        "Status updated.",
        "success"
    )

    return redirect(
        url_for("matching.lost_items")
    )


@matching_bp.route("/matches")
def view_matches():

    connection = get_db()

    lost_list = connection.execute(
        """
        SELECT *
        FROM lost_items
        WHERE status = 'Lost'
        ORDER BY id DESC
        """
    ).fetchall()

    available_found = connection.execute(
        """
        SELECT *
        FROM found_items
        WHERE status = 'Found'
        """
    ).fetchall()

    connection.close()

    results = []

    for lost in lost_list:

        results.append({
            "lost": lost,
            "matches": find_possible_matches(
                lost,
                available_found
            )
        })

    return render_template(
        "matches.html",
        results=results,
        threshold=MATCH_THRESHOLD
    )


@matching_bp.route(
    "/claim/<int:found_id>",
    methods=["GET", "POST"]
)
def submit_claim(found_id):

    connection = get_db()

    item = connection.execute(
        """
        SELECT *
        FROM found_items
        WHERE id = ?
        """,
        (found_id,)
    ).fetchone()

    if item is None:

        connection.close()

        abort(404)

    if item["status"] != "Found":

        connection.close()

        flash(
            "This item is no longer available to claim.",
            "error"
        )

        return redirect(
            url_for("matching.view_matches")
        )

    form = {
        "claimant_name": "",
        "claimant_email": "",
        "message": ""
    }

    if request.method == "POST":

        form["claimant_name"] = request.form.get(
            "claimant_name",
            ""
        ).strip()

        form["claimant_email"] = request.form.get(
            "claimant_email",
            ""
        ).strip()

        form["message"] = request.form.get(
            "message",
            ""
        ).strip()

        if not validate_non_empty(
            form["claimant_name"],
            form["claimant_email"]
        ):

            flash(
                "Name and email are required.",
                "error"
            )

        elif not EMAIL_PATTERN.match(
            form["claimant_email"]
        ):

            flash(
                "Please enter a valid email address.",
                "error"
            )

        elif len(form["message"]) > 500:

            flash(
                "Message must be 500 characters or fewer.",
                "error"
            )

        else:

            duplicate = connection.execute(
                """
                SELECT 1
                FROM claims
                WHERE found_item_id = ?
                AND LOWER(claimant_email) = ?
                AND status = 'Pending'
                """,
                (
                    found_id,
                    form["claimant_email"].lower()
                )
            ).fetchone()

            if duplicate:

                flash(
                    "You already have a pending claim for this item.",
                    "error"
                )

            else:

                connection.execute(
                    """
                    INSERT INTO claims
                    (
                        found_item_id,
                        claimant_name,
                        claimant_email,
                        message,
                        status
                    )
                    VALUES (?, ?, ?, ?, 'Pending')
                    """,
                    (
                        found_id,
                        form["claimant_name"],
                        form["claimant_email"],
                        form["message"]
                    )
                )

                connection.commit()

                connection.close()

                flash(
                    "Claim request submitted. Waiting for approval.",
                    "success"
                )

                return redirect(
                    url_for("matching.view_matches")
                )

    connection.close()

    return render_template(
        "claim.html",
        item=item,
        form=form
    )


@matching_bp.route("/claims")
def manage_claims():

    connection = get_db()

    claims = connection.execute(
        """
        SELECT
            claims.id,
            claims.claimant_name,
            claims.claimant_email,
            claims.message,
            claims.status,
            found_items.item_name,
            found_items.category,
            found_items.location
        FROM claims
        JOIN found_items
        ON claims.found_item_id = found_items.id
        ORDER BY
            CASE claims.status
                WHEN 'Pending' THEN 0
                ELSE 1
            END,
            claims.id DESC
        """
    ).fetchall()

    connection.close()

    return render_template(
        "claims.html",
        claims=claims
    )


@matching_bp.route(
    "/claims/<int:claim_id>/<decision>",
    methods=["POST"]
)
def process_claim(claim_id, decision):

    if decision not in ("accept", "reject"):

        abort(400)

    connection = get_db()

    claim = connection.execute(
        """
        SELECT *
        FROM claims
        WHERE id = ?
        """,
        (claim_id,)
    ).fetchone()

    if claim is None:

        connection.close()

        abort(404)

    if claim["status"] != "Pending":

        connection.close()

        flash(
            "This claim has already been processed.",
            "error"
        )

        return redirect(
            url_for("matching.manage_claims")
        )

    if decision == "accept":

        item = connection.execute(
            """
            SELECT status
            FROM found_items
            WHERE id = ?
            """,
            (claim["found_item_id"],)
        ).fetchone()

        if item is None or item["status"] != "Found":

            connection.close()

            flash(
                "This item is no longer available.",
                "error"
            )

            return redirect(
                url_for("matching.manage_claims")
            )

        connection.execute(
            """
            UPDATE claims
            SET status = 'Accepted'
            WHERE id = ?
            """,
            (claim_id,)
        )

        connection.execute(
            """
            UPDATE found_items
            SET status = 'Claimed'
            WHERE id = ?
            """,
            (claim["found_item_id"],)
        )

        connection.execute(
            """
            UPDATE claims
            SET status = 'Rejected'
            WHERE found_item_id = ?
            AND id != ?
            AND status = 'Pending'
            """,
            (
                claim["found_item_id"],
                claim_id
            )
        )

        flash(
            "Claim accepted. The item is now marked as Claimed.",
            "success"
        )

    else:

        connection.execute(
            """
            UPDATE claims
            SET status = 'Rejected'
            WHERE id = ?
            """,
            (claim_id,)
        )

        flash(
            "Claim rejected.",
            "success"
        )

    connection.commit()

    connection.close()

    return redirect(
        url_for("matching.manage_claims")
    )