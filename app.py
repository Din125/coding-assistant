import streamlit as st
from openai import OpenAI
import time
import os
import requests  
import json  


# Initialize OpenAI client
openai_api_key = st.secrets["OPENAI_API_KEY"]
if not openai_api_key:
    st.error("OpenAI API key is missing. Please check your .env file.")
    st.stop()

client = OpenAI(api_key=openai_api_key)

assistant_id = st.secrets["ASSISTANT_ID"]
if not assistant_id:
    st.error("Assistant ID is missing. Please check your .env file.")
    st.stop()

# Add Tavily API key
tavily_api_key = st.secrets["TAVILY_API_KEY"]
if not tavily_api_key:
    st.error("Tavily API key is missing. Please check your .env file.")
    st.stop()

# Define Tavily search function
def tavily_search(query):
    url = "https://api.tavily.com/search"
    headers = {
        "Content-Type": "application/json"
    }
    payload = {
        "api_key": tavily_api_key,
        "query": query,
        "search_depth": "advanced",
        "include_images": False,
    }
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        return {"error": f"Tavily API request failed with status code {response.status_code}"}

# Define the function for the assistant
functions = [
    {
        "name": "tavily_search",
        "description": "Perform a web search using the Tavily API",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query"
                }
            },
            "required": ["query"]
        }
    }
]

# Initialize session state variables
if "thread" not in st.session_state:
    st.session_state.thread = client.beta.threads.create()
if "messages" not in st.session_state:
    st.session_state.messages = []

# Update the submit_message function
def submit_message(thread, content):
    client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=content
    )
    return client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant_id,
        tools=[{"type": "function", "function": func} for func in functions]
    )

# Update the wait_on_run function
def wait_on_run(run, thread):
    while run.status not in ["completed", "failed", "requires_action"]:
        time.sleep(0.5)
        run = client.beta.threads.runs.retrieve(
            thread_id=thread.id,
            run_id=run.id,
        )

    if run.status == "requires_action":
        tool_calls = run.required_action.submit_tool_outputs.tool_calls
        tool_outputs = []
        for tool_call in tool_calls:
            if tool_call.function.name == "tavily_search":
                try:
                    arguments = json.loads(tool_call.function.arguments)
                    query = arguments.get("query")
                    if query:
                        result = tavily_search(query)
                        tool_outputs.append({
                            "tool_call_id": tool_call.id,
                            "output": json.dumps(result)
                        })
                except json.JSONDecodeError:
                    pass
                except Exception as e:
                    pass
        
        if tool_outputs:
            run = client.beta.threads.runs.submit_tool_outputs(
                thread_id=thread.id,
                run_id=run.id,
                tool_outputs=tool_outputs
            )
            return wait_on_run(run, thread)
    
    return run

# Update the get_response function
def get_response(thread):
    messages = client.beta.threads.messages.list(thread_id=thread.id, order='desc')
    return [
        {
            "role": msg.role,
            "content": msg.content[0].text.value if msg.content else "",
            "annotations": msg.content[0].text.annotations if msg.content else []
        }
        for msg in messages.data
    ]

# Set page config
st.set_page_config(page_title="Langgraph Coding Assistant", layout="wide", page_icon="💻")

# Sidebar content
with st.sidebar:
    st.markdown("## About")
    st.write("""
    The Langgraph Coding Assistant is a tool designed to help developers with Langgraph-related coding questions and issues. It provides guidance, explanations, and code suggestions for working with Langgraph agents.
    """)

# Main content
st.title("Langgraph Coding Assistant")
st.divider()

# Chat interface
chat_container = st.container()

with chat_container:
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if "annotations" in message:
                for annotation in message["annotations"]:
                    if annotation.type == "file_citation":
                        st.info(f"Citation: {annotation.text}")
                    elif annotation.type == "file_path":
                        st.info(f"File Path: {annotation.text}")

# User input
user_input = st.chat_input("Ask a question about Langgraph...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    with st.spinner('Assistant is thinking...'):
        run = submit_message(st.session_state.thread, user_input)
        run = wait_on_run(run, st.session_state.thread)
        
        if run.status == 'completed':
            response_messages = get_response(st.session_state.thread)
            for msg in response_messages:
                if msg["role"] == "assistant" and msg not in st.session_state.messages:
                    st.session_state.messages.append(msg)
    
    st.rerun()

# Footer
st.divider()
