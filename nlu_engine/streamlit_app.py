import streamlit as st
import numpy as np
import pandas as pd
from datetime import datetime
import re
import time

# ==================== NEURAL NETWORK IMPLEMENTATION ====================

class NeuralNLUEngine:
    def __init__(self):
        self.intents = {}
        self.model_trained = False
        self.vocab = set()
        self.word_to_idx = {}
        self.intent_to_idx = {}
        self.idx_to_intent = {}
        self.weights = None
        self.bias = None
        self.training_history = []
        
    def add_intent(self, intent_name, examples):
        """Add new intent with training examples"""
        self.intents[intent_name] = examples
        self.model_trained = False
        
    def preprocess_text(self, text):
        """Clean and tokenize text"""
        text = text.lower().strip()
        text = re.sub(r'[^\w\s]', ' ', text)
        return text.split()
    
    def build_vocabulary(self):
        """Build vocabulary from all examples"""
        self.vocab = set()
        for intent, examples in self.intents.items():
            for example in examples:
                words = self.preprocess_text(example)
                self.vocab.update(words)
        
        self.word_to_idx = {word: idx for idx, word in enumerate(sorted(self.vocab))}
        self.intent_to_idx = {intent: idx for idx, intent in enumerate(sorted(self.intents.keys()))}
        self.idx_to_intent = {idx: intent for intent, idx in self.intent_to_idx.items()}
    
    def vectorize_text(self, text):
        """Convert text to vector using bag of words"""
        words = self.preprocess_text(text)
        vector = np.zeros(len(self.vocab))
        for word in words:
            if word in self.word_to_idx:
                vector[self.word_to_idx[word]] += 1
        return vector
    
    def calculate_accuracy(self, X, y):
        """Calculate training accuracy"""
        predictions = []
        for x in X:
            logits = np.dot(x, self.weights) + self.bias
            pred = np.argmax(logits)
            predictions.append(pred)
        
        accuracy = np.mean(np.array(predictions) == y)
        return accuracy
    
    def train(self, epochs=10, learning_rate=0.01, batch_size=8):
        """Train the neural network with progress tracking"""
        if not self.intents:
            return False, "No intents to train", []
        
        self.build_vocabulary()
        self.training_history = []
        
        # Prepare training data
        X_train = []
        y_train = []
        
        for intent, examples in self.intents.items():
            intent_idx = self.intent_to_idx[intent]
            for example in examples:
                X_train.append(self.vectorize_text(example))
                y_train.append(intent_idx)
        
        X_train = np.array(X_train)
        y_train = np.array(y_train)
        
        # Initialize weights
        n_features = len(self.vocab)
        n_classes = len(self.intents)
        self.weights = np.random.randn(n_features, n_classes) * 0.01
        self.bias = np.zeros(n_classes)
        
        # Training loop with progress tracking
        for epoch in range(epochs):
            # Shuffle data
            indices = np.random.permutation(len(X_train))
            X_shuffled = X_train[indices]
            y_shuffled = y_train[indices]
            
            epoch_loss = 0
            n_batches = 0
            
            # Mini-batch gradient descent
            for i in range(0, len(X_train), batch_size):
                batch_X = X_shuffled[i:i+batch_size]
                batch_y = y_shuffled[i:i+batch_size]
                
                # Forward pass
                logits = np.dot(batch_X, self.weights) + self.bias
                exp_logits = np.exp(logits - np.max(logits, axis=1, keepdims=True))
                probs = exp_logits / np.sum(exp_logits, axis=1, keepdims=True)
                
                # Calculate loss
                batch_size_actual = len(batch_X)
                y_one_hot = np.zeros((batch_size_actual, n_classes))
                y_one_hot[np.arange(batch_size_actual), batch_y] = 1
                
                loss = -np.mean(np.sum(y_one_hot * np.log(probs + 1e-10), axis=1))
                epoch_loss += loss
                n_batches += 1
                
                # Backward pass
                grad = (probs - y_one_hot) / batch_size_actual
                self.weights -= learning_rate * np.dot(batch_X.T, grad)
                self.bias -= learning_rate * np.sum(grad, axis=0)
            
            # Calculate metrics
            avg_loss = epoch_loss / n_batches
            accuracy = self.calculate_accuracy(X_train, y_train)
            
            self.training_history.append({
                'epoch': epoch + 1,
                'loss': avg_loss,
                'accuracy': accuracy
            })
        
        self.model_trained = True
        return True, "Model trained successfully", self.training_history
    
    def predict(self, text, top_k=3):
        """Predict intent and confidence"""
        if not self.model_trained:
            return None, 0.0, {}
        
        vector = self.vectorize_text(text)
        logits = np.dot(vector, self.weights) + self.bias
        exp_logits = np.exp(logits - np.max(logits))
        probs = exp_logits / np.sum(exp_logits)
        
        # Get all scores
        all_scores = {self.idx_to_intent[i]: float(probs[i]) for i in range(len(probs))}
        
        # Get top prediction
        top_idx = np.argmax(probs)
        intent = self.idx_to_intent[top_idx]
        confidence = float(probs[top_idx])
        
        return intent, confidence, all_scores
    
    def extract_entities(self, text):
        """Extract entities using regex patterns"""
        entities = {}
        
        # Money patterns - Enhanced
        money_patterns = [
            (r'\$\s*(\d+(?:,\d{3})*(?:\.\d{2})?)', 'USD'),
            (r'RS\.?\s*(\d+(?:,\d{3})*(?:\.\d{2})?)', 'INR'),
            (r'₹\s*(\d+(?:,\d{3})*(?:\.\d{2})?)', 'INR'),
            (r'(\d+(?:,\d{3})*(?:\.\d{2})?)\s*(?:dollars?|usd)', 'USD'),
            (r'(\d+(?:,\d{3})*(?:\.\d{2})?)\s*(?:rupees?|rs|inr)', 'INR'),
        ]
        
        for pattern, currency in money_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                entities['money'] = [f"{currency} {m.replace(',', '')}" for m in matches]
                break
        
        # Account number - More specific
        account_patterns = [
            r'account\s*(?:number|no\.?|#)?\s*(\d{4,16})',
            r'to\s*account\s*(\d{4,16})',
            r'account\s*(\d{4,16})',
        ]
        
        for pattern in account_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                entities['account_number'] = matches
                break
        
        # Account types
        account_types = re.findall(r'\b(savings?|checking|current)\s*(?:account)?\b', text, re.IGNORECASE)
        if account_types:
            entities['account_type'] = list(set([t.lower() for t in account_types]))
        
        # Card types
        card_types = re.findall(r'\b(credit|debit|atm)\s*card\b', text, re.IGNORECASE)
        if card_types:
            entities['card_type'] = list(set([t.lower() for t in card_types]))
        
        # Date
        date_matches = re.findall(r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|today|tomorrow|yesterday', text, re.IGNORECASE)
        if date_matches:
            entities['date'] = date_matches
        
        return entities

# ==================== SESSION STATE ====================

def init_session_state():
    if 'nlu_engine' not in st.session_state:
        st.session_state.nlu_engine = NeuralNLUEngine()
        # Load default intents
        default_intents = {
            'check_balance': [
                "What's my account balance?",
                "Show balance for my savings account",
                "How much money do I have in my current account?",
                "Check balance of my savings",
                "Can you tell me my account balance?",
                "What's the balance in my checking account?",
                "Show me my balance",
                "How much is left in my savings?",
                "Account balance check",
                "Display my current balance",
                "How much do I have?",
                "Check my bank balance",
                "What is my balance?",
                "Balance inquiry",
                "Show my account balance",
                "Current account balance",
                "Savings account balance",
                "Tell me my balance",
                "How much money in my account",
                "Balance check please"
            ],
            'transfer_money': [
                "Transfer 5000 from savings to checking",
                "Move $1500 to account 12345678",
                "Please transfer $250 to my friend",
                "Transfer funds from my savings to current account",
                "I want to send 1000 rupees to account 9876543210",
                "Send money to account 4532",
                "Transfer $500 to checking",
                "Move funds between accounts",
                "Wire money to another account",
                "Send payment to account",
                "Transfer money please",
                "I need to transfer funds",
                "Move money from savings",
                "Send $1000 to account 8765",
                "Transfer amount to account",
                "Make a transfer",
                "Send funds to checking account",
                "Transfer RS 2000",
                "Wire transfer to account"
            ],
            'card_block': [
                "Block my credit card",
                "I lost my debit card",
                "Disable my card",
                "My card was stolen",
                "Freeze my credit card",
                "Lock my debit card",
                "Card block request",
                "Stop my card",
                "Deactivate my card",
                "I need to block my card",
                "Card lost, please block",
                "Emergency card block",
                "Suspend my card",
                "Cancel my card",
                "Block card immediately",
                "My card is missing",
                "Report stolen card",
                "Disable card access",
                "Stop card transactions",
                "Lock my card now"
            ],
            'find_atm': [
                "Where is the nearest ATM?",
                "Find ATM near me",
                "ATM locations nearby",
                "Show me ATM locations",
                "Nearest bank branch",
                "ATM finder",
                "Where can I withdraw cash?",
                "Find closest ATM",
                "ATM near my location",
                "Show ATMs in my area",
                "Locate ATM",
                "Find cash machine",
                "Where is ATM",
                "Nearest cash point",
                "ATM search",
                "Show me nearby ATMs",
                "Find ATM close to me",
                "ATM locator",
                "Where can I find ATM",
                "Nearest withdrawal point",
                "Show branch locations"
            ],
            'loan_inquiry': [
                "I want to apply for a home loan",
                "Personal loan information",
                "How can I get a car loan?",
                "Loan application",
                "Tell me about home loans",
                "What are loan rates?",
                "Apply for personal loan",
                "Education loan details",
                "Business loan inquiry",
                "How to apply for loan",
                "Loan eligibility check",
                "Interest rates for loans",
                "Home loan application",
                "Need a loan",
                "Loan information please",
                "Want to borrow money",
                "Loan options available",
                "Check loan eligibility",
                "Apply for credit"
            ]
        }
        for intent, examples in default_intents.items():
            st.session_state.nlu_engine.add_intent(intent, examples)
    
    if 'query_history' not in st.session_state:
        st.session_state.query_history = []
    
    if 'show_training' not in st.session_state:
        st.session_state.show_training = False
    
    if 'training_results' not in st.session_state:
        st.session_state.training_results = None

# ==================== MAIN APP ====================

def main():
    st.set_page_config(page_title="NLU Engine", page_icon="🧠", layout="wide")
    
    init_session_state()
    
    # Custom CSS
    st.markdown("""
    <style>
        .stApp {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        }
        
        .main-title {
            color: white;
            font-size: 2.5rem;
            font-weight: 900;
            margin-bottom: 0.5rem;
            text-align: center;
        }
        
        .subtitle {
            color: rgba(255,255,255,0.7);
            text-align: center;
            margin-bottom: 2rem;
        }
        
        .example-text {
            color: rgba(255,255,255,0.7);
            font-size: 0.9rem;
            margin: 0.3rem 0;
            padding-left: 1rem;
        }
        
        .metric-card {
            background: rgba(102, 126, 234, 0.2);
            border: 1px solid rgba(102, 126, 234, 0.4);
            border-radius: 10px;
            padding: 1rem;
            text-align: center;
            margin: 0.5rem 0;
        }
        
        .metric-value {
            font-size: 2rem;
            font-weight: bold;
            color: #667eea;
        }
        
        .metric-label {
            color: rgba(255,255,255,0.7);
            font-size: 0.9rem;
            margin-top: 0.5rem;
        }
        
        .entity-tag {
            background: rgba(102, 126, 234, 0.3);
            border: 1px solid rgba(102, 126, 234, 0.5);
            color: white;
            padding: 8px 16px;
            border-radius: 20px;
            display: inline-block;
            margin: 5px;
            font-size: 0.9rem;
        }
        
        .stTextInput>div>div>input, .stTextArea>div>div>textarea {
            background: rgba(255,255,255,0.05) !important;
            border: 1px solid rgba(255,255,255,0.2) !important;
            color: white !important;
        }
        
        .stButton>button {
            background: linear-gradient(135deg, #667eea, #764ba2) !important;
            color: white !important;
            border: none !important;
            font-weight: 600 !important;
            transition: all 0.3s !important;
        }
        
        .stButton>button:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        
        .success-box {
            background: linear-gradient(135deg, #11998e, #38ef7d);
            color: white;
            padding: 1.5rem;
            border-radius: 10px;
            margin: 1rem 0;
        }
        
        .success-box h3 {
            margin: 0 0 0.5rem 0;
            font-size: 1.3rem;
        }
        
        .success-box p {
            margin: 0.3rem 0;
        }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<h1 class="main-title">🧠 Neural NLU Engine</h1>', unsafe_allow_html=True)
    st.markdown('<p class="subtitle">Train custom intent classification models with real-time visualization</p>', unsafe_allow_html=True)
    
    # Main layout
    col_left, col_right = st.columns([1, 1.2])
    
    # LEFT SIDE - Intents Management
    with col_left:
        st.markdown("### 📚 Intent Library")
        
        # Model status indicator
        if st.session_state.nlu_engine.model_trained:
            st.success("✅ Model is trained and ready")
        else:
            st.warning("⚠️ Model needs training")
        
        st.markdown("---")
        
        # Display existing intents
        for intent_name in sorted(st.session_state.nlu_engine.intents.keys()):
            examples = st.session_state.nlu_engine.intents[intent_name]
            
            with st.expander(f"📋 {intent_name} ({len(examples)} examples)", expanded=False):
                st.markdown(f"**Training examples:**")
                for example in examples[:5]:
                    st.markdown(f'<p class="example-text">• {example}</p>', unsafe_allow_html=True)
                if len(examples) > 5:
                    st.markdown(f'<p class="example-text">... and {len(examples)-5} more</p>', unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Create new intent
        st.markdown("### ➕ Create New Intent")
        
        new_intent_name = st.text_input("Intent name", placeholder="e.g., account_opening", key="new_intent_name")
        new_intent_examples = st.text_area(
            "Examples (one per line)",
            height=120,
            placeholder="I want to open a new account\nHow can I create an account?\nSign me up for savings account",
            key="new_intent_examples"
        )
        
        if st.button("Create Intent", type="primary", use_container_width=True, key="create_intent_btn"):
            if new_intent_name and new_intent_examples:
                examples = [line.strip() for line in new_intent_examples.split('\n') if line.strip()]
                if examples:
                    st.session_state.nlu_engine.add_intent(new_intent_name, examples)
                    st.success(f"✅ Intent '{new_intent_name}' created with {len(examples)} examples!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Please provide at least one example")
            else:
                st.error("Please fill in all fields")
        
        # Training section
        st.markdown("---")
        if st.button("🎯 Train Model", use_container_width=True, key="toggle_training_btn"):
            st.session_state.show_training = not st.session_state.show_training
            st.rerun()
        
        if st.session_state.show_training:
            st.markdown("### 🔧 Training Configuration")
            
            if not st.session_state.nlu_engine.intents:
                st.error("⚠️ No intents found. Please create at least one intent.")
            else:
                epochs = st.slider("Training Epochs", min_value=5, max_value=100, value=20, step=5, key="epochs_slider")
                batch_size = st.selectbox("Batch Size", [4, 8, 16, 32], index=1, key="batch_size_select")
                learning_rate = st.select_slider(
                    "Learning Rate", 
                    options=[0.001, 0.005, 0.01, 0.05, 0.1],
                    value=0.01,
                    format_func=lambda x: f"{x:.3f}",
                    key="lr_slider"
                )
                
                if st.button("🚀 Start Training", type="primary", use_container_width=True, key="start_training_btn"):
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    with st.spinner("🧠 Training neural network..."):
                        success, message, history = st.session_state.nlu_engine.train(
                            epochs=epochs,
                            learning_rate=learning_rate,
                            batch_size=batch_size
                        )
                        
                        # Simulate progress for visual feedback
                        for i in range(100):
                            time.sleep(0.01)
                            progress_bar.progress(i + 1)
                            status_text.text(f"Training... {i+1}%")
                        
                        if success:
                            st.session_state.training_results = history
                            progress_bar.empty()
                            status_text.empty()
                            st.success("✅ " + message)
                            st.balloons()
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.error("❌ " + message)
    
    # RIGHT SIDE - NLU Visualizer & Results
    with col_right:
        # Show training results if available
        if st.session_state.training_results:
            st.markdown("### 📊 Training Results")
            
            history = st.session_state.training_results
            
            # Key metrics
            final_accuracy = history[-1]['accuracy']
            final_loss = history[-1]['loss']
            
            metric_col1, metric_col2, metric_col3 = st.columns(3)
            
            with metric_col1:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-value">{final_accuracy:.1%}</div>
                    <div class="metric-label">Final Accuracy</div>
                </div>
                """, unsafe_allow_html=True)
            
            with metric_col2:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-value">{final_loss:.3f}</div>
                    <div class="metric-label">Final Loss</div>
                </div>
                """, unsafe_allow_html=True)
            
            with metric_col3:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-value">{len(history)}</div>
                    <div class="metric-label">Epochs</div>
                </div>
                """, unsafe_allow_html=True)
            
            # Training progress chart
            st.markdown("#### Training Progress")
            
            df_history = pd.DataFrame(history)
            
            # Create two columns for charts
            chart_col1, chart_col2 = st.columns(2)
            
            with chart_col1:
                st.markdown("**Accuracy over Epochs**")
                st.line_chart(df_history.set_index('epoch')['accuracy'])
            
            with chart_col2:
                st.markdown("**Loss over Epochs**")
                st.line_chart(df_history.set_index('epoch')['loss'])
            
            # Detailed metrics table
            with st.expander("📈 View Detailed Training Metrics"):
                display_df = df_history.copy()
                display_df['accuracy'] = display_df['accuracy'].apply(lambda x: f"{x:.2%}")
                display_df['loss'] = display_df['loss'].apply(lambda x: f"{x:.4f}")
                st.dataframe(
                    display_df,
                    use_container_width=True,
                    hide_index=True
                )
            
            st.markdown("---")
        
        # NLU Testing Interface
        st.markdown("### 🔍 Test Your Model")
        
        st.markdown("**Enter a query to test:**")
        user_query = st.text_area(
            "User Query",
            height=100,
            placeholder="e.g., I want to transfer $500 from my savings account to checking account 4532",
            label_visibility="collapsed",
            key="user_query_input"
        )
        
        top_k = st.slider("Top predictions to show", min_value=1, max_value=10, value=3, key="top_k_slider")
        
        if st.button("🔎 Analyze Query", type="primary", use_container_width=True, key="analyze_btn"):
            if not st.session_state.nlu_engine.model_trained:
                st.warning("⚠️ Please train the model first before testing.")
            elif user_query:
                with st.spinner("🧠 Analyzing query..."):
                    intent, confidence, all_scores = st.session_state.nlu_engine.predict(user_query, top_k=top_k)
                    entities = st.session_state.nlu_engine.extract_entities(user_query)
                    
                    # Store in history
                    st.session_state.query_history.append({
                        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'query': user_query,
                        'intent': intent,
                        'confidence': confidence
                    })
                    
                    st.markdown("---")
                    
                    # Top Prediction Highlight
                    st.markdown(f"""
                    <div class="success-box">
                        <h3>🎯 Top Prediction</h3>
                        <p><strong>Intent:</strong> {intent}</p>
                        <p><strong>Confidence:</strong> {confidence:.1%}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # All Predicted Intents
                    st.markdown("#### All Intent Predictions")
                    
                    sorted_intents = sorted(all_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
                    
                    for idx, (intent_name, score) in enumerate(sorted_intents):
                        # Create progress bar for each intent
                        col_name, col_bar = st.columns([1, 3])
                        with col_name:
                            st.markdown(f"**{intent_name}**")
                        with col_bar:
                            st.progress(score)
                            st.caption(f"{score:.1%}")
                    
                    st.markdown("---")
                    
                    # Extracted Entities
                    st.markdown("#### 🏷️ Extracted Entities")
                    
                    if entities:
                        for entity_type, values in entities.items():
                            st.markdown(f"**{entity_type.replace('_', ' ').title()}:**")
                            entity_html = ""
                            for value in values:
                                entity_html += f'<span class="entity-tag">{value}</span>'
                            st.markdown(entity_html, unsafe_allow_html=True)
                    else:
                        st.info("No entities detected in the query")
            else:
                st.warning("Please enter a query to analyze")
    
    # Query History
    if st.session_state.query_history:
        st.markdown("---")
        st.markdown("### 📊 Query History")
        
        history_df = pd.DataFrame(st.session_state.query_history[-10:])
        display_history = history_df.copy()
        display_history['confidence'] = display_history['confidence'].apply(lambda x: f"{x:.1%}")
        
        st.dataframe(
            display_history,
            use_container_width=True,
            hide_index=True,
            column_config={
                "timestamp": "Time",
                "query": "Query",
                "intent": "Predicted Intent",
                "confidence": "Confidence"
            }
        )
        
        if st.button("Clear History", key="clear_history_btn"):
            st.session_state.query_history = []
            st.rerun()

if __name__ == "__main__":
    main()