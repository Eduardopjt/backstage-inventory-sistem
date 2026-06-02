from flask import Flask, render_template, request, jsonify, g, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import io
import secrets
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta
from functools import wraps

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None

try:
    import stripe
except ImportError:
    stripe = None

try:
    import pandas as pd
except ImportError:
    pd = None

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "inventory.db")
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
USE_POSTGRES = bool(DATABASE_URL and (DATABASE_URL.startswith("postgres://") or DATABASE_URL.startswith("postgresql://")))

STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY", "").strip()
STRIPE_PRICE_PRO_ID = os.environ.get("STRIPE_PRICE_PRO_ID", "").strip()
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()
EMAIL_PROVIDER = os.environ.get("EMAIL_PROVIDER", "smtp").strip().lower()
EMAIL_FROM = os.environ.get("EMAIL_FROM", "noreply@example.com").strip()
SMTP_HOST = os.environ.get("SMTP_HOST", "").strip()
SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
SMTP_USER = os.environ.get("SMTP_USER", "").strip()
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "").strip()
INVITE_EXPIRATION_DAYS = int(os.environ.get("INVITE_EXPIRATION_DAYS", 7))

if stripe is not None and STRIPE_API_KEY:
    stripe.api_key = STRIPE_API_KEY

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")


def login_required(f):
    """Decorador para proteger rotas que precisam de autenticação"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Não autenticado"}), 401
        return f(*args, **kwargs)
    return decorated_function


class DBConnection:
    def __init__(self, connection, driver):
        self.conn = connection
        self.driver = driver

    def execute(self, sql, params=()):
        if self.driver == "postgres":
            cursor = self.conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(sql.replace("?", "%s"), params)
            return cursor
        return self.conn.execute(sql, params)

    def commit(self):
        return self.conn.commit()

    def close(self):
        return self.conn.close()


def get_db():
    db = getattr(g, "db", None)
    if db is None:
        if USE_POSTGRES:
            if psycopg2 is None:
                raise RuntimeError("psycopg2-binary is required to use PostgreSQL. Install it with pip.")
            conn = psycopg2.connect(DATABASE_URL, sslmode="require")
            db = g.db = DBConnection(conn, "postgres")
        else:
            conn = sqlite3.connect(DATABASE)
            conn.row_factory = sqlite3.Row
            db = g.db = DBConnection(conn, "sqlite")
    return db


def parse_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def generate_token(length=32):
    return secrets.token_urlsafe(length)


def send_email(to_email, subject, html_content):
    if not to_email:
        return False

    # Se email não está configurado, apenas retorna True sem enviar
    if EMAIL_PROVIDER == "smtp" and not SMTP_HOST:
        print(f"[EMAIL] Simulado: {to_email} - {subject}")
        return True
    
    if EMAIL_PROVIDER == "sendgrid" and not os.environ.get("SENDGRID_API_KEY"):
        print(f"[EMAIL] Simulado: {to_email} - {subject}")
        return True

    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = EMAIL_FROM
        msg["To"] = to_email
        msg.set_content(html_content, subtype="html")

        if EMAIL_PROVIDER == "sendgrid":
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail
            message = Mail(from_email=EMAIL_FROM, to_emails=to_email, subject=subject, html_content=html_content)
            client = SendGridAPIClient(os.environ.get("SENDGRID_API_KEY", ""))
            client.send(message)
            return True

        if SMTP_HOST:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.starttls()
                if SMTP_USER and SMTP_PASSWORD:
                    server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(msg)
            return True
        
        return True
    except Exception as e:
        print(f"[EMAIL ERROR] {e}")
        return True


def get_current_user():
    if "user_id" not in session:
        return None
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    return user


def get_plan_limits(plan):
    if plan == "pro":
        return {"max_items": None, "max_categories": None}
    return {"max_items": 25, "max_categories": 10}


def init_db():
    db = get_db()
    if USE_POSTGRES:
        serial_type = "SERIAL PRIMARY KEY"
        timestamp_type = "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
    else:
        serial_type = "INTEGER PRIMARY KEY AUTOINCREMENT"
        timestamp_type = "DATETIME DEFAULT CURRENT_TIMESTAMP"

    # Contas / Organizações SaaS
    db.execute(
        f"""
        CREATE TABLE IF NOT EXISTS accounts (
            id {serial_type},
            name TEXT NOT NULL,
            plan TEXT NOT NULL DEFAULT 'free',
            status TEXT NOT NULL DEFAULT 'active',
            created_at {timestamp_type}
        )
        """
    )
    # Tabela de usuários
    db.execute(
        f"""
        CREATE TABLE IF NOT EXISTS users (
            id {serial_type},
            account_id INTEGER NOT NULL DEFAULT 1,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT,
            role TEXT NOT NULL DEFAULT 'owner',
            created_at {timestamp_type},
            FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE CASCADE
        )
        """
    )
    db.execute(
        f"""
        CREATE TABLE IF NOT EXISTS invites (
            id {serial_type},
            account_id INTEGER NOT NULL,
            email TEXT NOT NULL,
            token TEXT UNIQUE NOT NULL,
            role TEXT NOT NULL DEFAULT 'member',
            status TEXT NOT NULL DEFAULT 'pending',
            expires_at TIMESTAMP,
            created_at {timestamp_type},
            invited_by INTEGER,
            FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE CASCADE,
            FOREIGN KEY(invited_by) REFERENCES users(id) ON DELETE SET NULL
        )
        """
    )
    db.execute(
        f"""
        CREATE TABLE IF NOT EXISTS subscriptions (
            id {serial_type},
            account_id INTEGER NOT NULL,
            stripe_subscription_id TEXT UNIQUE,
            stripe_price_id TEXT,
            status TEXT NOT NULL DEFAULT 'inactive',
            current_period_end TIMESTAMP,
            created_at {timestamp_type},
            FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE CASCADE
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL DEFAULT 1,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            quantity INTEGER NOT NULL DEFAULT 0,
            location TEXT,
            min_quantity INTEGER DEFAULT 0,
            category TEXT,
            sku TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE CASCADE
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            observation TEXT,
            supplier TEXT,
            unit_price REAL,
            destination TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(item_id) REFERENCES items(id) ON DELETE CASCADE
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL DEFAULT 1,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            color TEXT DEFAULT '#2563eb',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE CASCADE,
            UNIQUE(account_id, name)
        )
        """
    )
    
    # Adiciona colunas se não existirem (para bancos existentes)
    try:
        db.execute("ALTER TABLE users ADD COLUMN account_id INTEGER DEFAULT 1")
    except:
        pass
    try:
        db.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'owner'")
    except:
        pass
    try:
        db.execute("ALTER TABLE items ADD COLUMN account_id INTEGER DEFAULT 1")
    except:
        pass
    try:
        db.execute("ALTER TABLE categories ADD COLUMN account_id INTEGER DEFAULT 1")
    except:
        pass
    try:
        db.execute("ALTER TABLE items ADD COLUMN category TEXT")
    except:
        pass
    try:
        db.execute("ALTER TABLE items ADD COLUMN sku TEXT")
    except:
        pass
    try:
        db.execute("ALTER TABLE movements ADD COLUMN supplier TEXT")
    except:
        pass
    try:
        db.execute("ALTER TABLE movements ADD COLUMN unit_price REAL")
    except:
        pass
    try:
        db.execute("ALTER TABLE movements ADD COLUMN destination TEXT")
    except:
        pass
    
    if not db.execute("SELECT 1 FROM accounts WHERE id = ?", (1,)).fetchone():
        db.execute(
            "INSERT INTO accounts (id, name, plan, status) VALUES (?, ?, ?, ?)",
            (1, 'Default Account', 'free', 'active'),
        )
    db.commit()


def register_movement(item_id, movement_type, quantity, observation="", supplier="", unit_price=None, destination=""):
    """Registra uma movimentação no histórico"""
    db = get_db()
    db.execute(
        "INSERT INTO movements (item_id, type, quantity, observation, supplier, unit_price, destination) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (item_id, movement_type, quantity, observation, supplier, unit_price, destination),
    )
    db.commit()


@app.teardown_appcontext
def close_db(exception=None):
    db = getattr(g, "db", None)
    if db is not None:
        db.close()


@app.route("/")
def index():
    init_db()
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        data = request.get_json() or {}
        username = data.get("username", "").strip()
        password = data.get("password", "")

        if not username or not password:
            return jsonify({"error": "Usuário e senha obrigatórios"}), 400

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["account_id"] = user["account_id"]
            return jsonify({"success": True})

        return jsonify({"error": "Usuário ou senha inválidos"}), 401

    if "user_id" in session:
        return redirect(url_for("index"))
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        data = request.get_json() or {}
        username = data.get("username", "").strip()
        password = data.get("password", "")
        password_confirm = data.get("password_confirm", "")
        email = data.get("email", "").strip()
        company = data.get("company", "").strip() or username
        plan = data.get("plan", "free").strip() or "free"
        invite_token = data.get("invite_token", "").strip()

        if not username or not password:
            return jsonify({"error": "Usuário e senha obrigatórios"}), 400
        if len(username) < 3:
            return jsonify({"error": "Usuário deve ter pelo menos 3 caracteres"}), 400
        if len(password) < 6:
            return jsonify({"error": "Senha deve ter pelo menos 6 caracteres"}), 400
        if password != password_confirm:
            return jsonify({"error": "Senhas não conferem"}), 400
        if not invite_token and not company:
            return jsonify({"error": "Nome da empresa/equipe é obrigatório"}), 400

        db = get_db()
        existing = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if existing:
            return jsonify({"error": "Usuário já existe"}), 400

        if invite_token:
            invite = db.execute(
                "SELECT * FROM invites WHERE token = ? AND status = 'pending' AND expires_at > ?",
                (invite_token, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),),
            ).fetchone()
            if not invite:
                return jsonify({"error": "Token de convite inválido ou expirado."}), 400
            account_id = invite["account_id"]
            role = invite["role"] or "member"
            db.execute(
                "UPDATE invites SET status = 'accepted' WHERE id = ?",
                (invite["id"],),
            )
        else:
            role = "owner"
            if USE_POSTGRES:
                account_cursor = db.execute(
                    "INSERT INTO accounts (name, plan) VALUES (?, ?) RETURNING id",
                    (company, plan),
                )
                account_id = account_cursor.fetchone()["id"]
            else:
                account_cursor = db.execute(
                    "INSERT INTO accounts (name, plan) VALUES (?, ?)",
                    (company, plan),
                )
                account_id = account_cursor.lastrowid

        db.execute(
            "INSERT INTO users (account_id, username, password, email, role) VALUES (?, ?, ?, ?, ?)",
            (account_id, username, generate_password_hash(password), email, role),
        )
        db.commit()
        return jsonify({"success": True})

    if "user_id" in session:
        return redirect(url_for("index"))

    invite_token = request.args.get("invite_token", "")
    return render_template("register.html", invite_token=invite_token)


@app.route("/invite/<token>")
def invite_accept(token):
    return render_template("register.html", invite_token=token)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/api/user")
@login_required
def get_user():
    db = get_db()
    user = db.execute(
        "SELECT u.id, u.username, u.role, a.name as account_name, a.plan, a.status FROM users u JOIN accounts a ON a.id = u.account_id WHERE u.id = ?",
        (session["user_id"],),
    ).fetchone()
    return jsonify({
        "id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "account_name": user["account_name"],
        "plan": user["plan"],
        "account_status": user["status"],
    })


@app.route("/api/account")
@login_required
def account_info():
    db = get_db()
    account_id = session["account_id"]
    account = db.execute("SELECT id, name, plan, status, created_at FROM accounts WHERE id = ?", (account_id,)).fetchone()
    item_count = db.execute("SELECT COUNT(*) as cnt FROM items WHERE account_id = ?", (account_id,)).fetchone()["cnt"]
    category_count = db.execute("SELECT COUNT(*) as cnt FROM categories WHERE account_id = ?", (account_id,)).fetchone()["cnt"]
    limits = get_plan_limits(account["plan"])
    return jsonify({
        "id": account["id"],
        "name": account["name"],
        "plan": account["plan"],
        "status": account["status"],
        "created_at": account["created_at"],
        "item_count": item_count,
        "category_count": category_count,
        "limits": limits,
    })


@app.route("/api/invites", methods=["GET", "POST"])
@login_required
def invites():
    db = get_db()
    user = get_current_user()
    if user is None or user["role"] != "owner":
        return jsonify({"error": "Apenas proprietários podem criar convites."}), 403

    account_id = user["account_id"]
    if request.method == "POST":
        data = request.get_json() or {}
        email = data.get("email", "").strip().lower()
        role = data.get("role", "member").strip().lower()

        if not email:
            return jsonify({"error": "Email do convidado é obrigatório."}), 400

        token = generate_token(24)
        expires_at = (datetime.utcnow() + timedelta(days=INVITE_EXPIRATION_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
        db.execute(
            "INSERT INTO invites (account_id, email, token, role, status, expires_at, invited_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (account_id, email, token, role, "pending", expires_at, user["id"]),
        )
        db.commit()

        invite_url = url_for("register", _external=True) + f"?invite_token={token}"
        html = f"<p>Você foi convidado para acessar o workspace <strong>{user['username']}</strong>.</p><p><a href=\"{invite_url}\">Clique aqui para aceitar o convite</a></p>"
        try:
            send_email(email, "Convite para acessar o workspace", html)
        except Exception as e:
            return jsonify({"error": f"Não foi possível enviar o convite: {e}"}), 500

        return jsonify({"success": True, "invite_url": invite_url})

    rows = db.execute("SELECT * FROM invites WHERE account_id = ? ORDER BY created_at DESC", (account_id,)).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/import/excel", methods=["POST"])
@login_required
def import_excel():
    if pd is None:
        return jsonify({"error": "Pandas e openpyxl são necessários para importar Excel."}), 500

    uploaded_file = request.files.get("file")
    if not uploaded_file or uploaded_file.filename == "":
        return jsonify({"error": "Arquivo Excel não enviado."}), 400

    try:
        df = pd.read_excel(uploaded_file, engine="openpyxl")
    except Exception as exc:
        return jsonify({"error": f"Falha ao ler o arquivo Excel: {exc}"}), 400

    required_columns = ["name", "quantity"]
    if not all(col in df.columns for col in required_columns):
        return jsonify({"error": f"O arquivo deve conter as colunas: {', '.join(required_columns)}."}), 400

    db = get_db()
    account_id = session["account_id"]
    user_id = session["user_id"]
    created = 0
    errors = []

    for index, row in df.iterrows():
        try:
            name = str(row.get("name", "")).strip()
            quantity = parse_int(row.get("quantity", 0), 0)
            description = str(row.get("description", "")).strip()
            location = str(row.get("location", "")).strip()
            min_quantity = parse_int(row.get("min_quantity", 0), 0)
            category = str(row.get("category", "")).strip()
            sku = str(row.get("sku", "")).strip()

            if not name:
                raise ValueError("Nome do item obrigatório")

            db.execute(
                "INSERT INTO items (account_id, user_id, name, description, quantity, location, min_quantity, category, sku) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (account_id, user_id, name, description, quantity, location, min_quantity, category, sku),
            )
            created += 1
        except Exception as exc:
            errors.append({"row": int(index) + 1, "error": str(exc)})

    db.commit()
    return jsonify({"success": True, "created": created, "errors": errors})


@app.route("/api/checkout", methods=["POST"])
@login_required
def create_checkout():
    if stripe is None or not STRIPE_API_KEY:
        return jsonify({"error": "Stripe não está configurado. Atualize seu plano manualmente depois."}), 400
    if not STRIPE_PRICE_PRO_ID:
        return jsonify({"error": "STRIPE_PRICE_PRO_ID não definido."}), 400

    data = request.get_json() or {}
    plan = data.get("plan", "pro").strip().lower()
    account_id = session["account_id"]
    success_url = data.get("success_url", request.host_url)
    cancel_url = data.get("cancel_url", request.host_url)

    user = get_current_user()
    if not user or not user.get("email"):
        return jsonify({"error": "Email do usuário não cadastrado. Atualize seu perfil antes de continuar."}), 400

    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",
            line_items=[{"price": STRIPE_PRICE_PRO_ID, "quantity": 1}],
            customer_email=user["email"],
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"account_id": str(account_id), "plan": plan},
        )
        return jsonify({"checkout_url": checkout_session.url})
    except Exception as exc:
        return jsonify({"error": f"Falha ao criar checkout Stripe: {exc}"}), 400


@app.route("/webhook", methods=["POST"])
def stripe_webhook():
    if stripe is None or not STRIPE_WEBHOOK_SECRET:
        # Retorna sucesso mesmo sem Stripe configurado
        return jsonify({"received": True}), 200

    payload = request.data
    sig_header = request.headers.get("Stripe-Signature", "")
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 400

    data = event["data"]["object"]
    db = get_db()

    if event["type"] == "checkout.session.completed":
        account_id = int(data["metadata"].get("account_id", 0))
        stripe_subscription_id = data.get("subscription")
        price_id = data["metadata"].get("plan")
        if stripe_subscription_id and account_id:
            current_period_end = datetime.utcfromtimestamp(data.get("current_period_end", datetime.utcnow().timestamp()))
            db.execute(
                "INSERT INTO subscriptions (account_id, stripe_subscription_id, stripe_price_id, status, current_period_end) VALUES (?, ?, ?, ?, ?)",
                (account_id, stripe_subscription_id, price_id, "active", current_period_end.strftime("%Y-%m-%d %H:%M:%S")),
            )
            db.execute("UPDATE accounts SET plan = ?, status = ? WHERE id = ?", (price_id, "active", account_id))
            db.commit()

    return jsonify({"received": True})


@app.route("/api/account/upgrade", methods=["POST"])
@login_required
def upgrade_account():
    db = get_db()
    account_id = session["account_id"]
    account = db.execute("SELECT plan FROM accounts WHERE id = ?", (account_id,)).fetchone()
    if account["plan"] == "pro":
        return jsonify({"success": True, "plan": "pro"})
    db.execute("UPDATE accounts SET plan = ?, status = ? WHERE id = ?", ("pro", "active", account_id))
    db.commit()
    return jsonify({"success": True, "plan": "pro"})


@app.route("/api/items", methods=["GET", "POST"])
@login_required
def items():
    db = get_db()
    user_id = session["user_id"]
    account_id = session["account_id"]
    if request.method == "POST":
        data = request.get_json() or {}
        name = data.get("name", "").strip()
        description = data.get("description", "").strip()
        quantity = parse_int(data.get("quantity", 0), 0)
        location = data.get("location", "").strip()
        min_quantity = parse_int(data.get("min_quantity", 0), 0)
        category = data.get("category", "").strip()
        sku = data.get("sku", "").strip()

        account = db.execute("SELECT plan FROM accounts WHERE id = ?", (account_id,)).fetchone()
        limits = get_plan_limits(account["plan"])
        if limits["max_items"] is not None:
            current_count = db.execute("SELECT COUNT(*) as cnt FROM items WHERE account_id = ?", (account_id,)).fetchone()["cnt"]
            if current_count >= limits["max_items"]:
                return jsonify({"error": f"O plano {account['plan']} permite até {limits['max_items']} itens. Faça upgrade para adicionar mais itens."}), 403

        if not name:
            return jsonify({"error": "Nome do item é obrigatório."}), 400
        if quantity < 0:
            return jsonify({"error": "Quantidade não pode ser negativa."}), 400
        if min_quantity < 0:
            return jsonify({"error": "Quantidade mínima não pode ser negativa."}), 400

        if USE_POSTGRES:
            item_cursor = db.execute(
                "INSERT INTO items (account_id, user_id, name, description, quantity, location, min_quantity, category, sku) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id",
                (account_id, user_id, name, description, quantity, location, min_quantity, category, sku),
            )
            item_id = item_cursor.fetchone()["id"]
        else:
            item_cursor = db.execute(
                "INSERT INTO items (account_id, user_id, name, description, quantity, location, min_quantity, category, sku) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (account_id, user_id, name, description, quantity, location, min_quantity, category, sku),
            )
            item_id = item_cursor.lastrowid
        db.commit()
        item = db.execute("SELECT * FROM items WHERE id = ? AND account_id = ?", (item_id, account_id)).fetchone()
        return jsonify(dict(item)), 201

    search = request.args.get("q", "").strip()
    category_filter = request.args.get("category", "").strip()
    query = "SELECT * FROM items WHERE account_id = ?"
    params = [account_id]
    if search:
        query += " AND (name LIKE ? OR description LIKE ? OR location LIKE ? OR sku LIKE ?)"
        term = f"%{search}%"
        params.extend([term, term, term, term])
    if category_filter:
        query += " AND category = ?"
        params.append(category_filter)
    rows = db.execute(query, params).fetchall()
    return jsonify([dict(row) for row in rows])


@app.route("/api/items/<int:item_id>", methods=["PUT", "DELETE"])
@login_required
def item_detail(item_id):
    db = get_db()
    account_id = session["account_id"]
    item = db.execute("SELECT * FROM items WHERE id = ? AND account_id = ?", (item_id, account_id)).fetchone()
    if item is None:
        return jsonify({"error": "Item não encontrado."}), 404

    if request.method == "DELETE":
        db.execute("DELETE FROM items WHERE id = ?", (item_id,))
        db.commit()
        return jsonify({"success": True})

    data = request.get_json() or {}

    # Helper to safely get string values (handles None)
    def safe_str(value, fallback=""):
        return (value if value is not None else fallback).strip()

    name = safe_str(data.get("name"), item["name"])
    description = safe_str(data.get("description"), item.get("description", ""))
    location = safe_str(data.get("location"), item.get("location", ""))
    category = safe_str(data.get("category"), item.get("category", ""))
    sku = safe_str(data.get("sku"), item.get("sku", ""))

    # Quantity should not be changed via item edit - use entrada/saida/ajuste endpoints instead.
    quantity = item["quantity"]

    # Validate and normalize min_quantity
    min_quantity = parse_int(data.get("min_quantity", item.get("min_quantity", 0)), item.get("min_quantity", 0))
    if min_quantity < 0:
        return jsonify({"error": "Quantidade mínima não pode ser negativa."}), 400

    if not name:
        return jsonify({"error": "Nome do item é obrigatório."}), 400

    # Update item metadata only (do NOT change quantity here)
    db.execute(
        "UPDATE items SET name = ?, description = ?, location = ?, min_quantity = ?, category = ?, sku = ? WHERE id = ?",
        (name, description, location, min_quantity, category, sku, item_id),
    )
    db.commit()
    updated = db.execute("SELECT * FROM items WHERE id = ? AND account_id = ?", (item_id, account_id)).fetchone()
    return jsonify(dict(updated))


@app.route("/api/items/<int:item_id>/entrada", methods=["POST"])
@login_required
def entrada(item_id):
    db = get_db()
    account_id = session["account_id"]
    item = db.execute("SELECT * FROM items WHERE id = ? AND account_id = ?", (item_id, account_id)).fetchone()
    if item is None:
        return jsonify({"error": "Item não encontrado."}), 404

    data = request.get_json() or {}
    quantity = parse_int(data.get("quantity", 1), 1)
    observation = data.get("observation", "").strip()
    supplier = data.get("supplier", "").strip()
    unit_price = data.get("unit_price")

    if quantity <= 0:
        return jsonify({"error": "Quantidade deve ser maior que 0."}), 400

    if unit_price is not None:
        try:
            unit_price = float(unit_price)
        except (TypeError, ValueError):
            unit_price = None

    new_quantity = item["quantity"] + quantity
    db.execute("UPDATE items SET quantity = ? WHERE id = ?", (new_quantity, item_id))
    register_movement(item_id, "ENTRADA", quantity, observation, supplier, unit_price)
    db.commit()

    updated = db.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    return jsonify(dict(updated))


@app.route("/api/items/<int:item_id>/saida", methods=["POST"])
@login_required
def saida(item_id):
    db = get_db()
    account_id = session["account_id"]
    item = db.execute("SELECT * FROM items WHERE id = ? AND account_id = ?", (item_id, account_id)).fetchone()
    if item is None:
        return jsonify({"error": "Item não encontrado."}), 404

    data = request.get_json() or {}
    quantity = parse_int(data.get("quantity", 1), 1)
    observation = data.get("observation", "").strip()
    destination = data.get("destination", "").strip()

    if quantity <= 0:
        return jsonify({"error": "Quantidade deve ser maior que 0."}), 400

    if not destination:
        return jsonify({"error": "Destino é obrigatório para saída."}), 400

    if item["quantity"] < quantity:
        return jsonify({"error": "Quantidade insuficiente em estoque."}), 400

    new_quantity = item["quantity"] - quantity
    db.execute("UPDATE items SET quantity = ? WHERE id = ?", (new_quantity, item_id))
    register_movement(item_id, "SAIDA", quantity, observation, destination=destination)
    db.commit()

    updated = db.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    return jsonify(dict(updated))


@app.route("/api/items/<int:item_id>/ajuste", methods=["POST"])
@login_required
def ajuste(item_id):
    db = get_db()
    account_id = session["account_id"]
    item = db.execute("SELECT * FROM items WHERE id = ? AND account_id = ?", (item_id, account_id)).fetchone()
    if item is None:
        return jsonify({"error": "Item não encontrado."}), 404

    data = request.get_json() or {}
    new_quantity = parse_int(data.get("quantity", item["quantity"]), item["quantity"])
    observation = data.get("observation", "").strip()

    if new_quantity < 0:
        return jsonify({"error": "Quantidade não pode ser negativa."}), 400

    delta = new_quantity - item["quantity"]
    db.execute("UPDATE items SET quantity = ? WHERE id = ?", (new_quantity, item_id))
    register_movement(item_id, "AJUSTE", delta, observation)
    db.commit()

    updated = db.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    return jsonify(dict(updated))


@app.route("/api/items/<int:item_id>/historico", methods=["GET"])
@login_required
def historico(item_id):
    db = get_db()
    account_id = session["account_id"]
    item = db.execute("SELECT * FROM items WHERE id = ? AND account_id = ?", (item_id, account_id)).fetchone()
    if item is None:
        return jsonify({"error": "Item não encontrado."}), 404

    rows = db.execute(
        "SELECT * FROM movements WHERE item_id = ? ORDER BY timestamp DESC",
        (item_id,),
    ).fetchall()
    return jsonify([dict(row) for row in rows])


@app.route("/api/balanco", methods=["GET"])
@login_required
def balanco():
    """Retorna resumo geral do estoque do usuário."""
    db = get_db()
    account_id = session["account_id"]
    start = request.args.get("start")
    end = request.args.get("end")
    low_thr = request.args.get("low_stock_threshold", None)

    # Total de SKUs e quantidade total
    total_items = db.execute("SELECT COUNT(*) as cnt FROM items WHERE account_id = ?", (account_id,)).fetchone()["cnt"]
    total_quantity = db.execute("SELECT COALESCE(SUM(quantity),0) as s FROM items WHERE account_id = ?", (account_id,)).fetchone()["s"]

    # Movimentações no período
    mov_query = "SELECT COUNT(*) as cnt FROM movements m JOIN items i ON i.id = m.item_id WHERE i.account_id = ?"
    params = [account_id]
    if start and end:
        mov_query += " AND m.timestamp BETWEEN ? AND ?"
        params.extend([start + " 00:00:00", end + " 23:59:59"])
    mov_count = db.execute(mov_query, params).fetchone()["cnt"]

    # Resumo por localização
    locs = db.execute(
        "SELECT COALESCE(location,'(Sem local)') as location, SUM(quantity) as total FROM items WHERE account_id = ? GROUP BY location ORDER BY total DESC",
        (account_id,)
    ).fetchall()
    locations = [dict(r) for r in locs]

    # Itens com baixo estoque
    low_items = []
    if low_thr is not None:
        try:
            t = int(low_thr)
            rows = db.execute("SELECT * FROM items WHERE account_id = ? AND quantity <= ? ORDER BY quantity ASC", (account_id, t)).fetchall()
            low_items = [dict(r) for r in rows]
        except ValueError:
            low_items = []

    value_row = db.execute(
        "SELECT COALESCE(SUM(m.quantity * m.unit_price), 0) as total_value FROM movements m JOIN items i ON i.id = m.item_id WHERE i.account_id = ? AND m.type = 'ENTRADA' AND m.unit_price IS NOT NULL",
        (account_id,),
    ).fetchone()
    total_value = value_row["total_value"] if value_row else 0

    type_rows = db.execute(
        "SELECT m.type, SUM(m.quantity) as total FROM movements m JOIN items i ON i.id = m.item_id WHERE i.account_id = ? GROUP BY m.type",
        (account_id,),
    ).fetchall()
    movement_types = {row["type"]: row["total"] for row in type_rows}

    return jsonify({
        "total_items": total_items,
        "total_quantity": total_quantity,
        "movements_count": mov_count,
        "locations": locations,
        "low_stock": low_items,
        "total_value": total_value,
        "movement_types": movement_types,
    })


@app.route("/api/balanco/movements", methods=["GET"])
@login_required
def balanco_movements():
    """Retorna movimentações do usuário no período."""
    db = get_db()
    account_id = session["account_id"]
    start = request.args.get("start")
    end = request.args.get("end")
    query = "SELECT m.*, i.name as item_name FROM movements m JOIN items i ON i.id = m.item_id WHERE i.account_id = ?"
    params = [account_id]
    if start and end:
        query += " AND m.timestamp BETWEEN ? AND ?"
        params.extend([start + " 00:00:00", end + " 23:59:59"])
    query += " ORDER BY m.timestamp DESC"
    rows = db.execute(query, params).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/balanco/suppliers", methods=["GET"])
@login_required
def balanco_suppliers():
    """Retorna análise de entradas por fornecedor."""
    db = get_db()
    account_id = session["account_id"]
    start = request.args.get("start")
    end = request.args.get("end")
    query = "SELECT m.*, i.name as item_name FROM movements m JOIN items i ON i.id = m.item_id WHERE i.account_id = ? AND m.type = 'ENTRADA'"
    params = [account_id]
    if start and end:
        query += " AND m.timestamp BETWEEN ? AND ?"
        params.extend([start + " 00:00:00", end + " 23:59:59"])
    query += " ORDER BY m.timestamp DESC"
    rows = db.execute(query, params).fetchall()
    
    # Agrupamento por fornecedor
    by_supplier = {}
    for row in rows:
        supplier = row["supplier"] or "(Sem fornecedor)"
        if supplier not in by_supplier:
            by_supplier[supplier] = {"total_qty": 0, "total_cost": 0.0, "items": []}
        qty = row["quantity"]
        price = row["unit_price"] or 0
        by_supplier[supplier]["total_qty"] += qty
        by_supplier[supplier]["total_cost"] += qty * price
        by_supplier[supplier]["items"].append({
            "item": row["item_name"],
            "qty": qty,
            "unit_price": price,
            "total": qty * price,
            "date": row["timestamp"]
        })
    
    return jsonify(by_supplier)


@app.route("/api/categories", methods=["GET", "POST"])
@login_required
def categories():
    """Gerencia categorias do usuário."""
    db = get_db()
    user_id = session["user_id"]
    account_id = session["account_id"]
    
    if request.method == "POST":
        data = request.get_json() or {}
        name = data.get("name", "").strip()
        color = data.get("color", "#2563eb").strip()
        
        if not name:
            return jsonify({"error": "Nome da categoria é obrigatório"}), 400

        account = db.execute("SELECT plan FROM accounts WHERE id = ?", (account_id,)).fetchone()
        limits = get_plan_limits(account["plan"])
        if limits["max_categories"] is not None:
            category_count = db.execute("SELECT COUNT(*) as cnt FROM categories WHERE account_id = ?", (account_id,)).fetchone()["cnt"]
            if category_count >= limits["max_categories"]:
                return jsonify({"error": f"O plano {account['plan']} permite até {limits['max_categories']} categorias."}), 403
        
        try:
            db.execute(
                "INSERT INTO categories (account_id, user_id, name, color) VALUES (?, ?, ?, ?)",
                (account_id, user_id, name, color)
            )
            db.commit()
            return jsonify({"success": True}), 201
        except sqlite3.IntegrityError:
            return jsonify({"error": "Categoria já existe"}), 400
    
    rows = db.execute("SELECT * FROM categories WHERE account_id = ? ORDER BY name", (account_id,)).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/categories/<int:category_id>", methods=["DELETE"])
@login_required
def delete_category(category_id):
    """Deleta uma categoria."""
    db = get_db()
    user_id = session["user_id"]
    account_id = session["account_id"]
    category = db.execute("SELECT * FROM categories WHERE id = ? AND account_id = ?", (category_id, account_id)).fetchone()
    
    if not category:
        return jsonify({"error": "Categoria não encontrada"}), 404
    
    db.execute("DELETE FROM categories WHERE id = ?", (category_id,))
    db.execute("UPDATE items SET category = NULL WHERE category = ? AND account_id = ?", (category["name"], account_id))
    db.commit()
    
    return jsonify({"success": True})


@app.route("/api/locations", methods=["GET"])
@login_required
def locations():
    """Retorna todas as localizações de um usuário."""
    db = get_db()
    account_id = session["account_id"]
    rows = db.execute(
        "SELECT DISTINCT location FROM items WHERE account_id = ? AND location IS NOT NULL AND location != '' ORDER BY location",
        (account_id,)
    ).fetchall()
    locations_list = [row["location"] for row in rows]
    return jsonify(locations_list)


@app.route("/api/user/change-password", methods=["POST"])
@login_required
def change_password():
    """Altera a senha do usuário."""
    db = get_db()
    user_id = session["user_id"]
    data = request.get_json() or {}
    current_password = data.get("current_password", "")
    new_password = data.get("new_password", "")
    confirm_password = data.get("confirm_password", "")
    
    if not current_password or not new_password:
        return jsonify({"error": "Todos os campos são obrigatórios"}), 400
    
    if len(new_password) < 6:
        return jsonify({"error": "Nova senha deve ter pelo menos 6 caracteres"}), 400
    
    if new_password != confirm_password:
        return jsonify({"error": "Novas senhas não conferem"}), 400
    
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user or not check_password_hash(user["password"], current_password):
        return jsonify({"error": "Senha atual incorreta"}), 401
    
    db.execute(
        "UPDATE users SET password = ? WHERE id = ?",
        (generate_password_hash(new_password), user_id)
    )
    db.commit()
    return jsonify({"success": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
