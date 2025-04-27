import os

from langchain.agents import (AgentExecutor, create_openai_tools_agent,
                              create_react_agent)
from langchain.memory import ConversationBufferMemory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from llm_setup import get_llm
from tools import \
    tools  # The list of exposed tools (check_availability, book_appointment, list_appointments, get_professional_info)
_BASE_PROMPT = """
    You are 'AppointmentBot', a friendly and efficient assistant for booking appointments. Your goal is to help users find and book available time slots or retrieve information based on their requests.

    Key Objectives:
    - Understand User Intent: Evaluate what the user wants to achieve and suggest the appropriate tools and actions.
    - Provide Relevant Information: Use the available tools to fetch and provide the information the user needs.
    - Handle Appointments: Assist with booking, editing, canceling, and retrieving appointments.

    Tools and Their Uses:
    1. get_datetime: Use this tool to know the current date and time.
    2. get_professional_info: Provide information about services, prices, payment, location, or general info about the professional.
    3. list_appointments: Retrieve existing bookings for a user. Requires the client's name.
    4. edit_appointment: Change or reschedule an existing appointment. Requires the client's name, current datetime, and new datetime in 'YYYY-MM-DD HH:MM' format.
    5. cancel_appointment: Cancel a previously booked appointment. Requires the exact timeslot in 'YYYY-MM-DD HH:MM' format and the client's name.
    6. check_availability: Check availability for new appointments. Requires a specific date query (e.g., 'today', 'tomorrow', 'YYYY-MM-DD', 'next Monday'). Use it when you have to book a new appointment or edit an exsisting one.
    7. book_appointment: Book a new appointment. Requires the exact datetime string, client's name, and client's email.

    Guidelines:
    - Greet and Assist: Greet the user and ask how you can help.
    - Evaluate Intent: Based on the user's request, determine the appropriate tool to use.
    - Clarify Information: If the user's request is vague (e.g., 'next week'), clarify the specifics (e.g., 'Which day next week?').
    - Confirm Actions: Before performing any action, confirm the details with the user.
    - Handle Errors: If a tool fails or returns an error, inform the user clearly and suggest alternative actions.
    - Maintain Context: Keep track of the conversation history to avoid asking for the same information repeatedly.

    Example Scenarios:
    - Information Request: If the user asks about services or general info, use the get_professional_info tool.
    - Retrieve Bookings: If the user wants to see their existing bookings, use the list_appointments tool.
    - Edit Appointment: If the user wants to change an appointment, gather the necessary details and use the edit_appointment tool.
    - Cancel Appointment: If the user wants to cancel an appointment, use the cancel_appointment tool.
    - Check Availability: If the user asks for available slots, use the check_availability tool.
    - Book Appointment: If the user wants to book a new appointment, gather the necessary details and use the book_appointment tool.

    Important Notes:
    - Do not make up information. Rely only on the tools provided and these instructions.
    - Ensure you have all required information before calling a tool.
    """
# Define the prompt template for the OpenAI Tools Agent (remains the same)
# This prompt structure is specific to how create_openai_tools_agent works.
prompt_openai = ChatPromptTemplate.from_messages([
    ("system", _BASE_PROMPT),
    MessagesPlaceholder(variable_name="chat_history"),
    ("user", "{input}"),
    # 'agent_scratchpad' for OpenAI tools agent stores intermediate steps like function calls/responses
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])


# Define the prompt template suitable for ReAct Agent
# ReAct relies heavily on the LLM understanding the Thought/Action/Action Input/Observation cycle.
# Often, using a pre-defined ReAct prompt structure is best. We can pull one from the LangChain Hub.
# This prompt includes placeholders for tools, tool_names, input, and agent_scratchpad (for the T/A/AI/O steps)
# If hub access is an issue, a custom string-based template following ReAct format would be the alternative.
try:
    from langchain import hub

    # This prompt structure is designed to guide the LLM through the ReAct steps.
    prompt_react = hub.pull("hwchase17/react-chat")
except ImportError:
    print("Warning: `langchain.hub` not available. ReAct agent might not function optimally without a tailored prompt.")
    prompt_react = None 

def create_memory():
    """Creates a new conversation memory buffer."""
    return ConversationBufferMemory(memory_key="chat_history", return_messages=True, return_intermediate_steps=True) # return_intermediate_steps might be useful for ReAct debugging

def create_agent_executor(llm):
    """Creates the LangChain agent executor instance based on MODEL_PROVIDER."""
    agent = None
    if os.getenv("MODEL_PROVIDER") == "openai":
        print("Creating OpenAI Tools Agent...")
        # Create agent specifically for OpenAI function/tool calling
        agent = create_openai_tools_agent(llm, tools, prompt_openai)

    else: # Assume Ollama or other model requiring ReAct
        print("Creating ReAct Agent for Ollama/other model...")
        if prompt_react:
            # Create a ReAct agent. It uses the LLM to determine the sequence of
            # Thoughts, Actions (tool calls), and Observations.
            # It relies heavily on the LLM's reasoning capabilities and the descriptions of the tools.
            agent = create_react_agent(llm, tools, prompt_react)
        else:
            # Fallback or raise error if prompt couldn't be loaded
            print("ERROR: ReAct prompt not available from Langchain Hub. Agent creation failed.")
            # You might want to raise an exception here or implement a basic string prompt as a fallback
            raise ValueError("Could not create ReAct agent because the prompt is unavailable.")

    # Combine Agent + Tools + Memory into an Executor
    # verbose=True is highly recommended for debugging ReAct agents to see the Thought process
    print("Creating Agent Executor...")
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True, # Set to True to see Thoughts, Actions, Observations
        handle_parsing_errors=True # Gracefully handle cases where the LLM output doesn't perfectly match the expected format
    )
    # Note: We are not explicitly passing memory here. It will be managed per-chat
    # in the main.py `get_agent_for_chat` function by assigning agent_executor.memory.

    return agent_executor