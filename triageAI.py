import re
import sqlite3
import requests
from fastapi import FastAPI, HTTPException, Depends
import uvicorn
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field
import hashlib
import os

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
app = FastAPI()

DB_NAME = "patient_memory.db"
MODEL = "llama3.1:8b"
QUESTION_COUNTS = 5

# Define Username & Password (store securely in env variables or a database in production)
VALID_USERNAME = os.getenv("TRIAGE_CHATBOT_USERNAME") 
VALID_PASSWORD = os.getenv("TRIAGE_CHATBOT_PASSWORD")

# Use HTTP Basic Authentication
security = HTTPBasic()

def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    """Verify the provided username and password using Basic Auth."""
    correct_username = hashlib.sha256(credentials.username.encode()).hexdigest() == hashlib.sha256(VALID_USERNAME.encode()).hexdigest()
    correct_password = hashlib.sha256(credentials.password.encode()).hexdigest() == hashlib.sha256(VALID_PASSWORD.encode()).hexdigest()

    if not (correct_username and correct_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return credentials.username  # Authenticated user

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT,
            session_id TEXT,
            user_input TEXT,
            ai_response TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_memory(patient_id, session_id, user_input, ai_response):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO chat_memory (patient_id, session_id, user_input, ai_response) VALUES (?, ?, ?, ?)", 
                       (patient_id, session_id, user_input, ai_response))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        conn.close()

def get_memory(patient_id, session_id):
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT user_input, ai_response FROM chat_memory WHERE patient_id=? AND session_id=? ORDER BY id ASC", 
                       (patient_id, session_id))
        history = cursor.fetchall()
        return history
    except sqlite3.Error as e:
        print(f"Database Error: {e}")
        return []
    finally:
        conn.close()

def clean_ai_response(response):
    return re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL).strip()

def determine_next_question(patient_id, session_id, user_input, question_count):
    """Determines the next relevant follow-up question for the patient based on chat history."""
    history = get_memory(patient_id, session_id)
    conversation = "\n".join([f"Patient: {u}\nAI: {a}" for u, a in history])

    if question_count == 1:
        prompt = (
            f"You are an AI assistant conducting a **triage assessment** for a patient. "
            f"The patient said: '{user_input}'. "
            f"Ask only **one relevant** follow-up question in a **friendly and professional tone** to better understand their condition. "
            f"Keep the conversation natural, as if a doctor is speaking to the patient."
        )
    elif question_count < QUESTION_COUNTS:
        prompt = (
            f"{conversation}\nPatient: {user_input}\n"
            f"Based on the symptoms so far, ask the **next relevant follow-up question** in a **conversational tone**. "
            f"Do not say 'Here is my next follow-up question', just **ask naturally** as a doctor would. "
            f"If symptoms indicate a **medical emergency** (such as severe chest pain, difficulty breathing, stroke symptoms), "
            f"IMMEDIATELY stop asking questions and tell the patient: 'This may be an emergency. Please call emergency services (911) or go to the nearest hospital immediately.'"
        )
    else:  # After 10 questions, AI must give final advice
        prompt = (
            f"{conversation}\nPatient: {user_input}\n"
            f"You have now gathered enough information. Based on all the patient's responses, provide a **clear final medical recommendation**. "
            f"Be **direct and professional**. Advise whether they should rest, visit urgent care, or consult a specialist. "
            f"If symptoms are life-threatening, remind them to **seek emergency care immediately.**"
        )

    payload = {
        "model": MODEL,
        "prompt": prompt,
        "num_predict": 150,  # Adjusted to allow longer advice
        "temperature": 0.7,
        "stream": False,
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload)
        response.raise_for_status()
        ai_response = response.json().get("response", "").strip()
    except requests.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Error calling AI model: {e}")

    cleaned_response = clean_ai_response(ai_response)
    save_memory(patient_id, session_id, user_input, cleaned_response)
    return cleaned_response


class ChatRequest(BaseModel):
    patient_id: str = Field(..., min_length=1, description="Patient ID must not be empty")
    session_id: str = Field(..., min_length=1, description="Session ID must not be empty")
    user_input: str = Field(..., min_length=1, description="User input must not be empty")
    question_count: int = Field(..., ge=0, description="Question count must be a non-negative integer")

@app.post("/chat")
def chat(request: ChatRequest, username: str = Depends(verify_credentials)):
    # Validate request parameters
    if not request.patient_id.strip():
        raise HTTPException(status_code=400, detail="Patient ID cannot be empty.")
    if not request.session_id.strip():
        raise HTTPException(status_code=400, detail="Session ID cannot be empty.")
    if not request.user_input.strip():
        raise HTTPException(status_code=400, detail="User input cannot be empty.")
    if request.question_count < 0:
        raise HTTPException(status_code=400, detail="Question count must be non-negative.")

    # Proceed with AI processing
    ai_response = determine_next_question(request.patient_id, request.session_id, request.user_input.strip(), request.question_count)
    return {"response": ai_response}


if __name__ == "__main__":
    init_db()
    uvicorn.run(app, host="0.0.0.0", port=8000)
