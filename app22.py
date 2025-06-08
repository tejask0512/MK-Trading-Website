from flask import Flask, render_template, jsonify, send_from_directory, request, redirect, url_for, session, flash
import subprocess
import pandas as pd
import threading
import time
import os
import sqlite3
import re
import hashlib
import secrets
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import razorpay
import json
from datetime import datetime, timedelta
import uuid
from dotenv import load_dotenv
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine
import os

load_dotenv() 



DEVELOPMENT_MODE = os.getenv("DEVELOPMENT_MODE", "true").lower() == "true"  # Set to False when going to production with Razorpay
print(DEVELOPMENT_MODE)

# Razorpay configuration (replace with your actual keys)
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

app = Flask(__name__, template_folder="templates", static_folder="static")

init_db()
# Secret key for session management
app.secret_key = "Tejas@0514"
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL", "postgresql://user:password@localhost:5432/mktrading")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

# Absolute paths to scripts and data
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

SCRAPER_PATH = os.path.join(BASE_DIR, "scraper.py")
print(f"THis is the {SCRAPER_PATH}")
SENTIMENT_PATH = os.path.join(BASE_DIR, "sentiment_analysis_pipeline.py")
print(f"This is sentiment path {SENTIMENT_PATH}")
SENTIMENT_RESULTS = os.path.join(DATA_DIR, "sentiment_results.csv")
USER_DB = os.path.join(DATA_DIR, "user.db")

# User authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

# Subscription check decorator
def subscription_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login', next=request.url))
        
        # Check if user has an active subscription
        conn = sqlite3.connect(USER_DB)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT us.id FROM user_subscriptions us
            WHERE us.user_id = ? AND us.is_active = 1 AND us.expiry_date > ?
        """, (session["user_id"], datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        subscription = cursor.fetchone()
        conn.close()
        
        if not subscription:
            flash("This feature requires an active subscription. Please subscribe to access this content.", "error")
            return redirect(url_for('subscription_menu'))  # Changed from subscription_plans to subscription_menu
        
        return f(*args, **kwargs)
    return decorated_function

# Password utility functions
def is_valid_password(password):
    """Check if password meets complexity requirements"""
    # At least 8 chars, 1 uppercase, 1 lowercase, 1 digit, 1 special character
    if len(password) < 8:
        return False
    if not re.search(r'[A-Z]', password):
        return False
    if not re.search(r'[a-z]', password):
        return False
    if not re.search(r'[0-9]', password):
        return False
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return False
    return True

def is_valid_email(email):
    """Check if email has valid format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def is_valid_phone(phone):
    if len(phone)==10:
        return True
    return False

# Initialize database
def init_db():
    conn = sqlite3.connect(USER_DB)
    cursor = conn.cursor()
    session=db.session
    
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            phone INTEGER UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        )
    ''')
    
    # Create subscription plans table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscription_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            duration_days INTEGER NOT NULL,
            features TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create user subscriptions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            plan_id INTEGER NOT NULL,
            transaction_id TEXT,
            payment_method TEXT,
            payment_details TEXT,
            start_date TIMESTAMP,
            expiry_date TIMESTAMP,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (plan_id) REFERENCES subscription_plans (id)
        )
    ''')
    
    # Create payment transactions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payment_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            razorpay_order_id TEXT,
            razorpay_payment_id TEXT,
            razorpay_signature TEXT,
            amount REAL,
            currency TEXT,
            status TEXT,
            payment_method TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Check if subscription plans exist, if not, insert default plans
    cursor.execute("SELECT COUNT(*) FROM subscription_plans")
    count = cursor.fetchone()[0]
    
    if count == 0:
    # Insert default subscription plans
    plans = [
        ("Basic", "Access to news and dashboard only", 5000, 30, "News Access, Dashboard Access"),
        ("Premium Monthly", "Complete access with priority support", 10000, 30, "News Access, Dashboard Access, BTC Livechart, Priority Support, Premium Updates"),
        ("Premium Quarterly", "Complete access with priority support for 3 months", 27000, 90, "News Access, Dashboard Access, BTC Livechart, Priority Support, Premium Updates"),
        ("Premium Annual", "Complete access with priority support for 12 months", 100000, 365, "News Access, Dashboard Access, BTC Livechart, Priority Support, Premium Updates")
    ]
    
    cursor.executemany('''
        INSERT INTO subscription_plans (name, description, price, duration_days, features)
        VALUES (?, ?, ?, ?, ?)
    ''', plans)
    

    
    conn.commit()
    conn.close()

# Initialize database on startup
init_db()


@app.route('/test-db')
def test_db():
    try: 
        from models.base import engine
        with engine.connect() as connection:
            return {"status":"success","message":"Database connection successful!"}
    except Exception as e:
        return {"status":"error","messsage":str(e)}

# Background task to run scraper and sentiment analysis
def run_scraper_and_sentiment_analysis():
    """Runs scraper and sentiment analysis every 30 minutes."""
    while True:
        try:
            print("Running scraper...")
            subprocess.run(["python", SCRAPER_PATH], check=True)

            print("Running sentiment analysis pipeline...")
            subprocess.run(["python", SENTIMENT_PATH], check=True)

            print("Data updated successfully.")
        except Exception as e:
            print(f"Error updating data: {e}")

        # Wait before running again (every 30 minutes)
        time.sleep(1800)

# Start background thread for data processing
threading.Thread(target=run_scraper_and_sentiment_analysis, daemon=True).start()

# Helper function to check if user has active subscription
def check_subscription(user_id):
    conn = sqlite3.connect(USER_DB)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT us.id, sp.name, us.expiry_date 
        FROM user_subscriptions us
        JOIN subscription_plans sp ON us.plan_id = sp.id
        WHERE us.user_id = ? AND us.is_active = 1 AND us.expiry_date > ?
    """, (user_id, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    subscription = cursor.fetchone()
    conn.close()
    
    if subscription:
        return {
            "has_subscription": True,
            "plan_name": subscription[1],
            "expiry_date": subscription[2]
        }
    return {"has_subscription": False}

@app.route("/subscription/checkout/<int:plan_id>")
@login_required
def subscription_checkout(plan_id):
    """Handle checkout process for subscription plans"""
    try:
        # Get plan details
        conn = sqlite3.connect(USER_DB)
        cursor = conn.cursor()
        cursor.execute("SELECT name, description, price, duration_days FROM subscription_plans WHERE id = ?", (plan_id,))
        plan = cursor.fetchone()
        conn.close()
        
        if not plan:
            flash("Selected plan not found", "error")
            return redirect(url_for("subscription_plans"))
        
        plan_data = {
            "id": plan_id,
            "name": plan[0],
            "description": plan[1],
            "price": plan[2],
            "duration_days": plan[3]
        }
        
        # Store plan_id in session for both modes
        session['plan_id'] = plan_id
        
        # Development Mode - Use test payment page
        if DEVELOPMENT_MODE:
            return render_template('test_payment.html',
                                  plan=plan_data,
                                  user_name=session.get("user_name"),
                                  user_email=session.get("user_email"))
        
        # Production Mode - Use Razorpay
        else:
            # Create Razorpay order
            order_amount = int(plan_data["price"] * 100)  # Convert to paise
            order_currency = 'INR'
            receipt_id = f"sub_{session['user_id']}_{int(time.time())}"
            
            order_data = {
                'amount': order_amount,
                'currency': order_currency,
                'receipt': receipt_id,
                'payment_capture': 1
            }
            
            order = razorpay_client.order.create(data=order_data)
            session['razorpay_order_id'] = order['id']
            
            return render_template('payment.html',
                                  plan=plan_data,
                                  razorpay_key_id=RAZORPAY_KEY_ID,
                                  order_id=order['id'],
                                  amount=order_amount,
                                  currency=order_currency,
                                  user_name=session.get("user_name"),
                                  user_email=session.get("user_email"))
    
    except Exception as e:
        print(f"Error in checkout: {str(e)}")
        flash(f"There was a problem processing your request. Please try again.", "error")
        return redirect(url_for("subscription_plans"))

# Routes
@app.route('/')
def home():
    # Check if user is already logged in
    if "user_id" in session:  
        return redirect(url_for('mainpage'))  # Go directly to mainpage
    
    # Check if this is a new visitor or a returning visitor
    if session.get('visited_before'):
        # Not a first-time visitor, go to login
        return redirect(url_for('login'))
    else:
        # Mark the user as having visited before
        session['visited_before'] = True
        # First-time visitor, go to registration
        return redirect(url_for('register'))

@app.route("/mainpage")
@login_required
def mainpage():
    # Get subscription info but don't redirect if not subscribed
    subscription_info = check_subscription(session["user_id"])
    
    return render_template("mainpage.html", 
                          user_name=session.get("user_name"), 
                          current_user=session,
                          subscription_info=subscription_info)



@app.route("/dashboard")
@login_required
@subscription_required
def dashboard():
    return render_template("dashboard.html", user_name=session.get("user_name"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        
        conn = sqlite3.connect(USER_DB)
        cursor = conn.cursor()
        cursor.execute("SELECT id, password_hash, name FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()
        
        if user and check_password_hash(user[1], password):
            session["user_id"] = user[0]
            session["user_name"] = user[2]
            session["user_email"] = email
            
            # Update last login time
            conn = sqlite3.connect(USER_DB)
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?", (user[0],))
            conn.commit()
            conn.close()
            
            # Check if user has subscription
            subscription_info = check_subscription(user[0])
            if not subscription_info["has_subscription"]:
                flash("Welcome back! Please subscribe to access our premium features", "info")
                return redirect(url_for("subscription_menu"))
            
            # Redirect to dashboard
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)
            return redirect(url_for("mainpage"))
        else:
            flash("Invalid email or password", "error")
    
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    # Check if user is already logged in
    if "user_id" in session:
        return redirect(url_for('mainpage'))  # User is logged in, go to dashboard
        
    if request.method == "POST":
        email = request.form.get("email")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")
        username = request.form.get("username")
        phone=request.form.get("phone")
        
        # Validate input
        if not all([email, phone, password, confirm_password, username]):
            flash("All fields are required", "error")
            return render_template("register.html")
        if not is_valid_phone(phone):
            flash("PLease Enter Valid Phone Number")
            return render_template("register.html")
        
        if not is_valid_email(email):
            flash("Invalid email format", "error")
            return render_template("register.html")
        
        if password != confirm_password:
            flash("Passwords do not match", "error")
            return render_template("register.html")
        
        if not is_valid_password(password):
            flash("Password should be at least 8 characters with at least 1 uppercase letter, 1 lowercase letter, 1 digit, and 1 special character", "error")
            return render_template("register.html")
        
        # Check if email already exists
        conn = sqlite3.connect(USER_DB)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        existing_user = cursor.fetchone()
        
        if existing_user:
            conn.close()
            flash("Email already registered", "error")
            return render_template("register.html")
        
        # Create new user
        password_hash = generate_password_hash(password)
        cursor.execute("INSERT INTO users (email, phone, password_hash, name) VALUES (?, ?, ?, ?)", 
                      (email, phone, password_hash, username))
        conn.commit()
        
        # Get the new user ID
        user_id = cursor.lastrowid
        conn.close()
        
        # Log in the user and redirect to subscription page
        session["user_id"] = user_id
        session["user_name"] = username
        session["user_email"] = email
        
        flash("Registration successful! Please subscribe to access our premium features.", "success")
        return redirect(url_for("subscription_menu"))
    
    return render_template("register.html")

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("user_name", None)
    session.pop("user_email", None)
    flash("You have been logged out", "info")
    return redirect(url_for("login"))



@app.route("/subscription/menu")
@login_required
def subscription_menu():
    """Renders the subscription menu page."""
    # Get subscription info
    subscription_info = check_subscription(session["user_id"])
    
    # Get available plans
    conn = sqlite3.connect(USER_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, description, price, duration_days, features FROM subscription_plans")
    plans = cursor.fetchall()
    conn.close()
    
    formatted_plans = []
    for plan in plans:
        plan_features = plan[5].split(',') if plan[5] else []
        formatted_plans.append({
            "id": plan[0],
            "name": plan[1],
            "description": plan[2],
            "price": plan[3],
            "duration_days": plan[4],
            "features": plan_features
        })
    
    return render_template("subscription_menu.html", 
                          plans=formatted_plans,
                          subscription_info=subscription_info,
                          user_name=session.get("user_name"))

@app.route("/profile")
@login_required
def profile():
    conn = sqlite3.connect(USER_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT email, name, created_at, last_login FROM users WHERE id = ?", (session["user_id"],))
    user = cursor.fetchone()
    
    # Get subscription info
    cursor.execute("""
        SELECT sp.name, us.start_date, us.expiry_date 
        FROM user_subscriptions us
        JOIN subscription_plans sp ON us.plan_id = sp.id
        WHERE us.user_id = ? AND us.is_active = 1 AND us.expiry_date > ?
        ORDER BY us.expiry_date DESC LIMIT 1
    """, (session["user_id"], datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    subscription = cursor.fetchone()
    conn.close()
    
    if not user:
        flash("User not found", "error")
        return redirect(url_for("login"))
    
    user_data = {
        "email": user[0],
        "name": user[1],
        "created_at": user[2],
        "last_login": user[3],
        "has_subscription": subscription is not None
    }
    
    if subscription:
        user_data["subscription"] = {
            "plan_name": subscription[0],
            "start_date": subscription[1],
            "expiry_date": subscription[2]
        }
    
    return render_template("profile.html", user_data=user_data)

@app.route("/reset_password", methods=["GET", "POST"])
@login_required
def reset_password():
    if request.method == "POST":
        current_password = request.form.get("current_password")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")
        
        # Validate input
        if not all([current_password, new_password, confirm_password]):
            flash("All fields are required", "error")
            return render_template("reset_password.html")
        
        if new_password != confirm_password:
            flash("New passwords do not match", "error")
            return render_template("reset_password.html")
        
        if not is_valid_password(new_password):
            flash("Password should be at least 8 characters with at least 1 uppercase letter, 1 lowercase letter, 1 digit, and 1 special character", "error")
            return render_template("reset_password.html")
        
        # Verify current password
        conn = sqlite3.connect(USER_DB)
        cursor = conn.cursor()
        cursor.execute("SELECT password_hash FROM users WHERE id = ?", (session["user_id"],))
        stored_password_hash = cursor.fetchone()[0]
        
        if not check_password_hash(stored_password_hash, current_password):
            conn.close()
            flash("Current password is incorrect", "error")
            return render_template("reset_password.html")
        
        # Update password
        new_password_hash = generate_password_hash(new_password)
        cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", 
                      (new_password_hash, session["user_id"]))
        conn.commit()
        conn.close()
        
        flash("Password updated successfully", "success")
        return redirect(url_for("profile"))
    
    return render_template("reset_password.html")

@app.route("/settings")
@login_required
def settings():
    conn = sqlite3.connect(USER_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT email, name FROM users WHERE id = ?", (session["user_id"],))
    user_data = cursor.fetchone()
    conn.close()
    
    if not user_data:
        flash("User not found", "error")
        return redirect(url_for("login"))
    
    user = {
        "email": user_data[0],
        "name": user_data[1]
    }
    
    return render_template("settings.html", user=user)

@app.route("/update_settings", methods=["POST"])
@login_required
def update_settings():
    new_name = request.form.get("name")
    email = request.form.get("email")
    
    if not new_name or not email:
        flash("Name and email are required", "error")
        return redirect(url_for("settings"))
    
    if not is_valid_email(email):
        flash("Invalid email format", "error")
        return redirect(url_for("settings"))
    
    # Check if email already exists (for other users)
    conn = sqlite3.connect(USER_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE email = ? AND id != ?", (email, session["user_id"]))
    existing_user = cursor.fetchone()
    
    if existing_user:
        conn.close()
        flash("Email already in use by another account", "error")
        return redirect(url_for("settings"))
    
    # Update user info
    cursor.execute("UPDATE users SET name = ?, email = ? WHERE id = ?", 
                  (new_name, email, session["user_id"]))
    conn.commit()
    conn.close()
    
    # Update session
    session["user_name"] = new_name
    session["user_email"] = email
    
    flash("Settings updated successfully", "success")
    return redirect(url_for("settings"))

# Subscription system routes
@app.route("/subscription/plans")
@login_required
def subscription_plans():
    conn = sqlite3.connect(USER_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, description, price, duration_days, features FROM subscription_plans")
    plans = cursor.fetchall()
    
    # Check if user already has an active subscription
    cursor.execute("""
        SELECT sp.id, sp.name, us.expiry_date 
        FROM user_subscriptions us
        JOIN subscription_plans sp ON us.plan_id = sp.id
        WHERE us.user_id = ? AND us.is_active = 1 AND us.expiry_date > ?
    """, (session["user_id"], datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    active_subscription = cursor.fetchone()
    conn.close()
    
    formatted_plans = []
    for plan in plans:
        plan_features = plan[5].split(',') if plan[5] else []
        formatted_plans.append({
            "id": plan[0],
            "name": plan[1],
            "description": plan[2],
            "price": plan[3],
            "duration_days": plan[4],
            "features": plan_features
        })
    
    return render_template("subscription_plans.html", 
                          plans=formatted_plans, 
                          active_subscription=active_subscription,
                          user_name=session.get("user_name"))


    
@app.route("/subscription/test_payment", methods=["POST"])
@login_required
def test_payment():
    """Process test payments (development mode only)"""
    if not DEVELOPMENT_MODE:
        return redirect(url_for("subscription_plans"))
    
    try:
        # Get plan details
        plan_id = session.get('plan_id')
        if not plan_id:
            flash("Plan information not found. Please try again.", "error")
            return redirect(url_for("subscription_plans"))
        
        conn = sqlite3.connect(USER_DB)
        cursor = conn.cursor()
        
        # Get plan details
        cursor.execute("SELECT name, price, duration_days FROM subscription_plans WHERE id = ?", (plan_id,))
        plan_data = cursor.fetchone()
        if not plan_data:
            conn.close()
            flash("Plan not found. Please try again.", "error")
            return redirect(url_for("subscription_plans"))
        
        plan_name, plan_price, plan_duration = plan_data
        
        # Generate mock payment details
        mock_payment_id = f"test_{uuid.uuid4().hex[:10]}"
        mock_order_id = f"order_{uuid.uuid4().hex[:10]}"
        
        # Record payment transaction
        cursor.execute("""
            INSERT INTO payment_transactions 
            (user_id, razorpay_order_id, razorpay_payment_id, razorpay_signature, amount, currency, status, payment_method)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session["user_id"],
            mock_order_id,
            mock_payment_id,
            "test_signature",
            plan_price,
            "INR",
            "captured",
            "test_payment"
        ))
        
        # Deactivate existing subscriptions
        cursor.execute("""
            UPDATE user_subscriptions
            SET is_active = 0
            WHERE user_id = ? AND is_active = 1
        """, (session["user_id"],))
        
        # Calculate subscription dates
        start_date = datetime.now()
        expiry_date = start_date + timedelta(days=plan_duration)
        
        # Create new subscription
        cursor.execute("""
            INSERT INTO user_subscriptions 
            (user_id, plan_id, transaction_id, payment_method, start_date, expiry_date, is_active)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        """, (
            session["user_id"],
            plan_id,
            mock_payment_id,
            "test_payment",
            start_date.strftime('%Y-%m-%d %H:%M:%S'),
            expiry_date.strftime('%Y-%m-%d %H:%M:%S')
        ))
        
        conn.commit()
        conn.close()
        
        # Clear session data
        session.pop('plan_id', None)
        
        flash("Test payment successful! Your subscription is now active.", "success")
        return redirect(url_for("payment_success"))
        
    except Exception as e:
        print(f"Error in test payment: {str(e)}")
        flash("An error occurred during the test payment. Please try again.", "error")
        return redirect(url_for("subscription_plans"))

@app.route("/subscription/process_payment", methods=["POST"])
@login_required
def process_payment():
    try:
        # Get payment details from the form
        razorpay_payment_id = request.form.get('razorpay_payment_id')
        razorpay_order_id = request.form.get('razorpay_order_id')
        razorpay_signature = request.form.get('razorpay_signature')
        
        # Verify payment signature
        params_dict = {
            'razorpay_order_id': razorpay_order_id,
            'razorpay_payment_id': razorpay_payment_id,
            'razorpay_signature': razorpay_signature
        }
        
        # Verify the payment signature
        razorpay_client.utility.verify_payment_signature(params_dict)
        
        # Get payment details from Razorpay
        payment = razorpay_client.payment.fetch(razorpay_payment_id)
        
        # Get plan details
        plan_id = session.get('plan_id')
        if not plan_id:
            flash("Plan information not found. Please try again.", "error")
            return redirect(url_for("subscription_plans"))
        
        conn = sqlite3.connect(USER_DB)
        cursor = conn.cursor()
        
        # Get plan duration
        cursor.execute("SELECT duration_days FROM subscription_plans WHERE id = ?", (plan_id,))
        plan_duration = cursor.fetchone()[0]
        
        # Record payment in database
        cursor.execute("""
            INSERT INTO payment_transactions 
            (user_id, razorpay_order_id, razorpay_payment_id, razorpay_signature, amount, currency, status, payment_method)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session["user_id"],
            razorpay_order_id,
            razorpay_payment_id,
            razorpay_signature,
            payment['amount'] / 100,  # Convert paise to rupees
            payment['currency'],
            payment['status'],
            payment.get('method', 'unknown')
        ))
        
        # Deactivate existing active subscriptions
        cursor.execute("""
            UPDATE user_subscriptions
            SET is_active = 0
            WHERE user_id = ? AND is_active = 1
        """, (session["user_id"],))
        
        # Calculate subscription start and end dates
        start_date = datetime.now()
        expiry_date = start_date + timedelta(days=plan_duration)
        
        # Create new subscription
        cursor.execute("""
            INSERT INTO user_subscriptions 
            (user_id, plan_id, transaction_id, payment_method, start_date, expiry_date, is_active)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        """, (
            session["user_id"],
            plan_id,
            razorpay_payment_id,
            payment.get('method', 'unknown'),
            start_date.strftime('%Y-%m-%d %H:%M:%S'),
            expiry_date.strftime('%Y-%m-%d %H:%M:%S')
        ))
        
        conn.commit()
        conn.close()
        
        # Clear the session variables
        session.pop('razorpay_order_id', None)
        session.pop('plan_id', None)
        
        flash("Payment successful! Your subscription is now active.", "success")
        return redirect(url_for("payment_success"))
        
    except Exception as e:
        flash(f"Payment verification failed: {str(e)}", "error")
        return redirect(url_for("payment_failure"))

@app.route("/subscription/payment/success")
@login_required
def payment_success():
    # Get the user's active subscription details
    conn = sqlite3.connect(USER_DB)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT sp.name, us.expiry_date 
        FROM user_subscriptions us
        JOIN subscription_plans sp ON us.plan_id = sp.id
        WHERE us.user_id = ? AND us.is_active = 1
        ORDER BY us.created_at DESC LIMIT 1
    """, (session["user_id"],))
    subscription = cursor.fetchone()
    conn.close()
    
    if not subscription:
        return redirect(url_for("subscription_plans"))
    
    subscription_data = {
        "plan_name": subscription[0],
        "expiry_date": subscription[1]
    }
    
    return render_template("payment_success.html", 
                          subscription=subscription_data,
                          user_name=session.get("user_name"))

@app.route("/subscription/payment/failure")
@login_required
def payment_failure():
    return render_template("payment_failure.html", user_name=session.get("user_name"))

@app.route("/subscription/history")
@login_required
def subscription_history():
    conn = sqlite3.connect(USER_DB)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT sp.name, us.start_date, us.expiry_date, us.is_active, us.transaction_id, us.payment_method
        FROM user_subscriptions us
        JOIN subscription_plans sp ON us.plan_id = sp.id
        WHERE us.user_id = ?
        ORDER BY us.created_at DESC
    """, (session["user_id"],))
    subscriptions = cursor.fetchall()
    conn.close()
    
    subscription_history = []
    for sub in subscriptions:
        subscription_history.append({
            "plan_name": sub[0],
            "start_date": sub[1],
            "expiry_date": sub[2],
            "is_active": sub[3] == 1,
            "transaction_id": sub[4],
            "payment_method": sub[5]
        })
    
    return render_template("subscription_history.html", 
                          subscriptions=subscription_history,
                          user_name=session.get("user_name"))

# Trading livechart route (now protected by subscription)
@app.route("/TradingLivechart-Development.html")
@login_required
@subscription_required
def trading_livechart():
    """Renders the trading livechart."""
    return render_template("TradingLivechart-Development.html")

@app.route("/faq")
@login_required
def faq():
    """Renders the FAQ page."""
    return render_template("faq.html")

@app.route("/policy")
@login_required
def policy():
    """Renders the privacy policy page."""
    return render_template("privacypolicy.html")

# Stock news impact dashboard route (protected by subscription)
@app.route("/StockNewsImpact.html")
@login_required
@subscription_required
def stock_news_impact():
    """Renders the stock news impact dashboard."""
    return render_template("StockNewsImpact.html")

# API endpoint for news data (protected by subscription)
@app.route("/api/news")
@login_required
@subscription_required
def get_news():
    """Returns the latest news from sentiment_results.csv."""
    if not os.path.exists(SENTIMENT_RESULTS):
        return jsonify({"error": "Sentiment results file not found"}), 500

    df = pd.read_csv(SENTIMENT_RESULTS).fillna("")
    news_data = df.to_dict(orient="records")

    return jsonify({"news": news_data})

# Serve static files
@app.route("/static/<path:path>")
def serve_static(path):
    return send_from_directory("static", path)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8000)