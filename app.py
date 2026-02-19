from flask import Flask, render_template, request, redirect, url_for,session
import random
from werkzeug.utils import secure_filename
import os
import PyPDF2
import re



import mysql.connector
from mysql.connector import Error


app = Flask(__name__)
app.secret_key = "student_nexus_secret_key"


# MySQL connection
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="GS1023",
    database="student_nexus"
)

cursor = db.cursor()

@app.route("/")
def landing():
    return render_template("index.html")



@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        full_name = request.form["full_name"]
        email = request.form["email"]
        phone = request.form["phone"]
        attend_class = request.form["attend_class"]

        try:
            query = """
            INSERT INTO users (full_name, email, phone, attend_class)
            VALUES (%s, %s, %s, %s)
            """
            values = (full_name, email, phone, attend_class)

            cursor.execute(query, values)
            db.commit()

            return redirect(url_for("login"))

        except Error:
            # Duplicate email / phone
            return render_template(
                "register.html",
                error="You are already registered. Please login."
            )

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        captcha_input = request.form["captcha_input"]
        captcha_real = request.form["captcha_real"]

        # Captcha check
        if captcha_input != captcha_real:
            new_captcha = str(random.randint(1000, 9999))
            return render_template(
                "login.html",
                error="Invalid captcha",
                captcha=new_captcha
            )

        # Check user in DB
        cursor.execute("SELECT full_name FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        if user is None:
            return redirect(url_for("register"))

        # ✅ SET SESSION
        session["user_email"] = email
        session["user_name"] = user[0]

        return redirect(url_for("dashboard"))

    captcha = str(random.randint(1000, 9999))
    return render_template("login.html", captcha=captcha)

@app.route("/dashboard")
def dashboard():
    if "user_email" not in session:
        return redirect(url_for("login"))

    email = session["user_email"]

    # Get name
    cursor.execute(
        "SELECT full_name FROM users WHERE email = %s",
        (email,)
    )
    user = cursor.fetchone()
    name = user[0] if user else "Student"

    # Get total credits
    cursor.execute("""
        SELECT SUM(c.credits)
        FROM courses c
        JOIN student_courses sc
        ON c.course_id = sc.course_id
        WHERE sc.student_email = %s
    """, (email,))

    result = cursor.fetchone()
    total_credits = result[0] if result and result[0] else 0

    return render_template(
        "dashboard.html",
        name=name,
        total_credits=total_credits
    )

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/resume", methods=["GET", "POST"])
def resume():
    if "user_email" not in session:
        return redirect(url_for("login"))

    analysis = None
    ats_color = "#f87171" # Default color (red)

    if request.method == "POST":
        file = request.files["resume"]

        if file and file.filename.endswith(".pdf"):
            filename = secure_filename(file.filename)
            path = os.path.join("uploads", filename)
            file.save(path)

            # Read PDF
            text = ""
            with open(path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    extracted = page.extract_text()
                    if extracted:
                        text += extracted.lower()

            # -------- EMAIL EXTRACTION --------
            email_match = re.search(
                r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
                text
            )
            email = email_match.group() if email_match else "Not found"

            # -------- NAME EXTRACTION --------
            name = "Not found"
            lines = text.split("\n")
            for line in lines[:5]:
                clean = line.strip()
                if clean.replace(" ", "").isalpha() and 2 <= len(clean.split()) <= 3:
                    name = clean.title()
                    break

            # -------- SKILL EXTRACTION --------
            skills = [
                "python", "java", "sql", "flask",
                "react", "data analysis", "pandas", "numpy"
            ]
            found_skills = [s for s in skills if s in text]

            # -------- ROLE SUGGESTION --------
            if "data analysis" in found_skills or "pandas" in found_skills:
                role = "Data Analyst"
            elif "flask" in found_skills:
                role = "Backend Developer"
            elif "react" in found_skills:
                role = "Frontend Developer"
            else:
                role = "Software Engineer (Fresher)"

            # -------- COMPANY SUGGESTIONS --------
            company_map = {
                "Data Analyst": ["Deloitte", "Accenture", "ZS Associates"],
                "Backend Developer": ["Amazon", "Flipkart", "Paytm"],
                "Frontend Developer": ["Swiggy", "Zomato", "Meesho"],
                "Software Engineer (Fresher)": ["Infosys", "TCS", "Wipro"]
            }
            companies = company_map.get(role, [])

            # -------- ATS SCORE --------
            total_skills = len(skills)
            matched_skills = len(found_skills)
            ats_score = int((matched_skills / total_skills) * 70) if total_skills else 0

            if email != "Not found":
                ats_score += 15
            if name != "Not found":
                ats_score += 15

            ats_score = min(ats_score, 100)

            # -------- NEW COLOR LOGIC (Fixes the HTML error) --------
            if ats_score >= 70:
                ats_color = "#22c55e" # Green
            elif ats_score >= 40:
                ats_color = "#facc15" # Yellow
            else:
                ats_color = "#f87171" # Red

            analysis = {
                "name": name,
                "email": email,
                "skills": found_skills,
                "role": role,
                "companies": companies,
                "ats": ats_score,
                "color": ats_color  # We pass the color directly
            }

    return render_template("resume.html", analysis=analysis)

@app.route("/grievance", methods=["GET", "POST"])
def grievance():
    if "user_email" not in session:
        return redirect(url_for("login"))

    email = session["user_email"]

    # Add new grievance
    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]

        cursor.execute(
            "INSERT INTO grievances (student_email, title, description) VALUES (%s, %s, %s)",
            (email, title, description)
        )
        db.commit()

    # Fetch all grievances of this student
    cursor.execute(
        "SELECT grievance_id, title, description, status, created_at, feedback \
         FROM grievances WHERE student_email=%s ORDER BY created_at DESC",
        (email,)
    )
    grievances = cursor.fetchall()

    # Stats calculation
    total = len(grievances)
    solved = sum(1 for g in grievances if g[3] == "Solved")
    pending = sum(1 for g in grievances if g[3] == "Pending")

    latest = grievances[0] if grievances else None

    return render_template(
        "grievance.html",
        grievances=grievances,
        total=total,
        solved=solved,
        pending=pending,
        latest=latest
    )
@app.route("/grievance/solve/<int:gid>")
def solve_grievance(gid):
    if "user_email" not in session:
        return redirect(url_for("login"))

    cursor.execute(
        "UPDATE grievances SET status='Solved' WHERE grievance_id=%s",
        (gid,)
    )
    db.commit()

    return redirect(url_for("grievance"))

@app.route("/courses", methods=["GET", "POST"])
def courses():
    if "user_email" not in session:
        return redirect(url_for("login"))

    email = session["user_email"]

    # Add course
    if request.method == "POST":
        course_id = request.form["course_id"]

        cursor.execute(
            "INSERT INTO student_courses (student_email, course_id) VALUES (%s, %s)",
            (email, course_id)
        )
        db.commit()

    # Get enrolled courses
    cursor.execute("""
    SELECT c.course_id, c.course_name, c.credits
    FROM courses c
    JOIN student_courses sc
    ON c.course_id = sc.course_id
    WHERE sc.student_email = %s
""", (email,))

    enrolled = cursor.fetchall()
    total_credits = sum(c[2] for c in enrolled)


    # Get all available courses
    cursor.execute("SELECT course_id, course_name FROM courses")
    all_courses = cursor.fetchall()

    return render_template(
        "courses.html",
        enrolled=enrolled,
        all_courses=all_courses ,
    total_credits=total_credits
)
    
@app.route("/courses/remove/<int:course_id>")
def remove_course(course_id):
    if "user_email" not in session:
        return redirect(url_for("login"))

    email = session["user_email"]

    cursor.execute(
        "DELETE FROM student_courses WHERE student_email=%s AND course_id=%s",
        (email, course_id)
    )
    db.commit()

    return redirect(url_for("courses"))





if __name__ == "__main__":
    app.run(debug=True)
