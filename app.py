from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "smart_complaint_secret"

DATABASE = "complaints.db"


# ---------------- DATABASE ----------------

def get_db():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def create_database():

    db = get_db()

    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'student'
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id TEXT,
            user_id INTEGER,
            category TEXT,
            title TEXT,
            description TEXT,
            location TEXT,
            priority TEXT,
            department TEXT,
            status TEXT DEFAULT 'Pending',
            created_at TEXT,
            due_at TEXT,
            resolved_at TEXT,
            resolution_note TEXT
        )
    """)

    db.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            complaint_id INTEGER,
            rating INTEGER,
            comment TEXT
        )
    """)

    # Create demo admin
    admin = db.execute(
        "SELECT * FROM users WHERE email = ?",
        ("admin@college.com",)
    ).fetchone()

    if not admin:
        db.execute("""
            INSERT INTO users(name,email,password,role)
            VALUES(?,?,?,?)
        """, (
            "College Admin",
            "admin@college.com",
            "admin123",
            "admin"
        ))

    db.commit()
    db.close()


# ---------------- HOME ----------------

@app.route("/")
def home():
    return render_template("index.html")


# ---------------- REGISTER ----------------

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        db = get_db()

        try:

            db.execute("""
                INSERT INTO users(name,email,password)
                VALUES(?,?,?)
            """, (name, email, password))

            db.commit()

            flash("Registration successful! Please login.", "success")

            return redirect(url_for("login"))

        except sqlite3.IntegrityError:

            flash("Email already registered.", "danger")

        db.close()

    return render_template("register.html")


# ---------------- LOGIN ----------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        db = get_db()

        user = db.execute("""
            SELECT * FROM users
            WHERE email = ? AND password = ?
        """, (email, password)).fetchone()

        db.close()

        if user:

            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["role"] = user["role"]

            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "danger")

    return render_template("login.html")


# ---------------- LOGOUT ----------------

@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("home"))


# ---------------- DASHBOARD ----------------

@app.route("/dashboard")
def dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()

    if session["role"] == "admin":

        complaints = db.execute("""
            SELECT complaints.*, users.name
            FROM complaints
            JOIN users
            ON complaints.user_id = users.id
            ORDER BY complaints.id DESC
        """).fetchall()

    else:

        complaints = db.execute("""
            SELECT *
            FROM complaints
            WHERE user_id = ?
            ORDER BY id DESC
        """, (session["user_id"],)).fetchall()

    db.close()

    return render_template(
        "dashboard.html",
        complaints=complaints
    )


# ---------------- NEW COMPLAINT ----------------

@app.route("/new_complaint", methods=["GET", "POST"])
def new_complaint():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":

        category = request.form["category"]
        title = request.form["title"]
        description = request.form["description"]
        location = request.form["location"]
        priority = request.form["priority"]

        # Automatic department assignment

        departments = {

            "Wi-Fi / Internet": "IT Department",

            "Electricity": "Electrical Department",

            "Water": "Maintenance Department",

            "Cleaning": "Housekeeping Department",

            "Classroom / Furniture": "Maintenance Department",

            "Other": "Administration"

        }

        department = departments.get(
            category,
            "Administration"
        )

        # Resolution time

        if priority == "High":

            hours = 6

        elif priority == "Medium":

            hours = 24

        else:

            hours = 48

        now = datetime.now()

        due_time = now + timedelta(hours=hours)

        db = get_db()

        cursor = db.execute("""
            INSERT INTO complaints(
                user_id,
                category,
                title,
                description,
                location,
                priority,
                department,
                status,
                created_at,
                due_at
            )
            VALUES(?,?,?,?,?,?,?,?,?,?)
        """, (
            session["user_id"],
            category,
            title,
            description,
            location,
            priority,
            department,
            "Pending",
            now.strftime("%Y-%m-%d %H:%M:%S"),
            due_time.strftime("%Y-%m-%d %H:%M:%S")
        ))

        complaint_number = cursor.lastrowid

        complaint_code = f"CMP{complaint_number:04d}"

        db.execute("""
            UPDATE complaints
            SET complaint_id = ?
            WHERE id = ?
        """, (complaint_code, complaint_number))

        db.commit()
        db.close()

        flash(
            f"Complaint submitted successfully! ID: {complaint_code}",
            "success"
        )

        return redirect(url_for("dashboard"))

    return render_template("new_complaint.html")


# ---------------- COMPLAINT DETAILS ----------------

@app.route("/complaint/<int:id>")
def complaint(id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()

    data = db.execute("""
        SELECT complaints.*, users.name
        FROM complaints
        JOIN users
        ON complaints.user_id = users.id
        WHERE complaints.id = ?
    """, (id,)).fetchone()

    feedback = db.execute("""
        SELECT *
        FROM feedback
        WHERE complaint_id = ?
    """, (id,)).fetchone()

    db.close()

    return render_template(
        "complaint.html",
        complaint=data,
        feedback=feedback
    )


# ---------------- UPDATE STATUS ----------------

@app.route("/update_status/<int:id>", methods=["POST"])
def update_status(id):

    if session.get("role") != "admin":
        flash("Only admin can update complaints.", "danger")
        return redirect(url_for("dashboard"))

    status = request.form["status"]
    note = request.form["note"]

    resolved_time = None

    if status == "Resolved":

        resolved_time = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    db = get_db()

    db.execute("""
        UPDATE complaints
        SET status = ?,
            resolution_note = ?,
            resolved_at = ?
        WHERE id = ?
    """, (
        status,
        note,
        resolved_time,
        id
    ))

    db.commit()
    db.close()

    flash("Complaint updated successfully.", "success")

    return redirect(url_for("complaint", id=id))


# ---------------- FEEDBACK ----------------

@app.route("/feedback/<int:id>", methods=["POST"])
def feedback(id):

    rating = request.form["rating"]
    comment = request.form["comment"]

    db = get_db()

    db.execute("""
        INSERT INTO feedback(
            complaint_id,
            rating,
            comment
        )
        VALUES(?,?,?)
    """, (
        id,
        rating,
        comment
    ))

    db.commit()
    db.close()

    flash("Thank you for your feedback!", "success")

    return redirect(url_for("complaint", id=id))


# ---------------- ADMIN ANALYTICS ----------------

@app.route("/admin")
def admin():

    if session.get("role") != "admin":

        flash("Admin access only.", "danger")

        return redirect(url_for("dashboard"))

    db = get_db()

    total = db.execute(
        "SELECT COUNT(*) FROM complaints"
    ).fetchone()[0]

    resolved = db.execute(
        "SELECT COUNT(*) FROM complaints WHERE status='Resolved'"
    ).fetchone()[0]

    pending = db.execute(
        "SELECT COUNT(*) FROM complaints WHERE status='Pending'"
    ).fetchone()[0]

    in_progress = db.execute(
        "SELECT COUNT(*) FROM complaints WHERE status='In Progress'"
    ).fetchone()[0]

    categories = db.execute("""
        SELECT category, COUNT(*) as total
        FROM complaints
        GROUP BY category
        ORDER BY total DESC
    """).fetchall()

    locations = db.execute("""
        SELECT location, COUNT(*) as total
        FROM complaints
        GROUP BY location
        ORDER BY total DESC
        LIMIT 5
    """).fetchall()

    db.close()

    return render_template(
        "admin.html",
        total=total,
        resolved=resolved,
        pending=pending,
        in_progress=in_progress,
        categories=categories,
        locations=locations
    )


# ---------------- RUN APPLICATION ----------------

create_database()

if __name__ == "__main__":

    app.run(
        debug=True,
        host="0.0.0.0",
        port=5000
    )