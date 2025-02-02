import requests

# Local Ollama API URL
url = "http://127.0.0.1:11434/api/generate"

# Initial question to start the chatbot
prompt = "Hello, I am your AI health assistant. What symptoms are you experiencing today?"

# Function to get AI response
def ask_ai(prompt):
    payload = {
        "model": "llama2-uncensored:7b",
        "prompt": prompt,
        "num_predict": 300,  # Set to a higher value for detailed responses
        "temperature": 0.7,
        "stream": False
    }
    
    response = requests.post(url, json=payload)
    return response.json().get("response", "")

# Start chatbot interaction
user_input = input(f"{prompt}\nYou: ")

# Dynamic questioning loop
while True:
    ai_response = ask_ai(f"Patient says: {user_input}. What should I ask next?")
    print(f"AI: {ai_response}")

    # Exit conditions
    if "seek immediate medical attention" in ai_response.lower():
        print("AI: I recommend calling emergency services.")
        break
    elif "consult a doctor" in ai_response.lower():
        print("AI: You should see a doctor soon.")
        break
    elif "self-care" in ai_response.lower():
        print("AI: You can manage your symptoms with rest and hydration.")
        break

    # Continue conversation
    user_input = input("You: ")
