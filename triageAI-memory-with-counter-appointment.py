import re
import sqlite3
import requests

# Ollama API URL
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"

# Database setup
DB_NAME = "patient_memory.db"
MODEL = "llama3.1:8b"  # The chosen model for conversation
QUESTION_COUNTS = 10

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

# Function to determine the next follow-up question and assess urgency
def determine_next_question(patient_id, user_input, question_count):
    history = get_memory(patient_id)
    
    if question_count == 0:
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
            f"AI: Ask ONLY ONE relevant follow-up question to better assess the patient's condition."
        )

    # API request to Ollama
    payload = {
        "model": MODEL,  # Change to your preferred model
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

# Function to provide advice and suggest a doctor appointment if necessary
def provide_advice_and_appointment(patient_id):
    history = get_memory(patient_id)
    advice_prompt = "Based on the conversation so far, provide a summary and give advice to the patient. " \
                    "Make sure the advice is based on the symptoms provided and any relevant medical conditions. " \
                    "If the symptoms suggest a serious condition, recommend setting up an appointment with a doctor."
    
    conversation = "\n".join([f"You: {u}\nAI: {a}" for u, a in history])

    # API request to Ollama for advice and doctor's appointment suggestion
    payload = {
        "model": MODEL,
        "prompt": conversation + "\n" + advice_prompt,
        "num_predict": 200,  # Adjust length as necessary for advice
        "temperature": 0.7,
        "stream": False
    }

    response = requests.post(OLLAMA_URL, json=payload)
    ai_advice = response.json().get("response", "").strip()

    return ai_advice

# Function to generate a summary report based on patient criteria
def generate_summary_report(patient_id):
    history = get_memory(patient_id)
    summary_prompt = "Create a detailed summary of the patient's responses and symptoms from the following conversation."
    
    conversation = "\n".join([f"You: {u}\nAI: {a}" for u, a in history])

    # API request to Ollama for generating the summary
    payload = {
        "model": MODEL,
        "prompt": conversation + "\n" + summary_prompt,
        "num_predict": 300,  # Adjust length as necessary for summary
        "temperature": 0.7,
        "stream": False
    }

    response = requests.post(OLLAMA_URL, json=payload)
    ai_summary = response.json().get("response", "").strip()

    return ai_summary

# Main chatbot loop
def chatbot():
    init_db()  # Ensure DB is initialized
    patient_id = input("Enter patient ID (or name): ").strip()  # Unique ID for each patient
    
    print("\nAI: Hello, I am your AI health assistant. What symptoms are you experiencing today?")
    user_input = input("You: ").strip()
    
    question_count = 0
    while user_input.lower() not in ["exit", "quit"]:
        # If 10 questions have been asked, stop and provide advice and possibly suggest an appointment
        if question_count >= QUESTION_COUNTS:
            ai_advice = provide_advice_and_appointment(patient_id)
            print(f"AI: Based on your symptoms, here's some advice: \n{ai_advice}")
            ai_summary = generate_summary_report(patient_id)
            print(f"AI: Here’s a summary report of your symptoms and responses: \n{ai_summary}")
            break
        
        ai_reply = determine_next_question(patient_id, user_input, question_count)
        print(f"AI: {ai_reply}")
        
        user_input = input("You: ").strip()
        question_count += 1

    print("AI: Take care! If symptoms worsen, consult a doctor. Goodbye! 👋")

# Run the chatbot
if __name__ == "__main__":
    chatbot()
