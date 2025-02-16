import os
import re
import sqlite3
import openai
import requests
from fastapi import FastAPI, HTTPException, Depends
import uvicorn
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field
import hashlib

# Read OpenAI API Key from Environment Variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OpenAI API Key not found. Set OPENAI_API_KEY environment variable.")

openai.api_key = OPENAI_API_KEY  # Set API key for OpenAI
client = openai.OpenAI(api_key=OPENAI_API_KEY)
app = FastAPI()

DB_NAME = "patient_memory.db"
MODEL = "gpt-4"  # Use GPT-4 for better medical responses
QUESTION_COUNTS = 5  # Number of questions before final advice

# Secure API with Basic Auth
VALID_USERNAME = "admin"
VALID_PASSWORD = "Admin123!"
security = HTTPBasic()

def verify_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    """Verify the provided username and password using Basic Auth."""
    correct_username = hashlib.sha256(credentials.username.encode()).hexdigest() == hashlib.sha256(VALID_USERNAME.encode()).hexdigest()
    correct_password = hashlib.sha256(credentials.password.encode()).hexdigest() == hashlib.sha256(VALID_PASSWORD.encode()).hexdigest()

    if not (correct_username and correct_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return credentials.username  # Authenticated user

# Database Functions
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
    """Store chat interactions in the database."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO chat_memory (patient_id, session_id, user_input, ai_response) VALUES (?, ?, ?, ?)",
            (patient_id, session_id, user_input, ai_response),
        )
        conn.commit()
    except sqlite3.Error as e:
        print(f"Database Error (save_memory): {e}")
    finally:
        conn.close()

def get_memory(patient_id, session_id):
    """Retrieve past conversation history for a given patient and session."""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_input, ai_response FROM chat_memory WHERE patient_id=? AND session_id=? ORDER BY id ASC",
            (patient_id, session_id),
        )
        history = cursor.fetchall()
        return history
    except sqlite3.Error as e:
        print(f"Database Error (get_memory): {e}")
        return []
    finally:
        conn.close()

def clean_ai_response(response):
    """Remove <think>...</think> sections from AI response."""
    return re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL).strip()

# Use OpenAI API Instead of Ollama
def determine_next_question(patient_id, session_id, user_input, question_count):
    """Determines the next relevant follow-up question for the patient based on chat history."""
    history = get_memory(patient_id, session_id)
    conversation = "\n".join([f"Patient: {u}\nAI: {a}" for u, a in history])

    if question_count == 1:
        prompt = (
            f"You are an AI assistant conducting a triage assessment for a patient. "
            f"The patient said: '{user_input}'. "
            f"Ask only one relevant follow-up question in a friendly and professional tone to better understand their condition. "
            f"Keep the conversation natural, as if a doctor is speaking to the patient."
        )
    elif question_count < QUESTION_COUNTS:
        prompt = (
            f"{conversation}\nPatient: {user_input}\n"
            f"Based on the symptoms so far, ask the next relevant follow-up question in a conversational tone. "
            f"Do not say 'Here is my next follow-up question', just ask naturally as a doctor would. "
            f"If symptoms indicate a medical emergency (such as severe chest pain, difficulty breathing, stroke symptoms), "
            f"IMMEDIATELY stop asking questions and tell the patient: 'This may be an emergency. Please call emergency services (911) or go to the nearest hospital immediately.'"
        )
    else:  # After 5 questions, AI must give final advice
        prompt = (
            f"{conversation}\nPatient: {user_input}\n"
            f"You have now gathered enough information. Based on all the patient's responses, provide a clear final medical recommendation. "
            f"Be direct and professional. Advise whether they should rest, visit urgent care, or consult a specialist. "
            f"If symptoms are life-threatening, remind them to seek emergency care immediately."
        )

    try:
        response = client.chat.completions.create(
            model="gpt-4",  # Updated OpenAI syntax
            messages=[
                {"role": "system", "content": "You are a medical AI chatbot conducting a triage."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=200,  # Limit response length
            temperature=0.7,
        )
        ai_response = response.choices[0].message.content.strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OpenAI API Error: {e}")

    cleaned_response = clean_ai_response(ai_response)
    save_memory(patient_id, session_id, user_input, cleaned_response)
    return cleaned_response

# Pydantic Model for Request Validation
class ChatRequest(BaseModel):
    patient_id: str = Field(..., min_length=1, description="Patient ID must not be empty")
    session_id: str = Field(..., min_length=1, description="Session ID must not be empty")
    user_input: str = Field(..., min_length=1, description="User input must not be empty")
    question_count: int = Field(..., ge=0, description="Question count must be a non-negative integer")

# Secure API Endpoint with Basic Auth
@app.post("/chat")
def chat(request: ChatRequest, username: str = Depends(verify_credentials)):
    """API endpoint for processing chat requests with Basic Authentication."""
    ai_response = determine_next_question(
        request.patient_id, request.session_id, request.user_input.strip(), request.question_count
    )
    return {"response": ai_response}

if __name__ == "__main__":
    init_db()
    uvicorn.run(app, host="0.0.0.0", port=8000)
