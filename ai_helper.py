import os
import re
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-2.5-flash")


def generate_question(role, difficulty, interview_type, focus_topic):
    extra_focus = f"Focus topic: {focus_topic}." if focus_topic else "Keep it broad and role-relevant."

    prompt = f"""
You are a professional interviewer.

Generate one unique {interview_type} interview question for a {role} at {difficulty} level.
{extra_focus}

Rules:
- Make it realistic and interview-ready
- Keep it concise
- Return only the question text
- Avoid repeating previous questions in style if possible
"""
    response = model.generate_content(prompt)
    return response.text.strip()


def evaluate_answer(role, difficulty, question, answer):
    prompt = f"""
You are a professional interviewer.

Role: {role}
Difficulty: {difficulty}
Question: {question}
Candidate Answer: {answer}

Evaluate the answer and return in this exact format:

Score: X
Strengths:
- point 1
- point 2

Mistakes:
- point 1
- point 2

Better Answer:
[Write a stronger interview-ready answer]

Score must be an integer from 1 to 10.
"""
    response = model.generate_content(prompt)
    feedback = response.text.strip()

    score_match = re.search(r"Score:\s*(\d+)", feedback)
    score = int(score_match.group(1)) if score_match else 5

    return feedback, score