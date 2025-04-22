# AppointMate: Appointment Agent App

A conversational AI agent built with LangChain that allows users to book appointments with a professional via Telegram. The agent can check availability based on a schedule stored in an SQLite database and confirm bookings, optionally sending email notifications.

## Functionalities

* **Conversational Interface:** Interacts with users naturally through Telegram.
* **Availability Checking:**
    * Understands natural language date queries (e.g., "today", "tomorrow", "next Friday", "July 10th") using `dateparser`.
    * Consults an SQLite database for existing appointments.
    * Checks against predefined working hours.
    * Presents available time slots to the user.
* **Appointment Booking:**
    * Guides the user to select a specific available slot.
    * Prompts the user for their name if not already provided in the conversation.
    * Saves the confirmed appointment to the SQLite database, preventing double booking.
* **LLM Integration:** Supports using different Language Models:
    * OpenAI models (e.g., GPT-4o-mini) via API.
    * Local models via Ollama (e.g., Llama 3).
* **(Optional) Email Notifications:**
    * Sends a confirmation email to the professional upon successful booking.
    * Attaches an `.ics` calendar invite file for easy addition to calendars (like Google Calendar, Outlook).
    * Requires SMTP configuration in the `.env` file to function.

## Technology Stack

* **Python 3.8+**
* **LangChain:** Core framework for building the agent, managing prompts, tools, and memory.
* **LLMs:**
    * `langchain-openai` for OpenAI models.
    * `langchain-community` (ChatOllama) for Ollama models.
* **Telegram:** `python-telegram-bot` library for the user interface.
* **Database:** `sqlite3` (Python built-in) for storing appointments.
* **Date Parsing:** `dateparser` for understanding user date queries.
* **Calendar Invites:** `ics` library for generating `.ics` files.
* **Email:** `smtplib` (Python built-in) for sending notifications.
* **Configuration:** `python-dotenv` for managing environment variables.

## Prerequisites

* **Python 3.8 or higher:** [Install Python](https://www.python.org/downloads/)
* **Telegram Account:** Needed to create a bot and interact with it.
* **(Optional) Ollama:** If you want to use local models, install Ollama and pull a model:
    * [Install Ollama](https://ollama.com/)
    * Run `ollama pull llama3` (or another model of your choice) in your terminal. Ensure Ollama is running (`ollama serve`).
* **(Optional) OpenAI API Key:** If you want to use OpenAI models. [Get an API key](https://platform.openai.com/api-keys).
* **(Optional) Dedicated Email Account:** Strongly recommended for sending notifications (e.g., a new Gmail account). See Configuration section for details on App Passwords.

## Setup & Installation

1.  **Clone the Repository (or Download Files):**
    ```bash
    # If you have it in a git repository:
    git clone <your-repo-url>
    cd appointment-agent-demo
    # Otherwise, navigate to the directory where you saved the project files.
    ```

2.  **Create and Activate a Virtual Environment:**
    ```bash
    # Create venv
    python -m venv venv

    # Activate venv
    # On macOS/Linux:
    source venv/bin/activate
    # On Windows:
    .\venv\Scripts\activate
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Create a Telegram Bot:**
    * Open Telegram and search for `BotFather`.
    * Send `/newbot` and follow the instructions to choose a name and username (ending in `bot`).
    * **Copy the HTTP API token** provided by BotFather. You'll need it for the configuration.

5.  **Configure Environment Variables:**
    * Make a copy of the `.env.example` file (if provided) or create a new file named `.env` in the project's root directory (`appointment_agent_demo/`).
    * **Add `.env` to your `.gitignore` file** to avoid committing secrets.
    * Edit the `.env` file and fill in the required values (see Configuration section below).

## Configuration (`.env` file)

Create a `.env` file in the project root with the following variables. Fill them according to your setup:

```dotenv
# --- Telegram ---
TELEGRAM_BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN_HERE" # Paste the token from BotFather

# --- LLM Configuration ---
MODEL_PROVIDER="openai" # Change to "ollama" to use a local model via Ollama
# MODEL_PROVIDER="ollama"

# --- OpenAI Settings (Required if MODEL_PROVIDER="openai") ---
OPENAI_API_KEY="sk-YOUR_OPENAI_API_KEY_HERE"       # Your OpenAI secret key
OPENAI_MODEL_NAME="gpt-4o-mini"                   # Or another OpenAI model like "gpt-4"

# --- Ollama Settings (Required if MODEL_PROVIDER="ollama") ---
OLLAMA_BASE_URL="http://localhost:11434"          # Default Ollama API URL
OLLAMA_MODEL="llama3"                             # Model name you pulled with Ollama (e.g., llama3, mistral)

# --- Professional & Email Settings ---
PROFESSIONAL_EMAIL="professional_recipient@example.com" # Professional's email for notifications
PROFESSIONAL_NAME="Dr. Demo"                          # Name used in email greeting
APPOINTMENT_DURATION_MINUTES=60                     # Default duration for appointments

# --- SMTP Settings (Required ONLY for sending email notifications) ---
# Strongly recommend using a dedicated email account (e.g., Gmail) and an App Password
SMTP_SERVER="smtp.gmail.com"                      # SMTP server address (e.g., smtp.gmail.com, smtp.office365.com)
SMTP_PORT=587                                     # SMTP port (587 for TLS is common)
SMTP_USER="your_bot_email_account@gmail.com"        # FULL email address the bot sends FROM
SMTP_PASSWORD="your_16_character_app_password"    # **Use App Password** for Gmail/Outlook with 2FA, NOT your regular password
```

Notes on Email Configuration:

    Email sending is optional. If you leave the SMTP_* variables blank or incomplete, the bot will function but skip sending emails.
    For Gmail/Google Workspace, you must enable 2-Step Verification on the SMTP_USER account and then generate a 16-character App Password. Use this App Password for SMTP_PASSWORD. Do not use your regular Google account password.
    For Outlook/Office365, similar App Password mechanisms may be required depending on your organization's security settings. Check Microsoft's documentation.


## Running the bot
Ensure your virtual environment is activated.
Make sure Ollama is running if you set ```MODEL_PROVIDER="ollama"```.

Run the main script from the project's root directory:
```
python main.py
```
The bot should start polling for messages. You'll see log output in the terminal.

## Usage
Open Telegram and find the bot you created.
Send ```/start``` to initialize the conversation (this also clears any previous chat state with the bot).
Send ```/help``` to see basic instructions.

### Interact naturally
Check Availability: ```"Are there slots for tomorrow?", "Check availability next Monday", "Any appointments on 2025-07-20?"```

Book Appointment: ```After seeing available slots like 2025-07-20 14:00, respond with "Book 2025-07-20 14:00". The bot will then ask for your name if needed.```