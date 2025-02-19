import re
import sqlite3
import requests
import os

# DeepSeek API setup
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
MODEL = "deepseek-chat"
QUESTION_COUNTS = 10
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

# Save memory to the database
def save_memory(patient_id, user_input, ai_response):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO chat_memory (patient_id, user_input, ai_response) VALUES (?, ?, ?)", 
                   (patient_id, user_input, ai_response))
    conn.commit()
    conn.close()

# Retrieve past conversation history
def get_memory(patient_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_input, ai_response FROM chat_memory WHERE patient_id=? ORDER BY id ASC", 
                   (patient_id,))
    history = cursor.fetchall()
    conn.close()
    return history

# Remove <think>...</think> sections from AI response
def clean_ai_response(response):
    return re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL).strip()

# Generate AI response using DeepSeek API
def get_ai_response(prompt, max_tokens=150):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
    }
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "You are a helpful medical AI assistant."},
            {"role": "user", "content": prompt}
        ],
        "stream": False
    }
    response = requests.post(DEEPSEEK_URL, json=payload, headers=headers)
    response_data = response.json()
    return response_data["choices"][0]["message"]["content"].strip()

# Determine next follow-up question
def determine_next_question(patient_id, user_input, question_count):
    history = get_memory(patient_id)
    
    if question_count == 0:
        prompt = (
            f"You are an AI assistant asking triage questions to a patient in pain. "
            f"I asked, 'What symptoms are you experiencing today?' and the patient answered: {user_input}. "
            f"Based on this, ask ONLY ONE relevant follow-up question."
        )
    else:
        conversation = "\n".join([f"You: {u}\nAI: {a}" for u, a in history])
        prompt = (
            f"{conversation}\nYou: {user_input}\nAI: "
            f"Ask ONLY ONE relevant follow-up question to better assess the patient's condition."
        )
    
    ai_response = get_ai_response(prompt, max_tokens=100)
    cleaned_response = clean_ai_response(ai_response)
    save_memory(patient_id, user_input, cleaned_response)
    return cleaned_response

# Provide advice and suggest a doctor appointment
def provide_advice_and_appointment(patient_id):
    history = get_memory(patient_id)
    conversation = "\n".join([f"You: {u}\nAI: {a}" for u, a in history])
    prompt = (
        "Based on the following conversation, provide a summary and advice to the patient. "
        "If symptoms indicate a serious condition, suggest setting up a doctor's appointment.\n"
        f"{conversation}"
    )
    return get_ai_response(prompt, max_tokens=200)

# Generate summary report
def generate_summary_report(patient_id):
    history = get_memory(patient_id)
    conversation = "\n".join([f"You: {u}\nAI: {a}" for u, a in history])
    prompt = f"Create a detailed summary of the patient's responses and symptoms from the following conversation:\n{conversation}"
    return get_ai_response(prompt, max_tokens=300)

# Main chatbot loop
def chatbot():
    init_db()
    patient_id = input("Enter patient ID (or name): ").strip()
    print("\nAI: Hello, I am your AI health assistant. What symptoms are you experiencing today?")
    user_input = input("You: ").strip()
    
    question_count = 0
    while user_input.lower() not in ["exit", "quit"]:
        if question_count >= QUESTION_COUNTS:
            ai_advice = provide_advice_and_appointment(patient_id)
            print(f"AI: Here's some advice based on your symptoms: \n{ai_advice}")
            ai_summary = generate_summary_report(patient_id)
            print(f"AI: Here’s a summary report of your symptoms and responses: \n{ai_summary}")
            break
        
        ai_reply = determine_next_question(patient_id, user_input, question_count)
        print(f"AI: {ai_reply}")
        user_input = input("You: ").strip()
        question_count += 1

    print("AI: Take care! If symptoms worsen, consult a doctor. Goodbye! 👋")

if __name__ == "__main__":
    chatbot()
