import sqlite3
import hashlib
import re      
import html
import requests
import os
import secrets
from dotenv import load_dotenv
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, render_template, request, flash, make_response, redirect, url_for, jsonify, abort
from flask_limiter import Limiter

load_dotenv()
from authlib.integrations.flask_client import OAuth
import jwt
from flask import session

app = Flask(__name__)



oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    api_base_url='https://www.googleapis.com/oauth2/v1/',
    client_kwargs={'scope': 'openid email profile'}
)
# Siri kwa ajili ya kusaini JWT tokens na usalama wa Flask
JWT_SECRET = os.getenv("JWT_SECRET")
app.config["SECRET_KEY"] =os.getenv("SECRET_KEY")

# Tunaanzisha limiter
limiter = Limiter(app)

# ===== DATABASE PATH =====
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "users.db")

# ===== FLASK-MAIL CONFIGURATION =====
def send_otp_via_api(email, otp):
    api_key = os.environ.get("RESEND_API_KEY")
    
    # Debug: Hii itakuambia kwenye Logs kama Key imesoma au la
    print(f"DEBUG: API Key exists: {bool(api_key)}")
    
    if not api_key:
        print("DEBUG: RESEND_API_KEY is missing in Environment Variables!")
        return False

    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "from": "onboarding@resend.dev", 
        "to": email,
        "subject": "Your Reset Code",
        "html": f"<p>Hello, your reset code from mr karume is: <strong>{otp}</strong>. It expires in 10 minutes.</p>"
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        # Debug: Hii itakuambia response kutoka Resend
        print(f"DEBUG: Resend Status Code: {response.status_code}")
        print(f"DEBUG: Resend Response: {response.text}")
        
        return response.status_code == 200
    except Exception as e:
        print(f"DEBUG: Exception during API call: {str(e)}")
        return False
        
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax', # Lax inaruhusu Google callback kufanya kazi
    SESSION_COOKIE_SECURE=False,   # Weka False ukiwa localhost (True ukiwa kwenye HTTPS)
    SESSION_TYPE='filesystem'
)


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            reset_code TEXT,
            code_expiry TEXT,
            current_level INTEGER DEFAULT 6,
            failed_attempts INTEGER DEFAULT 0,
            lockout_time TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# Maudhui ya Masomo ya Darasani
lessons = [
    {"id": 1, "title": "Intro to Hacking", "content": "Misingi ya udukuzi na maadili ya ki-cybersecurity."},
    {"id": 2, "title": "Web Security Basics", "content": "Jinsi ya kulinda na kuvunja mifumo ya tovuti."},
    {"id": 3, "title": "SQL Injection (SQLi)", "content": "Kuingiza amri haramu kwenye fomu ili kusoma database."},
    {"id": 4, "title": "Cross-Site Scripting (XSS)", "content": "Kuingiza kodi za JavaScript kwenye kivinjari cha muathirika."},
    {"id": 5, "title": "Broken Access Control (IDOR)", "content": "Kuvunja ulinzi wa akaunti kwa kubadili ID kwenye URL."},
    {"id": 6, "title": "Network Sniffing & Wireshark", "content": "Kunasha data zinazotembea hewani au kwenye mawasiliano ya mawimbi."}
]

ADMIN_PASSKEY = "tuwa"
ADMIN_USERNAME = "bakari_admin"
ADMIN_PASSWORD = "bakari2024"


# ========================================================
# JWT & UTUNZAJI WA TOKENS (COOKIES)
# ========================================================
def generate_token(username, is_admin=False):
    """Inatengeneza JWT Token inayokaa kwa masaa 24"""
    payload = {
        "user": username,
        "is_admin": is_admin,
        "exp": datetime.utcnow() + timedelta(hours=24)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def decode_token(token):
    """Inasoma token na kuhakikisha haijaharibiwa au kuisha muda"""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None

# ========================================================
# DECORATORS ZILIZOBORESHWA KUTUMIA JWT
# ========================================================
# 1. REKEBISHA DECORATOR HII
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.cookies.get("auth_token")
        data = decode_token(token) if token else None

        # Logic sahihi: Kama token haipo, basi login_required
        if not data:
            return redirect(url_for("login"))

        request.current_user = data["user"]
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.cookies.get("auth_token")
        data = decode_token(token) if token else None

        if not data or not data.get("is_admin"):
            abort(404)

        request.current_user = data["user"]
        return f(*args, **kwargs)
    return decorated_function


# ========================================================
# CORE SYSTEM ROUTES (USER FACING)
# ========================================================

@app.route("/")
def home():
    return redirect(url_for("dashboard"))

# ===============================================
#           REGISTER PAGE
# =============================================
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        # 1. Kuchukua data na kuondoa nafasi zilizoachwa wazi (Sanitization ya mwanzo)
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        confirm = request.form.get("confirm_password", "").strip()

        # Uhakiki wa kawaida
        if not username or not email or not password:
            return jsonify({"status": "error", "message": "all fields are required!"})
        if password != confirm:
            return jsonify({"status": "error", "message": "Password mismatch!"})

        # ========================================================
        # 🔥 KIWANGO CHA JUU: KUFUNGA WEAK PASSWORD POLICY
        # ========================================================
        if len(password) < 8:
            return jsonify({"status": "error", "message": "Pasword must contain atleast 8! character"})
        if not re.search(r"[A-Z]", password):
            return jsonify({"status": "error", "message": "Password must contain atlest one capital letter!"})
        if not re.search(r"[a-z]", password):
            return jsonify({"status": "error", "message": "Password must contain atleast one capital letter"})
        if not re.search(r"[0-9]", password):
            return jsonify({"status": "error", "message": "Password must contain number!"})
        if not re.search(r"[@#$%^&*]", password):
            return jsonify({"status": "error", "message": "Password must contain atleast one special character"})

        # ========================================================
        # 🔥 KIWANGO CHA JUU: KUZUIA UN-SANITIZED INPUTS (XSS)
        # ========================================================
        # Tunasafisha jina na email ili kama mtu ameweka kodi za JavaScript (XSS Attack) zisilete madhara
        safe_username = html.escape(username)
        safe_email = html.escape(email)

        hashed_password = hash_password(password)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        try:
            # 🔒 parameterized query (?) inazuia kabisa SQL Injection (SQLi)
            cursor.execute(
                "INSERT INTO users (username, email, password, current_level, failed_attempts) VALUES (?, ?, ?, 6, 0)",
                (safe_username, safe_email, hashed_password)
            )
            conn.commit()
            return jsonify({"status": "success", "redirect": url_for("login")})
        except sqlite3.IntegrityError:
            return jsonify({"status": "error", "message": "Username or email already exists!"})
        finally:
            conn.close()

    return render_template("register.html")

#=======================================
#         LOGIN PAGE
#=======================================

@app.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        hashed_password = hash_password(password)

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("SELECT password, failed_attempts, lockout_time FROM users WHERE email=?", (email,))
        user_record = cursor.fetchone()

        if user_record:
            db_password, failed_attempts, lockout_time = user_record

            if lockout_time:
                lockout_datetime = datetime.strptime(lockout_time, "%Y-%m-%d %H:%M:%S")
                if datetime.now() < lockout_datetime:
                    conn.close()
                    remaining_mins = int((lockout_datetime - datetime.now()).total_seconds() / 60)
                    return jsonify({"status": "error", "message": f"temporary blocked for {remaining_mins} minutes."})
                else:
                    cursor.execute("UPDATE users SET failed_attempts=0, lockout_time=NULL WHERE email=?", (email,))
                    conn.commit()
                    failed_attempts = 0

            if db_password == hashed_password:
                cursor.execute("UPDATE users SET failed_attempts=0, lockout_time=NULL WHERE email=?", (email,))
                conn.commit()
                conn.close()

                token = generate_token(email, is_admin=False)
                response = make_response(jsonify({"status": "success", "redirect": url_for("lesson_list")}))
                
                # REKEBISHO HAPA: Badilisha 'Strict' kuwa 'Lax' ili kuendana na flow ya Google OAuth
                response.set_cookie("auth_token", token, httponly=True, samesite='Lax')
                return response
            
            else:
                failed_attempts += 1
                if failed_attempts >= 5:
                    new_lockout_time = (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
                    cursor.execute("UPDATE users SET failed_attempts=?, lockout_time=? WHERE email=?", (failed_attempts, new_lockout_time, email))
                    message = "Wrong password or email. account is temporarily blocked for 1 hour."
                else:
                    cursor.execute("UPDATE users SET failed_attempts=? WHERE email=?", (failed_attempts, email))
                    message = f"Invalid credential. remain {5 - failed_attempts}. attempts"

                conn.commit()
                conn.close()
                return jsonify({"status": "error", "message": message})
        else:
            conn.close()
            return jsonify({"status": "error", "message": "Invalid credentials."})

    return render_template("login.html")

#====================================================
#    GOOGLE OAUTH LOGIN ROUTES
#====================================================



@app.route('/login/google')
def login_google():
    # prompt='select_account' inamlazimisha mtumiaji kuchagua akaunti kila wakati
    return google.authorize_redirect(
        url_for('authorize_google', _external=True),
        prompt='select_account'
    )


from requests.exceptions import ConnectionError

@app.route('/login/google/callback')
def authorize_google():
    try:
        token = google.authorize_access_token()
        resp = google.get('userinfo')
        user_info = resp.json()

    except ConnectionError:
        return "Network error during Google login. Please try again.", 503

    except Exception as e:
        return f"Google login failed: {str(e)}", 500

    email = user_info.get('email')
    name = user_info.get('name')

    if not email:
        return "Hitilafu: Hatukuweza kupata barua pepe yako.", 400
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT username FROM users WHERE email=?", (email,))
    user = cursor.fetchone()
    
    if user:
        username = user[0]
    else:
        # User mpya
        username = name.replace(" ", "_").lower() if name else email.split('@')[0]
        hashed_password = hash_password(secrets.token_hex(16))
        try:
            cursor.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)", 
                           (username, email, hashed_password))
            conn.commit()
        except:
            username = f"{username}_{secrets.token_hex(2)}"
            cursor.execute("INSERT INTO users (username, email, password) VALUES (?, ?, ?)", 
                           (username, email, hashed_password))
            conn.commit()
    conn.close()
    
    # 3. SET COOKIE KWA KUTUMIA LAX
    token = generate_token(username, is_admin=False)
    response = make_response(redirect(url_for("lesson_list")))
    response.set_cookie("auth_token", token, httponly=True, samesite='Lax')
    
    return response

# 4. HAKIKISHA KWENYE LOGIN YA KAWAIDA UNAFANYA HIVI:
# response.set_cookie("auth_token", token, httponly=True, samesite='Lax')

    #=======================================================
    #           FORGOT PASSWORD & OTP VERIFICATION
    #=======================================================


@app.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("5 per minute")
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip()

        if not email:
            flash("Email is required")
            return render_template("forgot_password.html")

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email=?", (email,))
        user = cursor.fetchone()

        # 🔥 UKUTA WA KIUSALAMA (Enumeration Prevented): Hatuonyeshi kama email ipo au haipo!
        if not user:
            conn.close()
            flash("We have sent otp to your Email if Exist")
            return render_template("forgot_password.html")

        verification_code = str(secrets.randbelow(900000) + 100000)
        expiry_time = (datetime.now() + timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute("UPDATE users SET reset_code=?, code_expiry=? WHERE email=?", (verification_code, expiry_time, email))
        conn.commit()
        conn.close()

        try:
            msg = Message("reset code OTP ", recipients=[email])
            msg.body = f"hello your reset code is: \n{verification_code}.\n it expires in 10 minutes."
            mail.send(msg)

            payload = {"reset_email": email, "otp_verified": False, "exp": datetime.utcnow() + timedelta(minutes=15)}
            reset_token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")

            response = make_response(redirect(url_for("verify_otp")))
            response.set_cookie("reset_token", reset_token, httponly=True, samesite='Strict')
            return response

        except Exception as e:
            flash(f"Poor network connection: {str(e)}")
            return render_template("forgot_password.html")

    return render_template("forgot_password.html")



    #========================================================
    #           OTP VERIFICATION & PASSWORD CHANGE  
    #========================================================


@app.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    r_token = request.cookies.get("reset_token")
    r_data = decode_token(r_token) if r_token else None

    if not r_data or "reset_email" not in r_data:
        return redirect(url_for("forgot_password"))

    email = r_data["reset_email"]

    if request.method == "POST":
        otp_entered = request.form.get("otp", "").strip()

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT reset_code, code_expiry FROM users WHERE email=?", (email,))
        user = cursor.fetchone()

        if not user:
            conn.close()
            return "User does not exist!"

        db_code, db_expiry = user[0], user[1]

        if db_code != otp_entered:
            conn.close()
            return "Invalid OTP code!"

        current_time = datetime.now()
        expiry_datetime = datetime.strptime(db_expiry, "%Y-%m-%d %H:%M:%S")
        if current_time > expiry_datetime:
            conn.close()
            return "OTP expired!"

        conn.close()

        payload = {"reset_email": email, "otp_verified": True, "exp": datetime.utcnow() + timedelta(minutes=10)}
        updated_reset_token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")

        response = make_response(redirect(url_for("change_password")))
        response.set_cookie("reset_token", updated_reset_token, httponly=True, samesite='Strict')
        return response

    return render_template("verify_otp.html", email=email)


    #========================================================
    #           CHANGE PASSWORD PAGE
    #========================================================


@app.route("/change-password", methods=["GET", "POST"])
def change_password():
    r_token = request.cookies.get("reset_token")
    r_data = decode_token(r_token) if r_token else None

    if not r_data or "reset_email" not in r_data or not r_data.get("otp_verified"):
        return redirect(url_for("forgot_password"))

    email = r_data["reset_email"]

    if request.method == "POST":
        new_password = request.form.get("new_password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        if not new_password:
            return "Password is required"
        if new_password != confirm_password:
            return "Passwords do not match"

        hashed_password = hash_password(new_password)

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET password=?, reset_code=NULL, code_expiry=NULL, failed_attempts=0, lockout_time=NULL WHERE email=?", (hashed_password, email))
        conn.commit()
        conn.close()

        response = make_response(redirect(url_for("login")))
        response.delete_cookie("reset_token")
        return response

    return render_template("change_password.html")


# ========================================================
# SECURED PROTECTED CLASSROOM PAGES 🔒
# ========================================================

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", user=request.current_user)


@app.route("/classroom")
@login_required
def lesson_list():
    return render_template("lesson.html", user=request.current_user.upper(), lessons=lessons, current_level=6)


@app.route("/oswap")
@login_required  # 🔥 SHIMO LIFUNGA: Hakuna kuingia bila password!
def oswap():
    return render_template("oswap.html")

@app.route("/services")
@login_required  # 🔥 SHIMO LIFUNGA: Hakuna kuingia bila password
def services():
    return render_template("services.html")

@app.route("/about")
@login_required  # 🔥 SHIMO LIFUNGA: Hakuna kuingia bila password
def about():
    return render_template("about.html")

@app.route("/contact")
@login_required  # 🔥 SHIMO LIFUNGA: Hakuna kuingia bila password
def contact():
    return render_template("contact.html")

@app.route("/advanced")
@login_required  # 🔥 SHIMO LIFUNGA: Hakuna kuingia bila password!
def advanced():
    return render_template("advanced.html")

@app.route("/xss")
@login_required  # 🔥 SHIMO LIFUNGA: Hakuna kuingia bila password!
def xss():
    return render_template("xss.html")


# ========================================================
# THE HIDDEN ADMIN PANEL (JWT BACKED)
# ========================================================

@app.route('/admin')
def fake_admin():
    abort(404)


@app.route('/kigamboni-labs-management', methods=['GET', 'POST'])
def secret_admin_login():
    url_token = request.args.get('passkey')
    if url_token != ADMIN_PASSKEY:
        abort(404)

    error = None
    if request.method == 'POST':
        input_username = request.form.get('username')
        input_password = request.form.get('password')

        if input_username == ADMIN_USERNAME and input_password == ADMIN_PASSWORD:
            token = generate_token(input_username, is_admin=True)
            response = make_response(redirect(url_for('secret_admin_dashboard')))
            response.set_cookie("auth_token", token, httponly=True, samesite='Strict')
            return response
        else:
            error = "server detect your attacker."

    return f'''
    <!DOCTYPE html>
    <html>
    <head><title>🔒 Terminal Alpha Gate</title></head>
    <body style="background:#0d1117; color:#ff7b72; font-family:monospace; padding:50px; text-align:center;">
        <div style="border:1px dashed #da3633; display:inline-block; padding:30px; background:#161b22; border-radius:8px;">
            <h2>⚠️ ROOT CONTROL INTERFACE</h2>
            {f'<p style="color:red;">{error}</p>' if error else ''}
            <form method="POST">
                <input type="text" name="username" placeholder="Operator ID" required style="background:#0d1117; color:white; border:1px solid #30363d; padding:10px; margin:5px;"><br>
                <input type="password" name="password" placeholder="Root Password" required style="background:#0d1117; color:white; border:1px solid #30363d; padding:10px; margin:5px;"><br>
                <input type="submit" value="EXECUTE AUTHENTICATION" style="background:#da3633; color:white; padding:10px 20px; border:none; cursor:pointer; font-weight:bold;">
            </form>
        </div>
    </body>
    </html>
    '''


@app.route('/kigamboni-labs-management/dashboard', methods=['GET', 'POST'])
@admin_required
def secret_admin_dashboard():
    message = None

    if request.method == 'POST':
        action_type = request.form.get('action_type')

        if action_type == 'update_lessons':
            for i in range(1, 7):
                lessons[i-1]['title'] = request.form.get(f'title_{i}')
                lessons[i-1]['content'] = request.form.get(f'content_{i}')
            message = "✅ Classroom content updated successfully."

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, email FROM users")
    registered_users = cursor.fetchall()
    conn.close()

    lessons_inputs_html = ""
    for idx, les in enumerate(lessons, 1):
        lessons_inputs_html += f'''
        <div style="border: 1px solid #30363d; padding: 10px; margin-bottom: 10px; background: #0d1117; border-radius: 4px;">
            <label><b>Somo la {idx} Kichwa:</b></label><br>
            <input type="text" name="title_{idx}" value="{html.escape(les['title'])}" style="width:95%;"><br>
            <label><b>Somo la {idx} Maelezo:</b></label><br>
            <textarea name="content_{idx}" style="width:95%; height:50px; background:#0d1117; color:white; border:1px solid #30363d; border-radius:4px; font-family:sans-serif;">{html.escape(les['content'])}</textarea>
        </div>
        '''

    users_list_html = ""
    for u in registered_users:
        # 🔥 ULINZI DHIDI YA XSS: Tunatumia html.escape kusafisha majina ya watumiaji kutoka databaseni
        safe_id = html.escape(str(u[0]))
        safe_username = html.escape(str(u[1]))
        safe_email = html.escape(str(u[2]))

        users_list_html += f'''
        <tr>
            <td>{safe_id}</td>
            <td>{safe_username}</td>
            <td>{safe_email}</td>
            <td>
                <form action="/kigamboni-labs-management/delete-user/{safe_id}" method="POST" style="margin:0;" onsubmit="return confirm('Je, una uhakika unataka kumfuta {safe_username}?');">
                    <input type="submit" value="FUTA" style="background:#da3633; color:white; padding:3px 8px; border:none; border-radius:4px; cursor:pointer; font-size:11px; margin:0;">
                </form>
            </td>
        </tr>
        '''

    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Dashboard - Chief Operator Node</title>
        <style>
            body {{ background:#0d1117; color:#c9d1d9; font-family:sans-serif; padding:20px; }}
            .container {{ display: flex; gap: 20px; max-width:1300px; margin:0 auto; }}
            .panel {{ background:#161b22; border:1px solid #30363d; padding:25px; border-radius:8px; flex: 1; }}
            .sidebar-data {{ background:#161b22; border:1px solid #30363d; padding:25px; border-radius:8px; width: 450px; }}
            h1, h2, h3 {{ color:#58a6ff; }}
            input[type="text"] {{ width:95%; padding:8px; background:#0d1117; color:white; border:1px solid #30363d; border-radius:4px; margin-bottom:10px; font-family:monospace; }}
            input[type="submit"] {{ background:#2ea44f; color:white; padding:10px 20px; border:none; border-radius:4px; cursor:pointer; font-weight:bold; margin-top:5px; }}
            input[type="submit"]:hover {{ background:#3fb950; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
            th, td {{ border: 1px solid #30363d; padding: 8px; text-align: left; font-size:13px; }}
            th {{ background: #0d1117; }}
            .alert {{ background:rgba(46,164,79,0.15); border:1px solid #2ea44f; color:#56d364; padding:12px; border-radius:6px; margin-bottom:20px; }}
        </style>
    </head>
    <body>
        <div style="text-align:center; margin-bottom:20px;">
            <h1>⚙️ Live System Administration</h1>
            <p>Karibu Operator Bakari. Hapa unaona wanafunzi wako na kusimamai masomo.</p>
            {f'<div class="alert" style="display:inline-block; text-align:left;">{message}</div>' if message else ''}
        </div>

        <div class="container">
            <div class="panel">
                <h3>📚 Badili Maudhui ya Masomo Live</h3>
                <form method="POST" style="background:#21262d; padding:15px; border-radius:6px;">
                    <input type="hidden" name="action_type" value="update_lessons">
                    {lessons_inputs_html}
                    <input type="submit" value="REBORN CLASSROOM CONTENT">
                </form>
            </div>

            <div class="sidebar-data">
                <h3>👥 Registered Database Users</h3>
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Username</th>
                            <th>Email</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {users_list_html}
                    </tbody>
                </table>
                <br><br>
                <a href="/admin-logout" style="color:#da3633; text-decoration:none; font-weight:bold; font-family:monospace; display:block; text-align:center; border:1px solid #da3633; padding:10px; border-radius:4px; background:rgba(218,54,51,0.1);">🚪 TERMINATE ADMIN SESSION</a>
            </div>
        </div>
    </body>
    </html>
    '''


#========================================================
#           ADMIN ACTION: DELETE USER
#========================================================


@app.route('/kigamboni-labs-management/delete-user/<int:user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('secret_admin_dashboard'))


#========================================================
#           LOGOUT ROUTES       
#========================================================


@app.route("/logout")
def logout():
    response = make_response(redirect(url_for("login")))

    response.delete_cookie(
        "auth_token",
        samesite="Lax"
    )

    session.clear()

    return response
#========================================================
#           ADMIN LOGOUT (TOKEN BASED)
#========================================================


@app.route("/admin-logout")
def admin_logout():
    # 🔥 MAREKEBISHHO YA KIUSALAMA: Baada ya kufuta cookie ya admin, tunamnyoosha mtu login badala ya kuacha text tupu screen
    response = make_response(redirect(url_for("login")))
    response.delete_cookie("auth_token")  # Kufuta token ya admin
    flash("Admin session terminated successfully.")
    return response


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000) 
