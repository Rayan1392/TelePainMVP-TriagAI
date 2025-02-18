import os
import requests
import uuid
import telebot
from telebot import types

# Constants
CHAT_API_URL = "https://chat.telepainsolutions.ca/chat"  # Your chat API URL
API_AUTHORIZATION_TOKEN = "Basic YWRtaW46QWRtaW4xMjMh"  # Replace with actual API authorization token

# Set up Telegram Bot Token
TELEGRAM_TOKEN = '7691070101:AAHfF0iRaH0jpOS7njeyIJ1o1FXMtfg7L7k' # @triage_ai_chatbot
if not TELEGRAM_TOKEN:
    raise ValueError("Telegram Bot Token is required. Set TELEGRAM_TOKEN environment variable.")

# Initialize the bot
bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Function to handle the /start command
@bot.message_handler(commands=['start'])
def start(message):
    # Storing the user's information
    user_info = {
        "chat_id": message.chat.id,
        "username": message.from_user.username,
        "first_name": message.from_user.first_name,
        "last_name": message.from_user.last_name,
        "question_count": 1,  # Initialize question count
        "session_id": str(uuid.uuid4())  # Generate unique session ID
    }

    # Save user info (in memory, or could be stored in a database for persistence)
    bot.user_data[message.chat.id] = user_info

    # Send greeting message
    bot.reply_to(message, "Hello, I am your AI health assistant. What symptoms are you experiencing today?")

# Function to handle user message
@bot.message_handler(func=lambda message: True)
def handle_message(message):
    user_info = bot.user_data.get(message.chat.id)
    if not user_info:
        bot.reply_to(message, "Please start the conversation by sending /start.")
        return

    user_input = message.text.strip()
    question_count = user_info.get("question_count", 1)
    session_id = user_info.get("session_id")  # Use the unique session_id

    # Prepare the data to send to the /chat API
    payload = {
        "patient_id": str(user_info["chat_id"]),  # Use chat_id as patient_id
        "session_id": session_id,  # Use unique session_id for the user session
        "user_input": user_input,
        "question_count": question_count,
    }

    headers = {
        'Content-Type': 'application/json',
        'Authorization': API_AUTHORIZATION_TOKEN  # Authorization header
    }

    # Call the /chat API using the provided structure
    try:
        response = requests.post(
            CHAT_API_URL,
            headers=headers,
            json=payload  # Directly passing the payload as JSON
        )

        # Check if the API response is successful
        if response.status_code == 200:
            api_response = response.json().get("response", "Sorry, I couldn't get a response.")
            bot.reply_to(message, api_response)  # Send the response to the user

            # Increase the question count for the next round
            user_info["question_count"] += 1
        else:
            bot.reply_to(message, "Sorry, I couldn't process your request at the moment.")
    except requests.exceptions.RequestException as e:
        bot.reply_to(message, "There was an error connecting to the AI service.")

# Start the bot
if __name__ == "__main__":
    bot.polling(none_stop=True)
