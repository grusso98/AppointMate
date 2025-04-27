import os

from dotenv import load_dotenv
from langchain_community.chat_models import ChatOllama
from langchain_openai import ChatOpenAI

load_dotenv() # Load variables from .env file

MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "openai")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")
OPENAI_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "gpt-4o-mini")

def get_llm():
    """Initializes and returns the appropriate LLM based on configuration."""
    if MODEL_PROVIDER == "ollama":
        print(f"Using Ollama model: {OLLAMA_MODEL} at {OLLAMA_BASE_URL}")
        # Ensure Ollama server is running
        try:
            llm = ChatOllama(model=OLLAMA_MODEL, temperature=0.2, base_url=OLLAMA_BASE_URL)
            # Test connection - Ollama doesn't have a simple ping,
            # invoking might be too slow here. Assume it's running.
            print("Ollama connection assumed successful (no direct ping).")
            return llm
        except Exception as e:
            raise ValueError(f"Failed to initialize Ollama. Is the server running at {OLLAMA_BASE_URL}? Error: {e}")

    elif MODEL_PROVIDER == "openai":
        if not OPENAI_API_KEY or not OPENAI_API_KEY.startswith("sk-"):
             raise ValueError("OPENAI_API_KEY is not set or invalid in .env file.")
        print(f"Using OpenAI model: {OPENAI_MODEL_NAME}")
        try:
            llm = ChatOpenAI(model=OPENAI_MODEL_NAME, temperature=0.2, api_key=OPENAI_API_KEY)
            # Add a simple test invocation if needed, e.g., llm.invoke("test")
            print("OpenAI LLM initialized.")
            return llm
        except Exception as e:
            raise ValueError(f"Failed to initialize OpenAI LLM. Check API key and model name. Error: {e}")
    else:
        raise ValueError(f"Unsupported MODEL_PROVIDER in .env file: {MODEL_PROVIDER}. Choose 'openai' or 'ollama'.")