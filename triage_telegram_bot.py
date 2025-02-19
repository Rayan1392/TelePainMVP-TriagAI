import os
import requests
import uuid
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# Constants
CHAT_API_URL = "https://chat.telepainsolutions.ca/chat"  # Your chat API URL
API_AUTHORIZATION_TOKEN = os.getenv('CHAT_API_AUTHORIZATION_TOKEN') # Replace with actual API authorization token

# Set up Telegram Bot Token
TELEGRAM_TOKEN = os.getenv('TRIAGE_AI_CHATBOT_TOKEN') # @triage_ai_chatbot
if not TELEGRAM_TOKEN:
    raise ValueError("Telegram Bot Token is required. Set TELEGRAM_TOKEN environment variable.")

# Function to handle the /start command
def start(update: Update, context: CallbackContext):
    # Storing the user's information
    user = update.message.from_user
    user_info = {
        "chat_id": update.message.chat_id,
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "question_count": 1,  # Initialize question count
        "session_id": str(uuid.uuid4())  # Generate unique session ID
    }

    # Save user info (in memory, or could be stored in a database for persistence)
    context.user_data["user_info"] = user_info

    # Send greeting message
    update.message.reply_text("Hello, I am your AI health assistant. What symptoms are you experiencing today?")

# Function to handle user message
def handle_message(update: Update, context: CallbackContext):
    user_info = context.user_data.get("user_info")
    if not user_info:
        update.message.reply_text("Please start the conversation by sending /start.")
        return

    user_input = update.message.text.strip()
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
            update.message.reply_text(api_response)  # Send the response to the user

            # Increase the question count for the next round
            user_info["question_count"] += 1
        else:
            update.message.reply_text("Sorry, I couldn't process your request at the moment.")
    except requests.exceptions.RequestException as e:
        update.message.reply_text("There was an error connecting to the AI service.")

# Main function to set up the Telegram Bot
def main():
    # Create Updater and pass it your bot's token
    updater = Updater(TELEGRAM_TOKEN, use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # Register command handlers
    dp.add_handler(CommandHandler("start", start))

    # Register message handler to capture symptoms
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    # Start the Bot
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
