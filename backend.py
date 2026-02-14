import os
os.environ["TRANSFORMERS_NO_TF"] = "1"
import base64
import io
import os as _os
import tempfile
import threading
from typing import Optional
import numpy as np
from PIL import Image
from flask import Flask, request, jsonify
from flask_cors import CORS
import pyttsx3
from transformers import pipeline
from fer import FER
from gtts import gTTS
# =====================================================
# APP SETUP
# =====================================================

app = Flask(__name__)
CORS(app)

# =====================================================
# TEXT TO SPEECH
# =====================================================

tts_engine = pyttsx3.init()
tts_engine.setProperty("rate", 160)
tts_engine.setProperty("volume", 1.0)


def text_to_audio_base64(text: str) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
        path = f.name
    try:
        tts = gTTS(text=text, lang="en")
        tts.save(path)

        with open(path, "rb") as audio:
            return base64.b64encode(audio.read()).decode("utf-8")
    finally:
        if _os.path.exists(path):
            _os.remove(path)

# =====================================================
# SENTIMENT ANALYSIS
# =====================================================

sentiment_model = None
_sentiment_lock = threading.Lock()

def load_sentiment_model():
    global sentiment_model
    with _sentiment_lock:
        if sentiment_model is None:
            sentiment_model = pipeline(
                "sentiment-analysis",
                model="distilbert-base-uncased-finetuned-sst-2-english"
            )

def sentiment_score(text: str) -> float:
    if not text:
        return 0.0
    load_sentiment_model()
    result = sentiment_model(text)[0]
    return result["score"] if result["label"] == "POSITIVE" else -result["score"]

# =====================================================
# FACIAL EMOTION DETECTION
# =====================================================

face_detector = FER(mtcnn=True)

EMOTION_WEIGHTS = {
    "angry": -0.9,
    "sad": -0.9,
    "disgust": -0.8,
    "fear": -0.7,
    "neutral": 0.0,
    "surprise": 0.2,
    "happy": 1.0
}

def b64_to_rgb(img_b64: str) -> Optional[np.ndarray]:
    if not img_b64:
        return None
    try:
        if img_b64.startswith("data:"):
            img_b64 = img_b64.split(",", 1)[1]
        img = Image.open(io.BytesIO(base64.b64decode(img_b64))).convert("RGB")
        return np.array(img)
    except Exception:
        return None

def emotion_score(image_rgb: Optional[np.ndarray]) -> float:
    if image_rgb is None:
        return 0.0
    emotions = face_detector.detect_emotions(image_rgb)
    if not emotions:
        return 0.0
    return sum(
        EMOTION_WEIGHTS.get(e, 0) * v
        for e, v in emotions[0]["emotions"].items()
    )

# =====================================================
# GPT-NEO QUESTION GENERATION
# =====================================================

# =====================================================
# FLAN-T5 QUESTION GENERATION (Better than GPT-Neo)
# =====================================================

from transformers import pipeline
import threading

question_model = None
_question_lock = threading.Lock()

def load_question_model():
    global question_model
    with _question_lock:
        if question_model is None:
            question_model = pipeline(
                "text2text-generation",
                model="google/flan-t5-base"
            )

def generate_question(prev_q: str, answer: str) -> str:
    load_question_model()

    prompt = f"""
You are a technical interviewer.
Ask ONLY ONE short follow-up interview question based on the candidate's answer.
Make it clear, specific, and professional.
Do not write explanation, only the question.

Previous question: {prev_q}
Candidate answer: {answer}

Follow-up question:
""".strip()

    output = question_model(
        prompt,
        max_length=40,
        do_sample=False
    )[0]["generated_text"]

    # Clean formatting
    q = output.strip()
    if not q.endswith("?"):
        q += "?"
    return q
# =====================================================
# INTERVIEW STATE
# =====================================================

last_question = None
question_count = 0
MAX_QUESTIONS = 5
total_score = 0.0

# =====================================================
# ROUTES
# =====================================================

@app.route("/")
def index():
    return "AI Interviewer Backend Running (GPT-Neo Step)"

@app.route("/interview", methods=["POST"])
def interview():
    global last_question, question_count, total_score

    data = request.get_json(silent=True) or {}

    # Reset interview
    if data.get("reset"):
        last_question = None
        question_count = 0
        total_score = 0.0

    # First question
    if last_question is None:
        last_question = "Tell me about yourself."
        return jsonify({
            "audio": text_to_audio_base64(
                "Hello interviewee. I am your AI interviewer. "
                "Let us begin. Tell me about yourself."
            )
        })

    # Read answer + image
    answer = data.get("answer", "")
    image_b64 = data.get("image")

    # ---- SCORING ----
    s_score = sentiment_score(answer)
    e_score = emotion_score(b64_to_rgb(image_b64))
    length_score = 0.5 if len(answer.split()) >= 15 else -0.2

    final_score = (
        0.4 * s_score +
        0.4 * e_score +
        0.2 * length_score
    )

    total_score += final_score
    question_count += 1

    # End interview
    if question_count >= MAX_QUESTIONS:
        avg = round(total_score / MAX_QUESTIONS, 2)
        performance = (
            "Excellent" if avg > 0.4 else
            "Good" if avg > 0 else
            "Needs Improvement"
        )

        return jsonify({
            "interview_complete": True,
            "average_score": avg,
            "performance": performance,
            "audio": text_to_audio_base64(
                f"Your interview is complete. "
                f"Your average score is {avg}. "
                f"Overall performance is {performance}."
            )
        })

    # Generate next question using GPT-Neo
    next_question = generate_question(last_question, answer)
    last_question = next_question

    return jsonify({
        "audio": text_to_audio_base64(next_question),
        "current_score": round(total_score, 2)
    })

# =====================================================
# RUN SERVER
# =====================================================

if __name__ == "__main__":
    app.run(debug=False, use_reloader=False, port=5000)
