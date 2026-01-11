# from langchain_groq import ChatGroq
# from langchain_core.messages import HumanMessage

# # Initialize Groq LLM
# llm = ChatGroq(
#     model="llama-3.1-8b-instant",
#     temperature=0.3,
# )

# # Invoke model
# response = llm.invoke([
#     HumanMessage(content="What is deep learning?")
# ])

# print(response.content)



# from dotenv import load_dotenv
# import os

# from langchain_groq import ChatGroq
# from langchain_core.messages import HumanMessage

# # Load environment variables
# load_dotenv()

# # Read API key
# api_key = os.getenv("GROQ_API_KEY")

# # Initialize LLM
# llm = ChatGroq(
#     model="llama-3.1-8b-instant",
#     temperature=0.3,
#     api_key=api_key
# )

# # Ask question
# response = llm.invoke([
#     HumanMessage(content="What is a data scientist? Explain step by step.")
# ])







import streamlit as st
from dotenv import load_dotenv
import os

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage

# Load .env
load_dotenv()

# Page config
st.set_page_config(
    page_title="Groq LLM Test (LangChain + Streamlit)",
    page_icon="⚡",
    layout="centered"
)

st.title("⚡ Groq LLM Test (LangChain + Streamlit)")

# Get API key
api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    st.error("❌ GROQ_API_KEY not found. Please set it in your .env file.")
    st.stop()

# Initialize LLM
llm = ChatGroq(
    model="llama-3.1-8b-instant",
    temperature=0.3,
    api_key=api_key
)

# User input
user_input = st.text_input(
    "Enter your prompt:",
    value="What is a data scientist? Explain step by step."
)

# Run model
if st.button("🚀 Run LLM"):
    if not user_input.strip():
        st.warning("Please enter a prompt.")
    else:
        with st.spinner("Thinking..."):
            response = llm.invoke([
                HumanMessage(content=user_input)
            ])

        st.subheader("📘 Response")
        st.write(response.content)

 
