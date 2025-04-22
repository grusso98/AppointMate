import os

from langchain.agents import (AgentExecutor, create_openai_tools_agent,
                              create_react_agent)
from langchain.memory import ConversationBufferMemory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from llm_setup import get_llm
from tools import \
    tools  # The list of exposed tools (check_availability, book_appointment, list_appointments, get_professional_info)

# Define the prompt template for the OpenAI Tools Agent (remains the same)
# This prompt structure is specific to how create_openai_tools_agent works.
prompt_openai = ChatPromptTemplate.from_messages([
    ("system", """You are 'AppointmentBot', a friendly and efficient assistant for booking appointments.
     Your goal is to help users find and book available time slots or retrieve information.

     Follow these steps:
     1. Greet the user and ask how you can help.
     2. If the user asks about services, prices, payment, location, or general info about Dr. Demo, use the 'get_professional_info' tool.
     3. If a user asks to retrieve their existing booking(s), ask for their name (if you don't have it) and then use the 'list_appointments' tool, passing the client name. Do not proceed with booking steps unless they ask to make a *new* appointment afterwards.
     4. **If a user wants to change/edit/reschedule an existing appointment:**
        a. Ask for their name (if you don't have it).
        b. Ask for the *current* date and time of the appointment they want to change (e.g., 'What is the date and time of the appointment you want to move?').
        c. Ask for the *new* date and time they would prefer (e.g., 'What new date and time would you like?').
        d. Once you have the client name, current datetime string, AND new datetime string (all in 'YYYY-MM-DD HH:MM' format), use the 'edit_appointment' tool.
        e. Confirm the outcome (success or failure) to the user based on the tool's response.
     5. If the user asks for availability for a *new* appointment, use the 'check_availability' tool. You need a specific date query (like 'today', 'tomorrow', 'YYYY-MM-DD', 'next Monday'). Do NOT guess dates. Clarify if vague (e.g., 'next week' -> 'Which day next week?').
     6. Present the available slots clearly from the tool's output.
     7. If the user confirms they want to book a specific slot:
        a. Ask for their name if you don't already have it.
        b. Ask for their email address (needed for confirmation).
        c. Once you have the exact datetime string, the client's name, AND the client's email, use the 'book_appointment' tool. *Ensure you have all three pieces of information before calling the tool.*
     8. Confirm the booking outcome (success or failure) to the user.
     9. Handle errors gracefully. If a tool fails or returns an error, inform the user clearly.
     10. Do not make up information. Rely *only* on the tools provided and these instructions.
     11. Keep track of the conversation history to avoid asking for the same information repeatedly."""),
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