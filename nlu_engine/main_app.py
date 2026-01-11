import streamlit as st
import json
import os
import subprocess
import time

# Paths - handle both running from root and from nlu_engine folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Check if we're inside nlu_engine folder
if os.path.basename(BASE_DIR) == "nlu_engine":
    # Running from nlu_engine folder
    PARENT_DIR = os.path.dirname(BASE_DIR)
    INTENTS_PATH = os.path.join(BASE_DIR, "intents.json")
    MODEL_DIR = os.path.join(PARENT_DIR, "models", "intent_model")
else:
    # Running from parent folder
    INTENTS_PATH = os.path.join(BASE_DIR, "nlu_engine", "intents.json")
    MODEL_DIR = os.path.join(BASE_DIR, "models", "intent_model")

# Page config
st.set_page_config(page_title="BankBot NLU - Milestone 1", layout="wide")

# Enhanced CSS with 3D animations
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    * {
        font-family: 'Inter', sans-serif;
    }
    
    /* Animated gradient background */
    .main {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        background-size: 400% 400%;
        animation: gradientShift 15s ease infinite;
    }
    
    @keyframes gradientShift {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    
    /* Main title with 3D effect */
    h1 {
        color: white !important;
        text-align: center;
        font-size: 3rem !important;
        font-weight: 700 !important;
        text-shadow: 
            2px 2px 4px rgba(0,0,0,0.3),
            4px 4px 8px rgba(0,0,0,0.2);
        animation: titleFloat 3s ease-in-out infinite;
        margin-bottom: 2rem !important;
    }
    
    @keyframes titleFloat {
        0%, 100% { transform: translateY(0px); }
        50% { transform: translateY(-10px); }
    }
    
    /* Section headers */
    h2, h3 {
        color: white !important;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
    }
    
    /* Glass morphism cards */
    .stApp > div > div > div > div {
        background: rgba(255, 255, 255, 0.1) !important;
        backdrop-filter: blur(10px);
        border-radius: 20px;
        border: 1px solid rgba(255, 255, 255, 0.2);
        padding: 2rem;
        box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
        transition: all 0.3s ease;
    }
    
    /* Input fields with glow effect */
    .stTextInput > div > div > input {
        background: rgba(255, 255, 255, 0.9) !important;
        border: 2px solid rgba(102, 126, 234, 0.3) !important;
        border-radius: 15px !important;
        padding: 1rem !important;
        font-size: 1rem !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
    }
    
    .stTextInput > div > div > input:focus {
        border-color: #667eea !important;
        box-shadow: 0 0 20px rgba(102, 126, 234, 0.5) !important;
        transform: scale(1.02);
    }
    
    /* Label styling */
    .stTextInput > label {
        color: white !important;
        font-weight: 600 !important;
        font-size: 1.1rem !important;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.2);
    }
    
    /* 3D Button with animations */
    .stButton > button {
        background: linear-gradient(145deg, #667eea, #764ba2) !important;
        color: white !important;
        border: none !important;
        border-radius: 15px !important;
        padding: 1rem 2rem !important;
        font-weight: 600 !important;
        font-size: 1.1rem !important;
        transition: all 0.3s ease !important;
        box-shadow: 
            0 8px 20px rgba(102, 126, 234, 0.4),
            inset 0 -3px 0 rgba(0, 0, 0, 0.2) !important;
        position: relative;
        overflow: hidden;
        width: 100%;
    }
    
    .stButton > button:before {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
        transition: left 0.5s;
    }
    
    .stButton > button:hover:before {
        left: 100%;
    }
    
    .stButton > button:hover {
        transform: translateY(-5px) scale(1.05) !important;
        box-shadow: 
            0 12px 30px rgba(102, 126, 234, 0.6),
            inset 0 -3px 0 rgba(0, 0, 0, 0.2) !important;
    }
    
    .stButton > button:active {
        transform: translateY(-2px) scale(1.02) !important;
        box-shadow: 
            0 6px 15px rgba(102, 126, 234, 0.5),
            inset 0 -1px 0 rgba(0, 0, 0, 0.2) !important;
    }
    
    /* Output card styling */
    .output-card {
        background: rgba(255, 255, 255, 0.95);
        border-radius: 20px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 
            0 8px 25px rgba(0, 0, 0, 0.15),
            inset 0 1px 0 rgba(255, 255, 255, 0.6);
        border: 2px solid rgba(102, 126, 234, 0.2);
        transition: all 0.3s ease;
        animation: slideIn 0.5s ease-out;
    }
    
    @keyframes slideIn {
        from {
            opacity: 0;
            transform: translateX(-30px);
        }
        to {
            opacity: 1;
            transform: translateX(0);
        }
    }
    
    .output-card:hover {
        transform: translateY(-5px) rotateY(2deg);
        box-shadow: 
            0 12px 35px rgba(102, 126, 234, 0.3),
            inset 0 1px 0 rgba(255, 255, 255, 0.6);
    }
    
    /* Intent badge with pulse animation */
    .intent-badge {
        background: linear-gradient(145deg, #667eea, #764ba2);
        color: white;
        padding: 0.8rem 1.5rem;
        border-radius: 25px;
        display: inline-block;
        font-weight: 600;
        font-size: 1.1rem;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
        animation: pulse 2s ease-in-out infinite;
        margin: 0.5rem 0;
    }
    
    @keyframes pulse {
        0%, 100% { 
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
            transform: scale(1);
        }
        50% { 
            box-shadow: 0 6px 25px rgba(102, 126, 234, 0.6);
            transform: scale(1.05);
        }
    }
    
    /* Entity tags with 3D effect */
    .entity-tag {
        background: linear-gradient(145deg, #43e97b, #38f9d7);
        color: white;
        padding: 0.5rem 1rem;
        border-radius: 20px;
        display: inline-block;
        margin: 0.3rem;
        font-weight: 500;
        box-shadow: 
            0 4px 10px rgba(67, 233, 123, 0.3),
            inset 0 1px 0 rgba(255, 255, 255, 0.3);
        transition: all 0.3s ease;
        animation: tagBounce 0.5s ease-out;
    }
    
    @keyframes tagBounce {
        0% { transform: scale(0) rotate(-180deg); opacity: 0; }
        50% { transform: scale(1.2) rotate(10deg); }
        100% { transform: scale(1) rotate(0deg); opacity: 1; }
    }
    
    .entity-tag:hover {
        transform: translateY(-3px) scale(1.1) rotate(2deg);
        box-shadow: 
            0 6px 15px rgba(67, 233, 123, 0.5),
            inset 0 1px 0 rgba(255, 255, 255, 0.4);
    }
    
    /* Success message */
    .stSuccess {
        background: linear-gradient(135deg, #43e97b 0%, #38f9d7 100%) !important;
        color: white !important;
        border-radius: 15px !important;
        padding: 1rem !important;
        box-shadow: 0 8px 20px rgba(67, 233, 123, 0.4) !important;
        animation: successPulse 2s ease-in-out infinite;
    }
    
    @keyframes successPulse {
        0%, 100% { box-shadow: 0 8px 20px rgba(67, 233, 123, 0.4); }
        50% { box-shadow: 0 8px 30px rgba(67, 233, 123, 0.6); }
    }
    
    /* Info message */
    .stInfo {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        color: white !important;
        border-radius: 15px !important;
        padding: 1rem !important;
        box-shadow: 0 8px 20px rgba(102, 126, 234, 0.4) !important;
    }
    
    /* Warning message */
    .stWarning {
        background: linear-gradient(135deg, #fa709a 0%, #fee140 100%) !important;
        color: white !important;
        border-radius: 15px !important;
        padding: 1rem !important;
        box-shadow: 0 8px 20px rgba(250, 112, 154, 0.4) !important;
    }
    
    /* Subheader with glow */
    .output-card h3 {
        color: #667eea !important;
        font-weight: 700 !important;
        margin-bottom: 1rem !important;
        text-shadow: 0 2px 10px rgba(102, 126, 234, 0.3);
    }
    
    /* Markdown text in output */
    .output-card p {
        color: #333 !important;
        font-size: 1rem !important;
        line-height: 1.8 !important;
        margin: 0.5rem 0 !important;
    }
    
    .output-card strong {
        color: #667eea !important;
        font-weight: 700 !important;
    }
    
    /* Footer styling */
    .footer {
        text-align: center;
        color: white;
        font-size: 1.1rem;
        margin-top: 3rem;
        padding: 2rem;
        background: rgba(255, 255, 255, 0.1);
        border-radius: 20px;
        backdrop-filter: blur(10px);
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.1);
    }
    
    /* Training progress animation */
    .stProgress > div > div > div {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%) !important;
        border-radius: 10px !important;
        animation: progressGlow 2s ease-in-out infinite;
    }
    
    @keyframes progressGlow {
        0%, 100% { box-shadow: 0 0 10px rgba(102, 126, 234, 0.5); }
        50% { box-shadow: 0 0 20px rgba(102, 126, 234, 0.8); }
    }
    
    /* Loading spinner */
    .stSpinner > div {
        border-top-color: #667eea !important;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Scrollbar styling */
    ::-webkit-scrollbar {
        width: 12px;
    }
    
    ::-webkit-scrollbar-track {
        background: rgba(255, 255, 255, 0.1);
        border-radius: 10px;
    }
    
    ::-webkit-scrollbar-thumb {
        background: linear-gradient(180deg, #667eea 0%, #764ba2 100%);
        border-radius: 10px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: linear-gradient(180deg, #764ba2 0%, #667eea 100%);
    }
    
    /* Column styling */
    [data-testid="column"] {
        background: rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(5px);
        border-radius: 20px;
        padding: 1.5rem;
        margin: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# Title
st.title("🤖 BankBot - Milestone 1 (Intent + Entity)")

# Load intents JSON
if os.path.exists(INTENTS_PATH):
    with open(INTENTS_PATH, "r") as f:
        intents_data = json.load(f)
else:
    intents_data = {}
    st.warning("⚠️ Intents JSON file not found!")

# Initialize session state for models
if 'models_loaded' not in st.session_state:
    st.session_state.models_loaded = False
    st.session_state.intent_classifier = None
    st.session_state.entity_extractor = None
    st.session_state.load_error = None

# Function to load models (not cached initially)
def load_models_on_demand():
    """Load models only when needed"""
    if st.session_state.models_loaded:
        return st.session_state.intent_classifier, st.session_state.entity_extractor, st.session_state.load_error
    
    try:
        # Try importing
        try:
            from nlu_engine.infer_intent import IntentClassifier
            from nlu_engine.entity_extractor import EntityExtractor
        except ModuleNotFoundError:
            from infer_intent import IntentClassifier
            from entity_extractor import EntityExtractor
        
        # Check if model exists
        if not os.path.exists(MODEL_DIR):
            return None, None, "Model directory not found. Please train the model first."
        
        intent = IntentClassifier(MODEL_DIR)
        entity = EntityExtractor()
        
        st.session_state.intent_classifier = intent
        st.session_state.entity_extractor = entity
        st.session_state.models_loaded = True
        st.session_state.load_error = None
        
        return intent, entity, None
        
    except Exception as e:
        error_msg = f"Failed to load models: {str(e)}"
        st.session_state.load_error = error_msg
        return None, None, error_msg

# Get models from session state (instant load)
intent_classifier = st.session_state.intent_classifier
entity_extractor = st.session_state.entity_extractor

# Layout: 2 columns
col1, col2 = st.columns(2)

with col1:
    st.header("📝 User Input")
    
    # Model status indicator
    if st.session_state.models_loaded:
        st.success("✅ Models loaded and ready")
    else:
        st.warning("⚠️ Models not loaded")
        if st.button("🔄 Load Models Now", type="primary"):
            with st.spinner("Loading models..."):
                intent_classifier, entity_extractor, error = load_models_on_demand()
                if error:
                    st.error(f"❌ {error}")
                else:
                    st.success("✅ Models loaded successfully!")
                    st.rerun()
    
    st.markdown("")
    
    # Multiple inputs with unique keys
    user_inputs = []
    for i in range(3):
        user_input = st.text_input(
            f"Enter your message #{i+1}:",
            key=f"user_input_{i}",
            placeholder=f"Type your banking query here..."
        )
        user_inputs.append(user_input)

with col2:
    st.header("🎯 NLU Output")
    st.markdown("")
    
    for i, text in enumerate(user_inputs):
        if text:
            # Auto-load models if not loaded and user entered text
            if not st.session_state.models_loaded:
                with st.spinner("Loading models for first use..."):
                    intent_classifier, entity_extractor, error = load_models_on_demand()
                    if error:
                        st.error(f"❌ {error}")
                        st.info("💡 Please train your model first using the button below")
                        continue
            
            # Create output card
            st.markdown(f'<div class="output-card">', unsafe_allow_html=True)
            st.subheader(f"Message #{i+1}")
            
            if st.session_state.intent_classifier and st.session_state.entity_extractor:
                try:
                    # Predict intent
                    intent_result = st.session_state.intent_classifier.predict(text)
                    st.markdown(f'<div class="intent-badge">📌 Intent: {intent_result}</div>', unsafe_allow_html=True)
                    
                    # Extract entities
                    entities = st.session_state.entity_extractor.extract(text)
                    
                    if entities:
                        st.markdown("**🏷️ Extracted Entities:**")
                        entity_html = '<div style="margin-top: 0.5rem;">'
                        for entity_type, values in entities.items():
                            for value in values:
                                entity_html += f'<span class="entity-tag">{entity_type}: {value}</span>'
                        entity_html += '</div>'
                        st.markdown(entity_html, unsafe_allow_html=True)
                    else:
                        st.markdown("**🏷️ Extracted Entities:** No entities found")
                except Exception as e:
                    st.error(f"Error processing query: {str(e)}")
            else:
                st.warning("⚠️ Models not available. Please train the model first.")
            
            st.markdown('</div>', unsafe_allow_html=True)
            st.markdown("")

# Training section
st.markdown("---")
st.markdown("### 🎯 Model Training")

col_train1, col_train2 = st.columns([3, 1])

with col_train1:
    if st.button("🚀 Retrain Intent Model"):
        st.info("🔄 Training started...")
        
        # Progress bar
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # Run training
            start_time = time.time()
            
            # Determine the correct path to train_intent.py
            if os.path.basename(BASE_DIR) == "nlu_engine":
                train_script = os.path.join(BASE_DIR, "train_intent.py")
            else:
                train_script = os.path.join(BASE_DIR, "nlu_engine", "train_intent.py")
            
            result = subprocess.run(
                ["python3", train_script],
                capture_output=True,
                text=True,
                check=True
            )
            
            # Simulate progress
            for i in range(100):
                progress_bar.progress(i + 1)
                status_text.text(f"Training... {i+1}%")
                time.sleep(0.02)
            
            end_time = time.time()
            training_time = end_time - start_time
            
            # Show success
            st.success(f"✅ Training completed successfully in {training_time:.2f} seconds!")
            
            # Show training output if available
            if result.stdout:
                with st.expander("📋 View Training Details"):
                    st.code(result.stdout, language="text")
            
            # Clear cache to reload models
            st.cache_resource.clear()
            st.balloons()
            
        except subprocess.CalledProcessError as e:
            st.error(f"❌ Training failed!")
            if e.stderr:
                with st.expander("🔍 Error Details"):
                    st.code(e.stderr, language="text")
        except Exception as e:
            st.error(f"❌ Unexpected error: {str(e)}")

with col_train2:
    if st.button("🔄 Reload Models"):
        st.session_state.models_loaded = False
        st.session_state.intent_classifier = None
        st.session_state.entity_extractor = None
        st.session_state.load_error = None
        st.success("✅ Models cache cleared!")
        st.rerun()

# Footer
st.markdown("---")
st.markdown('<div class="footer">💡 BankBot NLU Milestone 1 - Streamlit Demo</div>', unsafe_allow_html=True)