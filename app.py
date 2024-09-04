import streamlit as st
from openai import OpenAI
import time
import os




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

# Initialize session state variables
if "thread" not in st.session_state:
    st.session_state.thread = client.beta.threads.create()
if "messages" not in st.session_state:
    st.session_state.messages = []


def submit_message(thread, content):
    client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=content
    )
    return client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant_id
    )


def wait_on_run(run, thread):
    while run.status == "queued" or run.status == "in_progress":
        run = client.beta.threads.runs.retrieve(
            thread_id=thread.id,
            run_id=run.id,
        )
        time.sleep(0.5)
    return run


def get_response(thread):
    return client.beta.threads.messages.list(thread_id=thread.id, order='asc')

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
            st.write(message["content"])

# User input
user_input = st.chat_input("Ask a question about Langgraph...")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    with st.spinner('Assistant is thinking...'):
        run = submit_message(st.session_state.thread, user_input)
        run = wait_on_run(run, st.session_state.thread)
        
        if run.status == 'completed':
            response_messages = get_response(st.session_state.thread)
            response = response_messages.data[-1].content[0].text.value
            st.session_state.messages.append({"role": "assistant", "content": response})
    
    st.rerun()

# Footer
st.divider()
