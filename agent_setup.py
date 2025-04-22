import os

from langchain.agents import \
    create_react_agent  # Alternative for Ollama/other models
from langchain.agents import (  # Using OpenAI Tools agent as example
    AgentExecutor, create_openai_tools_agent)
from langchain.memory import ConversationBufferMemory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# Import LLM and Tools
from llm_setup import get_llm
from tools import tools  # The list of exposed tools

# Define the prompt template - this is crucial for agent behavior
# Adjust this prompt based on the agent type and desired personality/instructions
# For OpenAI Tools agent:
prompt = ChatPromptTemplate.from_messages([
    ("system", """You are 'AppointmentBot', a friendly and efficient assistant for booking appointments.
     Your goal is to help users find and book available time slots.

     Follow these steps:
     1. Greet the user and ask how you can help with booking.
     2. If the user asks about services, prices, payment, location, or general info about Dr. Demo, use the 'get_professional_info' tool to provide details.
     3. If a user asks to retrieve a booking instead of making a new reservation, ask for booking name and then use the 'list_client_appointments' tool passing the client name. Do not proceed with the following steps in this case unless stated by the user.
     4. If the user asks for availability, use the 'check_availability' tool. You need a specific date query (like 'today', 'tomorrow', 'YYYY-MM-DD', 'next Monday'). Do NOT guess dates. If the user is vague (e.g. 'next week'), ask them to specify a day.
        4.1. Present the available slots clearly to the user as returned by the tool.
        4.2. If the user confirms they want to book a specific slot (e.g., 'Book 2025-04-28 14:00'), ask for their name if you don't have it already. You MUST have the client's name.
        4.3. Also ask for the client's email to send them the booking confirmation.
        4.4. Once you have the exact datetime string, the client's name and the email, use the 'book_appointment' tool.
        4.5. Confirm the booking outcome (success or failure) to the user based on the tool's response.
        4.6. Handle errors gracefully. If a tool fails, inform the user and suggest trying again or providing different information.
        4.7. Do not make up information about availability or bookings. Only use the tools provided.
     5. Keep track of the conversation history.
     """),
    MessagesPlaceholder(variable_name="chat_history"),
    ("user", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"), # Crucial placeholder for agent intermediate steps
])

# Agent Memory (one instance per conversation/chat_id)
def create_memory():
    """Creates a new conversation memory buffer."""
    return ConversationBufferMemory(memory_key="chat_history", return_messages=True)

# Create the Agent (will be called per user session)
def create_agent_executor(llm):
    """Creates the LangChain agent executor instance."""
    # Assuming OpenAI Tools agent for this example
    # If using Ollama, you might prefer create_react_agent or another type
    if os.getenv("MODEL_PROVIDER") == "openai":
        agent = create_openai_tools_agent(llm, tools, prompt)
    else:
        # For Ollama/other models, ReAct is often a good choice
        # Note: ReAct prompt structure is different. You'd need to adapt the prompt above.
        # from langchain.agents import create_react_agent
        # react_prompt = ... # Define a ReAct compatible prompt
        # agent = create_react_agent(llm, tools, react_prompt)
        # Fallback to OpenAI tools agent structure for simplicity in demo,
        # but acknowledge it might not be optimal for non-OpenAI models.
        print("Warning: Using OpenAI Tools agent structure with non-OpenAI model. ReAct agent might be more suitable.")
        agent = create_openai_tools_agent(llm, tools, prompt)


    # Combine Agent + Tools + Memory
    # verbose=True helps in debugging - shows agent thought process
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
    return agent_executor
