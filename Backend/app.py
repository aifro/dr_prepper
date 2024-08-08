import streamlit as st
st.set_page_config(page_title="Health Assistant Chatbot", page_icon="🏥", layout="wide")

# Custom CSS to improve layout
st.markdown("""
<style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stApp {
        margin-bottom: 0px;
    }
    .stSidebar {
        background-color: #2E2E2E;
    }
    .stSidebar [data-testid="stMarkdownContainer"] {
        color: white;
    }
    .stButton button {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# Force Streamlit to use port 8502
import os
os.environ['STREAMLIT_SERVER_PORT'] = '8502'

import time
import json
from openai import OpenAI
import io
from markdown2 import Markdown
from dotenv import load_dotenv
load_dotenv()

if not os.getenv("OPENAI_API_KEY"):
    st.error("OpenAI API key is not set. Please set the OPENAI_API_KEY environment variable.")
    st.stop()

try:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
except Exception as e:
    st.error(f"Error initializing OpenAI client: {str(e)}")
    st.stop()

ASSISTANT_IDS = {
    "stage1": "asst_a9s6wbqUHXkbIX2vTj5DstO1",
    "stage2": "asst_WfpGAAkD9g0CHzPeHk3FZUD5",
    "stage3": "asst_JeCRuyTbKUi0P3gQh1mTT4yU",
    "stage4": "asst_VI2qxTfRSjFh7SHnEQdH20Lu",
    "stage5": "asst_VkefuaYBuipFKCtxf7cx3fsj"
}

STAGE_TITLES = {
    "stage0": "Fill this out to begin",
    "stage1": "Stage 1: Initial Assessment",
    "stage2": "Stage 2: Possible Diagnoses",
    "stage3": "Stage 3: Narrowing Down Diagnoses",
    "stage4": "Stage 4: Treatment Options",
    "stage5": "Stage 5: Summary for your doctor"
}

# Import SerpAPI library
import os
from serpapi import GoogleSearch

# Get SerpAPI key from environment variable
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")
if not SERPAPI_API_KEY:
    st.error("SerpAPI key is not set. Please set the SERPAPI_API_KEY environment variable.")
    st.stop()

# Define SerpAPI search function
def search_google(query, search_type=None):
    try:
        params = {
            "engine": "google",
            "q": query,
            "api_key": SERPAPI_API_KEY,
            "num": 5  # Limit to 5 results
        }
        search = GoogleSearch(params)
        results = search.get_dict()
        st.write(f"Search results for '{query}' (type: {search_type}):", results)
        
        # Extract and return relevant information
        organic_results = results.get('organic_results', [])
        extracted_results = [
            {
                'title': result.get('title'),
                'link': result.get('link'),
                'snippet': result.get('snippet')
            }
            for result in organic_results
        ]
        return extracted_results
    except Exception as e:
        st.error(f"Error in Google search: {str(e)}")
        return {"error": str(e)}

def generate_response(thread_id, assistant_id, prompt, stage):
    try:
        stage_instructions = {
            "stage1": "Provide an initial assessment based on the user's information.",
            "stage2": "Determine the top 5 possible diagnoses based on the information provided.",
            "stage3": "Analyze the 5 possible diagnoses and rank them from most to least likely. Present this in a markdown table.",
            "stage4": "Provide the top 3 treatment options for each diagnosis.",
            "stage5": "Summarize all information for the doctor."
        }
        
        full_prompt = f"Current stage: {stage}. Instructions: {stage_instructions.get(stage, '')}. User input: {prompt}"
        
        client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=full_prompt
        )

        run = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=assistant_id
        )

        while run.status not in ["completed", "failed"]:
            time.sleep(0.5)
            run = client.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)
            
            if run.status == "requires_action":
                st.write("Function call required")
                tool_calls = run.required_action.submit_tool_outputs.tool_calls
                tool_outputs = []
                for tool_call in tool_calls:
                    function_name = tool_call.function.name
                    function_args = json.loads(tool_call.function.arguments)
                    st.write(f"Function called: {function_name}")
                    st.write(f"Arguments: {function_args}")
                    
                    if function_name in ["search_statistics", "search_treatments"]:
                        output = search_google(f"{function_args['condition']} {function_args['treatment_type']}")
                    else:
                        output = f"Error: Unknown function {function_name}"
                    
                    tool_outputs.append({
                        "tool_call_id": tool_call.id,
                        "output": json.dumps(output)
                    })
                
                st.write("Submitting tool outputs:", tool_outputs)
                client.beta.threads.runs.submit_tool_outputs(
                    thread_id=thread_id,
                    run_id=run.id,
                    tool_outputs=tool_outputs
                )

        if run.status == "failed":
            st.error(f"Run failed: {run.last_error}")
            return None

        messages = client.beta.threads.messages.list(thread_id=thread_id)
        for message in messages:
            if message.role == "assistant":
                return message.content[0].text.value

    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
        return None

def create_pdf(summary):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    # Add title
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt="Health Summary", ln=1, align='C')
    pdf.ln(10)
    
    # Add content
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 10, txt=summary)
    
    # Save the pdf to a BytesIO object
    pdf_output = io.BytesIO()
    pdf.output(pdf_output)
    pdf_output.seek(0)
    return pdf_output

st.title("Health Assistant Chatbot")

if "stage" not in st.session_state:
    st.session_state.stage = "stage0"

if "thread_id" not in st.session_state:
    st.session_state.thread_id = client.beta.threads.create().id

if "messages" not in st.session_state:
    st.session_state.messages = []

if "user_info" not in st.session_state:
    st.session_state.user_info = None

st.sidebar.title("Stages")
for stage, title in STAGE_TITLES.items():
    if stage == st.session_state.stage:
        st.sidebar.markdown(f"**{title}**")
    else:
        st.sidebar.markdown(title)

if st.session_state.stage == "stage0":
    st.write("Please fill out this form to begin:")
    with st.form("user_info_form"):
        health_issue = st.text_input("What is the single health related issue you want to focus on today?")
        issue_duration = st.text_input("How long have you had this issue?")
        resolution_attempts = st.text_area("What have you done to try to resolve this issue? List surgeries, medication, therapy, counseling, etc.")
        family_history = st.text_input("Does this issue run in your family history? If so, what percent of family members have this issue?")
        birth_year = st.number_input("What year were you born?", min_value=1900, max_value=2023, step=1)
        exercise_habits = st.text_input("How many days a week do you exercise and for how long?")
        diet_rating = st.slider("On a scale from 1-10, how healthy do you eat?", 1, 10, 5)
        sleep_hours = st.number_input("How many hours of sleep do you get a night on average?", min_value=0, max_value=24, step=1)
        
        submit_button = st.form_submit_button("Submit")
        if submit_button:
            st.session_state.user_info = {
                "health_issue": health_issue,
                "issue_duration": issue_duration,
                "resolution_attempts": resolution_attempts,
                "family_history": family_history,
                "birth_year": birth_year,
                "exercise_habits": exercise_habits,
                "diet_rating": diet_rating,
                "sleep_hours": sleep_hours
            }
            st.session_state.stage = "stage1"
            initial_prompt = f"User information: {json.dumps(st.session_state.user_info)}. Please provide an initial assessment based on this information and ask for the user's consent to proceed."
            with st.spinner("Processing your information..."):
                response = generate_response(st.session_state.thread_id, ASSISTANT_IDS["stage1"], initial_prompt, "stage1")
            st.session_state.messages.append({"role": "assistant", "content": response})
            st.rerun()

# Display chat messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat container at the bottom
st.markdown('<div class="chat-container">', unsafe_allow_html=True)

user_input = st.chat_input("Type your message here...")

st.markdown('<div class="button-container">', unsafe_allow_html=True)
col1, col2 = st.columns(2)
with col1:
    if st.button("Reset Chat", key="reset_chat"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

with col2:
    if st.session_state.stage == "stage5":
        if st.button("Download your Summary", key="download_summary"):
            summary = next((msg['content'] for msg in reversed(st.session_state.messages) if msg['role'] == 'assistant'), None)
            if summary:
                pdf = create_pdf(summary)
                if pdf:
                    st.download_button(
                        label="Click here to download your summary",
                        data=pdf,
                        file_name="health_summary.pdf",
                        mime="application/pdf"
                    )
                else:
                    st.error("PDF generation failed. Please try again later.")
            else:
                st.error("No summary available to download.")
    else:
        next_stage = f"stage{int(st.session_state.stage[-1]) + 1}"
        next_stage_title = STAGE_TITLES.get(next_stage, "Finish")
        if st.button(f"Continue to {next_stage_title}", key="continue_button"):
            current_stage = int(st.session_state.stage[-1])
            if current_stage < 5:
                st.session_state.stage = next_stage
                summary_prompt = f"Provide a summary for {next_stage_title}. Start your summary with 'Summary for {next_stage_title}:'"
                with st.spinner("Generating summary..."):
                    summary = generate_response(st.session_state.thread_id, ASSISTANT_IDS[next_stage], summary_prompt, next_stage)
                st.session_state.messages.append({"role": "assistant", "content": summary})
            st.rerun()

st.markdown('</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.spinner("Generating response..."):
        response = generate_response(st.session_state.thread_id, ASSISTANT_IDS[st.session_state.stage], user_input, st.session_state.stage)
    st.session_state.messages.append({"role": "assistant", "content": response})
    st.rerun()

assistant3 = client.beta.assistants.retrieve(ASSISTANT_IDS["stage3"])
assistant4 = client.beta.assistants.retrieve(ASSISTANT_IDS["stage4"])

st.write("Assistant 3 configuration:", assistant3)
st.write("Assistant 4 configuration:", assistant4)