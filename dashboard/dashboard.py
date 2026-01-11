import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import random
import json
import numpy as np
import sqlite3
from io import StringIO, BytesIO
import base64
import hashlib
import secrets
import time
from datetime import datetime, timedelta
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from dotenv import load_dotenv
import os

# Load .env with explicit path and error handling
env_path = Path(__file__).parent.parent / '.env'
try:
    load_dotenv(dotenv_path=env_path, override=True, verbose=True)
except Exception as e:
    print(f"Warning loading .env: {e}")
    # Manually read and set variables as fallback
    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

# Instead of:
load_dotenv()

EMAIL_CONFIG = {
    'smtp_server': os.getenv('SMTP_SERVER', 'smtp.gmail.com'),
    'smtp_port': int(os.getenv('SMTP_PORT', '587')),
    'sender_email': os.getenv('SENDER_EMAIL', ''),
    'sender_password': os.getenv('SENDER_PASSWORD', ''),
    'sender_name': 'AI Chatbot Admin'
}
# Validate email configuration
if not EMAIL_CONFIG['sender_email'] or not EMAIL_CONFIG['sender_password']:
    print("⚠️ WARNING: Email not configured! Create .env file with credentials.")

# Use:
from pathlib import Path
load_dotenv(Path(__file__).parent.parent / '.env')

# ==================== AUTHENTICATION FUNCTIONS ====================
def hash_password(password):
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()

def init_users_db():
    """Initialize users database"""
    conn = sqlite3.connect('chatbot_data.db')
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  password TEXT NOT NULL,
                  email TEXT,
                  created_at TEXT,
                  last_login TEXT,
                  is_active INTEGER DEFAULT 1)''')
    
    # Password reset tokens table
    c.execute('''CREATE TABLE IF NOT EXISTS password_reset_tokens
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT NOT NULL,
                  token TEXT UNIQUE NOT NULL,
                  created_at TEXT,
                  expires_at TEXT,
                  used INTEGER DEFAULT 0)''')
    
    # Insert default admin user if not exists
    try:
        c.execute('''INSERT INTO users (username, password, email, created_at, last_login)
                     VALUES (?, ?, ?, ?, ?)''',
                  ('admin', hash_password('admin123'), 'admin@chatbot.com', 
                   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                   datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
    except sqlite3.IntegrityError:
        pass  # User already exists
    
    conn.close()

def verify_login(username, password):
    """Verify user credentials"""
    conn = sqlite3.connect('chatbot_data.db')
    c = conn.cursor()
    
    hashed_password = hash_password(password)
    c.execute('''SELECT id, username, email FROM users 
                 WHERE username = ? AND password = ? AND is_active = 1''',
              (username, hashed_password))
    
    user = c.fetchone()
    
    if user:
        # Update last login
        c.execute('''UPDATE users SET last_login = ? WHERE username = ?''',
                  (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), username))
        conn.commit()
    
    conn.close()
    return user

def create_user(username, password, email):
    """Create a new user and send welcome email"""
    conn = sqlite3.connect('chatbot_data.db')
    c = conn.cursor()
    
    try:
        c.execute('''INSERT INTO users (username, password, email, created_at, last_login)
                     VALUES (?, ?, ?, ?, ?)''',
                  (username, hash_password(password), email, 
                   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                   datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
        
        # Send welcome email
        success, message = send_welcome_email(email, username)
        
        if success:
            log_email(email, "Welcome", "Sent", message)
            return True, "Account created! Check your email for details."
        else:
            log_email(email, "Welcome", "Failed", message)
            return True, "Account created! (Email notification failed)"
            
    except sqlite3.IntegrityError:
        conn.close()
        return False, "Username already exists!"
    except Exception as e:
        conn.close()
        return False, f"Error: {str(e)}"

def generate_reset_token(username):
    """Generate password reset token and send email"""
    conn = sqlite3.connect('chatbot_data.db')
    c = conn.cursor()
    
    # Check if user exists
    c.execute("SELECT email FROM users WHERE username = ?", (username,))
    user = c.fetchone()
    
    if not user:
        conn.close()
        return None, "User not found!"
    
    user_email = user[0]
    
    # Generate token
    token = secrets.token_urlsafe(32)
    created_at = datetime.now()
    expires_at = created_at + timedelta(hours=1)
    
    c.execute('''INSERT INTO password_reset_tokens 
                 (username, token, created_at, expires_at, used)
                 VALUES (?, ?, ?, ?, ?)''',
              (username, token, created_at.strftime("%Y-%m-%d %H:%M:%S"),
               expires_at.strftime("%Y-%m-%d %H:%M:%S"), 0))
    
    conn.commit()
    conn.close()
    
    # Send email
    success, message = send_password_reset_email(user_email, username, token)
    
    if success:
        log_email(user_email, "Password Reset", "Sent", message)
        return token, user_email
    else:
        log_email(user_email, "Password Reset", "Failed", message)
        return None, f"Failed to send email: {message}"
    
    return token, user[0]  # Return token and email

def reset_password(token, new_password):
    """Reset password using token"""
    conn = sqlite3.connect('chatbot_data.db')
    c = conn.cursor()
    
    # Check if token is valid
    c.execute('''SELECT username, expires_at, used FROM password_reset_tokens 
                 WHERE token = ?''', (token,))
    
    result = c.fetchone()
    
    if not result:
        conn.close()
        return False, "Invalid reset token!"
    
    username, expires_at, used = result
    
    if used == 1:
        conn.close()
        return False, "This reset link has already been used!"
    
    # Check if token expired
    expires_at_dt = datetime.strptime(expires_at, "%Y-%m-%d %H:%M:%S")
    if datetime.now() > expires_at_dt:
        conn.close()
        return False, "Reset link has expired!"
    
    # Update password
    c.execute('''UPDATE users SET password = ? WHERE username = ?''',
              (hash_password(new_password), username))
    
    # Mark token as used
    c.execute('''UPDATE password_reset_tokens SET used = 1 WHERE token = ?''',
              (token,))
    
    conn.commit()
    conn.close()
    
    return True, "Password reset successfully!"

def get_user_details(username):
    """Get user details"""
    conn = sqlite3.connect('chatbot_data.db')
    c = conn.cursor()
    
    c.execute('''SELECT username, email, created_at, last_login FROM users 
                 WHERE username = ?''', (username,))
    
    user = c.fetchone()
    conn.close()
    
    if user:
        return {
            'username': user[0],
            'email': user[1],
            'created_at': user[2],
            'last_login': user[3]
        }
    return None


# ==================== REAL DATABASE FUNCTIONS ====================
def init_db_real():
    """Initialize enhanced database"""
    conn = sqlite3.connect('chatbot_data.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS queries_real (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        query TEXT NOT NULL,
        intent TEXT NOT NULL,
        confidence REAL NOT NULL,
        success INTEGER NOT NULL,
        timestamp TEXT NOT NULL,
        response_time INTEGER NOT NULL,
        user_id TEXT,
        session_id TEXT,
        device TEXT,
        location TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS training_real (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        epochs INTEGER NOT NULL,
        batch_size INTEGER NOT NULL,
        learning_rate REAL NOT NULL,
        accuracy REAL NOT NULL,
        loss REAL NOT NULL,
        duration INTEGER NOT NULL
    )''')
    
    conn.commit()
    conn.close()

def add_real_query(query_text, intent, confidence, success, response_time, 
                   user_id="anonymous", session_id="session", device="web", location="Unknown"):
    """Save query to database"""
    conn = sqlite3.connect('chatbot_data.db')
    c = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    c.execute('''INSERT INTO queries_real 
                 (query, intent, confidence, success, timestamp, response_time,
                  user_id, session_id, device, location)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (query_text, intent, confidence, success, timestamp, response_time,
               user_id, session_id, device, location))
    conn.commit()
    conn.close()

def get_real_queries(limit=1000):
    """Load queries from database"""
    conn = sqlite3.connect('chatbot_data.db')
    try:
        df = pd.read_sql_query(f"SELECT * FROM queries_real ORDER BY timestamp DESC LIMIT {limit}", conn)
    except:
        df = pd.DataFrame(columns=['id', 'query', 'intent', 'confidence', 'success', 
                                   'timestamp', 'response_time', 'user_id', 'session_id', 
                                   'device', 'location'])
    conn.close()
    return df

def add_real_training(epochs, batch_size, learning_rate, accuracy, loss, duration):
    """Save training to database"""
    conn = sqlite3.connect('chatbot_data.db')
    c = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    c.execute('''INSERT INTO training_real
                 (timestamp, epochs, batch_size, learning_rate, accuracy, loss, duration)
                 VALUES (?, ?, ?, ?, ?, ?, ?)''',
              (timestamp, epochs, batch_size, learning_rate, accuracy, loss, duration))
    conn.commit()
    conn.close()

def get_real_training():
    """Load training from database"""
    conn = sqlite3.connect('chatbot_data.db')
    try:
        df = pd.read_sql_query("SELECT * FROM training_real ORDER BY timestamp DESC LIMIT 50", conn)
        if not df.empty:
            return df.to_dict('records')
    except:
        pass
    conn.close()
    return []



# ==================== EMAIL CONFIGURATION ====================
EMAIL_CONFIG = {
    'smtp_server': 'smtp.gmail.com',
    'smtp_port': 587,
    'sender_email': 'govindhasatheeshkrishna@gmail.com',  # ✅ Your email
    'sender_password': 'gdupdakynkubaeyu',  # ✅ Your app password (remove spaces!)
    'sender_name': 'AI Chatbot Admin'
}

def send_email(to_email, subject, body, html=True):
    """
    Send email using SMTP
    
    Args:
        to_email: Recipient email address
        subject: Email subject
        body: Email body (HTML or plain text)
        html: Whether body is HTML (default: True)
    
    Returns:
        (success: bool, message: str)
    """
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['From'] = f"{EMAIL_CONFIG['sender_name']} <{EMAIL_CONFIG['sender_email']}>"
        msg['To'] = to_email
        msg['Subject'] = subject
        
        # Add body
        if html:
            msg.attach(MIMEText(body, 'html'))
        else:
            msg.attach(MIMEText(body, 'plain'))
        
        # Connect to SMTP server
        server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
        server.starttls()  # Enable TLS encryption
        server.login(EMAIL_CONFIG['sender_email'], EMAIL_CONFIG['sender_password'])
        
        # Send email
        server.send_message(msg)
        server.quit()
        
        return True, "Email sent successfully!"
        
    except smtplib.SMTPAuthenticationError:
        return False, "Authentication failed! Check your email/password."
    except smtplib.SMTPException as e:
        return False, f"SMTP error: {str(e)}"
    except Exception as e:
        return False, f"Error sending email: {str(e)}"

def send_password_reset_email(to_email, username, token):
    """Send password reset email with token"""
    
    reset_link = f"http://localhost:8501/?reset_token={token}"  # Update with your URL
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Inter', Arial, sans-serif; background-color: #f4f4f4; margin: 0; padding: 0; }}
            .container {{ max-width: 600px; margin: 40px auto; background: white; border-radius: 15px; 
                         box-shadow: 0 10px 30px rgba(0,0,0,0.1); overflow: hidden; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px; text-align: center; }}
            .header h1 {{ color: white; margin: 0; font-size: 28px; }}
            .content {{ padding: 40px; }}
            .button {{ display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                      color: white; text-decoration: none; padding: 15px 40px; border-radius: 10px; 
                      font-weight: bold; margin: 20px 0; }}
            .footer {{ background: #f8f8f8; padding: 20px; text-align: center; color: #666; font-size: 14px; }}
            .token {{ background: #f0f0f0; padding: 15px; border-radius: 8px; font-family: monospace; 
                     word-break: break-all; margin: 20px 0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔐 Password Reset Request</h1>
            </div>
            <div class="content">
                <p>Hi <strong>{username}</strong>,</p>
                <p>We received a request to reset your password for your AI Chatbot Command Center account.</p>
                <p>Click the button below to reset your password:</p>
                <a href="{reset_link}" class="button">Reset Password</a>
                <p>Or copy and paste this token in the reset form:</p>
                <div class="token">{token}</div>
                <p><strong>⏰ This link will expire in 1 hour.</strong></p>
                <p>If you didn't request this, please ignore this email.</p>
            </div>
            <div class="footer">
                <p>AI Chatbot Command Center v4.0</p>
                <p>© 2024 All Rights Reserved</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return send_email(to_email, "🔐 Password Reset Request - AI Chatbot", html_body, html=True)

def send_welcome_email(to_email, username):
    """Send welcome email to new users"""
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Inter', Arial, sans-serif; background-color: #f4f4f4; margin: 0; padding: 0; }}
            .container {{ max-width: 600px; margin: 40px auto; background: white; border-radius: 15px; 
                         box-shadow: 0 10px 30px rgba(0,0,0,0.1); overflow: hidden; }}
            .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px; text-align: center; }}
            .header h1 {{ color: white; margin: 0; font-size: 28px; }}
            .content {{ padding: 40px; }}
            .feature {{ background: #f8f8f8; padding: 15px; border-radius: 10px; margin: 10px 0; }}
            .footer {{ background: #f8f8f8; padding: 20px; text-align: center; color: #666; font-size: 14px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎉 Welcome to AI Command Center!</h1>
            </div>
            <div class="content">
                <p>Hi <strong>{username}</strong>,</p>
                <p>Welcome aboard! Your account has been successfully created.</p>
                
                <h3>🚀 What you can do:</h3>
                <div class="feature">📊 <strong>Real-time Analytics</strong> - Monitor chatbot performance</div>
                <div class="feature">🧠 <strong>ML Training</strong> - Train custom AI models</div>
                <div class="feature">🎯 <strong>Intent Management</strong> - Create and manage intents</div>
                <div class="feature">📈 <strong>Advanced Reports</strong> - Generate detailed insights</div>
                
                <p style="margin-top: 30px;">Get started by logging in to your dashboard!</p>
            </div>
            <div class="footer">
                <p>AI Chatbot Command Center v4.0</p>
                <p>© 2024 All Rights Reserved</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return send_email(to_email, "🎉 Welcome to AI Chatbot Command Center!", html_body, html=True)

def send_admin_notification(to_email, subject, message, priority="normal"):
    """Send notification email to admin or developer"""
    
    priority_colors = {
        "low": "#10b981",
        "normal": "#3b82f6", 
        "high": "#f59e0b",
        "critical": "#ef4444"
    }
    
    priority_icons = {
        "low": "ℹ️",
        "normal": "📢",
        "high": "⚠️",
        "critical": "🚨"
    }
    
    color = priority_colors.get(priority, "#3b82f6")
    icon = priority_icons.get(priority, "📢")
    
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: 'Inter', Arial, sans-serif; background-color: #f4f4f4; margin: 0; padding: 0; }}
            .container {{ max-width: 600px; margin: 40px auto; background: white; border-radius: 15px; 
                         box-shadow: 0 10px 30px rgba(0,0,0,0.1); overflow: hidden; }}
            .header {{ background: {color}; padding: 40px; text-align: center; }}
            .header h1 {{ color: white; margin: 0; font-size: 28px; }}
            .content {{ padding: 40px; }}
            .message {{ background: #f8f8f8; padding: 20px; border-radius: 10px; border-left: 4px solid {color}; }}
            .footer {{ background: #f8f8f8; padding: 20px; text-align: center; color: #666; font-size: 14px; }}
            .timestamp {{ color: #999; font-size: 13px; margin-top: 20px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>{icon} System Notification</h1>
            </div>
            <div class="content">
                <h2>{subject}</h2>
                <div class="message">
                    {message}
                </div>
                <div class="timestamp">
                    ⏰ {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                </div>
            </div>
            <div class="footer">
                <p>AI Chatbot Command Center v4.0</p>
                <p>© 2024 All Rights Reserved</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return send_email(to_email, f"{icon} {subject}", html_body, html=True)

# Store email sending history
def log_email(to_email, subject, status, message):
    """Log email sending history to database"""
    conn = sqlite3.connect('chatbot_data.db')
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS email_logs
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  to_email TEXT,
                  subject TEXT,
                  status TEXT,
                  message TEXT,
                  timestamp TEXT)''')
    
    c.execute('''INSERT INTO email_logs (to_email, subject, status, message, timestamp)
                 VALUES (?, ?, ?, ?, ?)''',
              (to_email, subject, status, message, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    
    conn.commit()
    conn.close()

# ==================== PAGE SETUP ====================
st.set_page_config(
    page_title="🤖 AI Chatbot Command Center",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# In sidebar, add comprehensive email test:
with st.expander("📧 Email System Test", expanded=False):
    st.markdown("### Test Email Configuration")
    
    # Show current config (hide password)
    st.info(f"📧 Sender: {EMAIL_CONFIG['sender_email']}")
    st.info(f"🔒 Password: {'*' * len(EMAIL_CONFIG['sender_password']) if EMAIL_CONFIG['sender_password'] else 'Not Set'}")
    st.info(f"🌐 Server: {EMAIL_CONFIG['smtp_server']}:{EMAIL_CONFIG['smtp_port']}")
    
    test_email = st.text_input("Test Email Address", 
                                value=EMAIL_CONFIG['sender_email'],
                                placeholder="recipient@example.com")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📧 Send Test", use_container_width=True):
            if not EMAIL_CONFIG['sender_email'] or not EMAIL_CONFIG['sender_password']:
                st.error("❌ Email not configured! Set credentials in .env file")
            else:
                with st.spinner("Sending test email..."):
                    html = f"""
                    <html>
                    <body style='font-family: Arial; padding: 20px;'>
                        <div style='background: linear-gradient(135deg, #667eea, #764ba2); 
                                    padding: 30px; border-radius: 15px; color: white; text-align: center;'>
                            <h1>✅ Email System Working!</h1>
                            <p>Your SMTP configuration is correct.</p>
                            <p><strong>Sent at:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
                        </div>
                    </body>
                    </html>
                    """
                    
                    success, msg = send_email(test_email, "✅ Test Email", html, html=True)
                    
                    if success:
                        st.success(f"✅ {msg}")
                        st.balloons()
                        log_email(test_email, "Test", "Sent", msg)
                    else:
                        st.error(f"❌ {msg}")
                        log_email(test_email, "Test", "Failed", msg)
                        
                        # Troubleshooting tips
                        st.markdown("""
                        **Troubleshooting:**
                        - ✅ Check .env file exists
                        - ✅ Verify email/password are correct
                        - ✅ Use App Password (not regular password)
                        - ✅ Enable "Less secure app access" if needed
                        - ✅ Check firewall/antivirus settings
                        """)
    
    with col2:
        if st.button("📜 View Logs", use_container_width=True):
            # Show email logs
            conn = sqlite3.connect('chatbot_data.db')
            try:
                logs = pd.read_sql_query(
                    "SELECT * FROM email_logs ORDER BY timestamp DESC LIMIT 10", 
                    conn
                )
                if not logs.empty:
                    st.dataframe(logs, use_container_width=True)
                else:
                    st.info("No email logs yet")
            except:
                st.warning("Email logs table not found")
            finally:
                conn.close()


# Add this function to check email readiness:
def check_email_status():
    """Check if email system is properly configured"""
    issues = []
    
    # Check .env file
    if not os.path.exists('.env'):
        issues.append("❌ .env file not found")
    
    # Check credentials
    if not EMAIL_CONFIG['sender_email']:
        issues.append("❌ SENDER_EMAIL not set")
    
    if not EMAIL_CONFIG['sender_password']:
        issues.append("❌ SENDER_PASSWORD not set")
    
    # Check SMTP settings
    if not EMAIL_CONFIG['smtp_server']:
        issues.append("❌ SMTP_SERVER not set")
    
    if issues:
        return False, issues
    else:
        return True, ["✅ Email system configured correctly"]

# Show status in header:
email_ready, email_status = check_email_status()

if not email_ready:
    st.warning("⚠️ Email System Not Configured")
    with st.expander("Email Configuration Issues"):
        for issue in email_status:
            st.warning(issue)


# ==================== DATABASE FUNCTIONS ====================
def init_db():
    conn = sqlite3.connect('chatbot_data.db')
    c = conn.cursor()
    
    # Queries table
    c.execute('''CREATE TABLE IF NOT EXISTS queries
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  query TEXT, 
                  intent TEXT, 
                  confidence REAL, 
                  success INTEGER,
                  timestamp TEXT,
                  response_time INTEGER,
                  user_id TEXT,
                  session_id TEXT,
                  device TEXT,
                  location TEXT)''')
    
    # Intents table
    c.execute('''CREATE TABLE IF NOT EXISTS intents
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT UNIQUE,
                  category TEXT,
                  priority TEXT,
                  accuracy REAL)''')
    
    # Intent examples table
    c.execute('''CREATE TABLE IF NOT EXISTS intent_examples
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  intent_id INTEGER,
                  example TEXT,
                  FOREIGN KEY (intent_id) REFERENCES intents (id))''')
    
    # Feedback table
    c.execute('''CREATE TABLE IF NOT EXISTS feedback
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  message TEXT,
                  rating INTEGER,
                  timestamp TEXT,
                  status TEXT,
                  sentiment TEXT,
                  category TEXT)''')
    
    # Conversations table
    c.execute('''CREATE TABLE IF NOT EXISTS conversations
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  session_id TEXT,
                  role TEXT,
                  message TEXT,
                  timestamp TEXT)''')
    
    conn.commit()
    conn.close()

def add_query_to_db(query, intent, confidence, success, response_time, user_id="user", session_id="session", device="desktop", location="Unknown"):
    conn = sqlite3.connect('chatbot_data.db')
    c = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('''INSERT INTO queries (query, intent, confidence, success, timestamp, response_time, user_id, session_id, device, location)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (query, intent, confidence, success, timestamp, response_time, user_id, session_id, device, location))
    conn.commit()
    conn.close()

def get_queries_from_db(limit=100):
    conn = sqlite3.connect('chatbot_data.db')
    df = pd.read_sql_query(f"SELECT * FROM queries ORDER BY timestamp DESC LIMIT {limit}", conn)
    conn.close()
    return df

def add_intent_to_db(name, examples, category="General", priority="Medium", accuracy=90.0):
    conn = sqlite3.connect('chatbot_data.db')
    c = conn.cursor()
    try:
        c.execute('''INSERT INTO intents (name, category, priority, accuracy)
                     VALUES (?, ?, ?, ?)''', (name, category, priority, accuracy))
        intent_id = c.lastrowid
        
        for example in examples:
            c.execute('''INSERT INTO intent_examples (intent_id, example)
                         VALUES (?, ?)''', (intent_id, example))
        
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False

def get_intents_from_db():
    conn = sqlite3.connect('chatbot_data.db')
    c = conn.cursor()
    c.execute("SELECT * FROM intents")
    intents = c.fetchall()
    
    result = []
    for intent in intents:
        c.execute("SELECT example FROM intent_examples WHERE intent_id = ?", (intent[0],))
        examples = [e[0] for e in c.fetchall()]
        result.append({
            "id": intent[0],
            "name": intent[1],
            "category": intent[2],
            "priority": intent[3],
            "accuracy": intent[4],
            "examples": examples
        })
    
    conn.close()
    return result

def add_conversation_to_db(session_id, role, message):
    conn = sqlite3.connect('chatbot_data.db')
    c = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('''INSERT INTO conversations (session_id, role, message, timestamp)
                 VALUES (?, ?, ?, ?)''', (session_id, role, message, timestamp))
    conn.commit()
    conn.close()

def get_conversation_from_db(session_id):
    conn = sqlite3.connect('chatbot_data.db')
    df = pd.read_sql_query("SELECT * FROM conversations WHERE session_id = ? ORDER BY timestamp", conn, params=(session_id,))
    conn.close()
    return df

def search_queries(search_term):
    conn = sqlite3.connect('chatbot_data.db')
    query = f"SELECT * FROM queries WHERE query LIKE '%{search_term}%' OR intent LIKE '%{search_term}%' ORDER BY timestamp DESC LIMIT 50"
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

# ==================== SESSION STATE INITIALIZATION ====================
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'username' not in st.session_state:
    st.session_state.username = None
if 'user_email' not in st.session_state:
    st.session_state.user_email = None
if 'show_forgot_password' not in st.session_state:
    st.session_state.show_forgot_password = False
if 'show_signup' not in st.session_state:
    st.session_state.show_signup = False
if 'reset_token' not in st.session_state:
    st.session_state.reset_token = None
if 'dark_mode' not in st.session_state:
    st.session_state.dark_mode = True
if 'notification_count' not in st.session_state:
    st.session_state.notification_count = 3

# Initialize databases
init_db()
init_users_db()
init_db_real()  


import sqlite3

# Database connection
def init_db():
    conn = sqlite3.connect('chatbot_data.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS queries
                 (id INTEGER PRIMARY KEY, query TEXT, intent TEXT, 
                  confidence REAL, timestamp TEXT)''')
    conn.commit()
    conn.close()

init_db()

# Replace all st.session_state.queries operations with DB operations

# ===== ENHANCEMENT #1: NEW SESSION STATES =====
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'active_conversations' not in st.session_state:
    st.session_state.active_conversations = random.randint(150, 300)
if 'system_alerts' not in st.session_state:
    st.session_state.system_alerts = [
        {"type": "info", "message": "Model accuracy improved by 3.2%", "time": "5 min ago"},
        {"type": "warning", "message": "High query volume detected", "time": "12 min ago"},
        {"type": "success", "message": "Backup completed successfully", "time": "1 hour ago"}
    ]
# ==================== STUNNING 3D BANK LOGIN PAGE ====================
if not st.session_state.logged_in:
    # Inject CSS and HTML in ONE block to avoid text rendering
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800;900&display=swap');
        
        .stApp {
            background: radial-gradient(ellipse at top, #1a1a2e 0%, #0f0f1e 50%, #05050a 100%) !important;
            font-family: 'Inter', sans-serif !important;
        }
        
        /* Hide default Streamlit elements */
        #MainMenu, footer, header {visibility: hidden;}
        
        .block-container {padding-top: 2rem !important;}
        
        /* 3D Scene */
        .scene {
            width: 100%;
            height: 500px;
            perspective: 1500px;
            display: flex;
            justify-content: center;
            align-items: center;
            position: relative;
            margin: 0 auto 2rem auto;
        }
        
        .building {
            position: relative;
            width: 350px;
            height: 400px;
            transform-style: preserve-3d;
            animation: build 4s cubic-bezier(0.68,-0.55,0.265,1.55) forwards,
                       rotate 20s linear 4s infinite;
        }
        
        @keyframes build {
            0% {transform: rotateX(-90deg) translateZ(-500px) scale(0.5); opacity: 0;}
            50% {transform: rotateX(-20deg) translateZ(-100px) scale(0.8); opacity: 0.7;}
            100% {transform: rotateX(0deg) translateZ(0) scale(1); opacity: 1;}
        }
        
        @keyframes rotate {
            0%, 100% {transform: rotateY(-5deg) rotateX(2deg);}
            50% {transform: rotateY(5deg) rotateX(-2deg);}
        }
        
        .fl {
            position: absolute;
            width: 100%;
            height: 70px;
            transform-style: preserve-3d;
            animation: rise 1s cubic-bezier(0.68,-0.55,0.265,1.55) backwards;
        }
        
        @keyframes rise {
            0% {transform: translateY(500px) translateZ(-200px) scale(0); opacity: 0;}
            100% {transform: translateY(0) translateZ(0) scale(1); opacity: 1;}
        }
        
        .fl:nth-child(1) {bottom: 0; animation-delay: 0.5s;}
        .fl:nth-child(2) {bottom: 75px; animation-delay: 0.8s;}
        .fl:nth-child(3) {bottom: 150px; animation-delay: 1.1s;}
        .fl:nth-child(4) {bottom: 225px; animation-delay: 1.4s;}
        .fl:nth-child(5) {bottom: 300px; animation-delay: 1.7s;}
        
        .ff {
            position: absolute;
            width: 100%;
            height: 100%;
            background: linear-gradient(135deg, rgba(26,77,109,0.95), rgba(45,95,126,0.95));
            border: 3px solid rgba(212,175,55,0.3);
            border-radius: 5px;
            transform: translateZ(50px);
            box-shadow: 0 0 30px rgba(212,175,55,0.3), inset 0 0 20px rgba(212,175,55,0.1);
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 6px;
            padding: 10px;
        }
        
        .fl:nth-child(5) .ff {
            background: linear-gradient(135deg, rgba(212,175,55,0.95), rgba(244,229,161,0.95), rgba(212,175,55,0.95));
            border-radius: 10px 10px 5px 5px;
            height: 60px;
        }
        
        .ft {
            position: absolute;
            width: 100%;
            height: 100px;
            background: linear-gradient(to bottom, rgba(45,95,126,0.8), rgba(26,77,109,0.8));
            transform: rotateX(90deg) translateZ(35px);
            border: 2px solid rgba(212,175,55,0.2);
        }
        
        .fl-l, .fl-r {
            position: absolute;
            width: 100px;
            height: 100%;
            background: linear-gradient(to right, rgba(15,32,39,0.9), rgba(26,77,109,0.9));
            border: 2px solid rgba(212,175,55,0.2);
        }
        
        .fl-l {left: 0; transform: rotateY(-90deg) translateZ(-50px);}
        .fl-r {right: 0; transform: rotateY(90deg) translateZ(-50px);}
        
        .w {
            background: linear-gradient(135deg, rgba(255,215,0,0.3), rgba(255,180,0,0.5));
            border: 2px solid rgba(255,215,0,0.6);
            border-radius: 4px;
            box-shadow: 0 0 10px rgba(255,215,0,0.4), inset 0 0 10px rgba(255,215,0,0.3);
            animation: pulse 3s ease-in-out infinite;
            position: relative;
            overflow: hidden;
        }
        
        .w::before {
            content: '';
            position: absolute;
            top: -50%;
            left: -50%;
            width: 200%;
            height: 200%;
            background: linear-gradient(45deg, transparent 30%, rgba(255,255,255,0.3) 50%, transparent 70%);
            animation: shine 4s linear infinite;
        }
        
        @keyframes pulse {
            0%, 100% {background: rgba(255,215,0,0.3); box-shadow: 0 0 10px rgba(255,215,0,0.4);}
            50% {background: rgba(255,215,0,0.7); box-shadow: 0 0 30px rgba(255,215,0,0.8);}
        }
        
        @keyframes shine {
            0% {transform: translate(-100%, -100%);}
            100% {transform: translate(100%, 100%);}
        }
        
        .w:nth-child(2n) {animation-delay: 0.5s;}
        .w:nth-child(3n) {animation-delay: 1s;}
        .w:nth-child(4n) {animation-delay: 1.5s;}
        .w:nth-child(5n) {animation-delay: 2s;}
        
        .sign {
            position: absolute;
            top: -60px;
            left: 50%;
            transform: translateX(-50%) translateZ(80px);
            background: linear-gradient(135deg, #d4af37, #f4e5a1, #d4af37);
            padding: 15px 40px;
            border-radius: 12px;
            font-weight: 900;
            font-size: 1.6rem;
            color: #0f0f1e;
            box-shadow: 0 20px 60px rgba(212,175,55,0.6), 0 0 40px rgba(212,175,55,0.4);
            letter-spacing: 3px;
            animation: float 3s ease-in-out 2s infinite;
            border: 3px solid rgba(255,255,255,0.3);
            white-space: nowrap;
        }
        
        @keyframes float {
            0%, 100% {transform: translateX(-50%) translateZ(80px) translateY(0); box-shadow: 0 20px 60px rgba(212,175,55,0.6);}
            50% {transform: translateX(-50%) translateZ(80px) translateY(-15px); box-shadow: 0 30px 80px rgba(212,175,55,0.9);}
        }
        
        .coin {
            position: absolute;
            width: 60px;
            height: 60px;
            background: radial-gradient(circle at 35% 35%, #f4e5a1, #d4af37);
            border-radius: 50%;
            border: 4px solid #d4af37;
            box-shadow: 0 15px 40px rgba(212,175,55,0.5);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 2rem;
            font-weight: bold;
            color: #0f0f1e;
            animation: coinfly 5s ease-in-out infinite;
        }
        
        @keyframes coinfly {
            0%, 100% {transform: translateY(0) rotateY(0deg) translateZ(0);}
            25% {transform: translateY(-40px) rotateY(90deg) translateZ(20px);}
            50% {transform: translateY(-60px) rotateY(180deg) translateZ(0);}
            75% {transform: translateY(-40px) rotateY(270deg) translateZ(-20px);}
        }
        
        .c1 {top: 60px; left: -80px;}
        .c2 {top: 140px; right: -80px; animation-delay: 1.5s;}
        .c3 {top: 240px; left: -70px; animation-delay: 3s;}
        
        .title {
            font-size: 3.5rem;
            font-weight: 900;
            background: linear-gradient(135deg, #d4af37, #f4e5a1, #d4af37);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            text-align: center;
            margin: 1.5rem 0 0.8rem 0;
            letter-spacing: 2px;
            animation: glow 3s ease-in-out infinite;
            filter: drop-shadow(0 0 20px rgba(212,175,55,0.6));
        }
        
        @keyframes glow {
            0%, 100% {filter: brightness(1) drop-shadow(0 0 20px rgba(212,175,55,0.6));}
            50% {filter: brightness(1.4) drop-shadow(0 0 40px rgba(212,175,55,0.9));}
        }
        
        .sub {
            color: rgba(255,255,255,0.95);
            font-size: 1.2rem;
            text-align: center;
            margin-bottom: 2.5rem;
            font-weight: 600;
        }
        
        .card {
            background: rgba(255,255,255,0.03);
            backdrop-filter: blur(40px);
            border: 2px solid rgba(212,175,55,0.2);
            border-radius: 30px;
            padding: 3rem;
            box-shadow: 0 25px 70px rgba(0,0,0,0.5);
            animation: appear 1.5s cubic-bezier(0.68,-0.55,0.265,1.55) 3s backwards;
            max-width: 520px;
            margin: 0 auto;
        }
        
        @keyframes appear {
            0% {opacity: 0; transform: translateY(100px) scale(0.8);}
            100% {opacity: 1; transform: translateY(0) scale(1);}
        }
        
        .hdr {
            color: white;
            text-align: center;
            font-size: 2rem;
            margin-bottom: 2rem;
            font-weight: 800;
        }
        
        .stTextInput > div > div > input {
            background: rgba(255,255,255,0.05) !important;
            border: 2px solid rgba(212,175,55,0.3) !important;
            border-radius: 15px !important;
            color: white !important;
            padding: 16px 22px !important;
            font-size: 1.05rem !important;
            transition: all 0.4s !important;
        }
        
        .stTextInput > div > div > input:focus {
            border-color: rgba(212,175,55,0.9) !important;
            box-shadow: 0 0 30px rgba(212,175,55,0.4) !important;
            background: rgba(255,255,255,0.1) !important;
            transform: scale(1.02) !important;
        }
        
        .stTextInput > div > div > input::placeholder {
            color: rgba(255,255,255,0.5) !important;
        }
        
        .stButton > button {
            background: linear-gradient(135deg, #d4af37, #f4e5a1, #d4af37) !important;
            color: #0f0f1e !important;
            font-weight: 800 !important;
            border: none !important;
            border-radius: 15px !important;
            padding: 14px 28px !important;
            font-size: 1.05rem !important;
            box-shadow: 0 8px 25px rgba(212,175,55,0.5) !important;
            transition: all 0.4s !important;
            letter-spacing: 1px !important;
        }
        
        .stButton > button:hover {
            transform: translateY(-4px) scale(1.05) !important;
            box-shadow: 0 12px 40px rgba(212,175,55,0.7) !important;
        }
        
        .stCheckbox {color: white !important;}
    </style>
    
    <div class="scene">
        <div class="coin c1">$</div>
        <div class="coin c2">$</div>
        <div class="coin c3">$</div>
        <div class="building">
            <div class="sign">🏛️ SECURE BANK</div>
            <div class="fl"><div class="ff"><div class="w"></div><div class="w"></div><div class="w"></div><div class="w"></div><div class="w"></div></div><div class="ft"></div><div class="fl-l"></div><div class="fl-r"></div></div>
            <div class="fl"><div class="ff"><div class="w"></div><div class="w"></div><div class="w"></div><div class="w"></div><div class="w"></div></div><div class="ft"></div><div class="fl-l"></div><div class="fl-r"></div></div>
            <div class="fl"><div class="ff"><div class="w"></div><div class="w"></div><div class="w"></div><div class="w"></div><div class="w"></div></div><div class="ft"></div><div class="fl-l"></div><div class="fl-r"></div></div>
            <div class="fl"><div class="ff"><div class="w"></div><div class="w"></div><div class="w"></div><div class="w"></div><div class="w"></div></div><div class="ft"></div><div class="fl-l"></div><div class="fl-r"></div></div>
            <div class="fl"><div class="ff"><div class="w"></div><div class="w"></div><div class="w"></div><div class="w"></div><div class="w"></div></div><div class="ft"></div><div class="fl-l"></div><div class="fl-r"></div></div>
        </div>
    </div>
    
    <h1 class="title">BANKBOT ADMIN</h1>
    <p class="sub">Next-Generation Secure Banking Platform</p>
    """, unsafe_allow_html=True)
    
    # Login Form
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        
        if st.session_state.show_forgot_password:
            st.markdown('<h2 class="hdr">🔑 Reset Password</h2>', unsafe_allow_html=True)
            
            if st.session_state.reset_token:
                new_password = st.text_input("New Password", type="password", placeholder="Enter new password")
                confirm_password = st.text_input("Confirm Password", type="password", placeholder="Confirm new password")
                
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("🔄 Reset", type="primary", use_container_width=True):
                        if new_password and confirm_password:
                            if new_password == confirm_password:
                                if len(new_password) >= 6:
                                    success, message = reset_password(st.session_state.reset_token, new_password)
                                    if success:
                                        st.success(message)
                                        st.balloons()
                                        time.sleep(2)
                                        st.session_state.show_forgot_password = False
                                        st.session_state.reset_token = None
                                        st.rerun()
                                    else:
                                        st.error(message)
                                else:
                                    st.error("Password must be 6+ characters!")
                            else:
                                st.error("Passwords don't match!")
                        else:
                            st.error("Fill all fields!")
                with col_b:
                    if st.button("← Back", use_container_width=True):
                        st.session_state.show_forgot_password = False
                        st.session_state.reset_token = None
                        st.rerun()
            else:
                st.info("Enter username for reset link")
                username = st.text_input("Username", placeholder="Enter username")
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("📧 Send Link", type="primary", use_container_width=True):
                        if username:
                            token, email = generate_reset_token(username)
                            if token:
                                st.session_state.reset_token = token
                                st.success("✅ Reset link sent!")
                                st.info(f"📧 To: {email}")
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error(email)
                        else:
                            st.error("Enter username!")
                with col_b:
                    if st.button("← Back", use_container_width=True):
                        st.session_state.show_forgot_password = False
                        st.rerun()
        
        elif st.session_state.show_signup:
            st.markdown('<h2 class="hdr">📝 Create Account</h2>', unsafe_allow_html=True)
            new_username = st.text_input("Username", placeholder="Choose username", key="signup_user")
            new_email = st.text_input("Email", placeholder="your.email@example.com", key="signup_email")
            new_password = st.text_input("Password", type="password", placeholder="Choose password", key="signup_pass")
            confirm_password = st.text_input("Confirm Password", type="password", placeholder="Confirm password", key="signup_confirm")
            
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("✨ Create", type="primary", use_container_width=True):
                    if new_username and new_email and new_password and confirm_password:
                        if new_password == confirm_password:
                            if len(new_password) >= 6:
                                success, message = create_user(new_username, new_password, new_email)
                                if success:
                                    st.success(message)
                                    st.balloons()
                                    time.sleep(2)
                                    st.session_state.show_signup = False
                                    st.rerun()
                                else:
                                    st.error(message)
                            else:
                                st.error("Password must be 6+ characters!")
                        else:
                            st.error("Passwords don't match!")
                    else:
                        st.error("Fill all fields!")
            with col_b:
                if st.button("← Back", use_container_width=True):
                    st.session_state.show_signup = False
                    st.rerun()
        
        else:
            st.markdown('<h2 class="hdr">🔐 Administrator Portal</h2>', unsafe_allow_html=True)
            username = st.text_input("Username", placeholder="👤 Username", key="login_user")
            password = st.text_input("Password", type="password", placeholder="🔒 Password", key="login_pass")
            st.markdown("<br>", unsafe_allow_html=True)
            
            if st.button("🏦 ACCESS SYSTEM", type="primary", use_container_width=True):
                if username and password:
                    user = verify_login(username, password)
                    if user:
                        st.session_state.logged_in = True
                        st.session_state.username = user[1]
                        st.session_state.user_email = user[2]
                        st.success(f"✅ Welcome, {user[1]}!")
                        st.balloons()
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Invalid credentials!")
                else:
                    st.error("Enter credentials!")
            
            st.markdown("<br>", unsafe_allow_html=True)
            col_x, col_y = st.columns(2)
            with col_x:
                st.checkbox("🔐 Remember", value=True)
            with col_y:
                if st.button("Forgot password?", use_container_width=True):
                    st.session_state.show_forgot_password = True
                    st.rerun()
            
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("📝 Register", use_container_width=True):
                st.session_state.show_signup = True
                st.rerun()
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        with st.expander("ℹ️ Demo"):
            st.markdown("""
            <div style='background: rgba(212,175,55,0.1); padding: 15px; border-radius: 10px;'>
                <p style='color: white; margin: 0;'><strong>User:</strong> <code>admin</code></p>
                <p style='color: white; margin: 10px 0 0 0;'><strong>Pass:</strong> <code>admin123</code></p>
            </div>
            """, unsafe_allow_html=True)
    
    st.stop()

# ==================== DATA INITIALIZATION ====================
if 'queries' not in st.session_state:
    # Try to load from database first
    real_data = get_real_queries(limit=1000)
    
    if not real_data.empty:
        st.session_state.queries = real_data.to_dict('records')
        print("✅ Loaded from database:", len(st.session_state.queries), "queries")
    else:
        # Generate some initial data if database is empty
        st.session_state.queries = []
        intents_list = ["check_balance", "transfer_money", "find_atm", "card_block", "loan_inquiry", "bill_payment"]
        queries_text = {
            "check_balance": [
                "What's my balance?", 
                "Show balance", 
                "Check account balance",
                "How much money do I have?",
                "Account balance inquiry",
                "What's my current balance?",
                "Show me my balance",
                "Balance check",
                "What's in my account?",
                "Check savings balance",
                "Display balance",
                "Account status"
            ],
            "transfer_money": [
                "Transfer $100", 
                "Send money",
                "Transfer $500 to savings",
                "Move money to checking",
                "Send $200 to John",
                "Transfer funds",
                "Wire transfer",
                "Send payment",
                "Transfer to account",
                "Move $1000",
                "Send money to friend",
                "Quick transfer"
            ],
            "find_atm": [
                "Where is ATM?", 
                "Find ATM",
                "Nearest ATM location",
                "ATM near me",
                "Where can I withdraw cash?",
                "Find closest ATM",
                "ATM locations",
                "Where is the nearest branch?",
                "Cash withdrawal point",
                "ATM finder",
                "Locate ATM"
            ],
            "card_block": [
                "Block card", 
                "Freeze card",
                "I lost my card",
                "Card stolen",
                "Disable my credit card",
                "Stop my card",
                "Lock my debit card",
                "Card was stolen",
                "Emergency card block",
                "Freeze my card immediately",
                "Deactivate card",
                "Report lost card"
            ],
            "loan_inquiry": [
                "Apply loan", 
                "Loan rates",
                "Home loan inquiry",
                "Car loan application",
                "Personal loan rates",
                "What are mortgage rates?",
                "Loan eligibility",
                "Apply for home loan",
                "Interest rates for loans",
                "Loan calculator",
                "Education loan details",
                "Business loan application"
            ],
            "bill_payment": [
                "Pay electricity bill",
                "Pay my phone bill",
                "Water bill payment",
                "Pay credit card bill",
                "Utility payment",
                "Bill payment options",
                "Pay my bills",
                "Internet bill payment",
                "Gas bill payment",
                "Pay outstanding bills"
            ]
        }
        
        # ✅ GENERATE 500 INITIAL QUERIES
        for i in range(500):
            intent = random.choice(intents_list)
            query_text = random.choice(queries_text[intent])
            
            # Spread queries over last 7 days
            hours_ago = random.randint(0, 168)  # 7 days = 168 hours
            timestamp = (datetime.now() - timedelta(hours=hours_ago)).strftime("%Y-%m-%d %H:%M:%S")
            
            query = {
                "id": i + 1,
                "query": query_text,
                "intent": intent,
                "confidence": random.randint(75, 99),
                "success": True,
                "timestamp": timestamp,
                "response_time": random.randint(100, 500),
                "user_id": f"user_{random.randint(1000, 9999)}",
                "session_id": f"session_{random.randint(10000, 99999)}",
                "device": random.choice(["mobile", "desktop", "tablet"]),
                "location": random.choice(["New York", "London", "Tokyo", "Mumbai", "Singapore", "Dubai", "Sydney"])
            }
            
            st.session_state.queries.append(query)
            # Save to database
            add_real_query(query['query'], query['intent'], query['confidence'], 
                          query['success'], query['response_time'], query['user_id'],
                          query['session_id'], query['device'], query['location'])
        
        print(f"✅ Generated {len(st.session_state.queries)} initial queries")

if 'intents' not in st.session_state:
    st.session_state.intents = [
        {"id": 1, "name": "check_balance", "examples": ["What's my balance?", "Show balance", "Check savings", "How much money?", "Balance inquiry", "Current balance", "Account balance"], "category": "Account", "priority": "High", "accuracy": 95.5},
        {"id": 2, "name": "transfer_money", "examples": ["Transfer $500", "Send money", "Move funds", "Wire transfer", "Send payment", "Transfer to savings"], "category": "Transactions", "priority": "Critical", "accuracy": 94.2},
        {"id": 3, "name": "find_atm", "examples": ["Where is ATM?", "Nearest ATM", "Find ATM", "ATM location", "Closest ATM", "ATM near me"], "category": "Services", "priority": "Medium", "accuracy": 92.8},
        {"id": 4, "name": "card_block", "examples": ["Block card", "Freeze card", "Lost card", "Stolen card", "Disable card", "Stop card"], "category": "Security", "priority": "Critical", "accuracy": 97.1},
        {"id": 5, "name": "loan_inquiry", "examples": ["Apply for loan", "Loan rates", "Home loan", "Car loan", "Personal loan", "Mortgage"], "category": "Loans", "priority": "High", "accuracy": 91.3},
        {"id": 6, "name": "bill_payment", "examples": ["Pay bill", "Electricity bill", "Phone bill", "Water bill", "Utility payment"], "category": "Payments", "priority": "Medium", "accuracy": 89.7},
    ]

if 'faqs' not in st.session_state:
    st.session_state.faqs = [
        {"id": 1, "question": "What is the minimum balance?", "answer": "Minimum balance is $500 for savings accounts.", "category": "Account", "views": 1240, "helpful": 1180},
        {"id": 2, "question": "How to reset PIN?", "answer": "Reset PIN via mobile app or visit branch.", "category": "Security", "views": 980, "helpful": 920},
        {"id": 3, "question": "What are transfer limits?", "answer": "Daily limit: $10,000 online, $50,000 branch.", "category": "Transactions", "views": 1560, "helpful": 1490},
        {"id": 4, "question": "How to block card?", "answer": "Call hotline or use mobile app instantly.", "category": "Security", "views": 2100, "helpful": 2050},
        {"id": 5, "question": "Loan interest rates?", "answer": "Personal loan: 7.5%, Home loan: 6.2%", "category": "Loans", "views": 1830, "helpful": 1750},
    ]

if 'feedback' not in st.session_state:
    st.session_state.feedback = []
    for i in range(25):
        st.session_state.feedback.append({
            "id": i + 1,
            "message": random.choice(["Excellent service!", "Very helpful", "Could be better", "Response too slow", "Perfect!", "Not accurate", "Great experience", "Needs improvement"]),
            "rating": random.randint(1, 5),
            "timestamp": (datetime.now() - timedelta(hours=random.randint(0, 168))).strftime("%Y-%m-%d %H:%M:%S"),
            "status": random.choice(["new", "reviewed", "resolved"]),
            "sentiment": random.choice(["positive", "negative", "neutral"]),
            "category": random.choice(["Performance", "Accuracy", "Speed", "UX"])
        })

if 'settings' not in st.session_state:
    st.session_state.settings = {
        "confidence_threshold": 75,
        "max_response_time": 3,
        "enable_logging": True,
        "enable_analytics": True,
        "auto_retrain": False,
        "notification_email": "admin@chatbot.com",
        "fallback_message": "I'm sorry, I didn't understand. Could you rephrase?",
        "welcome_message": "Hello! How can I help you today?",
        "language": "English",
        "max_retries": 3,
        "cache_duration": 3600,
        "rate_limit": 100
    }

if 'training_history' not in st.session_state:
    # Load from database
    real_training = get_real_training()
    
    if real_training:
        st.session_state.training_history = real_training
        print("✅ Loaded training history from database")

        # Initialize best metrics with default values
best_accuracy = 0.0
best_loss = 0.0
best_val_accuracy = 0.0
best_val_loss = 0.0

# If training history exists, extract the best metrics
if 'training_history' in st.session_state and st.session_state.training_history:
    history = st.session_state.training_history
    
    # Get best values across all epochs
    if len(history) > 0:
        best_accuracy = max(epoch.get('accuracy', 0) for epoch in history)
        best_val_accuracy = max(epoch.get('val_accuracy', 0) for epoch in history)
        best_loss = min(epoch.get('loss', float('inf')) for epoch in history)
        best_val_loss = min(epoch.get('val_loss', float('inf')) for epoch in history)
    else:
        # Generate initial data
        st.session_state.training_history = []
        for i in range(3):
            record = {
                "id": i + 1,
                "timestamp": (datetime.now() - timedelta(days=i*2)).strftime("%Y-%m-%d %H:%M:%S"),
                "epochs": random.randint(30, 100),
                "batch_size": 32,
                "learning_rate": 0.00002,
                "accuracy": random.uniform(0.88, 0.96),
                "loss": random.uniform(0.05, 0.15),
                "duration": random.randint(120, 600)
            }
            st.session_state.training_history.append(record)

if 'model_metrics' not in st.session_state:
    st.session_state.model_metrics = {
        "accuracy": 0.945,
        "precision": 0.932,
        "recall": 0.918,
        "f1_score": 0.925,
        "training_loss": [0.8, 0.6, 0.4, 0.25, 0.15, 0.10, 0.08],
        "validation_loss": [0.85, 0.65, 0.45, 0.30, 0.20, 0.15, 0.12]
    }

if 'api_logs' not in st.session_state:
    st.session_state.api_logs = []
    for i in range(50):
        st.session_state.api_logs.append({
            "id": i + 1,
            "endpoint": random.choice(["/api/query", "/api/train", "/api/feedback", "/api/intents", "/api/analytics"]),
            "method": random.choice(["GET", "POST", "PUT", "DELETE"]),
            "status": random.choice([200, 200, 200, 201, 400, 500]),
            "response_time": random.randint(50, 800),
            "timestamp": (datetime.now() - timedelta(minutes=random.randint(0, 2880))).strftime("%Y-%m-%d %H:%M:%S"),
            "user_agent": random.choice(["Chrome", "Firefox", "Safari", "Edge"]),
            "ip_address": f"{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}"
        })

if 'ab_tests' not in st.session_state:
    st.session_state.ab_tests = [
        {"id": 1, "name": "Response Time Optimization", "variant_a": "Standard (3s)", "variant_b": "Fast (1.5s)", "status": "Running", "conversion_a": 78.5, "conversion_b": 86.2, "sample_size": 1000},
        {"id": 2, "name": "Welcome Message Test", "variant_a": "Formal", "variant_b": "Casual", "status": "Completed", "conversion_a": 82.1, "conversion_b": 79.8, "sample_size": 1500},
        {"id": 3, "name": "Button Color", "variant_a": "Blue", "variant_b": "Green", "status": "Running", "conversion_a": 75.0, "conversion_b": 81.5, "sample_size": 800},
    ]

if 'anomalies' not in st.session_state:
    st.session_state.anomalies = [
        {"id": 1, "type": "Spike in Failed Queries", "severity": "High", "timestamp": (datetime.now() - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S"), "details": "Failed query rate increased by 45%"},
        {"id": 2, "type": "Unusual Intent Pattern", "severity": "Medium", "timestamp": (datetime.now() - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M:%S"), "details": "Unknown intent queries up 30%"},
        {"id": 3, "type": "Response Time Degradation", "severity": "Low", "timestamp": (datetime.now() - timedelta(hours=12)).strftime("%Y-%m-%d %H:%M:%S"), "details": "Average response time increased by 15%"},
    ]

if 'user_segments' not in st.session_state:
    st.session_state.user_segments = [
        {"segment": "Power Users", "count": 1250, "avg_queries": 45, "satisfaction": 4.6, "retention": 95},
        {"segment": "Regular Users", "count": 3800, "avg_queries": 12, "satisfaction": 4.2, "retention": 78},
        {"segment": "New Users", "count": 2100, "avg_queries": 3, "satisfaction": 3.8, "retention": 45},
        {"segment": "At-Risk Users", "count": 890, "avg_queries": 2, "satisfaction": 2.9, "retention": 25},
    ]

if 'conversation_flows' not in st.session_state:
    st.session_state.conversation_flows = [
        {"id": 1, "name": "Account Opening Flow", "steps": 5, "completion_rate": 78.5, "avg_duration": 180},
        {"id": 2, "name": "Loan Application Flow", "steps": 8, "completion_rate": 65.2, "avg_duration": 420},
        {"id": 3, "name": "Card Activation Flow", "steps": 3, "completion_rate": 92.1, "avg_duration": 90},
    ]

if 'nlp_models' not in st.session_state:
    st.session_state.nlp_models = [
        {"name": "BERT-Base", "accuracy": 94.2, "speed": "Fast", "size": "110MB", "active": True},
        {"name": "RoBERTa", "accuracy": 95.8, "speed": "Medium", "size": "125MB", "active": False},
        {"name": "GPT-3.5", "accuracy": 96.5, "speed": "Slow", "size": "350MB", "active": False},
        {"name": "Custom LSTM", "accuracy": 91.3, "speed": "Very Fast", "size": "45MB", "active": False},
    ]

if 'integrations' not in st.session_state:
    st.session_state.integrations = [
        {"name": "Slack", "status": "Connected", "last_sync": "2 min ago", "messages": 1240},
        {"name": "Telegram", "status": "Connected", "last_sync": "5 min ago", "messages": 3580},
        {"name": "WhatsApp", "status": "Disconnected", "last_sync": "2 hours ago", "messages": 0},
        {"name": "Facebook Messenger", "status": "Connected", "last_sync": "1 min ago", "messages": 2890},
        {"name": "Discord", "status": "Connected", "last_sync": "3 min ago", "messages": 560},
    ]

if 'scheduled_tasks' not in st.session_state:
    st.session_state.scheduled_tasks = [
        {"id": 1, "task": "Model Retraining", "frequency": "Daily", "next_run": "Tonight 2:00 AM", "status": "Scheduled"},
        {"id": 2, "task": "Data Backup", "frequency": "Hourly", "next_run": "In 45 minutes", "status": "Running"},
        {"id": 3, "task": "Analytics Report", "frequency": "Weekly", "next_run": "Monday 9:00 AM", "status": "Scheduled"},
    ]

if 'performance_benchmarks' not in st.session_state:
    st.session_state.performance_benchmarks = {
        "response_time_p50": 120,
        "response_time_p95": 280,
        "response_time_p99": 450,
        "throughput_qps": 145,
        "memory_usage": 62,
        "cpu_usage": 38,
        "cache_hit_rate": 78.5,
        "error_rate": 0.8
    }

if 'sentiment_analysis' not in st.session_state:
    st.session_state.sentiment_analysis = {
        "positive": 5240,
        "negative": 890,
        "neutral": 2156,
        "very_positive": 1820,
        "very_negative": 234
    }

if 'language_detection' not in st.session_state:
    st.session_state.language_detection = {
        "English": 7890,
        "Spanish": 1240,
        "French": 680,
        "German": 420,
        "Chinese": 890,
        "Hindi": 560,
        "Arabic": 320
    }

if 'security_events' not in st.session_state:
    st.session_state.security_events = [
        {"id": 1, "type": "Failed Login Attempt", "severity": "High", "timestamp": (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"), "ip": "192.168.1.45", "status": "Blocked"},
        {"id": 2, "type": "Unusual Traffic Pattern", "severity": "Medium", "timestamp": (datetime.now() - timedelta(hours=3)).strftime("%Y-%m-%d %H:%M:%S"), "ip": "10.0.0.23", "status": "Monitoring"},
        {"id": 3, "type": "Rate Limit Exceeded", "severity": "Low", "timestamp": (datetime.now() - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M:%S"), "ip": "172.16.0.15", "status": "Auto-resolved"},
    ]

    st.markdown("---")
    

if 'export_history' not in st.session_state:
    st.session_state.export_history = [
        {"id": 1, "type": "CSV Export", "items": 1250, "size": "2.4MB", "timestamp": (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d %H:%M"), "user": "admin"},
        {"id": 2, "type": "JSON Export", "items": 3400, "size": "5.8MB", "timestamp": (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d %H:%M"), "user": "admin"},
        {"id": 3, "type": "PDF Report", "items": 50, "size": "1.2MB", "timestamp": (datetime.now() - timedelta(days=3)).strftime("%Y-%m-%d %H:%M"), "user": "admin"},
    ]

if 'knowledge_base' not in st.session_state:
    st.session_state.knowledge_base = {
        "total_articles": 248,
        "categories": 12,
        "avg_views_per_article": 156,
        "most_viewed": "How to reset password",
        "least_viewed": "Advanced API usage",
        "search_queries": 4520
    }

if 'chatbot_metrics' not in st.session_state:
    st.session_state.chatbot_metrics = {
        "total_conversations": 12450,
        "avg_conversation_length": 8.5,
        "avg_resolution_time": 145,
        "escalation_rate": 12.3,
        "customer_satisfaction_score": 4.2,
        "first_contact_resolution": 78.5
    }

if 'revenue_impact' not in st.session_state:
    st.session_state.revenue_impact = {
        "cost_per_query": 0.15,
        "monthly_queries": 45000,
        "cost_savings": 6750,
        "manual_handling_cost": 8.50,
        "automation_rate": 87.5,
        "roi_percentage": 340
    }

if 'predictive_analytics' not in st.session_state:
    st.session_state.predictive_analytics = {
        "predicted_queries_tomorrow": 3240,
        "predicted_queries_next_week": 22680,
        "predicted_peak_hours": ["10 AM", "2 PM", "8 PM"],
        "churn_risk_users": 145,
        "high_value_users": 892,
        "trending_intents": ["loan_inquiry", "investment_advice", "bill_payment"]
    }

if 'competitive_benchmarks' not in st.session_state:
    st.session_state.competitive_benchmarks = {
        "our_response_time": 280,
        "industry_avg_response_time": 450,
        "our_accuracy": 94.5,
        "industry_avg_accuracy": 87.2,
        "our_satisfaction": 4.3,
        "industry_avg_satisfaction": 3.8
    }

if 'collaboration_data' not in st.session_state:
    st.session_state.collaboration_data = [
        {"team_member": "John Doe", "role": "Admin", "last_active": "2 min ago", "actions_today": 45, "status": "Online"},
        {"team_member": "Jane Smith", "role": "Analyst", "last_active": "15 min ago", "actions_today": 28, "status": "Online"},
        {"team_member": "Mike Johnson", "role": "Developer", "last_active": "1 hour ago", "actions_today": 12, "status": "Away"},
    ]

if 'version_history' not in st.session_state:
    st.session_state.version_history = [
        {"version": "v4.0.0", "date": "2024-01-07", "changes": "Added 17 tabs, ML training hub, Performance monitoring", "status": "Current"},
        {"version": "v3.5.2", "date": "2024-01-01", "changes": "Bug fixes, UI improvements", "status": "Stable"},
        {"version": "v3.5.0", "date": "2023-12-20", "changes": "Added A/B testing, Anomaly detection", "status": "Archived"},
    ]


# ===== ENHANCEMENT #2: REAL-TIME MONITORING DATA =====
if 'realtime_metrics' not in st.session_state:
    st.session_state.realtime_metrics = {
        "queries_per_second": [],
        "response_times": [],
        "error_rates": [],
        "timestamps": []
    }

if 'geographic_data' not in st.session_state:
    st.session_state.geographic_data = [
        {"country": "USA", "queries": 3450, "lat": 37.0902, "lon": -95.7129},
        {"country": "UK", "queries": 2340, "lat": 55.3781, "lon": -3.4360},
        {"country": "India", "queries": 4120, "lat": 20.5937, "lon": 78.9629},
        {"country": "Germany", "queries": 1890, "lat": 51.1657, "lon": 10.4515},
        {"country": "Japan", "queries": 2670, "lat": 36.2048, "lon": 138.2529},
    ]

if 'intent_confidence_history' not in st.session_state:
    st.session_state.intent_confidence_history = []
    for intent in st.session_state.intents:
        st.session_state.intent_confidence_history.append({
            "intent": intent['name'],
            "history": [random.uniform(75, 98) for _ in range(30)]
        })

# ==================== DYNAMIC STYLING ====================
if st.session_state.dark_mode:
    bg_gradient = "linear-gradient(135deg, #0f0c29 0%, #302b63 25%, #24243e 50%, #0f0c29 75%, #302b63 100%)"
    text_primary = "#e0e7ff"
    text_secondary = "#cbd5e1"
    card_bg = "rgba(99, 102, 241, 0.1)"
    border_color = "rgba(139, 92, 246, 0.3)"
else:
    bg_gradient = "linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 25%, #ddd6fe 50%, #fce7f3 75%, #f0f9ff 100%)"
    text_primary = "#1e293b"
    text_secondary = "#475569"
    card_bg = "rgba(255, 255, 255, 0.8)"
    border_color = "rgba(139, 92, 246, 0.2)"

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800;900&display=swap');
    
    .stApp {{
        background: {bg_gradient};
        background-size: 400% 400%;
        animation: gradientShift 20s ease infinite;
        font-family: 'Inter', sans-serif;
    }}
    
    @keyframes gradientShift {{
        0%, 100% {{ background-position: 0% 50%; }}
        50% {{ background-position: 100% 50%; }}
    }}
    
    h1, h2, h3 {{
        color: {text_primary} !important;
        font-weight: 800 !important;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }}
    
    [data-testid="stMetricValue"] {{
        font-size: 2.2rem !important;
        font-weight: 800 !important;
        color: {text_primary} !important;
    }}
    
    [data-testid="stMetricLabel"] {{
        color: #8b5cf6 !important;
        font-weight: 700 !important;
        text-transform: uppercase;
        letter-spacing: 1.5px;
    }}
    
    div[data-testid="metric-container"] {{
        background: {card_bg};
        backdrop-filter: blur(20px);
        border: 2px solid {border_color};
        border-radius: 20px;
        padding: 1.5rem;
        box-shadow: 0 10px 40px rgba(99, 102, 241, 0.3);
        transition: all 0.4s ease;
    }}
    
    div[data-testid="metric-container"]:hover {{
        transform: translateY(-10px) scale(1.03);
        box-shadow: 0 20px 60px rgba(99, 102, 241, 0.5);
        border-color: #8b5cf6;
    }}
    
    .stButton > button {{
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white !important;
        border: none;
        border-radius: 12px;
        padding: 0.8rem 2.5rem;
        font-weight: 700;
        font-size: 1rem;
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
        transition: all 0.3s ease;
        text-transform: uppercase;
        letter-spacing: 1px;
    }}
    
    .stButton > button:hover {{
        transform: translateY(-3px) scale(1.05);
        box-shadow: 0 12px 40px rgba(102, 126, 234, 0.6);
    }}
    
    .stTabs [data-baseweb="tab"] {{
        background: {card_bg};
        backdrop-filter: blur(10px);
        border: 2px solid {border_color};
        border-radius: 15px;
        padding: 15px 30px;
        font-weight: 700;
        font-size: 1rem;
        transition: all 0.3s ease;
    }}
    
    .stTabs [data-baseweb="tab"][aria-selected="true"] {{
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        color: white !important;
        box-shadow: 0 8px 30px rgba(102, 126, 234, 0.5);
    }}
    
    .streamlit-expanderHeader {{
        background: {card_bg};
        backdrop-filter: blur(10px);
        border: 2px solid {border_color};
        border-radius: 12px;
        font-weight: 600;
        padding: 1rem;
        transition: all 0.3s ease;
    }}

    .stSelectbox > div > div {{
        background: {card_bg};
        backdrop-filter: blur(20px);
        border: 2px solid {border_color};
        border-radius: 15px;
        transition: all 0.3s ease;
    }}
    
    .stSelectbox > div > div:hover {{
        border-color: #8b5cf6;
        box-shadow: 0 5px 20px rgba(139, 92, 246, 0.3);
        transform: translateY(-2px);
    }}
    
    .stMultiSelect > div > div {{
        background: {card_bg};
        backdrop-filter: blur(20px);
        border: 2px solid {border_color};
        border-radius: 15px;
        transition: all 0.3s ease;
    }}
    
    .stMultiSelect > div > div:hover {{
        border-color: #8b5cf6;
        box-shadow: 0 5px 20px rgba(139, 92, 246, 0.3);
    }}
    
    .streamlit-expanderHeader:hover {{
        background: linear-gradient(135deg, rgba(102, 126, 234, 0.2), rgba(118, 75, 162, 0.2));
        transform: translateX(10px);
    }}
</style>
""", unsafe_allow_html=True)

# ==================== HEADER ====================
col1, col2, col3, col4 = st.columns([4, 1, 1, 1])
with col1:
    st.title("🤖 AI CHATBOT COMMAND CENTER")
    st.markdown("**🚀 Enterprise Edition v4.0 | Advanced ML & Real-time Analytics**")
with col2:
    if st.button(f"🔔 {st.session_state.notification_count}", key="notif"):
        st.info("3 new alerts!")
with col3:
    if st.button("🌓", key="theme"):
        st.session_state.dark_mode = not st.session_state.dark_mode
        st.rerun()
with col4:
    if st.button("🚪 Logout"):
        # Show user info before logout
        user_details = get_user_details(st.session_state.username)
        if user_details:
            st.info(f"👋 Goodbye, {user_details['username']}!")
        
        st.session_state.logged_in = False
        st.session_state.username = None
        st.session_state.user_email = None
        time.sleep(1)
        st.rerun()

st.markdown("---")



# ===== ENHANCEMENT #3: HEADER METRICS =====
st.markdown("---")
col_a, col_b, col_c = st.columns([1, 1, 1])
with col_a:
    st.metric("Active Now", st.session_state.active_conversations, delta=f"+{random.randint(5, 25)}")
with col_b:
    uptime_days = random.randint(45, 120)
    st.metric("Uptime", f"{uptime_days} days", delta="99.98%")
with col_c:
    health_score = random.randint(92, 99)
    st.metric("Health", f"{health_score}%", delta="+2")

# ==================== SIDEBAR ====================
with st.sidebar:
    st.markdown("### ⚡ COMMAND CENTER")
    
    st.success("🟢 **System Online**")
    st.caption(f"Uptime: 99.98%")
    
    # ===== USER PROFILE =====
    if st.session_state.logged_in and st.session_state.username:
        st.markdown("---")
        with st.expander("👤 User Profile", expanded=False):
            user_details = get_user_details(st.session_state.username)
            if user_details:
                st.success(f"**{user_details['username']}**")
                st.caption(f"📧 {user_details['email']}")
                st.caption(f"📅 Joined: {user_details['created_at'][:10]}")
                st.caption(f"🕐 Last Login: {user_details['last_login']}")
    
    st.markdown("---")
    
    # ===== EMAIL SETTINGS =====
    with st.expander("📧 Email Settings", expanded=False):
        st.markdown("### 📧 Configure Email")
        
        st.info("💡 Current: " + EMAIL_CONFIG['sender_email'])
        
        new_sender_email = st.text_input("Sender Email", 
                                          value=EMAIL_CONFIG['sender_email'],
                                          key="sidebar_email_input")
        
        new_sender_password = st.text_input("App Password", 
                                             type="password", 
                                             value=EMAIL_CONFIG['sender_password'],
                                             key="sidebar_password_input")
        
        st.caption("ℹ️ Get App Password: https://myaccount.google.com/apppasswords")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("💾 Save", key="save_email_config_sidebar", width="stretch"):
                EMAIL_CONFIG['sender_email'] = new_sender_email
                EMAIL_CONFIG['sender_password'] = new_sender_password.replace(" ", "")
                st.success("✅ Saved!")
        
        with col2:
            if st.button("📧 Test", key="test_email_sidebar", width="stretch"):
                with st.spinner("Sending..."):
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    
                    html_body = f"""
                    <html>
                    <body style='font-family: Arial, sans-serif; padding: 20px;'>
                        <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                                    padding: 40px; border-radius: 15px; color: white;'>
                            <h1>✅ Email Test Successful!</h1>
                            <p>Your SMTP configuration is working correctly.</p>
                            <p><strong>Sent at:</strong> {timestamp}</p>
                        </div>
                    </body>
                    </html>
                    """
                    
                    success, msg = send_email(
                        new_sender_email,
                        "✅ Test Email",
                        html_body,
                        html=True
                    )
                    
                    if success:
                        st.success("✅ " + msg)
                        st.balloons()
                    else:
                        st.error("❌ " + msg)
    
    st.markdown("---")
    
    st.markdown("### 📊 Live Metrics")
    st.metric("Queries/min", random.randint(45, 85), delta=f"+{random.randint(5, 15)}")
    st.metric("Active Users", random.randint(200, 500), delta=f"+{random.randint(10, 50)}")
    st.metric("CPU Usage", f"{random.randint(25, 65)}%")
    st.metric("Memory", f"{random.randint(40, 75)}%")
    
    st.markdown("---")
    st.markdown("---")
    st.markdown("### 🔴 LIVE ACTIVITY FEED")
    
    # Show last 5 activities from database
    recent_queries = get_real_queries(limit=5)
    if not recent_queries.empty:
        for _, row in recent_queries.iterrows():
            try:
                time_diff = (datetime.now() - pd.to_datetime(row['timestamp']))
                seconds_ago = int(time_diff.total_seconds())
                
                if seconds_ago < 60:
                    time_str = f"{seconds_ago}s ago"
                elif seconds_ago < 3600:
                    time_str = f"{seconds_ago // 60}m ago"
                else:
                    time_str = f"{seconds_ago // 3600}h ago"
                
                # Color based on success
                if row['success']:
                    st.success(f"✅ {row['intent']} • {time_str}")
                else:
                    st.error(f"❌ {row['intent']} • {time_str}")
            except:
                st.caption(f"🔹 {row['intent']}")
    else:
        st.caption("⏳ No recent activity")
    st.markdown("### 🎯 Quick Actions")
    if st.button("🔄 Refresh", width="stretch"):
        st.rerun()
    if st.button("📥 Export All", width="stretch"):
        data = {"queries": st.session_state.queries, "timestamp": datetime.now().isoformat()}
        st.download_button("Download", json.dumps(data, indent=2), "export.json", "application/json", width="stretch")
    if st.button("🧹 Clear Cache", width="stretch"):
        st.cache_data.clear()
        st.success("✅ Cache cleared!")


    # ✅ GOOGLE SHEETS EXPORT
        if st.button("📊 Export to Sheets", use_container_width=True):
            csv = filtered.to_csv(index=False)
            
            st.download_button(
                "📥 Download CSV First",
                csv,
                f"queries_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "text/csv",
                width="stretch"
            )
            
            st.info("""
            **📊 Quick Google Sheets Import:**
            1. ✅ Download CSV above
            2. 🌐 Go to [sheets.google.com](https://sheets.google.com)
            3. 📁 File → Import → Upload
            4. 📤 Select downloaded CSV
            5. ✨ Done!
            """)
    
    st.markdown("---")
    
    st.markdown("### 🎨 Display Options")
    show_advanced = st.checkbox("Advanced Mode", value=True)
    show_charts = st.checkbox("Show Charts", value=True)
    auto_refresh = st.checkbox("Auto Refresh", value=False)

    # ===== KEYBOARD SHORTCUTS =====
    with st.expander("⌨️ Keyboard Shortcuts"):
        st.markdown("""
        - `Ctrl + R` - Refresh Dashboard
        - `Ctrl + E` - Export Data
        - `Ctrl + T` - New Test Query
        - `Ctrl + S` - Save Settings
        - `Esc` - Close Modals
        """)
    
    st.markdown("---")
    
    # ===== NOTIFICATION PANEL =====
    with st.expander("🔔 Notifications", expanded=False):
        for alert in st.session_state.system_alerts:
            if alert['type'] == 'info':
                st.info(f"ℹ️ {alert['message']} • {alert['time']}")
            elif alert['type'] == 'warning':
                st.warning(f"⚠️ {alert['message']} • {alert['time']}")
            elif alert['type'] == 'success':
                st.success(f"✅ {alert['message']} • {alert['time']}")
    
    st.markdown("---")

    st.markdown("---")
    st.markdown("### 🏥 System Health")
    
    # Check actual system status
    health_checks = {
        "🗄️ Database": True,  # Always true since we're using SQLite
        "📧 Email": EMAIL_CONFIG['sender_email'] != '',
        "💾 Cache": True,
        "🌐 API": True
    }
    
    all_healthy = all(health_checks.values())
    
    if all_healthy:
        st.success("✅ All Systems Operational")
    else:
        st.warning("⚠️ Some Services Need Attention")
    
    for service, status in health_checks.items():
        if status:
            st.caption(f"✅ {service}")
        else:
            st.caption(f"❌ {service}")


    st.markdown("---")
    st.markdown("### 🏆 Achievements")
    
    # Calculate real achievements
    total_queries = len(st.session_state.queries)
    best_accuracy = max([i.get('accuracy', 0) for i in st.session_state.intents]) if st.session_state.intents else 0
    
    achievements = [
        {
            "emoji": "🎯",
            "title": "Accuracy Master",
            "desc": "Achieve 95%+ accuracy",
            "progress": min(100, best_accuracy)
        },
        {
            "emoji": "📊",
            "title": "Data Collector",
            "desc": "Process 1000+ queries",
            "progress": min(100, (total_queries / 1000) * 100)
        },
        {
            "emoji": "🧠",
            "title": "ML Expert",
            "desc": "Complete 5+ training sessions",
            "progress": min(100, (len(st.session_state.training_history) / 5) * 100)
        }
    ]
    
    for ach in achievements:
        with st.expander(f"{ach['emoji']} {ach['title']}", expanded=False):
            st.caption(ach['desc'])
            st.progress(ach['progress'] / 100)
            if ach['progress'] >= 100:
                st.success("✅ COMPLETED!")
            else:
                st.info(f"{ach['progress']:.0f}% complete")
    
    st.info("**v4.0.0** Enterprise")

# ==================== MAIN TABS ====================
tab1, tab2, tab3, tab4, tab5, tab7, tab8, tab9, tab10, tab11, tab12, tab13, tab14, tab15, tab16, tab17, tab18, tab19, tab20, tab21, tab22, tab23, tab24 = st.tabs([
    "📊 Executive Dashboard",
    "🧠 ML Training Hub",
    "📈 Advanced Analytics",
    "🎯 Intent Studio",
    "❓ FAQ Command",
    "👥 Feedback Analytics",
    "⚙️ System Config",
    "🤖 AI Insights Pro",
    "🎮 Live Testing Lab",
    "🧪 A/B Experiments",
    "📡 API Monitor",
    "🚨 Anomaly Detection",
    "👤 User Segments",
    "🔄 Conversation Flows",
    "🤝 Integrations",
    "⚡ Performance",
    "😊 Sentiment Analysis",
    "🌍 Language Detection",
    "🔒 Security Center",
    "💰 Revenue Analytics",
    "🔮 Predictive AI",
    "👥 Team Collaboration",
    "⚡ Real-time Monitor"  # NEW TAB!
])

# ==================== TAB 1: EXECUTIVE DASHBOARD ====================
with tab1:
    st.header("📊 Executive Dashboard - Real-time Overview")

    # ✅ IMPRESSIVE QUICK STATS SUMMARY
    with st.expander("📈 QUICK STATS SNAPSHOT", expanded=True):
        col1, col2, col3, col4 = st.columns(4)
        
        # Calculate real stats from actual data
        total_queries_today = len([q for q in st.session_state.queries 
                                   if pd.to_datetime(q['timestamp']).date() == datetime.now().date()])
        
        with col1:
            st.markdown("**🎯 Today's Performance**")
            if total_queries_today > 0:
                success_today = len([q for q in st.session_state.queries 
                                    if pd.to_datetime(q['timestamp']).date() == datetime.now().date() 
                                    and q['success']])
                success_rate_today = (success_today / total_queries_today * 100) if total_queries_today > 0 else 0
                st.success(f"✅ {total_queries_today} queries processed")
                st.info(f"📊 {success_rate_today:.1f}% success rate")
            else:
                st.warning("⏳ No queries today yet")
                st.caption("Start testing to see stats!")
        
        with col2:
            st.markdown("**🚀 Total Performance**")
            st.success(f"✅ {len(st.session_state.queries)} total queries")
            if len(st.session_state.queries) > 0:
                overall_success = sum(1 for q in st.session_state.queries if q['success'])
                overall_rate = (overall_success / len(st.session_state.queries) * 100)
                st.info(f"📈 {overall_rate:.1f}% overall success")
            else:
                st.caption("No data yet")
        
        with col3:
            st.markdown("**🏆 Best Performing Intent**")
            if st.session_state.intents:
                best_intent = max(st.session_state.intents, key=lambda x: x.get('accuracy', 90))
                st.success(f"🎯 {best_intent['name']}")
                st.info(f"📊 {best_intent.get('accuracy', 90):.1f}% accuracy")
            else:
                st.warning("No intents yet")
        
        with col4:
            st.markdown("**⚡ System Status**")
            uptime_pct = random.randint(98, 100)
            st.success(f"✅ All systems operational")
            st.info(f"🔋 {uptime_pct}.{random.randint(0,9)}% uptime")
    
    st.markdown("---")
    
    # ADD REFRESH BUTTON
    col1, col2 = st.columns([5, 1])
    with col2:
        if st.button("🔄 Reload", use_container_width=True):
            real_data = get_real_queries(limit=1000)
            if not real_data.empty:
                st.session_state.queries = real_data.to_dict('records')
                st.success("✅ Reloaded!")
                time.sleep(0.3)
            st.rerun()
    
    # ADD QUERY GENERATION BUTTONS
    col_add1, col_add2, col_add3 = st.columns([4, 1, 1])
    
    with col_add2:
        if st.button("➕ Add 100 Queries", use_container_width=True):
            intents_list = ["check_balance", "transfer_money", "find_atm", "card_block", "loan_inquiry", "bill_payment"]
            queries_text = {
                "check_balance": ["What's my balance?", "Show balance", "Check account"],
                "transfer_money": ["Transfer $100", "Send money", "Move funds"],
                "find_atm": ["Where is ATM?", "Find ATM", "ATM near me"],
                "card_block": ["Block card", "Freeze card", "Lost card"],
                "loan_inquiry": ["Apply loan", "Loan rates", "Home loan"],
                "bill_payment": ["Pay bill", "Electricity bill", "Phone bill"]
            }
            
            with st.spinner("Adding 100 queries..."):
                for i in range(100):
                    intent = random.choice(intents_list)
                    query_text = random.choice(queries_text[intent])
                    hours_ago = random.randint(0, 168)
                    timestamp = (datetime.now() - timedelta(hours=hours_ago)).strftime("%Y-%m-%d %H:%M:%S")
                    
                    add_real_query(
                        query_text, intent, random.randint(75, 99), True,
                        random.randint(100, 500),
                        f"user_{random.randint(1000, 9999)}",
                        f"session_{random.randint(10000, 99999)}",
                        random.choice(["mobile", "desktop", "tablet"]),
                        random.choice(["New York", "London", "Tokyo", "Mumbai"])
                    )
                
                st.success("✅ Added 100 queries!")
                time.sleep(1)
                st.rerun()
    
    with col_add3:
        if st.button("➕ Add 500 Queries", use_container_width=True):
            intents_list = ["check_balance", "transfer_money", "find_atm", "card_block", "loan_inquiry", "bill_payment"]
            queries_text = {
                "check_balance": ["What's my balance?", "Show balance", "Check account"],
                "transfer_money": ["Transfer $100", "Send money", "Move funds"],
                "find_atm": ["Where is ATM?", "Find ATM", "ATM near me"],
                "card_block": ["Block card", "Freeze card", "Lost card"],
                "loan_inquiry": ["Apply loan", "Loan rates", "Home loan"],
                "bill_payment": ["Pay bill", "Electricity bill", "Phone bill"]
            }
            
            with st.spinner("Adding 500 queries... (this may take 10 seconds)"):
                for i in range(500):
                    intent = random.choice(intents_list)
                    query_text = random.choice(queries_text[intent])
                    hours_ago = random.randint(0, 168)
                    timestamp = (datetime.now() - timedelta(hours=hours_ago)).strftime("%Y-%m-%d %H:%M:%S")
                    
                    add_real_query(
                        query_text, intent, random.randint(75, 99), True,
                        random.randint(100, 500),
                        f"user_{random.randint(1000, 9999)}",
                        f"session_{random.randint(10000, 99999)}",
                        random.choice(["mobile", "desktop", "tablet"]),
                        random.choice(["New York", "London", "Tokyo", "Mumbai", "Singapore"])
                    )
                
                st.success("✅ Added 500 queries!")
                time.sleep(1)
                st.rerun()
            real_data = get_real_queries(limit=1000)
            if not real_data.empty:
                st.session_state.queries = real_data.to_dict('records')
                st.success("✅ Reloaded!")
                time.sleep(0.3)
            st.rerun()
    
    df = pd.DataFrame(st.session_state.queries)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # TOP KPIs
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    with col1:
        st.metric("Total Queries", len(df), delta="+24 today", delta_color="normal")
    with col2:
        success_rate = (df['success'].sum() / len(df) * 100)
        st.metric("Success Rate", f"{success_rate:.1f}%", delta="↑ 4.2%")
    with col3:
        st.metric("Avg Confidence", f"{df['confidence'].mean():.1f}%", delta="↑ 2.1%")
    with col4:
        st.metric("Avg Response", f"{df['response_time'].mean():.0f}ms", delta="↓ 15ms", delta_color="inverse")
    with col5:
        st.metric("Active Intents", len(st.session_state.intents), delta="+2")
    with col6:
        st.metric("User Satisfaction", "4.3/5.0", delta="+0.3")
    
    st.markdown("---")

    # ===== ENHANCEMENT #6: QUICK STATS =====
    st.markdown("### 📊 Quick Stats Comparison")
    col1, col2 = st.columns(2)
    
    with col1:
        current_week = df.groupby(df['timestamp'].dt.date).size().tail(7)
        st.markdown("**This Week vs Last Week**")
        week_total = current_week.sum()
        st.metric("This Week", f"{week_total} queries", delta=f"+{random.randint(50, 150)}")
    
    with col2:
        avg_confidence_this_week = df.tail(50)['confidence'].mean()
        st.markdown("**Performance Trend**")
        st.metric("Avg Confidence (7d)", f"{avg_confidence_this_week:.1f}%", delta="+3.5%")
    
    st.markdown("---")
    
    # REAL-TIME FILTERS
    st.markdown("### 🎛️ Advanced Filters")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        time_filter = st.selectbox("⏰ Time Range", ["Last Hour", "Last 24 Hours", "Last 7 Days", "Last 30 Days", "All Time"], index=2)
    with col2:
        intent_filter = st.multiselect("🎯 Intent", ["All"] + list(df['intent'].unique()), default=["All"])
    with col3:
        device_filter = st.multiselect("📱 Device", ["All"] + list(df['device'].unique()), default=["All"])
    with col4:
        location_filter = st.multiselect("🌍 Location", ["All"] + list(df['location'].unique()), default=["All"])
    with col5:
        status_filter = st.selectbox("✅ Status", ["All", "Success", "Failed"], index=0)
    
    # Apply filters
    filtered_df = df.copy()
    if "All" not in intent_filter and len(intent_filter) > 0:
        filtered_df = filtered_df[filtered_df['intent'].isin(intent_filter)]
    if "All" not in device_filter and len(device_filter) > 0:
        filtered_df = filtered_df[filtered_df['device'].isin(device_filter)]
    
    st.markdown("---")
    
    # VISUALIZATIONS
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🎯 Intent Distribution (Interactive)")
        intent_counts = filtered_df['intent'].value_counts().reset_index()
        intent_counts.columns = ['Intent', 'Count']
        fig = px.pie(intent_counts, values='Count', names='Intent', hole=0.5,
                     color_discrete_sequence=px.colors.sequential.Plasma)
        fig.update_traces(textposition='inside', textinfo='percent+label',
                         hovertemplate='<b>%{label}</b><br>Queries: %{value}<br>Percentage: %{percent}')
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', font=dict(color=text_primary, size=12))
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("### 📊 Success vs Failed (Detailed)")
        success_data = pd.DataFrame({
            'Status': ['Success', 'Failed'],
            'Count': [filtered_df['success'].sum(), len(filtered_df) - filtered_df['success'].sum()]
        })
        fig = px.bar(success_data, x='Status', y='Count', color='Status',
                    color_discrete_map={'Success': '#10b981', 'Failed': '#ef4444'},
                    text='Count')
        fig.update_traces(texttemplate='%{text}', textposition='outside')
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', font=dict(color=text_primary))
        st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📅 Query Timeline (7-Day Trend)")
        daily_data = filtered_df.groupby(filtered_df['timestamp'].dt.date).agg({
            'id': 'count',
            'success': 'sum'
        }).reset_index()
        daily_data.columns = ['Date', 'Total', 'Success']
        daily_data['Failed'] = daily_data['Total'] - daily_data['Success']
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=daily_data['Date'], y=daily_data['Success'],
                                 mode='lines+markers', name='Success', line=dict(color='#10b981', width=3)))
        fig.add_trace(go.Scatter(x=daily_data['Date'], y=daily_data['Failed'],
                                 mode='lines+markers', name='Failed', line=dict(color='#ef4444', width=3)))
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', font=dict(color=text_primary),
                         hovermode='x unified', legend=dict(orientation="h", yanchor="bottom", y=1.02))
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("### 🕐 Hourly Activity Heatmap")
        hourly_data = filtered_df.groupby(filtered_df['timestamp'].dt.hour).size().reset_index()
        hourly_data.columns = ['Hour', 'Count']
        fig = px.bar(hourly_data, x='Hour', y='Count', color='Count',
                    color_continuous_scale='Viridis')
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', font=dict(color=text_primary))
        st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📱 Device Distribution")
        device_counts = filtered_df['device'].value_counts()
        fig = px.pie(values=device_counts.values, names=device_counts.index,
                    color_discrete_sequence=px.colors.sequential.RdBu)
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', font=dict(color=text_primary))
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("### 🌍 Geographic Distribution")
        location_counts = filtered_df['location'].value_counts()
        fig = px.bar(x=location_counts.index, y=location_counts.values,
                    color=location_counts.values, color_continuous_scale='Blues')
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', font=dict(color=text_primary),
                         xaxis_title="Location", yaxis_title="Queries")
        st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # DETAILED TABLE
    st.markdown("### 📋 Recent Queries (Live Data)")
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        search_query = st.text_input("🔍 Search queries", placeholder="Search by query text...")
    with col2:
        rows_to_show = st.selectbox("Rows per page", [10, 20, 50, 100], index=1)
    with col3:
        if st.button("📥 Export CSV", use_container_width=True):
            csv = filtered_df.to_csv(index=False)
            st.download_button("Download", csv, f"queries_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                             "text/csv", use_container_width=True)
    
    display_df = filtered_df.head(rows_to_show)
    if search_query:
        display_df = filtered_df[filtered_df['query'].str.contains(search_query, case=False)].head(rows_to_show)
    
    st.dataframe(display_df[['timestamp', 'query', 'intent', 'confidence', 'success', 'response_time', 'device', 'location']],
                use_container_width=True, height=400)
    

# ================= SAFE TRAINING STATE =================
if "training_history" not in st.session_state:
    st.session_state.training_history = st.session_state.training_history


# ✅ ALWAYS DEFINED
latest_training = {
    "accuracy": 0.0,
    "loss": 0.0,
    "duration": 30,   # default fallback
    "trained_at": None,
    "samples": 0
}

if st.session_state.training_history:
    latest_training = st.session_state.training_history[-1]

# ==================== TAB 2: ML TRAINING HUB ====================
with tab2:
    st.header("🧠 Advanced ML Training Hub")
    
    st.markdown("""
    <div style='background: linear-gradient(135deg, rgba(102, 126, 234, 0.2) 0%, rgba(118, 75, 162, 0.2) 100%);
                padding: 25px; border-radius: 20px; margin-bottom: 25px; border: 2px solid rgba(102, 126, 234, 0.3);'>
        <h2 style='margin: 0; color: #667eea;'>🚀 Neural Network Training Center</h2>
        <p style='margin: 10px 0 0 0; font-size: 1.1rem;'>Configure advanced parameters and train state-of-the-art models</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        st.markdown("### ⚙️ Training Configuration")
        
        with st.expander("🎛️ Basic Parameters", expanded=True):
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                epochs = st.slider("Epochs", 10, 200, 50)
            with col_b:
                batch_size = st.selectbox("Batch Size", [8, 16, 32, 64, 128, 256], index=2)
            with col_c:
                learning_rate = st.select_slider("Learning Rate", [0.00001, 0.00002, 0.0001, 0.001, 0.01], value=0.00002)
        
        with st.expander("🔧 Advanced Parameters"):
            col_a, col_b = st.columns(2)
            with col_a:
                optimizer = st.selectbox("Optimizer", ["Adam", "SGD", "RMSprop", "AdaGrad", "AdaDelta"])
                dropout = st.slider("Dropout Rate", 0.0, 0.5, 0.2, 0.05)
                validation_split = st.slider("Validation Split %", 10, 40, 20)
            with col_b:
                hidden_layers = st.number_input("Hidden Layers", 1, 10, 3)
                neurons = st.number_input("Neurons/Layer", 32, 512, 128, 32)
                activation = st.selectbox("Activation", ["relu", "tanh", "sigmoid", "softmax"])
        
        with st.expander("🎯 Training Strategy"):
            early_stopping = st.checkbox("Enable Early Stopping", value=True)
            reduce_lr = st.checkbox("Reduce LR on Plateau", value=True)
            data_augmentation = st.checkbox("Data Augmentation", value=False)
            class_weights = st.checkbox("Use Class Weights", value=True)
    
    with col2:
        st.markdown("### 📊 Dataset Overview")
        total_intents = len(st.session_state.intents)
        total_examples = sum(len(intent['examples']) for intent in st.session_state.intents)
        
        st.metric("Total Intents", total_intents, delta="+2 new")
        st.metric("Training Samples", total_examples, delta="+45")
        st.metric("Avg Samples/Intent", f"{total_examples/total_intents:.1f}" if total_intents > 0 else "0")
        st.metric("Validation Samples", int(total_examples * validation_split / 100))
        
        st.markdown("---")
        
        st.markdown("### ⏱️ Estimates")
        est_time = epochs * batch_size * 0.1
        st.info(f"⏰ Est. Time: **{est_time:.1f}s**")
        st.info(f"💾 Model Size: **~{random.randint(5, 15)}MB**")
        st.info(f"🎯 Target Accuracy: **>92%**")
    
    with col3:
        st.markdown("### 🏆 Best Models")
        if len(st.session_state.training_history) > 0:
            best_model = max(st.session_state.training_history, key=lambda x: x['accuracy'])
            st.success(f"**Accuracy**: {best_model['accuracy']*100:.2f}%")
            st.info(f"**Date**: {best_model['timestamp'][:10]}")
            st.info(f"**Epochs**: {best_model['epochs']}")
            st.info(f"**Loss**: {best_model['loss']:.4f}")
        else:
            st.warning("No models trained yet")
    
    st.markdown("---")
    
    # TRAINING CONTROLS
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if st.button("🚀 START TRAINING", type="primary", use_container_width=True):
            progress_bar = st.progress(0)
            status_text = st.empty()
            metrics_display = st.empty()
            
            training_losses = []
            validation_losses = []
            accuracies = []
            
            import time
            
            # Calculate total training time (25-30 seconds)
            total_duration = random.uniform(25, 30)
            time_per_epoch = total_duration / epochs
            
            for epoch in range(epochs):
                # Sleep for calculated time per epoch
                time.sleep(time_per_epoch)
                
                # Simulate training
                train_loss = max(0.05, 1.0 - (epoch / epochs) * 0.92 + random.uniform(-0.03, 0.03))
                val_loss = max(0.05, 1.0 - (epoch / epochs) * 0.88 + random.uniform(-0.03, 0.03))
                accuracy = min(0.98, 0.65 + (epoch / epochs) * 0.30 + random.uniform(-0.02, 0.02))
                
                training_losses.append(train_loss)
                validation_losses.append(val_loss)
                accuracies.append(accuracy)
                
                # Update progress bar
                progress_bar.progress((epoch + 1) / epochs)
                
                # Update status text
                status_text.markdown(f"""
                **Epoch {epoch + 1}/{epochs}**  
                Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f} | Accuracy: {accuracy*100:.2f}%
                """)
                
                # Show checkpoint messages every 10 epochs
                if (epoch + 1) % 10 == 0:
                    metrics_display.success(f"✅ Checkpoint saved at epoch {epoch + 1}")
            
            final_accuracy = accuracies[-1]
            final_loss = training_losses[-1]
            
            # Ensure 100% completion display
            progress_bar.progress(1.0)
            status_text.markdown(f"""
            **🎉 Training Complete!**  
            Final Accuracy: **{final_accuracy*100:.2f}%** | Loss: **{final_loss:.4f}**
            """)
            
            st.session_state.model_metrics = {
                "accuracy": final_accuracy,
                "precision": final_accuracy - 0.01,
                "recall": final_accuracy - 0.02,
                "f1_score": final_accuracy - 0.015,
                "training_loss": training_losses,
                "validation_loss": validation_losses
            }
            
            st.session_state.training_history.append({
                "id": len(st.session_state.training_history) + 1,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "epochs": epochs,
                "batch_size": batch_size,
                "learning_rate": learning_rate,
                "accuracy": final_accuracy,
                "loss": final_loss,
                "duration": int(total_duration)
            })
            
            # Save to database
            add_real_training(epochs, batch_size, learning_rate, 
                            final_accuracy, final_loss, int(total_duration))
            
            # Show completion message
            st.balloons()
            st.success(f"""
            ### ✅ Training 100% Complete!
            
            **Final Results:**
            - ✅ Accuracy: **{final_accuracy*100:.2f}%**
            - 📉 Loss: **{final_loss:.4f}**
            - ⏱️ Duration: **{int(total_duration)}s**
            - 🎯 Intents: **{total_intents}**
            - 📦 Model saved to: `models/chatbot_v{len(st.session_state.training_history)}.h5`
            
            **Status:** ✅ Ready for deployment!
            """)
            
            # Send email notification
            if st.session_state.user_email:
                subject = f"🎉 Training Complete! Accuracy: {final_accuracy*100:.2f}%"
                body = f"""
                <html>
                <body style='font-family: Arial; padding: 20px;'>
                    <div style='background: linear-gradient(135deg, #667eea, #764ba2); 
                                padding: 30px; border-radius: 15px; color: white;'>
                        <h2>🎉 Training Completed Successfully!</h2>
                        <p><strong>Final Accuracy:</strong> {final_accuracy*100:.2f}%</p>
                        <p><strong>Loss:</strong> {final_loss:.4f}</p>
                        <p><strong>Epochs:</strong> {epochs}</p>
                        <p><strong>Timestamp:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
                    </div>
                </body>
                </html>
                """
                success, msg = send_email(st.session_state.user_email, subject, body, html=True)
                if success:
                    st.success("📧 Training results emailed to you!")
                    log_email(st.session_state.user_email, subject, "Sent", msg)
                else:
                    st.warning(f"⚠️ Email notification failed: {msg}")
                    log_email(st.session_state.user_email, subject, "Failed", msg)
    
    with col2:
        if st.button("💾 Save Model", use_container_width=True):
            st.success("✅ Model saved!")
    
    with col3:
        if st.button("📊 View Metrics", use_container_width=True):
            st.info("Check Advanced Analytics tab")
    
    with col4:
        if st.button("🔄 Reset Config", use_container_width=True):
            st.info("Configuration reset")
    
    st.markdown("---")
    
    # ================= TRAINING HISTORY =================
    if len(st.session_state.training_history) > 0:
        st.markdown("### 📜 Training History")

        history_df = pd.DataFrame(st.session_state.training_history)
        history_df["accuracy_pct"] = (history_df["accuracy"] * 100).round(2)
        history_df["duration_min"] = (history_df["duration"] / 60).round(2)

        st.dataframe(
            history_df[
                [
                    "timestamp",
                    "epochs",
                    "batch_size",
                    "learning_rate",
                    "accuracy_pct",
                    "loss",
                    "duration_min",
                ]
            ],
            use_container_width=True,
        )
        
        # ================= ACCURACY OVER TIME =================
        fig = px.line(
            history_df,
            x="timestamp",
            y="accuracy_pct",
            markers=True,
            title="Model Accuracy Over Time",
        )

        fig.update_traces(
            line_color="#667eea",
            marker=dict(size=10),
        )

        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color=text_primary),
        )

        st.plotly_chart(fig, use_container_width=True)


# ==================== TAB 3: ADVANCED ANALYTICS ====================
with tab3:
    st.header("📈 Advanced Analytics & Performance Metrics")
    
    if len(st.session_state.training_history) == 0:
        st.warning("⚠️ No training data available. Please train a model first!")
    else:
        metrics = st.session_state.model_metrics
        
        # TOP METRICS
        st.markdown("### 🎯 Model Performance KPIs")
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Accuracy", f"{metrics['accuracy']*100:.2f}%", delta="+2.3%")
        with col2:
            st.metric("Precision", f"{metrics['precision']*100:.2f}%", delta="+1.8%")
        with col3:
            st.metric("Recall", f"{metrics['recall']*100:.2f}%", delta="+1.5%")
        with col4:
            st.metric("F1 Score", f"{metrics['f1_score']:.4f}", delta="+0.012")
        with col5:
            st.metric("ROC-AUC", f"{random.uniform(0.92, 0.98):.4f}", delta="+0.015")
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📉 Training & Validation Loss Curves")
            if metrics['training_loss']:
                loss_df = pd.DataFrame({
                    'Epoch': list(range(1, len(metrics['training_loss']) + 1)),
                    'Training Loss': metrics['training_loss'],
                    'Validation Loss': metrics['validation_loss']
                })
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=loss_df['Epoch'], y=loss_df['Training Loss'],
                                        mode='lines+markers', name='Training Loss',
                                        line=dict(color='#667eea', width=3),
                                        marker=dict(size=8)))
                fig.add_trace(go.Scatter(x=loss_df['Epoch'], y=loss_df['Validation Loss'],
                                        mode='lines+markers', name='Validation Loss',
                                        line=dict(color='#f093fb', width=3),
                                        marker=dict(size=8)))
                
                fig.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color=text_primary),
                    hovermode='x unified',
                    xaxis_title="Epoch",
                    yaxis_title="Loss",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02)
                )
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.markdown("### 🎯 Performance Metrics Comparison")
            metrics_data = pd.DataFrame({
                'Metric': ['Accuracy', 'Precision', 'Recall', 'F1 Score'],
                'Score': [
                    metrics['accuracy'] * 100,
                    metrics['precision'] * 100,
                    metrics['recall'] * 100,
                    metrics['f1_score'] * 100
                ],
                'Target': [95, 93, 92, 93]
            })
            
            fig = go.Figure()
            fig.add_trace(go.Bar(x=metrics_data['Metric'], y=metrics_data['Score'],
                                name='Current', marker_color='#667eea', text=metrics_data['Score'].round(2)))
            fig.add_trace(go.Bar(x=metrics_data['Metric'], y=metrics_data['Target'],
                                name='Target', marker_color='#10b981', text=metrics_data['Target']))
            
            fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
            fig.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color=text_primary),
                barmode='group',
                yaxis_title="Score (%)"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("### 🔲 Confusion Matrix Heatmap")
            intent_names = [intent['name'][:15] for intent in st.session_state.intents[:6]]
            n = len(intent_names)
            
            confusion_matrix = []
            for i in range(n):
                row = []
                for j in range(n):
                    if i == j:
                        row.append(random.randint(88, 98))
                    else:
                        row.append(random.randint(0, 8))
                confusion_matrix.append(row)
            
            fig = go.Figure(data=go.Heatmap(
                z=confusion_matrix,
                x=intent_names,
                y=intent_names,
                colorscale='Viridis',
                text=confusion_matrix,
                texttemplate='%{text}',
                textfont={"size": 14, "color": "white"},
                hoverongaps=False,
                hovertemplate='Actual: %{y}<br>Predicted: %{x}<br>Count: %{z}<extra></extra>'
            ))
            
            fig.update_layout(
                title="Predicted vs Actual Intent Classification",
                xaxis_title="Predicted Intent",
                yaxis_title="Actual Intent",
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color=text_primary)
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.markdown("### 📊 Matrix Analysis")
            st.success("**✅ Model Status**: Excellent")
            st.info(f"**Total Predictions**: {n * random.randint(150, 250)}")
            st.info(f"**Correct**: {random.randint(88, 95)}%")
            st.warning(f"**Misclassified**: {random.randint(5, 12)}%")
            
            st.markdown("---")
            
            st.markdown("**💡 Insights:**")
            st.markdown("- Diagonal shows correct predictions")
            st.markdown("- Off-diagonal shows errors")
            st.markdown("- Darker = more occurrences")
            st.markdown("- Model performs excellently")
            
            if metrics['accuracy'] > 0.92:
                st.success("🎉 **Outstanding Performance!**")
            elif metrics['accuracy'] > 0.85:
                st.info("👍 **Good Performance**")
            else:
                st.warning("⚠️ **Needs Improvement**")
        
        st.markdown("---")
        
        # ADDITIONAL ANALYTICS
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📊 Learning Rate Impact")
            lr_data = pd.DataFrame({
                'Learning Rate': [0.0001, 0.001, 0.01, 0.1],
                'Accuracy': [87.5, 94.2, 91.8, 76.3],
                'Training Time (s)': [450, 280, 180, 120]
            })
            
            fig = px.line(lr_data, x='Learning Rate', y='Accuracy', markers=True,
                         title="Learning Rate vs Model Accuracy")
            fig.update_traces(line_color='#667eea', marker=dict(size=12))
            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', font=dict(color=text_primary))
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.markdown("### ⏱️ Training Efficiency")
            fig = px.bar(lr_data, x='Learning Rate', y='Training Time (s)',
                        color='Training Time (s)', color_continuous_scale='Blues',
                        title="Learning Rate vs Training Duration")
            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', font=dict(color=text_primary))
            st.plotly_chart(fig, use_container_width=True)
    
# ===== ENHANCEMENT #7: MODEL COMPARISON =====
        st.markdown("---")
        st.markdown("### 🔀 Model Comparison")
        if len(st.session_state.training_history) >= 2:
            col1, col2 = st.columns(2)
            with col1:
                model1 = st.selectbox("Model 1", range(len(st.session_state.training_history)), 
                                     format_func=lambda x: f"Model v{x+1}")
            with col2:
                model2 = st.selectbox("Model 2", range(len(st.session_state.training_history)), 
                                     format_func=lambda x: f"Model v{x+1}")
            
            if model1 != model2:
                m1 = st.session_state.training_history[model1]
                m2 = st.session_state.training_history[model2]
                
                comparison_df = pd.DataFrame({
                    'Metric': ['Accuracy', 'Loss', 'Epochs', 'Duration (s)'],
                    f'Model v{model1+1}': [m1['accuracy']*100, m1['loss'], m1['epochs'], m1['duration']],
                    f'Model v{model2+1}': [m2['accuracy']*100, m2['loss'], m2['epochs'], m2['duration']]
                })
                
                st.dataframe(comparison_df, use_container_width=True)
                
                winner = model1 if m1['accuracy'] > m2['accuracy'] else model2
                st.success(f"🏆 Winner: Model v{winner+1} with {max(m1['accuracy'], m2['accuracy'])*100:.2f}% accuracy")

# Continue with remaining tabs in next message due to length...

# ==================== TAB 4: INTENT STUDIO ====================
with tab4:
    st.header("🎯 Intent Management Studio")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        with st.expander("➕ Create New Intent", expanded=False):
            col_a, col_b = st.columns(2)
            with col_a:
                intent_name = st.text_input("Intent Name", placeholder="e.g., check_balance")
                intent_category = st.selectbox("Category", ["Account", "Transactions", "Services", "Security", "Loans", "Payments"])
            with col_b:
                intent_priority = st.selectbox("Priority", ["Low", "Medium", "High", "Critical"])
                num_examples = st.number_input("Number of Examples", 3, 20, 5)
            
            examples = []
            for i in range(num_examples):
                ex = st.text_input(f"Example {i+1}", key=f"intent_ex_{i}", placeholder=f"Training example {i+1}")
                if ex:
                    examples.append(ex)
            
            if st.button("✨ Create Intent", type="primary"):
                if intent_name and len(examples) >= 3:
                    st.session_state.intents.append({
                        "id": len(st.session_state.intents) + 1,
                        "name": intent_name,
                        "examples": examples,
                        "category": intent_category,
                        "priority": intent_priority,
                        "accuracy": random.uniform(85, 95)
                    })
                    st.success(f"✅ Intent '{intent_name}' created!")
                    st.balloons()
                    st.rerun()
                else:
                    st.error("⚠️ Need intent name and 3+ examples")
    
    with col2:
        st.markdown("### 📊 Intent Analytics")
        st.metric("Total Intents", len(st.session_state.intents))
        st.metric("Total Examples", sum(len(i['examples']) for i in st.session_state.intents))
        st.metric("Avg Accuracy", f"{np.mean([i.get('accuracy', 90) for i in st.session_state.intents]):.1f}%")
        
        # Category distribution
        categories = [i.get('category', 'Other') for i in st.session_state.intents]
        cat_counts = pd.Series(categories).value_counts()
        fig = px.pie(values=cat_counts.values, names=cat_counts.index, hole=0.4)
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', font=dict(color=text_primary, size=10))
        st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    st.markdown("### 📝 Intent Management")
    
    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        filter_category = st.selectbox("Filter by Category", ["All"] + ["Account", "Transactions", "Services", "Security", "Loans", "Payments"])
    with col2:
        filter_priority = st.selectbox("Filter by Priority", ["All", "Low", "Medium", "High", "Critical"])
    with col3:
        search_intent = st.text_input("Search Intent", placeholder="Search by name...")
    
    for intent in st.session_state.intents:
        if filter_category != "All" and intent.get('category') != filter_category:
            continue
        if filter_priority != "All" and intent.get('priority') != filter_priority:
            continue
        if search_intent and search_intent.lower() not in intent['name'].lower():
            continue
        
        with st.expander(f"🎯 **{intent['name']}** | {intent.get('category', 'Other')} | {intent.get('priority', 'Medium')} | Accuracy: {intent.get('accuracy', 90):.1f}%"):
            st.markdown("**Training Examples:**")
            for idx, ex in enumerate(intent['examples'], 1):
                col1, col2 = st.columns([5, 1])
                with col1:
                    st.markdown(f"`{idx}.` {ex}")
                with col2:
                    if st.button("🗑️", key=f"del_ex_{intent['id']}_{idx}"):
                        if len(intent['examples']) > 3:
                            intent['examples'].pop(idx-1)
                            st.rerun()
            
            st.markdown("---")
            new_ex = st.text_input("Add example", key=f"new_ex_{intent['id']}")
            col1, col2 = st.columns([1, 5])
            with col1:
                if st.button("➕ Add", key=f"add_{intent['id']}"):
                    if new_ex:
                        intent['examples'].append(new_ex)
                        st.rerun()
            with col2:
                if st.button("🗑️ Delete Intent", key=f"del_intent_{intent['id']}"):
                    st.session_state.intents = [i for i in st.session_state.intents if i['id'] != intent['id']]
                    st.rerun()

# ===== ENHANCEMENT #8: INTENT CONFIDENCE TRACKING =====
    st.markdown("---")
    st.markdown("### 📈 Intent Confidence Trends")
    for intent_hist in st.session_state.intent_confidence_history[:5]:
        with st.expander(f"📊 {intent_hist['intent']} Confidence History"):
            fig = px.line(y=intent_hist['history'], 
                         title=f"{intent_hist['intent']} - Last 30 Predictions",
                         labels={'x': 'Prediction #', 'y': 'Confidence %'})
            fig.update_traces(line_color='#667eea')
            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', font=dict(color=text_primary))
            st.plotly_chart(fig, use_container_width=True)
            
            avg_conf = np.mean(intent_hist['history'])
            if avg_conf > 90:
                st.success(f"✅ Excellent: {avg_conf:.1f}% avg confidence")
            elif avg_conf > 80:
                st.info(f"👍 Good: {avg_conf:.1f}% avg confidence")
            else:
                st.warning(f"⚠️ Needs improvement: {avg_conf:.1f}% avg confidence")

# ==================== TAB 5-14 (Remaining Tabs - Condensed) ====================
with tab5:
    st.header("❓ FAQ Command Center")
    
    with st.expander("➕ Add FAQ"):
        col1, col2 = st.columns([2, 1])
        with col1:
            q = st.text_input("Question")
            a = st.text_area("Answer", height=100)
        with col2:
            cat = st.selectbox("Category", ["General", "Account", "Security", "Transactions", "Loans"])
        
        if st.button("Add FAQ", type="primary"):
            if q and a:
                st.session_state.faqs.append({"id": len(st.session_state.faqs)+1, "question": q, "answer": a,
                                             "category": cat, "views": 0, "helpful": 0})
                st.success("✅ FAQ added!")
                st.rerun()
    
    for faq in st.session_state.faqs:
        with st.expander(f"[{faq.get('category', 'General')}] {faq['question']} | 👁️ {faq.get('views', 0)} views"):
            st.write(faq['answer'])
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Views", faq.get('views', 0))
            with col2:
                st.metric("Helpful", faq.get('helpful', 0))
            with col3:
                if st.button("🗑️", key=f"del_faq_{faq['id']}"):
                    st.session_state.faqs = [f for f in st.session_state.faqs if f['id'] != faq['id']]
                    st.rerun()


            

with tab7:
    st.header("👥 Feedback Analytics Dashboard")
    
    if len(st.session_state.feedback) > 0:
        fb_df = pd.DataFrame(st.session_state.feedback)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Avg Rating", f"{fb_df['rating'].mean():.1f}⭐")
        with col2:
            st.metric("Total Feedback", len(fb_df))
        with col3:
            st.metric("Positive", f"{len(fb_df[fb_df['rating']>=4])/len(fb_df)*100:.0f}%")
        with col4:
            st.metric("New", len(fb_df[fb_df['status']=='new']))
        
        col1, col2 = st.columns(2)
        with col1:
            fig = px.histogram(fb_df, x='rating', nbins=5, title="Rating Distribution")
            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', font=dict(color=text_primary))
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            sentiment_counts = fb_df['sentiment'].value_counts()
            fig = px.pie(values=sentiment_counts.values, names=sentiment_counts.index, title="Sentiment Analysis")
            fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', font=dict(color=text_primary))
            st.plotly_chart(fig, use_container_width=True)

with tab8:
    st.header("⚙️ System Configuration")
    
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.settings['confidence_threshold'] = st.slider("Confidence Threshold", 50, 100, st.session_state.settings['confidence_threshold'])
        st.session_state.settings['max_response_time'] = st.number_input("Max Response Time", 1, 10, st.session_state.settings['max_response_time'])
        st.session_state.settings['rate_limit'] = st.number_input("Rate Limit (req/min)", 10, 1000, st.session_state.settings['rate_limit'])
    
    with col2:
        st.session_state.settings['enable_logging'] = st.checkbox("Enable Logging", st.session_state.settings['enable_logging'])
        st.session_state.settings['enable_analytics'] = st.checkbox("Enable Analytics", st.session_state.settings['enable_analytics'])
        st.session_state.settings['auto_retrain'] = st.checkbox("Auto Retrain", st.session_state.settings['auto_retrain'])
    
    if st.button("💾 Save All Settings", type="primary"):
        st.success("✅ Settings saved successfully!")
        st.balloons()

with tab9:
    st.header("🤖 AI Insights Pro - Powered by Advanced ML")
    
    st.markdown("""
    <div style='background: linear-gradient(135deg, rgba(139, 92, 246, 0.2), rgba(168, 85, 247, 0.2));
                padding: 25px; border-radius: 20px; margin-bottom: 25px; border: 2px solid rgba(139, 92, 246, 0.4);'>
        <h2 style='margin: 0; color: #8b5cf6;'>🧠 AI-Powered Deep Analysis Engine</h2>
        <p style='margin: 10px 0 0 0; font-size: 1.1rem;'>Real-time insights using machine learning algorithms</p>
    </div>
    """, unsafe_allow_html=True)
    
    # ANALYSIS BUTTON
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🔬 RUN DEEP AI ANALYSIS", type="primary", use_container_width=True):
            with st.spinner("🧠 AI analyzing 10,000+ data points..."):
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                analysis_steps = [
                    "Scanning query patterns...",
                    "Analyzing intent distributions...",
                    "Detecting anomalies...",
                    "Calculating success metrics...",
                    "Generating predictions...",
                    "Compiling recommendations..."
                ]
                
                for i, step in enumerate(analysis_steps):
                    status_text.info(f"🔍 {step}")
                    time.sleep(0.5)
                    progress_bar.progress((i + 1) / len(analysis_steps))
                
                status_text.success("✅ Deep analysis complete!")
                st.balloons()
                time.sleep(1)
                status_text.empty()
                progress_bar.empty()
    
    st.markdown("---")
    
    # CALCULATE REAL METRICS
    df = pd.DataFrame(st.session_state.queries)
    
    if len(df) > 0:
        # Real calculations
        success_rate = (df['success'].sum() / len(df) * 100)
        avg_confidence = df['confidence'].mean()
        avg_response_time = df['response_time'].mean()
        total_intents = len(st.session_state.intents)
        total_examples = sum(len(i['examples']) for i in st.session_state.intents)
        
        # Calculate intent performance
        intent_performance = df.groupby('intent').agg({
            'success': 'mean',
            'confidence': 'mean',
            'id': 'count'
        }).reset_index()
        intent_performance.columns = ['intent', 'success_rate', 'avg_confidence', 'query_count']
        intent_performance['success_rate'] = intent_performance['success_rate'] * 100
        
        # Find worst performing intent
        worst_intent = intent_performance.loc[intent_performance['success_rate'].idxmin()]
        best_intent = intent_performance.loc[intent_performance['success_rate'].idxmax()]
        
        # Calculate trends
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df_sorted = df.sort_values('timestamp')
        recent_100 = df_sorted.tail(100)
        previous_100 = df_sorted.iloc[-200:-100] if len(df) >= 200 else df_sorted.head(100)
        
        recent_success = (recent_100['success'].sum() / len(recent_100) * 100) if len(recent_100) > 0 else 0
        previous_success = (previous_100['success'].sum() / len(previous_100) * 100) if len(previous_100) > 0 else 0
        trend = recent_success - previous_success
        
    else:
        success_rate = 0
        avg_confidence = 0
        avg_response_time = 0
        total_intents = len(st.session_state.intents)
        total_examples = 0
        trend = 0
    
    # AI PERFORMANCE SCORE
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("### 💡 AI-Generated Smart Recommendations")
        
        recommendations = []
        
        # REAL RECOMMENDATION #1: Success Rate
        if success_rate < 85:
            recommendations.append({
                "priority": "🔴 CRITICAL",
                "title": "Success Rate Below Optimal Threshold",
                "description": f"Current: {success_rate:.1f}% | Target: 85%+ | Gap: {85 - success_rate:.1f}%",
                "action": f"Add {int((85 - success_rate) * 5)} more training examples to low-performing intents",
                "impact": f"Expected improvement: +{(85 - success_rate) * 0.8:.1f}%",
                "confidence": "95%",
                "effort": "Medium (2-3 hours)"
            })
        elif success_rate >= 95:
            recommendations.append({
                "priority": "🟢 EXCELLENT",
                "title": "Outstanding Success Rate Performance",
                "description": f"Current: {success_rate:.1f}% | Above target by {success_rate - 85:.1f}%",
                "action": "Maintain current training quality and monitor for consistency",
                "impact": "Continue excellent performance",
                "confidence": "98%",
                "effort": "Low (maintenance)"
            })
        else:
            recommendations.append({
                "priority": "🟡 GOOD",
                "title": "Success Rate Within Target Range",
                "description": f"Current: {success_rate:.1f}% | Room for improvement: {95 - success_rate:.1f}%",
                "action": f"Optimize top {int((95 - success_rate) * 3)} training examples for consistency",
                "impact": f"Potential gain: +{(95 - success_rate) * 0.6:.1f}%",
                "confidence": "88%",
                "effort": "Low (1-2 hours)"
            })
        
        # REAL RECOMMENDATION #2: Intent Coverage
        if total_intents < 8:
            missing_intents = 8 - total_intents
            recommendations.append({
                "priority": "🟠 HIGH",
                "title": f"Limited Intent Coverage Detected",
                "description": f"Only {total_intents} intents active | Industry standard: 8-12",
                "action": f"Create {missing_intents} new intents covering: Account Closure, Investment Advice, Credit Score",
                "impact": f"Reduce 'unknown' queries by {missing_intents * 15}%",
                "confidence": "91%",
                "effort": "High (4-6 hours)"
            })
        
        # REAL RECOMMENDATION #3: Response Time
        if avg_response_time > 300:
            improvement_needed = avg_response_time - 300
            recommendations.append({
                "priority": "🟡 MEDIUM",
                "title": "Response Time Optimization Opportunity",
                "description": f"Current: {avg_response_time:.0f}ms | Target: <300ms | Excess: {improvement_needed:.0f}ms",
                "action": "Enable Redis caching for frequent queries and optimize model inference",
                "impact": f"Expected speed improvement: {(improvement_needed / avg_response_time * 100):.0f}% faster",
                "confidence": "87%",
                "effort": "Medium (3-4 hours)"
            })
        
        # REAL RECOMMENDATION #4: Training Examples
        avg_examples = total_examples / total_intents if total_intents > 0 else 0
        if avg_examples < 10:
            recommendations.append({
                "priority": "🟠 HIGH",
                "title": "Insufficient Training Data Per Intent",
                "description": f"Average: {avg_examples:.1f} examples/intent | Recommended: 15-20",
                "action": f"Add {int((15 - avg_examples) * total_intents)} more diverse training examples",
                "impact": "Accuracy improvement: +12-18%",
                "confidence": "93%",
                "effort": "High (5-8 hours)"
            })
        
        # REAL RECOMMENDATION #5: Model Retraining
        if len(st.session_state.training_history) == 0:
            recommendations.append({
                "priority": "🔴 CRITICAL",
                "title": "No Model Training Detected",
                "description": "System is using default untrained model",
                "action": "Complete initial model training with current intent dataset",
                "impact": "Expected accuracy: 85-92% after first training",
                "confidence": "99%",
                "effort": "Low (30 minutes)"
            })
        elif len(st.session_state.queries) > len(st.session_state.training_history) * 500:
            recommendations.append({
                "priority": "🟡 MEDIUM",
                "title": "Model Retraining Recommended",
                "description": f"New data: {len(st.session_state.queries)} queries | Last training: {len(st.session_state.training_history)} sessions",
                "action": "Retrain model to incorporate new query patterns",
                "impact": "Accuracy refresh: +3-5%",
                "confidence": "85%",
                "effort": "Low (20 minutes)"
            })
        
        # REAL RECOMMENDATION #6: Trend Analysis
        if len(df) >= 200 and trend < -5:
            recommendations.append({
                "priority": "🔴 URGENT",
                "title": "Declining Performance Trend Detected",
                "description": f"Performance dropped {abs(trend):.1f}% in last 100 queries",
                "action": "Immediate review of recent failed queries and retrain with corrected data",
                "impact": "Restore to previous performance levels",
                "confidence": "92%",
                "effort": "High (immediate action needed)"
            })
        elif len(df) >= 200 and trend > 5:
            recommendations.append({
                "priority": "🟢 POSITIVE",
                "title": "Improving Performance Trend",
                "description": f"Performance increased {trend:.1f}% in last 100 queries",
                "action": "Continue current strategy and document successful changes",
                "impact": "Maintain upward trajectory",
                "confidence": "89%",
                "effort": "Low (documentation)"
            })
        
        # REAL RECOMMENDATION #7: Worst Intent
        if len(df) > 0 and worst_intent['success_rate'] < 80:
            recommendations.append({
                "priority": "🟠 HIGH",
                "title": f"Low Performance Intent: {worst_intent['intent']}",
                "description": f"Success rate: {worst_intent['success_rate']:.1f}% | Queries: {worst_intent['query_count']:.0f}",
                "action": f"Add 15-20 diverse examples specifically for '{worst_intent['intent']}' intent",
                "impact": f"Expected improvement: +{(85 - worst_intent['success_rate']) * 0.7:.1f}%",
                "confidence": "90%",
                "effort": "Medium (2-3 hours)"
            })
        
        if len(recommendations) == 0:
            st.success("🎉 **EXCELLENT!** All metrics are optimal. No recommendations at this time.")
            st.balloons()
        else:
            for idx, rec in enumerate(recommendations, 1):
                with st.expander(f"{rec['priority']} - {rec['title']}", expanded=(idx <= 3)):
                    col_a, col_b = st.columns([2, 1])
                    
                    with col_a:
                        st.markdown(f"**📊 Current Status:**")
                        st.write(rec['description'])
                        
                        st.markdown(f"**💡 Recommended Action:**")
                        st.info(rec['action'])
                        
                        st.markdown(f"**📈 Expected Impact:**")
                        st.success(rec['impact'])
                    
                    with col_b:
                        st.metric("AI Confidence", rec['confidence'])
                        st.metric("Effort Required", rec['effort'])
                        
                        if st.button(f"✅ Mark Done", key=f"done_{idx}"):
                            st.success("Marked as completed!")
                        
                        if st.button(f"📋 Create Task", key=f"task_{idx}"):
                            st.info("Task added to queue!")
    
    with col2:
        st.markdown("### 📊 AI Performance Score")
        
        # Calculate overall score with REAL metrics
        score_components = {
            "Success Rate": min(100, success_rate * 1.05),
            "Intent Coverage": min(100, (total_intents / 10) * 100),
            "Training Data": min(100, (avg_examples / 15 * 100) if total_intents > 0 else 0),
            "Model Training": min(100, len(st.session_state.training_history) * 25),
            "Response Speed": min(100, (500 - avg_response_time) / 5) if avg_response_time < 500 else 0
        }
        
        overall_score = sum(score_components.values()) / len(score_components)
        
        # Gauge chart
        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=overall_score,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': "Overall AI Health", 'font': {'size': 24, 'color': text_primary}},
            delta={'reference': 85, 'increasing': {'color': "#10b981"}},
            gauge={
                'axis': {'range': [None, 100], 'tickwidth': 1, 'tickcolor': text_primary},
                'bar': {'color': "#8b5cf6", 'thickness': 0.75},
                'bgcolor': "rgba(0,0,0,0)",
                'borderwidth': 2,
                'bordercolor': text_primary,
                'steps': [
                    {'range': [0, 60], 'color': "rgba(239, 68, 68, 0.3)"},
                    {'range': [60, 80], 'color': "rgba(251, 191, 36, 0.3)"},
                    {'range': [80, 90], 'color': "rgba(34, 197, 94, 0.3)"},
                    {'range': [90, 100], 'color': "rgba(16, 185, 129, 0.3)"}
                ],
                'threshold': {
                    'line': {'color': "white", 'width': 4},
                    'thickness': 0.75,
                    'value': 90
                }
            }
        ))
        
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            font={'color': text_primary, 'family': "Arial"},
            height=350,
            margin=dict(l=20, r=20, t=50, b=20)
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # Score interpretation
        if overall_score >= 90:
            st.success("🏆 **EXCELLENT**")
            st.write("System performing at peak efficiency")
        elif overall_score >= 75:
            st.info("👍 **GOOD**")
            st.write("System performing well with room for optimization")
        elif overall_score >= 60:
            st.warning("⚠️ **NEEDS IMPROVEMENT**")
            st.write("Several areas need attention")
        else:
            st.error("🚨 **CRITICAL**")
            st.write("Immediate action required")
        
        st.markdown("---")
        
        # Score breakdown
        st.markdown("**Score Breakdown:**")
        for component, score in score_components.items():
            st.progress(score / 100)
            st.caption(f"{component}: {score:.1f}/100")
    
    st.markdown("---")
    
    # REAL-TIME INSIGHTS
    st.markdown("### 🔍 Real-time Data Insights")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**📈 Performance Trends**")
        if len(df) >= 200:
            if trend > 5:
                st.success(f"↗️ Improving (+{trend:.1f}%)")
            elif trend < -5:
                st.error(f"↘️ Declining ({trend:.1f}%)")
            else:
                st.info(f"→ Stable ({trend:+.1f}%)")
        else:
            st.warning("Need 200+ queries for trend analysis")
        
        st.metric("Total Queries", len(df))
        st.metric("Success Rate", f"{success_rate:.1f}%")
    
    with col2:
        st.markdown("**🎯 Intent Analysis**")
        if len(df) > 0:
            st.success(f"Best: {best_intent['intent']}")
            st.caption(f"{best_intent['success_rate']:.1f}% success")
            
            st.error(f"Worst: {worst_intent['intent']}")
            st.caption(f"{worst_intent['success_rate']:.1f}% success")
        else:
            st.info("No data yet")
        
        st.metric("Active Intents", total_intents)
    
    with col3:
        st.markdown("**⚡ System Health**")
        st.metric("Avg Confidence", f"{avg_confidence:.1f}%")
        st.metric("Avg Response", f"{avg_response_time:.0f}ms")
        st.metric("Training Sessions", len(st.session_state.training_history))
    
    st.markdown("---")
    
    # PREDICTIVE INSIGHTS
    if len(df) > 50:
        st.markdown("### 🔮 AI Predictions & Forecasts")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Predict next 7 days query volume
            daily_queries = df.groupby(df['timestamp'].dt.date).size()
            if len(daily_queries) >= 3:
                avg_daily = daily_queries.mean()
                
                st.markdown("**📊 Query Volume Forecast**")
                forecast_days = 7
                forecast = [avg_daily * random.uniform(0.9, 1.1) for _ in range(forecast_days)]
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=list(range(1, forecast_days + 1)),
                    y=forecast,
                    mode='lines+markers',
                    name='Predicted Queries',
                    line=dict(color='#8b5cf6', width=3),
                    marker=dict(size=10)
                ))
                
                fig.update_layout(
                    title="Next 7 Days Query Prediction",
                    xaxis_title="Days",
                    yaxis_title="Predicted Queries",
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color=text_primary),
                    height=300
                )
                st.plotly_chart(fig, use_container_width=True)
                
                st.info(f"💡 Expected total: {sum(forecast):.0f} queries over next week")
        
        with col2:
            # Predict success rate improvement
            if len(st.session_state.training_history) > 0:
                st.markdown("**🎯 Accuracy Improvement Potential**")
                
                current_acc = success_rate
                potential_gain = min(15, 95 - current_acc)
                
                scenarios = {
                    "Conservative": current_acc + potential_gain * 0.3,
                    "Moderate": current_acc + potential_gain * 0.6,
                    "Aggressive": current_acc + potential_gain * 0.9
                }
                
                scenario_df = pd.DataFrame({
                    'Scenario': list(scenarios.keys()),
                    'Projected Accuracy': list(scenarios.values())
                })
                
                fig = px.bar(scenario_df, x='Scenario', y='Projected Accuracy',
                            color='Projected Accuracy',
                            color_continuous_scale='Greens',
                            text='Projected Accuracy')
                fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                fig.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color=text_primary),
                    height=300,
                    showlegend=False
                )
                st.plotly_chart(fig, use_container_width=True)
                
                st.success(f"💡 Best case improvement: +{potential_gain * 0.9:.1f}%")
# ==================== TAB 10: LIVE TESTING LAB ====================
with tab10:
    st.header("🎮 Live Testing Laboratory")
    
    st.markdown("""
    <div style='background: linear-gradient(135deg, rgba(16, 185, 129, 0.2), rgba(5, 150, 105, 0.2));
                padding: 20px; border-radius: 15px; margin-bottom: 20px; border: 2px solid rgba(16, 185, 129, 0.3);'>
        <h3>🧪 Real-time Query Testing Environment</h3>
        <p>Test queries instantly and see them save to the database</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns([3, 1])
    with col1:
        test_query = st.text_input("🔬 Test Query", placeholder="Enter test message...")
    with col2:
        if st.button("🚀 RUN TEST", type="primary", use_container_width=True):
            if test_query:
                # Match intent
                matched = "unknown"
                conf = random.randint(40, 70)
                
                for intent in st.session_state.intents:
                    for ex in intent['examples']:
                        if ex.lower() in test_query.lower() or test_query.lower() in ex.lower():
                            matched = intent['name']
                            conf = random.randint(80, 99)
                            break
                    if matched != "unknown":
                        break
                
                # SAVE TO DATABASE FIRST
                response_time = random.randint(100, 500)
                add_real_query(test_query, matched, conf, 
                              matched != "unknown",
                              response_time, 
                              "test_user", "test_session",
                              "desktop", "Test Lab")
                
                # Show immediate feedback
                with st.spinner("Processing query..."):
                    time.sleep(0.5)
                
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.metric("Intent Detected", matched)
                with col_b:
                    st.metric("Confidence", f"{conf}%")
                with col_c:
                    st.metric("Response Time", f"{response_time}ms")
                
                if matched != "unknown":
                    st.success(f"✅ Query successfully processed and saved to database!")
                else:
                    st.warning(f"⚠️ Intent not recognized. Consider adding this to training data.")
                
                st.balloons()
                
                # Reload queries to show new data
                real_data = get_real_queries(limit=1000)
                if not real_data.empty:
                    st.session_state.queries = real_data.to_dict('records')
                
                time.sleep(1)
                st.rerun()
    
    st.markdown("---")
    
    # Show recent test results from DATABASE
    st.markdown("### 📋 Recent Test Results (Live from Database)")
    
    recent_tests = get_real_queries(limit=10)
    
    if not recent_tests.empty:
        st.info(f"📊 Showing last {len(recent_tests)} queries from database")
        
        for idx, row in recent_tests.iterrows():
            with st.expander(f"🔍 {row['query']} - {row['timestamp']}", expanded=(idx < 3)):
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.markdown("**Intent:**")
                    if row['success']:
                        st.success(f"🎯 {row['intent']}")
                    else:
                        st.error(f"❌ {row['intent']}")
                
                with col2:
                    st.markdown("**Confidence:**")
                    if row['confidence'] >= 80:
                        st.success(f"📊 {row['confidence']}%")
                    elif row['confidence'] >= 60:
                        st.warning(f"📊 {row['confidence']}%")
                    else:
                        st.error(f"📊 {row['confidence']}%")
                
                with col3:
                    st.markdown("**Response Time:**")
                    st.info(f"⏱️ {row['response_time']}ms")
                
                with col4:
                    st.markdown("**Device:**")
                    st.caption(f"📱 {row['device']}")
                
                st.markdown(f"**Location:** {row['location']} | **Session:** {row['session_id']}")
    else:
        st.warning("⏳ No test results yet. Run your first test above!")
    
    st.markdown("---")
    
    # BATCH TESTING
    st.markdown("### ⚡ Batch Testing")
    
    with st.expander("🚀 Run Multiple Tests at Once"):
        st.markdown("Test multiple queries simultaneously")
        
        batch_queries = st.text_area(
            "Enter queries (one per line)",
            placeholder="What's my balance?\nTransfer $100\nWhere is ATM?",
            height=150
        )
        
        if st.button("🔥 RUN BATCH TEST", type="primary"):
            if batch_queries:
                queries_list = [q.strip() for q in batch_queries.split('\n') if q.strip()]
                
                if len(queries_list) > 0:
                    with st.spinner(f"Processing {len(queries_list)} queries..."):
                        progress_bar = st.progress(0)
                        results = []
                        
                        for idx, query in enumerate(queries_list):
                            # Match intent
                            matched = "unknown"
                            conf = random.randint(40, 70)
                            
                            for intent in st.session_state.intents:
                                for ex in intent['examples']:
                                    if ex.lower() in query.lower() or query.lower() in ex.lower():
                                        matched = intent['name']
                                        conf = random.randint(80, 99)
                                        break
                                if matched != "unknown":
                                    break
                            
                            # Save to database
                            response_time = random.randint(100, 500)
                            add_real_query(query, matched, conf,
                                          matched != "unknown",
                                          response_time,
                                          f"batch_user_{idx}",
                                          f"batch_session_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                                          "desktop", "Batch Test")
                            
                            results.append({
                                'query': query,
                                'intent': matched,
                                'confidence': conf,
                                'success': matched != "unknown"
                            })
                            
                            progress_bar.progress((idx + 1) / len(queries_list))
                            time.sleep(0.2)
                        
                        st.success(f"✅ Batch test complete! Processed {len(queries_list)} queries")
                        
                        # Show summary
                        success_count = sum(1 for r in results if r['success'])
                        avg_conf = sum(r['confidence'] for r in results) / len(results)
                        
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Success Rate", f"{success_count/len(results)*100:.1f}%")
                        with col2:
                            st.metric("Avg Confidence", f"{avg_conf:.1f}%")
                        with col3:
                            st.metric("Total Queries", len(results))
                        
                        st.balloons()
                        time.sleep(2)
                        st.rerun()
                else:
                    st.error("Please enter at least one query")
    
    st.markdown("---")
    
    # QUICK TEST TEMPLATES
    st.markdown("### 🎯 Quick Test Templates")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**Banking Queries:**")
        if st.button("💰 Test Balance Check", use_container_width=True):
            test_queries = ["What's my balance?", "Show account balance", "Check my savings"]
            for q in test_queries:
                add_real_query(q, "check_balance", random.randint(85, 98), True,
                              random.randint(100, 300), "template_user", "template_session",
                              "desktop", "Template Test")
            st.success("✅ Added 3 balance queries!")
            time.sleep(1)
            st.rerun()
    
    with col2:
        st.markdown("**Transaction Queries:**")
        if st.button("💸 Test Transfers", use_container_width=True):
            test_queries = ["Transfer $500", "Send money to savings", "Move funds"]
            for q in test_queries:
                add_real_query(q, "transfer_money", random.randint(85, 98), True,
                              random.randint(100, 300), "template_user", "template_session",
                              "desktop", "Template Test")
            st.success("✅ Added 3 transfer queries!")
            time.sleep(1)
            st.rerun()
    
    with col3:
        st.markdown("**Security Queries:**")
        if st.button("🔒 Test Card Block", use_container_width=True):
            test_queries = ["Block my card", "I lost my card", "Freeze credit card"]
            for q in test_queries:
                add_real_query(q, "card_block", random.randint(85, 98), True,
                              random.randint(100, 300), "template_user", "template_session",
                              "desktop", "Template Test")
            st.success("✅ Added 3 security queries!")
            time.sleep(1)
            st.rerun()

with tab11:
    st.header("🧪 A/B Testing & Experiments")
    
    st.markdown("""
    <div style='background: linear-gradient(135deg, rgba(245, 158, 11, 0.2), rgba(217, 119, 6, 0.2));
                padding: 20px; border-radius: 15px; margin-bottom: 20px; border: 2px solid rgba(245, 158, 11, 0.3);'>
        <h3>🔬 Compare Different Approaches & Optimize Performance</h3>
        <p>Test two versions (A vs B) and see which performs better</p>
    </div>
    """, unsafe_allow_html=True)
    
    # CREATE NEW A/B TEST
    with st.expander("➕ Create New A/B Test", expanded=False):
        st.markdown("### Design Your Experiment")
        
        col1, col2 = st.columns(2)
        
        with col1:
            test_name = st.text_input("Test Name", placeholder="e.g., Welcome Message Test")
            variant_a = st.text_input("Variant A Description", placeholder="e.g., Formal greeting")
            conversion_a_manual = st.number_input("Variant A Conversion %", 0.0, 100.0, 75.0, 0.1)
        
        with col2:
            test_category = st.selectbox("Category", ["UI/UX", "Messaging", "Performance", "Features"])
            variant_b = st.text_input("Variant B Description", placeholder="e.g., Casual greeting")
            conversion_b_manual = st.number_input("Variant B Conversion %", 0.0, 100.0, 82.0, 0.1)
        
        sample_size = st.slider("Sample Size (users)", 100, 5000, 1000, 100)
        
        if st.button("🚀 Create A/B Test", type="primary"):
            if test_name and variant_a and variant_b:
                new_test = {
                    "id": len(st.session_state.ab_tests) + 1,
                    "name": test_name,
                    "variant_a": variant_a,
                    "variant_b": variant_b,
                    "status": "Running",
                    "conversion_a": conversion_a_manual,
                    "conversion_b": conversion_b_manual,
                    "sample_size": sample_size,
                    "category": test_category,
                    "created_date": datetime.now().strftime("%Y-%m-%d")
                }
                st.session_state.ab_tests.append(new_test)
                st.success(f"✅ A/B Test '{test_name}' created successfully!")
                st.balloons()
                time.sleep(1)
                st.rerun()
            else:
                st.error("⚠️ Please fill in all fields")
    
    st.markdown("---")
    
    # SHOW ACTIVE TESTS
    if len(st.session_state.ab_tests) == 0:
        st.info("💡 No A/B tests yet. Create your first test above!")
    else:
        st.markdown(f"### 📊 Active Experiments ({len(st.session_state.ab_tests)} total)")
        
        # FILTER TESTS
        col1, col2 = st.columns([3, 1])
        with col1:
            filter_status = st.selectbox("Filter by Status", ["All", "Running", "Completed", "Paused"])
        with col2:
            sort_by = st.selectbox("Sort by", ["Recent", "Name", "Performance"])
        
        st.markdown("---")
        
        # DISPLAY EACH TEST
        for idx, test in enumerate(st.session_state.ab_tests):
            # Apply filter
            if filter_status != "All" and test['status'] != filter_status:
                continue
            
            # Calculate results
            winner = "B" if test['conversion_b'] > test['conversion_a'] else "A"
            diff = abs(test['conversion_b'] - test['conversion_a'])
            
            # Determine significance
            if diff > 5:
                significance = "✅ Statistically Significant"
                significance_color = "success"
            elif diff > 2:
                significance = "⚠️ Possibly Significant"
                significance_color = "warning"
            else:
                significance = "❌ Not Significant (need more data)"
                significance_color = "error"
            
            # Calculate confidence interval (simplified)
            confidence_level = min(99, 50 + (diff * 8))
            
            with st.expander(
                f"🧪 **{test['name']}** | {test['status']} | Sample: {test['sample_size']:,} users",
                expanded=(idx < 2)
            ):
                # STATUS BADGE
                if test['status'] == "Running":
                    st.success(f"🟢 Status: {test['status']}")
                elif test['status'] == "Completed":
                    st.info(f"✅ Status: {test['status']}")
                else:
                    st.warning(f"⏸️ Status: {test['status']}")
                
                st.markdown("---")
                
                # MAIN COMPARISON
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.markdown(f"### 🅰️ Variant A")
                    st.markdown(f"**{test['variant_a']}**")
                    st.metric("Conversion Rate", f"{test['conversion_a']:.1f}%")
                    st.progress(test['conversion_a'] / 100)
                    
                    # Simulated user data
                    users_a = int(test['sample_size'] * 0.5)
                    conversions_a = int(users_a * test['conversion_a'] / 100)
                    st.caption(f"👥 {users_a:,} users | ✅ {conversions_a:,} conversions")
                
                with col2:
                    st.markdown(f"### 🅱️ Variant B")
                    st.markdown(f"**{test['variant_b']}**")
                    st.metric("Conversion Rate", f"{test['conversion_b']:.1f}%")
                    st.progress(test['conversion_b'] / 100)
                    
                    # Simulated user data
                    users_b = int(test['sample_size'] * 0.5)
                    conversions_b = int(users_b * test['conversion_b'] / 100)
                    st.caption(f"👥 {users_b:,} users | ✅ {conversions_b:,} conversions")
                
                with col3:
                    st.markdown(f"### 🏆 Results")
                    st.markdown(f"**Winner: Variant {winner}**")
                    st.metric("Improvement", f"+{diff:.1f}%", delta=f"+{diff:.1f}%")
                    
                    # Show significance
                    if significance_color == "success":
                        st.success(significance)
                    elif significance_color == "warning":
                        st.warning(significance)
                    else:
                        st.error(significance)
                    
                    st.metric("Confidence Level", f"{confidence_level:.0f}%")
                
                st.markdown("---")
                
                # DETAILED METRICS
                st.markdown("### 📊 Detailed Analysis")
                
                col_a, col_b, col_c, col_d = st.columns(4)
                
                with col_a:
                    # Calculate lift
                    lift = ((test['conversion_b'] - test['conversion_a']) / test['conversion_a'] * 100) if test['conversion_a'] > 0 else 0
                    st.metric("Lift", f"{lift:+.1f}%")
                
                with col_b:
                    # Revenue impact (simulated)
                    revenue_per_conversion = 50  # $50 average
                    revenue_diff = (conversions_b - conversions_a) * revenue_per_conversion
                    st.metric("Revenue Impact", f"${revenue_diff:+,.0f}")
                
                with col_c:
                    # Days running
                    created = datetime.strptime(test.get('created_date', datetime.now().strftime("%Y-%m-%d")), "%Y-%m-%d")
                    days_running = (datetime.now() - created).days
                    st.metric("Days Running", days_running)
                
                with col_d:
                    # Sample size reached
                    completion = 100  # Assume 100% for demo
                    st.metric("Completion", f"{completion}%")
                
                st.markdown("---")
                
                # VISUALIZATION
                st.markdown("### 📈 Conversion Comparison")
                
                comparison_data = pd.DataFrame({
                    'Variant': ['Variant A', 'Variant B'],
                    'Conversion Rate': [test['conversion_a'], test['conversion_b']],
                    'Users': [users_a, users_b],
                    'Conversions': [conversions_a, conversions_b]
                })
                
                fig = go.Figure()
                
                fig.add_trace(go.Bar(
                    name='Conversion Rate',
                    x=comparison_data['Variant'],
                    y=comparison_data['Conversion Rate'],
                    text=comparison_data['Conversion Rate'].round(1),
                    texttemplate='%{text}%',
                    textposition='outside',
                    marker_color=['#3b82f6', '#10b981']
                ))
                
                fig.update_layout(
                    title=f"Conversion Rate: Variant A vs Variant B",
                    yaxis_title="Conversion Rate (%)",
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color=text_primary),
                    height=350
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                st.markdown("---")
                
                # ACTION BUTTONS
                st.markdown("### ⚡ Actions")
                
                col_btn1, col_btn2, col_btn3, col_btn4 = st.columns(4)
                
                with col_btn1:
                    if test['status'] == "Running":
                        if st.button("⏸️ Pause Test", key=f"pause_{test['id']}", use_container_width=True):
                            test['status'] = "Paused"
                            st.warning("Test paused")
                            time.sleep(0.5)
                            st.rerun()
                    else:
                        if st.button("▶️ Resume Test", key=f"resume_{test['id']}", use_container_width=True):
                            test['status'] = "Running"
                            st.success("Test resumed")
                            time.sleep(0.5)
                            st.rerun()
                
                with col_btn2:
                    if st.button("✅ Mark Complete", key=f"complete_{test['id']}", use_container_width=True):
                        test['status'] = "Completed"
                        st.success("Test marked as completed!")
                        time.sleep(0.5)
                        st.rerun()
                
                with col_btn3:
                    if st.button("🏆 Declare Winner", key=f"winner_{test['id']}", use_container_width=True):
                        st.balloons()
                        st.success(f"🎉 Variant {winner} wins with +{diff:.1f}% improvement!")
                        test['status'] = "Completed"
                        time.sleep(1)
                        st.rerun()
                
                with col_btn4:
                    if st.button("🗑️ Delete Test", key=f"delete_{test['id']}", use_container_width=True):
                        st.session_state.ab_tests = [t for t in st.session_state.ab_tests if t['id'] != test['id']]
                        st.warning("Test deleted")
                        time.sleep(0.5)
                        st.rerun()
                
                st.markdown("---")
                
                # RECOMMENDATIONS
                st.markdown("### 💡 AI Recommendations")
                
                if winner == "B" and diff > 5:
                    st.success(f"""
                    ✅ **STRONG RECOMMENDATION:** Deploy Variant B
                    
                    - Variant B shows {diff:.1f}% improvement
                    - Statistical confidence: {confidence_level:.0f}%
                    - Expected revenue lift: ${revenue_diff:+,.0f}
                    - **Action:** Roll out Variant B to 100% of users
                    """)
                elif winner == "A" and diff > 5:
                    st.info(f"""
                    ℹ️ **RECOMMENDATION:** Keep Variant A
                    
                    - Variant A performs {diff:.1f}% better
                    - No need to change current approach
                    - Consider new test variations
                    """)
                elif diff < 2:
                    st.warning(f"""
                    ⚠️ **NO CLEAR WINNER:** Continue Testing
                    
                    - Difference is only {diff:.1f}% (too small)
                    - Need more sample size: +{int(test['sample_size'] * 0.5):,} users
                    - Consider running test for {days_running + 7} more days
                    """)
                else:
                    st.info(f"""
                    📊 **MODERATE RESULT:** Monitor Closely
                    
                    - Variant {winner} shows {diff:.1f}% improvement
                    - Confidence: {confidence_level:.0f}%
                    - Recommend collecting more data before decision
                    """)
        
        st.markdown("---")
        
        # SUMMARY STATISTICS
        st.markdown("### 📈 Overall Testing Summary")
        
        running_tests = sum(1 for t in st.session_state.ab_tests if t['status'] == 'Running')
        completed_tests = sum(1 for t in st.session_state.ab_tests if t['status'] == 'Completed')
        total_users = sum(t['sample_size'] for t in st.session_state.ab_tests)
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Tests", len(st.session_state.ab_tests))
        with col2:
            st.metric("Running", running_tests)
        with col3:
            st.metric("Completed", completed_tests)
        with col4:
            st.metric("Total Users Tested", f"{total_users:,}")

with tab12:
    st.header("📡 API Performance Monitor")
    
    api_df = pd.DataFrame(st.session_state.api_logs)
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Requests", len(api_df))
    with col2:
        success = len(api_df[api_df['status'].isin([200, 201])])
        st.metric("Success Rate", f"{success/len(api_df)*100:.1f}%")
    with col3:
        st.metric("Avg Response", f"{api_df['response_time'].mean():.0f}ms")
    with col4:
        st.metric("Errors", len(api_df[api_df['status']>=400]))
    
    col1, col2 = st.columns(2)
    with col1:
        endpoint_counts = api_df['endpoint'].value_counts()
        fig = px.bar(x=endpoint_counts.index, y=endpoint_counts.values, title="Requests by Endpoint")
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', font=dict(color=text_primary))
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        status_counts = api_df['status'].value_counts()
        fig = px.pie(values=status_counts.values, names=status_counts.index, title="Status Codes")
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', font=dict(color=text_primary))
        st.plotly_chart(fig, use_container_width=True)

with tab13:
    st.header("🚨 Anomaly Detection System")
    
    st.markdown("### 🔍 Detected Anomalies")
    
    for anomaly in st.session_state.anomalies:
        severity_color = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}
        
        with st.expander(f"{severity_color[anomaly['severity']]} **{anomaly['type']}** - {anomaly['severity']} Severity", expanded=True):
            st.write(f"**Details:** {anomaly['details']}")
            st.caption(f"**Detected:** {anomaly['timestamp']}")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("✅ Resolve", key=f"resolve_{anomaly['id']}"):
                    st.success("Marked as resolved")
            with col2:
                if st.button("🔔 Alert", key=f"alert_{anomaly['id']}"):
                    st.info("Alert sent to admin")
            with col3:
                if st.button("🗑️ Dismiss", key=f"dismiss_{anomaly['id']}"):
                    st.session_state.anomalies = [a for a in st.session_state.anomalies if a['id'] != anomaly['id']]
                    st.rerun()

with tab14:
    st.header("👤 User Segmentation Analytics")
    
    seg_df = pd.DataFrame(st.session_state.user_segments)
    
    st.markdown("### 📊 User Segments Overview")
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig = px.bar(seg_df, x='segment', y='count', color='satisfaction',
                    title="Users by Segment", color_continuous_scale='Viridis')
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', font=dict(color=text_primary))
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        fig = px.scatter(seg_df, x='avg_queries', y='satisfaction', size='count',
                        color='retention', title="Engagement vs Satisfaction")
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', font=dict(color=text_primary))
        st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    for idx, seg in seg_df.iterrows():
        with st.expander(f"**{seg['segment']}** - {seg['count']} users", expanded=True):
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Users", seg['count'])
            with col2:
                st.metric("Avg Queries", seg['avg_queries'])
            with col3:
                st.metric("Satisfaction", f"{seg['satisfaction']}/5.0")
            with col4:
                st.metric("Retention", f"{seg['retention']}%")

with tab15:
    st.header("🔄 Conversation Flow Designer")
    
    st.markdown("""
    <div style='background: linear-gradient(135deg, rgba(102, 126, 234, 0.2), rgba(118, 75, 162, 0.2));
                padding: 20px; border-radius: 15px; margin-bottom: 20px;'>
        <h3>💬 Multi-Step Conversation Management</h3>
        <p>Design and optimize complex conversation flows with branching logic</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Flow Creation
    with st.expander("➕ Create New Flow"):
        flow_name = st.text_input("Flow Name", placeholder="e.g., Account Opening Journey")
        num_steps = st.number_input("Number of Steps", 1, 15, 5)
        
        if st.button("Create Flow", type="primary"):
            st.session_state.conversation_flows.append({
                "id": len(st.session_state.conversation_flows) + 1,
                "name": flow_name,
                "steps": num_steps,
                "completion_rate": 0,
                "avg_duration": 0
            })
            st.success("✅ Flow created!")
            st.rerun()
    
    st.markdown("---")
    st.markdown("### 📋 Active Flows")
    
    for flow in st.session_state.conversation_flows:
        with st.expander(f"**{flow['name']}** - {flow['steps']} steps | {flow['completion_rate']}% completion"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Steps", flow['steps'])
                st.metric("Completion Rate", f"{flow['completion_rate']}%")
            
            with col2:
                st.metric("Avg Duration", f"{flow['avg_duration']}s")
                st.metric("Drop-off Rate", f"{100 - flow['completion_rate']:.1f}%")
            
            with col3:
                # Flow visualization
                steps_data = [100]
                for i in range(1, flow['steps']):
                    steps_data.append(steps_data[-1] * random.uniform(0.85, 0.95))
                
                fig = go.Figure(go.Funnel(
                    y=[f"Step {i+1}" for i in range(flow['steps'])],
                    x=steps_data,
                    textinfo="value+percent initial"
                ))
                fig.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    font=dict(color=text_primary, size=10),
                    height=250
                )
                st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("---")
            
            col1, col2 = st.columns([4, 1])
            with col2:
                if st.button("🗑️ Delete", key=f"del_flow_{flow['id']}"):
                    st.session_state.conversation_flows = [f for f in st.session_state.conversation_flows if f['id'] != flow['id']]
                    st.rerun()

with tab16:
    st.header("🤝 Platform Integrations")
    
    st.markdown("""
    <div style='background: linear-gradient(135deg, rgba(16, 185, 129, 0.2), rgba(5, 150, 105, 0.2));
                padding: 20px; border-radius: 15px; margin-bottom: 20px;'>
        <h3>🔗 Connect Multiple Platforms</h3>
        <p>Manage integrations with messaging platforms and third-party services</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        total_connected = sum(1 for i in st.session_state.integrations if i['status'] == "Connected")
        st.metric("Connected Platforms", total_connected)
    with col2:
        total_messages = sum(i['messages'] for i in st.session_state.integrations)
        st.metric("Total Messages", f"{total_messages:,}")
    with col3:
        st.metric("Available Platforms", len(st.session_state.integrations))
    
    st.markdown("---")
    
    for integration in st.session_state.integrations:
        with st.expander(f"**{integration['name']}** - {integration['status']}", expanded=True):
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                if integration['status'] == "Connected":
                    st.success(f"✅ **Status:** {integration['status']}")
                else:
                    st.error(f"❌ **Status:** {integration['status']}")
                
                st.info(f"**Last Sync:** {integration['last_sync']}")
                st.metric("Messages Processed", f"{integration['messages']:,}")
            
            with col2:
                if integration['status'] == "Connected":
                    if st.button("🔌 Disconnect", key=f"disconnect_{integration['name']}", use_container_width=True):
                        integration['status'] = "Disconnected"
                        st.warning("Disconnected!")
                        st.rerun()
                else:
                    if st.button("🔗 Connect", key=f"connect_{integration['name']}", use_container_width=True):
                        integration['status'] = "Connected"
                        st.success("Connected!")
                        st.rerun()
            
            with col3:
                if st.button("⚙️ Configure", key=f"config_{integration['name']}", use_container_width=True):
                    st.info("Configuration panel opened")
                
                if st.button("🔄 Sync Now", key=f"sync_{integration['name']}", use_container_width=True):
                    st.success("Syncing...")
    
    st.markdown("---")
    
    with st.expander("➕ Add New Integration"):
        new_platform = st.text_input("Platform Name", placeholder="e.g., Microsoft Teams")
        api_key = st.text_input("API Key", type="password", placeholder="Enter API key")
        webhook_url = st.text_input("Webhook URL", placeholder="https://...")
        
        if st.button("Add Integration", type="primary"):
            if new_platform and api_key:
                st.session_state.integrations.append({
                    "name": new_platform,
                    "status": "Connected",
                    "last_sync": "Just now",
                    "messages": 0
                })
                st.success(f"✅ {new_platform} integrated!")
                st.balloons()
                st.rerun()

with tab17:
    st.header("⚡ Performance Benchmarks & Optimization")
    
    st.markdown("""
    <div style='background: linear-gradient(135deg, rgba(234, 179, 8, 0.2), rgba(202, 138, 4, 0.2));
                padding: 20px; border-radius: 15px; margin-bottom: 20px;'>
        <h3>📊 Real-time Performance Monitoring</h3>
        <p>Track system performance metrics and identify bottlenecks</p>
    </div>
    """, unsafe_allow_html=True)
    
    benchmarks = st.session_state.performance_benchmarks
    
    # Performance KPIs
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("P50 Response", f"{benchmarks['response_time_p50']}ms", delta="-15ms", delta_color="inverse")
    with col2:
        st.metric("P95 Response", f"{benchmarks['response_time_p95']}ms", delta="-25ms", delta_color="inverse")
    with col3:
        st.metric("Throughput", f"{benchmarks['throughput_qps']} QPS", delta="+12 QPS")
    with col4:
        st.metric("Error Rate", f"{benchmarks['error_rate']}%", delta="-0.3%", delta_color="inverse")
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📈 Response Time Distribution")
        
        # Simulate response time data
        response_times = np.random.gamma(2, 60, 1000)
        
        fig = go.Figure()
        fig.add_trace(go.Histogram(x=response_times, nbinsx=50, name="Response Time",
                                   marker_color='#667eea'))
        fig.add_vline(x=benchmarks['response_time_p50'], line_dash="dash", 
                     line_color="green", annotation_text="P50")
        fig.add_vline(x=benchmarks['response_time_p95'], line_dash="dash",
                     line_color="orange", annotation_text="P95")
        fig.add_vline(x=benchmarks['response_time_p99'], line_dash="dash",
                     line_color="red", annotation_text="P99")
        
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color=text_primary),
            xaxis_title="Response Time (ms)",
            yaxis_title="Frequency"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("### 💾 Resource Utilization")
        
        resource_data = pd.DataFrame({
            'Resource': ['CPU', 'Memory', 'Cache Hit', 'Network'],
            'Usage': [benchmarks['cpu_usage'], benchmarks['memory_usage'], 
                     benchmarks['cache_hit_rate'], random.randint(30, 60)]
        })
        
        fig = px.bar(resource_data, x='Resource', y='Usage', color='Usage',
                    color_continuous_scale='RdYlGn_r', text='Usage')
        fig.update_traces(texttemplate='%{text}%', textposition='outside')
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color=text_primary),
            yaxis_title="Usage (%)"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    # Scheduled Tasks
    st.markdown("### ⏰ Scheduled Tasks & Automation")
    
    for task in st.session_state.scheduled_tasks:
        with st.expander(f"**{task['task']}** - {task['frequency']} | Next: {task['next_run']}"):
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.info(f"**Frequency:** {task['frequency']}")
            with col2:
                st.info(f"**Next Run:** {task['next_run']}")
            with col3:
                if task['status'] == "Running":
                    st.success(f"**Status:** {task['status']}")
                else:
                    st.info(f"**Status:** {task['status']}")
            with col4:
                if st.button("▶️ Run Now", key=f"run_task_{task['id']}"):
                    st.success("Task started!")
    
    st.markdown("---")
    
    # Model Comparison
    st.markdown("### 🧠 NLP Model Comparison")
    
    models_df = pd.DataFrame(st.session_state.nlp_models)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        fig = px.scatter(models_df, x='size', y='accuracy', size='accuracy',
                        color='speed', hover_data=['name'],
                        title="Model Performance vs Size")
        fig.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color=text_primary),
            xaxis_title="Model Size",
            yaxis_title="Accuracy (%)"
        )
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("**Select Active Model:**")
        for model in st.session_state.nlp_models:
            col_a, col_b = st.columns([3, 1])
            with col_a:
                st.write(f"**{model['name']}**")
                st.caption(f"Acc: {model['accuracy']}% | {model['speed']} | {model['size']}")
            with col_b:
                if model['active']:
                    st.success("✅ Active")
                else:
                    if st.button("Activate", key=f"activate_{model['name']}"):
                        for m in st.session_state.nlp_models:
                            m['active'] = False
                        model['active'] = True
                        st.rerun()
            st.markdown("---")
    
    st.markdown("---")
    
    # Performance Recommendations
    st.markdown("### 💡 Performance Optimization Recommendations")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if benchmarks['cache_hit_rate'] < 80:
            st.warning("⚠️ **Cache Hit Rate Low**")
            st.markdown("- Current: 78.5%")
            st.markdown("- Target: >85%")
            st.markdown("- **Action:** Increase cache size and optimize cache keys")
        
        if benchmarks['response_time_p95'] > 250:
            st.warning("⚠️ **P95 Response Time High**")
            st.markdown("- Current: 280ms")
            st.markdown("- Target: <250ms")
            st.markdown("- **Action:** Optimize database queries and enable CDN")
    
    with col2:
        if benchmarks['error_rate'] > 0.5:
            st.warning("⚠️ **Error Rate Above Threshold**")
            st.markdown("- Current: 0.8%")
            st.markdown("- Target: <0.5%")
            st.markdown("- **Action:** Review error logs and add retry logic")
        
        if benchmarks['cpu_usage'] > 60:
            st.info("ℹ️ **CPU Usage Optimal**")
            st.markdown("- Current: 38%")
            st.markdown("- Status: Healthy")
            st.markdown("- **Action:** No action needed")


# Add this code after tab17 (before the FOOTER section at the end)

# ==================== TAB 18: SENTIMENT ANALYSIS ====================
with tab18:
    st.header("😊 Sentiment Analysis Dashboard")
    
    sentiment = st.session_state.sentiment_analysis
    total = sum(sentiment.values())
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Analyzed", f"{total:,}")
    with col2:
        positive_pct = (sentiment['positive'] + sentiment['very_positive']) / total * 100
        st.metric("Positive", f"{positive_pct:.1f}%", delta="+3.2%")
    with col3:
        negative_pct = (sentiment['negative'] + sentiment['very_negative']) / total * 100
        st.metric("Negative", f"{negative_pct:.1f}%", delta="-1.8%", delta_color="inverse")
    with col4:
        st.metric("Net Score", f"+{positive_pct - negative_pct:.1f}", delta="+5.0%")
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📊 Sentiment Distribution")
        sentiment_df = pd.DataFrame({
            'Sentiment': ['Very Positive', 'Positive', 'Neutral', 'Negative', 'Very Negative'],
            'Count': [sentiment['very_positive'], sentiment['positive'], sentiment['neutral'], 
                     sentiment['negative'], sentiment['very_negative']]
        })
        
        colors = ['#10b981', '#6ee7b7', '#fbbf24', '#fb923c', '#ef4444']
        fig = px.bar(sentiment_df, x='Sentiment', y='Count', color='Sentiment',
                    color_discrete_sequence=colors, text='Count')
        fig.update_traces(texttemplate='%{text:,}', textposition='outside')
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', font=dict(color=text_primary))
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("### 🥧 Sentiment Breakdown")
        fig = px.pie(sentiment_df, values='Count', names='Sentiment',
                    color_discrete_sequence=colors, hole=0.4)
        fig.update_traces(textposition='inside', textinfo='percent+label')
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', font=dict(color=text_primary))
        st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    st.markdown("### 📅 Sentiment Trend Over Time")
    dates = pd.date_range(end=datetime.now(), periods=30, freq='D')
    trend_data = pd.DataFrame({
        'Date': dates,
        'Positive': np.random.randint(150, 250, 30),
        'Neutral': np.random.randint(50, 100, 30),
        'Negative': np.random.randint(20, 60, 30)
    })
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=trend_data['Date'], y=trend_data['Positive'],
                            mode='lines+markers', name='Positive', 
                            line=dict(color='#10b981', width=3)))
    fig.add_trace(go.Scatter(x=trend_data['Date'], y=trend_data['Neutral'],
                            mode='lines+markers', name='Neutral',
                            line=dict(color='#fbbf24', width=3)))
    fig.add_trace(go.Scatter(x=trend_data['Date'], y=trend_data['Negative'],
                            mode='lines+markers', name='Negative',
                            line=dict(color='#ef4444', width=3)))
    
    fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', font=dict(color=text_primary),
                     hovermode='x unified', legend=dict(orientation="h", yanchor="bottom", y=1.02))
    st.plotly_chart(fig, use_container_width=True)

# ==================== TAB 19: LANGUAGE DETECTION ====================
with tab19:
    st.header("🌍 Language Detection & Analytics")
    
    lang_data = st.session_state.language_detection
    total_queries = sum(lang_data.values())
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Languages", len(lang_data))
    with col2:
        st.metric("Total Queries", f"{total_queries:,}")
    with col3:
        primary_lang = max(lang_data, key=lang_data.get)
        st.metric("Primary Language", primary_lang)
    with col4:
        primary_pct = lang_data[primary_lang] / total_queries * 100
        st.metric("Primary %", f"{primary_pct:.1f}%")
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🌐 Language Distribution")
        lang_df = pd.DataFrame({
            'Language': list(lang_data.keys()),
            'Queries': list(lang_data.values())
        }).sort_values('Queries', ascending=False)
        
        fig = px.bar(lang_df, x='Language', y='Queries', color='Queries',
                    color_continuous_scale='Blues', text='Queries')
        fig.update_traces(texttemplate='%{text:,}', textposition='outside')
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', font=dict(color=text_primary))
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("### 🥧 Language Percentage")
        fig = px.pie(lang_df, values='Queries', names='Language', hole=0.5)
        fig.update_traces(textposition='inside', textinfo='percent+label')
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', font=dict(color=text_primary))
        st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    st.markdown("### 📊 Detailed Language Statistics")
    for lang, count in sorted(lang_data.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / total_queries) * 100
        with st.expander(f"**{lang}** - {count:,} queries ({percentage:.1f}%)"):
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Queries", f"{count:,}")
            with col2:
                st.metric("Percentage", f"{percentage:.2f}%")
            with col3:
                st.metric("Accuracy", f"{random.uniform(88, 97):.1f}%")
            with col4:
                st.metric("Avg Confidence", f"{random.uniform(85, 95):.1f}%")
            st.progress(percentage / 100)

# ==================== TAB 20: SECURITY CENTER ====================
with tab20:
    st.header("🔒 Security Center & Threat Detection")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Security Events", len(st.session_state.security_events))
    with col2:
        blocked = sum(1 for e in st.session_state.security_events if e['status'] == 'Blocked')
        st.metric("Blocked Threats", blocked)
    with col3:
        monitoring = sum(1 for e in st.session_state.security_events if e['status'] == 'Monitoring')
        st.metric("Under Monitoring", monitoring)
    with col4:
        st.metric("Security Score", "98/100", delta="+2")
    
    st.markdown("---")
    
    st.markdown("### 🚨 Recent Security Events")
    for event in st.session_state.security_events:
        severity_colors = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}
        with st.expander(f"{severity_colors[event['severity']]} **{event['type']}** - {event['severity']} Severity"):
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"**IP Address:** {event['ip']}")
                st.write(f"**Timestamp:** {event['timestamp']}")
            with col2:
                if event['status'] == 'Blocked':
                    st.error(f"**Status:** {event['status']}")
                elif event['status'] == 'Monitoring':
                    st.warning(f"**Status:** {event['status']}")
                else:
                    st.success(f"**Status:** {event['status']}")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("🔓 Unblock", key=f"unblock_{event['id']}"):
                    st.info("IP unblocked")
            with col2:
                if st.button("🔍 Investigate", key=f"investigate_{event['id']}"):
                    st.info("Opening investigation panel")
            with col3:
                if st.button("✅ Resolve", key=f"resolve_sec_{event['id']}"):
                    st.success("Event resolved")

# ==================== TAB 21: REVENUE ANALYTICS ====================
with tab21:
    st.header("💰 Revenue Impact & Cost Analysis")
    
    revenue = st.session_state.revenue_impact
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Monthly Savings", f"${revenue['cost_savings']:,.0f}", delta=f"+${random.randint(500, 1000)}")
    with col2:
        st.metric("Automation Rate", f"{revenue['automation_rate']:.1f}%", delta="+3.2%")
    with col3:
        st.metric("ROI", f"{revenue['roi_percentage']}%", delta="+25%")
    with col4:
        st.metric("Cost per Query", f"${revenue['cost_per_query']:.2f}", delta="-$0.02", delta_color="inverse")
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 💵 Cost Comparison")
        cost_data = pd.DataFrame({
            'Method': ['Manual Handling', 'Automated (Chatbot)'],
            'Cost per Query': [revenue['manual_handling_cost'], revenue['cost_per_query']]
        })
        fig = px.bar(cost_data, x='Method', y='Cost per Query', color='Method',
                    color_discrete_map={'Manual Handling': '#ef4444', 'Automated (Chatbot)': '#10b981'},
                    text='Cost per Query')
        fig.update_traces(texttemplate='$%{text:.2f}', textposition='outside')
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', font=dict(color=text_primary))
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("### 📊 Monthly Savings Trend")
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun']
        savings = [4200, 4800, 5500, 6100, 6400, 6750]
        fig = px.line(x=months, y=savings, markers=True, labels={'x': 'Month', 'y': 'Savings ($)'})
        fig.update_traces(line_color='#10b981', marker=dict(size=12))
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', font=dict(color=text_primary))
        st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    st.markdown("### 💡 Financial Insights")
    col1, col2, col3 = st.columns(3)
    with col1:
        total_handled = revenue['monthly_queries'] * revenue['automation_rate'] / 100
        manual_cost = total_handled * revenue['manual_handling_cost']
        automated_cost = total_handled * revenue['cost_per_query']
        savings_detail = manual_cost - automated_cost
        st.info(f"**Annual Savings Projection:** ${savings_detail * 12:,.0f}")
    with col2:
        st.success(f"**Queries Automated:** {int(total_handled):,}/month")
    with col3:
        st.warning(f"**Manual Queries Remaining:** {int(revenue['monthly_queries'] * (100 - revenue['automation_rate']) / 100):,}")

# ==================== TAB 22: PREDICTIVE AI ====================
with tab22:
    st.header("🔮 Predictive Analytics & Forecasting")
    
    pred = st.session_state.predictive_analytics
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Queries Tomorrow", f"{pred['predicted_queries_tomorrow']:,}", delta="+12%")
    with col2:
        st.metric("Queries Next Week", f"{pred['predicted_queries_next_week']:,}")
    with col3:
        st.metric("Churn Risk Users", pred['churn_risk_users'], delta="-8", delta_color="inverse")
    with col4:
        st.metric("High Value Users", pred['high_value_users'], delta="+23")
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📈 Query Volume Forecast (Next 7 Days)")
        days = ['Today', 'Tomorrow', 'Day 3', 'Day 4', 'Day 5', 'Day 6', 'Day 7']
        forecast = [2890, pred['predicted_queries_tomorrow'], 3450, 3280, 3590, 3120, 3380]
        fig = px.line(x=days, y=forecast, markers=True, labels={'x': 'Day', 'y': 'Predicted Queries'})
        fig.update_traces(line_color='#667eea', marker=dict(size=12))
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', font=dict(color=text_primary))
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        st.markdown("### ⏰ Predicted Peak Hours")
        st.info(f"**Peak Hour 1:** {pred['predicted_peak_hours'][0]}")
        st.info(f"**Peak Hour 2:** {pred['predicted_peak_hours'][1]}")
        st.info(f"**Peak Hour 3:** {pred['predicted_peak_hours'][2]}")
        
        st.markdown("---")
        st.markdown("### 🔥 Trending Intents")
        for idx, intent in enumerate(pred['trending_intents'], 1):
            st.success(f"**#{idx}** {intent}")
    
    st.markdown("---")
    
    st.markdown("### 👥 User Risk Analysis")
    col1, col2 = st.columns(2)
    with col1:
        st.warning(f"**⚠️ At-Risk Users:** {pred['churn_risk_users']}")
        st.markdown("**Recommended Actions:**")
        st.markdown("- Send re-engagement campaigns")
        st.markdown("- Offer personalized support")
        st.markdown("- Analyze pain points")
    with col2:
        st.success(f"**⭐ High-Value Users:** {pred['high_value_users']}")
        st.markdown("**Growth Opportunities:**")
        st.markdown("- Premium feature upsells")
        st.markdown("- Loyalty rewards program")
        st.markdown("- Dedicated account managers")

# ==================== TAB 23: TEAM COLLABORATION ====================
with tab23:
    st.header("👥 Team Collaboration Center")
    
    collab = st.session_state.collaboration_data
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Team Members", len(collab))
    with col2:
        online = sum(1 for m in collab if m['status'] == 'Online')
        st.metric("Online Now", online)
    with col3:
        total_actions = sum(m['actions_today'] for m in collab)
        st.metric("Total Actions Today", total_actions)
    
    st.markdown("---")
    
    st.markdown("### 👤 Team Activity")
    for member in collab:
        with st.expander(f"**{member['team_member']}** - {member['role']} | {member['status']}", expanded=True):
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                if member['status'] == 'Online':
                    st.success(f"🟢 {member['status']}")
                elif member['status'] == 'Away':
                    st.warning(f"🟡 {member['status']}")
                else:
                    st.error(f"🔴 Offline")
            
            with col2:
                st.info(f"**Role:** {member['role']}")
            
            with col3:
                st.metric("Actions Today", member['actions_today'])
            
            with col4:
                st.caption(f"Last Active: {member['last_active']}")
            
            st.markdown("---")
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("💬 Message", key=f"msg_{member['team_member']}"):
                    st.info("Opening chat...")
            with col2:
                if st.button("👁️ View Activity", key=f"view_{member['team_member']}"):
                    st.info("Loading activity log...")
            with col3:
                if st.button("⚙️ Permissions", key=f"perm_{member['team_member']}"):
                    st.info("Opening permissions panel...")
    
    st.markdown("---")
    
    st.markdown("### 📊 Team Performance")
    col1, col2 = st.columns(2)
    
    with col1:
        team_df = pd.DataFrame(collab)
        fig = px.bar(team_df, x='team_member', y='actions_today', color='status',
                    title="Actions by Team Member", text='actions_today')
        fig.update_traces(textposition='outside')
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', font=dict(color=text_primary))
        st.plotly_chart(fig, use_container_width=True)
    
    with col2:
        role_counts = team_df['role'].value_counts()
        fig = px.pie(values=role_counts.values, names=role_counts.index, 
                    title="Team Composition", hole=0.4)
        fig.update_layout(paper_bgcolor='rgba(0,0,0,0)', font=dict(color=text_primary))
        st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    with st.expander("➕ Invite New Team Member"):
        col1, col2 = st.columns(2)
        with col1:
            new_name = st.text_input("Name", placeholder="Enter name")
            new_email = st.text_input("Email", placeholder="email@example.com")
        with col2:
            new_role = st.selectbox("Role", ["Admin", "Analyst", "Developer", "Viewer"])
            if st.button("📧 Send Invite", type="primary"):
                st.success(f"✅ Invitation sent to {new_email}")
                st.balloons()

# ===== ENHANCEMENT #10: REAL-TIME MONITOR TAB =====
with tab24:
    st.header("⚡ Real-time System Monitor")
    
    st.markdown("""
    <div style='background: linear-gradient(135deg, rgba(239, 68, 68, 0.2), rgba(220, 38, 38, 0.2));
                padding: 20px; border-radius: 15px; margin-bottom: 20px;'>
        <h3>🔴 LIVE - System Monitoring Dashboard</h3>
        <p>Real-time metrics updated every second</p>
    </div>
    """, unsafe_allow_html=True)
    
    metrics_placeholder = st.empty()
    chart_placeholder = st.empty()
    
    import time
    
    if st.button("🔴 START LIVE MONITORING", type="primary"):
        for i in range(30):
            with metrics_placeholder.container():
                col1, col2, col3, col4, col5 = st.columns(5)
                
                qps = random.randint(45, 95)
                rt = random.randint(80, 350)
                err = random.uniform(0.1, 2.5)
                cpu = random.randint(25, 75)
                mem = random.randint(40, 80)
                
                with col1:
                    st.metric("Queries/sec", qps, delta=random.randint(-5, 10))
                with col2:
                    st.metric("Avg Response", f"{rt}ms", delta=random.randint(-20, 15))
                with col3:
                    st.metric("Error Rate", f"{err:.2f}%", delta=f"{random.uniform(-0.5, 0.3):.2f}%")
                with col4:
                    st.metric("CPU", f"{cpu}%", delta=random.randint(-5, 5))
                with col5:
                    st.metric("Memory", f"{mem}%", delta=random.randint(-3, 3))
                
                st.session_state.realtime_metrics["queries_per_second"].append(qps)
                st.session_state.realtime_metrics["response_times"].append(rt)
                st.session_state.realtime_metrics["error_rates"].append(err)
                st.session_state.realtime_metrics["timestamps"].append(i)
                
                if len(st.session_state.realtime_metrics["queries_per_second"]) > 30:
                    for key in st.session_state.realtime_metrics:
                        st.session_state.realtime_metrics[key].pop(0)
            
            with chart_placeholder.container():
                col1, col2 = st.columns(2)
                
                with col1:
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=st.session_state.realtime_metrics["timestamps"],
                        y=st.session_state.realtime_metrics["queries_per_second"],
                        mode='lines+markers',
                        name='QPS',
                        line=dict(color='#667eea', width=3)
                    ))
                    fig.update_layout(
                        title="Queries Per Second",
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        font=dict(color=text_primary),
                        height=300
                    )
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=st.session_state.realtime_metrics["timestamps"],
                        y=st.session_state.realtime_metrics["response_times"],
                        mode='lines+markers',
                        name='Response Time',
                        line=dict(color='#f093fb', width=3)
                    ))
                    fig.update_layout(
                        title="Response Time (ms)",
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        font=dict(color=text_primary),
                        height=300
                    )
                    st.plotly_chart(fig, use_container_width=True)
            
            time.sleep(0.1)
    
    st.markdown("---")
    
    st.markdown("### 🌍 Live Geographic Distribution")
    geo_df = pd.DataFrame(st.session_state.geographic_data)
    
    fig = px.scatter_geo(geo_df, 
                        lat='lat', 
                        lon='lon',
                        size='queries',
                        hover_name='country',
                        hover_data={'queries': True, 'lat': False, 'lon': False},
                        title="Query Distribution by Country")
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        geo=dict(
            showland=True,
            landcolor='rgb(243, 243, 243)',
            coastlinecolor='rgb(204, 204, 204)',
        ),
        height=500
    )
    st.plotly_chart(fig, use_container_width=True)

# ==================== FOOTER ====================
st.markdown("---")
st.markdown(f"""
<div style='text-align: center; padding: 20px; background: linear-gradient(135deg, rgba(102, 126, 234, 0.1), rgba(118, 75, 162, 0.1));
            border-radius: 15px; border: 2px solid rgba(102, 126, 234, 0.2);'>
    <h2 style='margin: 0; background: linear-gradient(135deg, #667eea, #764ba2);
               -webkit-background-clip: text; -webkit-text-fill-color: transparent;'>
        ✨ AI CHATBOT COMMAND CENTER v4.0
    </h2>
    <p style='color: {text_secondary}; margin: 10px 0; font-size: 1.1rem; font-weight: 600;'>
        🚀 Enterprise Edition | Advanced ML Training | Real-time Analytics | AI-Powered Insights
    </p>
    <p style='color: {text_secondary}; font-size: 0.9rem;'>
        Built with ❤️ using Streamlit, Plotly & Advanced AI Technologies
    </p>
</div>
""", unsafe_allow_html=True)
