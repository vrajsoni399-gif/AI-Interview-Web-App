from flask import Flask, render_template, request, redirect, url_for, session
from dotenv import load_dotenv
import os
import sqlite3

from ai_helper import generate_question, evaluate_answer

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "defaultsecretkey")


def get_db_connection():
    conn = sqlite3.connect("interview_prep.db")
    conn.row_factory = sqlite3.Row
    return conn


@app.route("/")
def index():
    user = None
    if "user_id" in session:
        user = {
            "id": session["user_id"],
            "name": session["user_name"],
            "email": session["user_email"]
        }
    return render_template("index.html", user=user)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if password != confirm_password:
            return "Passwords do not match"

        conn = get_db_connection()
        existing_user = conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        ).fetchone()

        if existing_user:
            conn.close()
            return "Email already registered"

        conn.execute(
            "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
            (name, email, password)
        )
        conn.commit()
        conn.close()

        return redirect(url_for("login"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE email = ? AND password = ?",
            (email, password)
        ).fetchone()
        conn.close()

        if user:
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["user_email"] = user["email"]
            return redirect(url_for("index"))

        return "Invalid email or password"

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/start", methods=["POST"])
def start():
    if "user_id" not in session:
        return redirect(url_for("login"))

    full_name = request.form["full_name"]
    email = request.form["email"]
    role = request.form["role"]
    difficulty = request.form["difficulty"]
    interview_type = request.form["interview_type"]
    question_count = int(request.form["question_count"])
    focus_topic = request.form["focus_topic"].strip()

    questions = []
    for _ in range(question_count):
        question = generate_question(role, difficulty, interview_type, focus_topic)
        questions.append(question)

    session["interview_data"] = {
        "full_name": full_name,
        "email": email,
        "role": role,
        "difficulty": difficulty,
        "interview_type": interview_type,
        "question_count": question_count,
        "focus_topic": focus_topic,
        "questions": questions,
        "current_index": 0,
        "results": []
    }

    return redirect(url_for("interview_round"))


@app.route("/interview-round", methods=["GET"])
def interview_round():
    if "user_id" not in session:
        return redirect(url_for("login"))

    interview_data = session.get("interview_data")
    if not interview_data:
        return redirect(url_for("index"))

    current_index = interview_data["current_index"]
    questions = interview_data["questions"]

    if current_index >= len(questions):
        return redirect(url_for("final_result"))

    return render_template(
        "interview.html",
        full_name=interview_data["full_name"],
        email=interview_data["email"],
        role=interview_data["role"],
        difficulty=interview_data["difficulty"],
        interview_type=interview_data["interview_type"],
        question_count=interview_data["question_count"],
        focus_topic=interview_data["focus_topic"],
        question=questions[current_index],
        current_round=current_index + 1,
        total_rounds=len(questions)
    )


@app.route("/submit-answer", methods=["POST"])
def submit_answer():
    if "user_id" not in session:
        return redirect(url_for("login"))

    interview_data = session.get("interview_data")
    if not interview_data:
        return redirect(url_for("index"))

    answer = request.form["answer"]
    current_index = interview_data["current_index"]
    question = interview_data["questions"][current_index]

    feedback, score = evaluate_answer(
        interview_data["role"],
        interview_data["difficulty"],
        question,
        answer
    )

    interview_data["results"].append({
        "question": question,
        "answer": answer,
        "feedback": feedback,
        "score": score
    })

    conn = get_db_connection()
    conn.execute("""
        INSERT INTO attempts (user_id, role, difficulty, question, user_answer, ai_feedback, score)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        session["user_id"],
        interview_data["role"],
        interview_data["difficulty"],
        question,
        answer,
        feedback,
        score
    ))
    conn.commit()
    conn.close()

    interview_data["current_index"] += 1
    session["interview_data"] = interview_data

    if interview_data["current_index"] < len(interview_data["questions"]):
        return redirect(url_for("round_result"))

    return redirect(url_for("final_result"))


@app.route("/round-result")
def round_result():
    if "user_id" not in session:
        return redirect(url_for("login"))

    interview_data = session.get("interview_data")
    if not interview_data or not interview_data["results"]:
        return redirect(url_for("index"))

    latest_result = interview_data["results"][-1]
    current_done = len(interview_data["results"])
    total_rounds = len(interview_data["questions"])

    return render_template(
        "round_result.html",
        role=interview_data["role"],
        difficulty=interview_data["difficulty"],
        interview_type=interview_data["interview_type"],
        focus_topic=interview_data["focus_topic"],
        question=latest_result["question"],
        answer=latest_result["answer"],
        feedback=latest_result["feedback"],
        score=latest_result["score"],
        current_done=current_done,
        total_rounds=total_rounds
    )


@app.route("/final-result")
def final_result():
    if "user_id" not in session:
        return redirect(url_for("login"))

    interview_data = session.get("interview_data")
    if not interview_data or not interview_data["results"]:
        return redirect(url_for("index"))

    results = interview_data["results"]
    total_score = sum(item["score"] for item in results)
    avg_score = round(total_score / len(results), 1)

    return render_template(
        "result.html",
        full_name=interview_data["full_name"],
        email=interview_data["email"],
        role=interview_data["role"],
        difficulty=interview_data["difficulty"],
        interview_type=interview_data["interview_type"],
        question_count=interview_data["question_count"],
        focus_topic=interview_data["focus_topic"],
        results=results,
        avg_score=avg_score,
        total_score=total_score,
        total_rounds=len(results)
    )


@app.route("/history")
def history():
    if "user_id" not in session:
        return redirect(url_for("login"))

    search = request.args.get("search", "").strip()
    difficulty = request.args.get("difficulty", "").strip()

    query = "SELECT * FROM attempts WHERE user_id = ?"
    params = [session["user_id"]]

    if search:
        query += " AND role LIKE ?"
        params.append(f"%{search}%")

    if difficulty:
        query += " AND difficulty = ?"
        params.append(difficulty)

    query += " ORDER BY created_at DESC"

    conn = get_db_connection()
    attempts = conn.execute(query, params).fetchall()
    conn.close()

    return render_template(
        "history.html",
        attempts=attempts,
        search=search,
        difficulty=difficulty
    )


@app.route("/delete-history/<int:attempt_id>", methods=["POST"])
def delete_history(attempt_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    conn.execute(
        "DELETE FROM attempts WHERE id = ? AND user_id = ?",
        (attempt_id, session["user_id"])
    )
    conn.commit()
    conn.close()

    return redirect(url_for("history"))


if __name__ == "__main__":
    app.run(debug=True)