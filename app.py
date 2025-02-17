import streamlit as st
import dotenv
import os
import google.generativeai as genai
from datetime import datetime, timedelta
import json

# Set up the page configuration
st.set_page_config(
    page_title="Healthcare Virtual Assistant",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Set up theme colors
st.markdown("""
<style>
body {
    color: #333;
    background-color: #f5f5f5;
}
.streamlit-sdk {
    color: #666;
}
</style>
""", unsafe_allow_html=True)

# Load environment variables
dotenv.load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Initialize Gemini model
def initialize_model():
    return genai.GenerativeModel("gemini-pro")

# Define base system prompt
BASE_CONTEXT = """You are an empathetic, professional healthcare virtual assistant for U.S. healthcare facilities. Your primary goals are to:
1. Provide warm, supportive assistance while maintaining medical professionalism
2. Ensure patient privacy and confidentiality
3. Give clear, accurate information within scope
4. Express genuine concern for patient well-being
5. Maintain cultural sensitivity
6. Guide patients to appropriate resources when needed

Remember to:
- Use natural, conversational language
- Show empathy and understanding
- Verify important information
- Provide clear next steps
- Respect medical privacy guidelines
- Redirect out-of-scope queries appropriately"""

# Define conversation flows
CONVERSATION_FLOWS = {
    "urgent_care_booking": {
        "steps": [
            {
                "id": "initial_symptoms",
                "prompt": "I understand you need an urgent care appointment. Could you please describe your current symptoms or urgent care needs?",
                "required_info": ["symptoms", "severity"],
                "next_step": "verify_urgency"
            },
            {
                "id": "verify_urgency",
                "prompt": "Based on your symptoms, I'll help schedule an urgent care visit. Do you have any of these severe symptoms: severe pain, difficulty breathing, or high fever?",
                "required_info": ["urgency_level"],
                "next_step": "collect_patient_info"
            },
            {
                "id": "collect_patient_info",
                "prompt": "To schedule your appointment, I'll need:\n- Your full name\n- Date of birth\n- Insurance provider (if any)\nPlease provide these details.",
                "required_info": ["name", "dob", "insurance"],
                "next_step": "time_preference"
            },
            {
                "id": "time_preference",
                "prompt": "We have the following urgent care slots available today:\n- 10:00 AM\n- 11:30 AM\n- 2:00 PM\nWhich time works best for you?",
                "required_info": ["preferred_time"],
                "next_step": "confirmation"
            },
            {
                "id": "confirmation",
                "prompt": "I'll confirm your urgent care appointment for [time] today. Would you like me to proceed with the booking?",
                "required_info": ["confirmation"],
                "next_step": "final_instructions"
            },
            {
                "id": "final_instructions",
                "prompt": "Your appointment is confirmed. Please bring:\n- Photo ID\n- Insurance card\n- List of current medications\n- Mask\nPlease arrive 15 minutes early. Do you need directions to the facility?",
                "required_info": ["needs_directions"],
                "next_step": None
            }
        ]
    },
    "post_surgical_recovery": {
        "steps": [
            {
                "id": "verify_procedure",
                "prompt": "To provide accurate recovery instructions, could you confirm which surgical procedure you had and when it was performed?",
                "required_info": ["procedure", "surgery_date"],
                "next_step": "current_status"
            },
            {
                "id": "current_status",
                "prompt": "How are you feeling now? Any specific concerns about your recovery?",
                "required_info": ["current_symptoms", "concerns"],
                "next_step": "review_instructions"
            },
            {
                "id": "review_instructions",
                "prompt": "Let's review your post-surgical care instructions. Which aspect would you like to discuss first:\n- Pain management\n- Wound care\n- Activity restrictions\n- Follow-up appointments",
                "required_info": ["topic_preference"],
                "next_step": "specific_guidance"
            },
            {
                "id": "specific_guidance",
                "prompt": "I'll provide specific guidance for [topic]. What questions do you have about this aspect of your recovery?",
                "required_info": ["understanding"],
                "next_step": "next_steps"
            },
            {
                "id": "next_steps",
                "prompt": "Based on your recovery timeline, here are your next steps. Would you like me to schedule your follow-up appointment?",
                "required_info": ["schedule_followup"],
                "next_step": None
            }
        ]
    },
    "medication_alerts": {
        "steps": [
            {
                "id": "initial_info",
                "prompt": "I'll help set up medication alerts. Please provide:\n- Patient's name\n- Your relationship to them\n- Any existing medication schedule",
                "required_info": ["patient_name", "relationship", "current_schedule"],
                "next_step": "medication_details"
            },
            {
                "id": "medication_details",
                "prompt": "For each medication, please provide:\n- Name\n- Dosage\n- Frequency\n- Special instructions",
                "required_info": ["medications"],
                "next_step": "alert_preferences"
            },
            {
                "id": "alert_preferences",
                "prompt": "How would you like to receive alerts?\n- Text message\n- Email\n- Mobile app\nAnd how early would you like to be reminded?",
                "required_info": ["alert_method", "reminder_timing"],
                "next_step": "confirmation"
            },
            {
                "id": "confirmation",
                "prompt": lambda info: generate_alert_summary(info),
                "required_info": ["confirm_schedule"],
                "next_step": None
            }
        ]
    }
}

def generate_alert_summary(info):
    """Generate a formatted summary of medication alerts"""
    alert_method = info.get('alert_method', '')
    reminder_timing = info.get('reminder_timing', '')
    medications = info.get('medications', '')
    
    summary = f"""Based on your preferences, I'll set up the following alert schedule:
    Alert Method: {alert_method}
    Reminder Timing: {reminder_timing} before each medication
    Medications Schedule: {medications}
    Would you like to confirm this setup?"""
    return summary

# Initialize Streamlit interface
# Initialize Streamlit interface
main_container = st.container()
with main_container:
    # Header
    st.title("Healthcare Virtual Assistant")
        
    

# Initialize session state
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'current_flow' not in st.session_state:
    st.session_state.current_flow = None
if 'flow_step' not in st.session_state:
    st.session_state.flow_step = None
if 'collected_info' not in st.session_state:
    st.session_state.collected_info = {}

# Add custom styling for chat interface
st.markdown("""
<style>
.chat-container {
    display: flex;
    flex-direction: column;
    padding: 20px;
    background-color: #f5f5f5;
    border-radius: 8px;
    max-height: 500px;
    overflow-y: auto;
}

.chat-message {
    padding: 12px;
    border-radius: 8px;
    margin-bottom: 8px;
    max-width: 70%;
    position: relative;
}

.user-message {
    background-color: #007bff;
    color: white;
    align-self: flex-end;
    border-bottom-right-radius: 4px;
}

.assistant-message {
    background-color: #e9ecef;
    color: black;
    align-self: flex-start;
    border-bottom-left-radius: 4px;
}

.chat-input-container {
    display: flex;
    gap: 10px;
    padding: 20px;
    background-color: white;
    border-radius: 8px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.chat-input {
    flex: 1;
    padding: 12px;
    border: 1px solid #e9ecef;
    border-radius: 20px;
    font-size: 14px;
}

.chat-button {
    padding: 12px 24px;
    background-color: #007bff;
    color: white;
    border: none;
    border-radius: 20px;
    cursor: pointer;
    font-size: 14px;
}

.chat-button:hover {
    background-color: #0056b3;
}

.chat-button:active {
    transform: translateY(1px);
}

.chat-container::-webkit-scrollbar {
    width: 4px;
}

.chat-container::-webkit-scrollbar-track {
    background: #f5f5f5;
}

.chat-container::-webkit-scrollbar-thumb {
    background: #007bff;
    border-radius: 2px;
}
</style>
""", unsafe_allow_html=True)
# Sidebar flow selection
with st.sidebar:
    st.write("---")
    st.header("Conversation Flows")
    
    flow_options = {
        "Urgent Care Booking": "urgent_care_booking",
        "Post-Surgical Recovery": "post_surgical_recovery",
        "Medication Alerts Setup": "medication_alerts"
    }
    
    selected_flow = st.selectbox(
        "Select Conversation Type",
        ["None"] + list(flow_options.keys()),
        help="Choose a specific healthcare service"
    )

# Chat interface
chat_area = st.container()
with chat_area:
    # Display chat history with styled messages
    for message in st.session_state.chat_history:
        msg_class = "user-message" if message["role"] == "user" else "assistant-message"
        st.markdown(f'<div class="chat-message {msg_class}">{message["content"]}</div>', unsafe_allow_html=True)

# Input area
input_container = st.container()
with input_container:
    with st.form("chat_form"):
        col1, col2 = st.columns([10, 1])
        with col1:
            user_input = st.text_input("Type a message...", key="user_input", placeholder="Type a message...")
        with col2:
            send_button = st.form_submit_button("Send", type="primary")

# Flow management functions
def start_new_flow(flow_name):
    st.session_state.current_flow = flow_name
    st.session_state.flow_step = CONVERSATION_FLOWS[flow_name]["steps"][0]["id"]
    st.session_state.collected_info = {}

def get_current_prompt():
    if not st.session_state.current_flow or not st.session_state.flow_step:
        return None
    
    flow = CONVERSATION_FLOWS[st.session_state.current_flow]
    current_step = next((step for step in flow["steps"] if step["id"] == st.session_state.flow_step), None)
    
    return current_step["prompt"] if current_step else None

def process_flow_response(user_input):
    flow = CONVERSATION_FLOWS[st.session_state.current_flow]
    current_step = next((step for step in flow["steps"] if step["id"] == st.session_state.flow_step), None)
    
    if current_step:
        # Store collected information
        for info in current_step["required_info"]:
            st.session_state.collected_info[info] = user_input
        
        # Move to next step
        if current_step["next_step"]:
            st.session_state.flow_step = current_step["next_step"]
            return get_current_prompt()
        else:
            st.session_state.current_flow = None
            st.session_state.flow_step = None
            return "Thank you for providing all the information. Is there anything else I can help you with?"

# Handle flow selection
if selected_flow != "None" and (not st.session_state.current_flow or 
                               flow_options[selected_flow] != st.session_state.current_flow):
    start_new_flow(flow_options[selected_flow])

# Display current prompt if in a flow
if st.session_state.current_flow:
    current_prompt = get_current_prompt()
    if current_prompt:
        st.write(f"Assistant: {current_prompt}")

# Handle send button click
if send_button:
    if user_input:
        # Add user message to chat history
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        
        # Handle structured flow or general conversation
        if st.session_state.current_flow:
            response = process_flow_response(user_input)
            if response:
                st.session_state.chat_history.append({"role": "assistant", "content": response})
        else:
            # Generate response using Gemini
            model = initialize_model()
            conversation_history = "\n".join([
                f"{msg['role'].capitalize()}: {msg['content']}" 
                for msg in st.session_state.chat_history[:-1]
            ])
            
            full_prompt = f"{BASE_CONTEXT}\n\nPrevious conversation:\n{conversation_history}\n\nUser: {user_input}\n\nProvide a natural, empathetic response that:\n1. Addresses the user's immediate concern\n2. Maintains professional medical context\n3. Provides clear next steps if applicable\n4. Stays within appropriate scope\n5. Uses conversational, warm language"
            
            response = model.generate_content(full_prompt)
            st.session_state.chat_history.append({"role": "assistant", "content": response.text})

# Add clear chat button
if st.button("Clear Chat"):
    st.session_state.chat_history = []
    st.session_state.current_flow = None
    st.session_state.flow_step = None
    st.session_state.collected_info = {}