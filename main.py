import logging
import os

import telegram
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (Application, CommandHandler, ContextTypes,
                          MessageHandler, filters)

from agent_setup import create_agent_executor, create_memory
from database import initialize_database  # Ensure DB is ready
# Import project components
from llm_setup import get_llm

# Load environment variables from .env file
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# --- Logging ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING) # Reduce noisy logging from http client
logger = logging.getLogger(__name__)

# --- Global LLM instance (initialize once) ---
try:
    LLM = get_llm()
except ValueError as e:
    logger.error(f"Failed to initialize LLM: {e}")
    LLM = None # Set LLM to None if initialization fails

# --- Store agent executors and memory per chat_id ---
# Use context.chat_data provided by python-telegram-bot for per-chat storage
# context.chat_data is a dict unique to each chat

AGENT_EXECUTOR_KEY = 'agent_executor'
AGENT_MEMORY_KEY = 'agent_memory'

def get_agent_for_chat(context: ContextTypes.DEFAULT_TYPE):
    """Gets or creates an agent executor and memory for the current chat."""
    if AGENT_EXECUTOR_KEY not in context.chat_data:
        logger.info(f"Creating new agent executor for chat_id: {context._chat_id}")
        if LLM is None:
             raise RuntimeError("LLM is not initialized. Cannot create agent.")
        memory = create_memory()
        agent_executor = create_agent_executor(LLM) # Create the agent structure
        context.chat_data[AGENT_MEMORY_KEY] = memory
        context.chat_data[AGENT_EXECUTOR_KEY] = agent_executor # Store the executor
    # Retrieve memory and agent
    memory = context.chat_data[AGENT_MEMORY_KEY]
    agent_executor = context.chat_data[AGENT_EXECUTOR_KEY]
    # Link the current memory instance to the agent executor for this run
    agent_executor.memory = memory
    return agent_executor

# --- Telegram Command Handlers ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a welcome message when the /start command is issued."""
    user_name = update.message.from_user.first_name
    # Clear previous agent state for this chat on /start
    if AGENT_EXECUTOR_KEY in context.chat_data:
        del context.chat_data[AGENT_EXECUTOR_KEY]
    if AGENT_MEMORY_KEY in context.chat_data:
        del context.chat_data[AGENT_MEMORY_KEY]
        logger.info(f"Cleared agent state for chat_id: {update.message.chat_id}")

    await update.message.reply_text(f'Hello {user_name}! I am AppointmentBot. How can I help you book an appointment today?')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a help message when the /help command is issued."""
    await update.message.reply_text("""
I can help you check appointment availability and book a slot.

You can ask things like:
- "Are there any slots available tomorrow?"
- "Check availability for next Tuesday"
- "See slots for 2025-07-15"

Once you see available slots (like '2025-07-15 14:00'), you can book by saying:
- "Book 2025-07-15 14:00"
I will then ask for your name to complete the booking.

Use /start to reset our conversation.
    """)


# --- Telegram Message Handler ---

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles regular text messages by invoking the LangChain agent."""
    if LLM is None:
        await update.message.reply_text("Sorry, the booking agent is currently unavailable. Please try again later.")
        return

    chat_id = update.message.chat_id
    user_input = update.message.text
    user_name = update.message.from_user.first_name # Get user's first name for booking

    logger.info(f"Received message from chat_id {chat_id}: {user_input}")

    try:
        # Get or create the agent executor for this chat, linking memory
        agent_executor = get_agent_for_chat(context)

        # Show typing indicator
        await context.bot.send_chat_action(chat_id=chat_id, action=telegram.constants.ChatAction.TYPING)

        # Invoke the agent asynchronously ONLY with the 'input' key
        # The agent's prompt should guide it to ask for the name if needed for booking.
        logger.debug(f"Invoking agent for chat {chat_id} with input: '{user_input}'")
        response = await agent_executor.ainvoke({"input": user_input})

        ai_response = response.get('output', "Sorry, I didn't get a valid response.")
        logger.debug(f"Agent response for chat {chat_id}: '{ai_response}'")

    except RuntimeError as e: # Catch LLM initialization error
         logger.error(f"RuntimeError during agent execution for chat {chat_id}: {e}")
         ai_response = "Sorry, the booking agent is currently unavailable due to an internal issue."
    except Exception as e:
        logger.error(f"Agent execution error for chat {chat_id}: {e}", exc_info=True)
        ai_response = "Sorry, I encountered an error processing your request. Please try rephrasing or use /start to begin again."

    # Send the agent's response back to the user
    await update.message.reply_text(ai_response)


# --- Main Bot Execution ---

def main() -> None:
    """Starts the Telegram bot."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("FATAL: TELEGRAM_BOT_TOKEN environment variable not set.")
        return

    if LLM is None:
        logger.error("FATAL: LLM could not be initialized. Check API keys/Ollama setup. Bot cannot start.")
        return

    # Initialize database explicitly on start, although import does it too
    initialize_database()

    # Create the Telegram Application and pass it the bot's token.
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Register command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))

    # Register message handler for non-command text messages
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Start the Bot
    logger.info("Starting Telegram bot polling...")
    application.run_polling()


if __name__ == '__main__':
    main()