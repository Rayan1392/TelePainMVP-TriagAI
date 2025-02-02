import re
import sqlite3
import requests

# Ollama API URL
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"

# Database setup
DB_NAME = "patient_memory.db"

# Initialize database
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT,
            user_input TEXT,
            ai_response TEXT
        )
    """)
    conn.commit()
    conn.close()

# Function to save memory to the database
def save_memory(patient_id, user_input, ai_response):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO chat_memory (patient_id, user_input, ai_response) VALUES (?, ?, ?)", 
                   (patient_id, user_input, ai_response))
    conn.commit()
    conn.close()

# Function to retrieve past conversation history
def get_memory(patient_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_input, ai_response FROM chat_memory WHERE patient_id=? ORDER BY id ASC", 
                   (patient_id,))
    history = cursor.fetchall()
    conn.close()
    return history

# Function to remove <think>...</think> sections from AI response
def clean_ai_response(response):
    # Remove anything between <think>...</think> tags
    cleaned_response = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL).strip()
    return cleaned_response

# Function to determine the next follow-up question
def determine_next_question(patient_id, user_input):
    history = get_memory(patient_id)
    
    if not history:
        # First interaction: Set up initial prompt
        prompt = (
            f"You are an AI assistant to ask triage questions from a patient who is suffering from pain. "
            f"I asked the patient, 'What symptoms are you experiencing today?' and the patient answered: {user_input}. "
            f"Based on this, ask ONLY ONE relevant follow-up question to better understand the patient's condition."
        )
    else:
        # Fetch conversation history and generate only ONE follow-up question at a time
        conversation = "\n".join([f"You: {u}\nAI: {a}" for u, a in history])
        prompt = (
            f"{conversation}\nYou: {user_input}\n"
            f"AI: Based on this response, ask ONLY ONE relevant follow-up question related to the patient's condition."
        )

    # API request to Ollama
    payload = {
        "model": "deepseek-r1:8b",  # Change to your preferred model
        "prompt": prompt,
        "num_predict": 150,  # Limit to a short response to ensure one question at a time
        "temperature": 0.7,
        "stream": False
    }

    response = requests.post(OLLAMA_URL, json=payload)
    ai_response = response.json().get("response", "").strip()

    # Clean the response to remove any <think>...</think> sections
    cleaned_ai_response = clean_ai_response(ai_response)

    # Save memory with the cleaned response
    save_memory(patient_id, user_input, cleaned_ai_response)

    return cleaned_ai_response

# Main chatbot loop
def chatbot():
    init_db()  # Ensure DB is initialized
    patient_id = input("Enter patient ID (or name): ").strip()  # Unique ID for each patient
    
    print("\nAI: Hello, I am your AI health assistant. What symptoms are you experiencing today?")
    user_input = input("You: ").strip()
    
    while user_input.lower() not in ["exit", "quit"]:
        ai_reply = determine_next_question(patient_id, user_input)
        print(f"AI: {ai_reply}")
        user_input = input("You: ").strip()

    print("AI: Take care! If symptoms worsen, consult a doctor. Goodbye! 👋")

# Run the chatbot
if __name__ == "__main__":
    chatbot()
