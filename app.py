from flask import Flask, render_template, request, jsonify, g, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import json
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from functools import wraps

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.environ.get("DATABASE_PATH") or os.path.join(BASE_DIR, "inventory.db")

if DATABASE:
    db_folder = os.path.dirname(DATABASE)
    if db_folder and not os.path.exists(db_folder):
        os.makedirs(db_folder, exist_ok=True)

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")


def login_required(f):
    """Decorador para proteger rotas que precisam de autenticacao"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Nao autenticado"}), 401

        user = get_current_user()
        if not user:
            session.clear()
            return jsonify({"error": "Nao autenticado"}), 401

        return f(*args, **kwargs)
    return decorated_function


def get_db():
    db = getattr(g, "db", None)
    if db is None:
        db = g.db = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


def parse_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_permissions_value(value):
    if not value:
        return []
    if isinstance(value, str):
        return [perm.strip() for perm in value.split(",") if perm.strip()]
    if isinstance(value, (list, tuple)):
        return [perm.strip() for perm in value if perm and str(perm).strip()]
    return []


def join_permissions(perms):
    if perms is None:
        return ""
    if isinstance(perms, str):
        return perms
    return ",".join([perm.strip() for perm in perms if perm and str(perm).strip()])

MAIL_FROM = os.environ.get("MAIL_FROM", "backstage@localhost")
SMTP_HOST = os.environ.get("SMTP_HOST")
try:
    SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
except ValueError:
    SMTP_PORT = 587
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD")
SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "true").lower() in ("1", "true", "yes")
SMTP_USE_SSL = os.environ.get("SMTP_USE_SSL", "false").lower() in ("1", "true", "yes")


def send_email(to_address, subject, body):
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASSWORD:
        return False, "SMTP não configurado"
    message = MIMEText(body, "plain", "utf-8")
    message["Subject"] = subject
    message["From"] = MAIL_FROM
    message["To"] = to_address
    try:
        if SMTP_USE_SSL:
            server = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=10)
        else:
            server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10)
            if SMTP_USE_TLS:
                server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.sendmail(MAIL_FROM, [to_address], message.as_string())
        server.quit()
        return True, None
    except Exception as err:
        return False, str(err)


def get_current_user():
    db = get_db()
    user_id = session.get("user_id")
    if not user_id:
        return None
    
    row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        session.clear()
        return None
    user = dict(row)
    
    # Validar e corrigir colunas críticas
    if user.get("status") is None:
        db.execute("UPDATE users SET status = 'active' WHERE id = ?", (user_id,))
        db.commit()
        user["status"] = "active"
    if user.get("account_id") is None:
        db.execute("UPDATE users SET account_id = 1 WHERE id = ?", (user_id,))
        db.commit()
        user["account_id"] = 1
    
    return user


def permission_required(permission):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            user = get_current_user()
            if not user:
                return jsonify({"error": "Não autenticado"}), 401
            
            # Usar .get() para evitar KeyError se coluna não existe
            user_status = user.get("status") or "active"
            if user_status != "active":
                return jsonify({"error": "Usuário inativo"}), 403
            
            if user.get("role") == "owner":
                return f(*args, **kwargs)
            
            permissions = parse_permissions_value(user.get("permissions"))
            if permission not in permissions:
                return jsonify({"error": "Sem permissão para acessar este recurso."}), 403
            return f(*args, **kwargs)
        return wrapped
    return decorator


def get_project_access(project_id, user_id):
    db = get_db()
    return db.execute(
        "SELECT * FROM project_access WHERE project_id = ? AND user_id = ?",
        (project_id, user_id),
    ).fetchone()


def has_project_access(user, project_id):
    db = get_db()
    project = db.execute(
        "SELECT * FROM projects WHERE id = ? AND account_id = ?",
        (project_id, session["account_id"]),
    ).fetchone()
    if not project:
        return False
    if project["owner_id"] == user["id"]:
        return True
    return bool(get_project_access(project_id, user["id"]))


def has_project_edit_access(user, project_id):
    db = get_db()
    project = db.execute(
        "SELECT * FROM projects WHERE id = ? AND account_id = ?",
        (project_id, session["account_id"]),
    ).fetchone()
    if not project:
        return False
    if project["owner_id"] == user["id"]:
        return True
    access = get_project_access(project_id, user["id"])
    return bool(access and access["access"] == "edit")


def default_permissions_for_role(role):
    core = ["dashboard", "projects", "items", "historico"]
    if role == "owner" or role == "admin":
        return ["dashboard", "projects", "team", "purchases", "warehouse", "romaneios", "items", "historico", "relatorios"]
    return core


def init_db():
    db = get_db()
    # Contas / Organizações SaaS
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            plan TEXT NOT NULL DEFAULT 'free',
            status TEXT NOT NULL DEFAULT 'active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    # Tabela de usuários
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL DEFAULT 1,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT,
            role TEXT NOT NULL DEFAULT 'owner',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
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
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL DEFAULT 1,
            owner_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'planejamento',
            start_date DATE,
            due_date DATE,
            assembly_start_date DATE,
            assembly_end_date DATE,
            event_start_date DATE,
            event_end_date DATE,
            dismantle_start_date DATE,
            dismantle_end_date DATE,
            assembly_address TEXT,
            event_address TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(owner_id) REFERENCES users(id) ON DELETE SET NULL,
            FOREIGN KEY(account_id) REFERENCES accounts(id) ON DELETE CASCADE
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS project_access (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            access TEXT NOT NULL DEFAULT 'view',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(project_id, user_id)
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            assigned_to INTEGER,
            sector TEXT,
            name TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'pendente',
            priority TEXT NOT NULL DEFAULT 'média',
            due_date DATE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY(assigned_to) REFERENCES users(id) ON DELETE SET NULL
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS project_discussions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            kind TEXT NOT NULL DEFAULT 'chat',
            message TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS project_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'aberta',
            approver_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS task_assignees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(task_id, user_id)
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS task_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS task_subtasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS task_checklist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            label TEXT NOT NULL,
            checked INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS purchase_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            project_request_id INTEGER,
            user_id INTEGER NOT NULL,
            approver_id INTEGER,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'aberta',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY(project_request_id) REFERENCES project_requests(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS warehouse_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            project_request_id INTEGER,
            user_id INTEGER NOT NULL,
            approver_id INTEGER,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'aberta',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY(project_request_id) REFERENCES project_requests(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS romaneios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,
            purchase_id INTEGER,
            warehouse_id INTEGER,
            name TEXT NOT NULL,
            note TEXT,
            status TEXT NOT NULL DEFAULT 'aberto',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE CASCADE,
            FOREIGN KEY(purchase_id) REFERENCES purchase_orders(id) ON DELETE SET NULL,
            FOREIGN KEY(warehouse_id) REFERENCES warehouse_requests(id) ON DELETE SET NULL
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS user_reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            note TEXT,
            due_date DATE,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
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
        db.execute("ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'active'")
    except:
        pass
    try:
        db.execute(
            "ALTER TABLE users ADD COLUMN permissions TEXT DEFAULT 'dashboard,projects,team,purchases,warehouse,romaneios,items,historico,relatorios'"
        )
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
    # Adicionar colunas que possam estar faltando
    columns_to_add = [
        ("items", "sku", "TEXT"),
        ("movements", "supplier", "TEXT"),
        ("movements", "unit_price", "REAL"),
        ("movements", "destination", "TEXT"),
        ("tasks", "sector", "TEXT"),
        ("projects", "assembly_start_date", "DATE"),
        ("projects", "assembly_end_date", "DATE"),
        ("projects", "event_start_date", "DATE"),
        ("projects", "event_end_date", "DATE"),
        ("projects", "dismantle_start_date", "DATE"),
        ("projects", "dismantle_end_date", "DATE"),
        ("projects", "assembly_address", "TEXT"),
        ("projects", "event_address", "TEXT"),
        ("project_requests", "approver_id", "INTEGER"),
        ("purchase_orders", "approver_id", "INTEGER"),
        ("warehouse_requests", "approver_id", "INTEGER"),
    ]
    
    for table, column, col_type in columns_to_add:
        try:
            db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
            db.commit()
        except sqlite3.OperationalError as e:
            if "duplicate column" not in str(e):
                print(f"Aviso: Erro ao adicionar {column} em {table}: {e}")
    
    # Corrigir valores NULL em colunas críticas
    db.execute("UPDATE users SET status = 'active' WHERE status IS NULL")
    db.execute("UPDATE users SET account_id = 1 WHERE account_id IS NULL")
    db.commit()
    
    db.execute(
        "INSERT OR IGNORE INTO accounts (id, name, plan, status) VALUES (1, 'Default Account', 'free', 'active')"
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


@app.before_request
def check_database():
    try:
        db = get_db()
        db.execute("SELECT 1").fetchone()
    except Exception as e:
        print(f"Database error in before_request: {e}")
        pass


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


@app.route("/project/<int:project_id>")
@login_required
def project_page(project_id):
    init_db()
    return render_template("project.html", project_id=project_id)


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
            if user["status"] != "active":
                return jsonify({"error": "Usuário desativado. Peça para o administrador reativar."}), 403
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

        if not username or not password:
            return jsonify({"error": "Usuário e senha obrigatórios"}), 400
        if len(username) < 3:
            return jsonify({"error": "Usuário deve ter pelo menos 3 caracteres"}), 400
        if len(password) < 6:
            return jsonify({"error": "Senha deve ter pelo menos 6 caracteres"}), 400
        if password != password_confirm:
            return jsonify({"error": "Senhas não conferem"}), 400
        if not company:
            return jsonify({"error": "Nome da empresa/equipe é obrigatório"}), 400

        db = get_db()
        existing = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if existing:
            return jsonify({"error": "Usuário já existe"}), 400

        db.execute(
            "INSERT INTO accounts (name, plan) VALUES (?, ?)",
            (company, plan),
        )
        account_id = db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]

        db.execute(
            "INSERT INTO users (account_id, username, password, email, role, status, permissions) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                account_id,
                username,
                generate_password_hash(password),
                email,
                "owner",
                "active",
                "dashboard,projects,team,purchases,warehouse,romaneios,items,historico,relatorios",
            ),
        )
        db.commit()
        return jsonify({"success": True})

    if "user_id" in session:
        return redirect(url_for("index"))
    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/api/user")
@login_required
def get_user():
    db = get_db()
    user = db.execute(
        "SELECT u.id, u.username, u.role, u.status AS user_status, u.permissions, a.name as account_name, a.plan, a.status FROM users u JOIN accounts a ON a.id = u.account_id WHERE u.id = ?",
        (session["user_id"],),
    ).fetchone()
    
    # Validar se usuário e conta foram encontrados
    if not user:
        session.clear()
        return jsonify({"error": "Nao autenticado"}), 401
    
    return jsonify({
        "id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "status": user["user_status"],
        "permissions": parse_permissions_value(user["permissions"]),
        "account_name": user["account_name"],
        "plan": user["plan"],
        "account_status": user["status"],
    })


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

        if not name:
            return jsonify({"error": "Nome do item é obrigatório."}), 400
        if quantity < 0:
            return jsonify({"error": "Quantidade não pode ser negativa."}), 400
        if min_quantity < 0:
            return jsonify({"error": "Quantidade mínima não pode ser negativa."}), 400

        db.execute(
            "INSERT INTO items (account_id, user_id, name, description, quantity, location, min_quantity, category, sku) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (account_id, user_id, name, description, quantity, location, min_quantity, category, sku),
        )
        db.commit()
        item_id = db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
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
    item = dict(item)

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
@permission_required("relatorios")
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


@app.route("/api/users", methods=["GET"])
@login_required
def list_users():
    db = get_db()
    account_id = session["account_id"]
    rows = db.execute(
        "SELECT id, username, email, role, status, permissions, created_at FROM users WHERE account_id = ? ORDER BY created_at DESC",
        (account_id,),
    ).fetchall()
    users = []
    for row in rows:
        user = dict(row)
        user["permissions"] = parse_permissions_value(user.get("permissions"))
        users.append(user)
    return jsonify(users)


@app.route("/api/team/invite", methods=["POST"])
@login_required
def invite_team_member():
    db = get_db()
    current_user = get_current_user()
    if current_user["role"] not in ("owner", "admin"):
        return jsonify({"error": "Apenas administradores podem convidar novos membros."}), 403

    account_id = session["account_id"]
    data = request.get_json() or {}
    username = (data.get("username", "") or "").strip()
    password = data.get("password", "")
    email = (data.get("email", "") or "").strip()
    role = (data.get("role", "member") or "member").strip()
    if role not in ("owner", "admin", "member"):
        role = "member"

    if role == "owner" and current_user["role"] != "owner":
        return jsonify({"error": "Somente o proprietário pode criar outro proprietário."}), 403

    if not username or not password:
        return jsonify({"error": "Usuário e senha são obrigatórios para convite."}), 400
    if len(username) < 3:
        return jsonify({"error": "Usuário deve ter pelo menos 3 caracteres."}), 400
    if len(password) < 6:
        return jsonify({"error": "Senha deve ter pelo menos 6 caracteres."}), 400

    existing = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if existing:
        return jsonify({"error": "Este usuário já existe."}), 400

    permissions = join_permissions(default_permissions_for_role(role))

    db.execute(
        "INSERT INTO users (account_id, username, password, email, role, status, permissions) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (account_id, username, generate_password_hash(password), email, role, "active", permissions),
    )
    db.commit()

    warning = None
    if email:
        sent, error_message = send_email(
            email,
            "Convite BACKSTAGE",
            f"Olá {username},\n\nVocê foi convidado para o BACKSTAGE.\nLogin: {username}\nSenha: {password}\n\nAcesse o sistema e altere sua senha após o primeiro acesso.",
        )
        if not sent:
            warning = f"Convite criado, mas não foi possível enviar email: {error_message}"
    else:
        warning = "Membro criado sem email. Informe o usuário manualmente sobre o acesso."

    response = {"success": True}
    if warning:
        response["warning"] = warning
    return jsonify(response)


@app.route("/api/users/<int:user_id>", methods=["PUT"])
@login_required
@permission_required("team")
def update_user(user_id):
    db = get_db()
    current_user = get_current_user()
    if current_user["role"] not in ("owner", "admin"):
        return jsonify({"error": "Apenas administradores podem editar usuários."}), 403

    user = db.execute("SELECT * FROM users WHERE id = ? AND account_id = ?", (user_id, session["account_id"])) .fetchone()
    if not user:
        return jsonify({"error": "Usuário não encontrado."}), 404

    data = request.get_json() or {}
    role = (data.get("role") or user["role"]).strip()
    status = (data.get("status") or user["status"]).strip()
    permissions = data.get("permissions")
    if isinstance(permissions, list):
        permissions = join_permissions(permissions)
    elif isinstance(permissions, str):
        permissions = permissions
    else:
        permissions = user["permissions"]

    if role not in ("owner", "admin", "member"):
        role = user["role"]
    if status not in ("active", "inactive"):
        status = user["status"]
    if role == "owner" and current_user["role"] != "owner":
        return jsonify({"error": "Somente o proprietário pode atribuir função owner."}), 403

    db.execute(
        "UPDATE users SET role = ?, status = ?, permissions = ? WHERE id = ?",
        (role, status, permissions, user_id),
    )
    db.commit()

    updated = db.execute(
        "SELECT id, username, email, role, status, permissions, created_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    result = dict(updated)
    result["permissions"] = parse_permissions_value(result.get("permissions"))
    return jsonify(result)


@app.route("/api/projects", methods=["GET", "POST"])
@login_required
def projects():
    db = get_db()
    account_id = session["account_id"]
    user = get_current_user()

    if request.method == "POST":
        data = request.get_json() or {}
        name = (data.get("name", "") or "").strip()
        description = (data.get("description", "") or "").strip()
        status = (data.get("status", "planejamento") or "planejamento").strip()
        start_date = data.get("start_date")
        due_date = data.get("due_date")
        assembly_start = data.get("assembly_start_date")
        assembly_end = data.get("assembly_end_date")
        event_start = data.get("event_start_date")
        event_end = data.get("event_end_date")
        dismantle_start = data.get("dismantle_start_date")
        dismantle_end = data.get("dismantle_end_date")
        assembly_address = data.get("assembly_address")
        event_address = data.get("event_address")
        members = data.get("members")

        if not name:
            return jsonify({"error": "Nome do projeto é obrigatório."}), 400

        db.execute(
            "INSERT INTO projects (account_id, owner_id, name, description, status, start_date, due_date, assembly_start_date, assembly_end_date, event_start_date, event_end_date, dismantle_start_date, dismantle_end_date, assembly_address, event_address) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (account_id, session["user_id"], name, description, status, start_date, due_date, assembly_start, assembly_end, event_start, event_end, dismantle_start, dismantle_end, assembly_address, event_address),
        )
        db.commit()
        project_id = db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        db.execute(
            "INSERT OR IGNORE INTO project_access (project_id, user_id, access) VALUES (?, ?, ?)",
            (project_id, session["user_id"], "edit"),
        )

        if isinstance(members, list):
            for member in members:
                user_id = parse_int(member.get("user_id"), 0)
                access = (member.get("access") or "view").strip()
                if access not in ("view", "edit"):
                    access = "view"
                if user_id and user_id != session["user_id"]:
                    target_user = db.execute(
                        "SELECT id FROM users WHERE id = ? AND account_id = ?",
                        (user_id, account_id),
                    ).fetchone()
                    if target_user:
                        db.execute(
                            "INSERT OR REPLACE INTO project_access (project_id, user_id, access) VALUES (?, ?, ?)",
                            (project_id, user_id, access),
                        )
        db.commit()

        project = db.execute(
            "SELECT p.*, u.username as owner_name FROM projects p LEFT JOIN users u ON u.id = p.owner_id WHERE p.id = ?",
            (project_id,),
        ).fetchone()
        return jsonify(dict(project)), 201

    rows = db.execute(
        "SELECT p.*, u.username as owner_name, pa.access AS access_level FROM projects p "
        "LEFT JOIN users u ON u.id = p.owner_id "
        "LEFT JOIN project_access pa ON pa.project_id = p.id AND pa.user_id = ? "
        "WHERE p.account_id = ? AND (p.owner_id = ? OR pa.user_id = ?) "
        "ORDER BY p.created_at DESC",
        (user["id"], account_id, user["id"], user["id"]),
    ).fetchall()
    return jsonify([dict(row) for row in rows])


@app.route("/api/projects/<int:project_id>", methods=["GET", "PUT", "DELETE"])
@login_required
def project_detail(project_id):
    db = get_db()
    account_id = session["account_id"]
    current_user = get_current_user()
    project = db.execute("SELECT * FROM projects WHERE id = ? AND account_id = ?", (project_id, account_id)).fetchone()
    if not project or not has_project_access(current_user, project_id):
        return jsonify({"error": "Projeto não encontrado."}), 404

    if request.method == "GET":
        project_data = db.execute(
            "SELECT p.*, u.username as owner_name FROM projects p LEFT JOIN users u ON u.id = p.owner_id WHERE p.id = ?",
            (project_id,),
        ).fetchone()
        members = db.execute(
            "SELECT pa.user_id, u.username, pa.access FROM project_access pa JOIN users u ON u.id = pa.user_id WHERE pa.project_id = ?",
            (project_id,),
        ).fetchall()
        project_data = dict(project_data)
        project_data["access_level"] = "edit" if has_project_edit_access(current_user, project_id) else "view"
        project_data["members"] = [dict(row) for row in members]

        task_stats = db.execute(
            "SELECT COUNT(*) AS total, "
            "SUM(CASE WHEN status = 'concluído' THEN 1 ELSE 0 END) AS completed, "
            "SUM(CASE WHEN status != 'concluído' THEN 1 ELSE 0 END) AS open_count, "
            "SUM(CASE WHEN status != 'concluído' AND date(due_date) < date('now') THEN 1 ELSE 0 END) AS overdue_count "
            "FROM tasks WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        total_tasks = task_stats["total"] or 0
        completed_tasks = task_stats["completed"] or 0
        open_tasks = task_stats["open_count"] or 0
        overdue_tasks = task_stats["overdue_count"] or 0
        progress = int((completed_tasks / total_tasks) * 100) if total_tasks else 0

        open_requests = db.execute(
            "SELECT COUNT(*) AS count FROM project_requests WHERE project_id = ? AND status = 'aberta'",
            (project_id,),
        ).fetchone()["count"]

        due_soon = db.execute(
            "SELECT name, due_date FROM tasks WHERE project_id = ? AND status != 'concluído' "
            "AND date(due_date) BETWEEN date('now') AND date('now', '+3 days') ORDER BY due_date ASC LIMIT 4",
            (project_id,),
        ).fetchall()

        alerts = []
        if overdue_tasks:
            alerts.append({
                "type": "overdue",
                "message": f"{overdue_tasks} tarefas atrasadas",
            })
        for row in due_soon:
            alerts.append({
                "type": "due_soon",
                "message": f"{row['name']} vence em {row['due_date']}",
            })
        if open_requests:
            alerts.append({
                "type": "requests",
                "message": f"{open_requests} solicitações abertas",
            })

        recent_tasks = db.execute(
            "SELECT 'task' AS type, name AS title, status AS detail, due_date AS date, created_at "
            "FROM tasks WHERE project_id = ? ORDER BY created_at DESC LIMIT 4",
            (project_id,),
        ).fetchall()
        recent_discussions = db.execute(
            "SELECT 'discussion' AS type, message AS title, kind AS detail, NULL AS date, created_at "
            "FROM project_discussions WHERE project_id = ? ORDER BY created_at DESC LIMIT 4",
            (project_id,),
        ).fetchall()
        recent_requests = db.execute(
            "SELECT 'request' AS type, title AS title, status AS detail, NULL AS date, created_at "
            "FROM project_requests WHERE project_id = ? ORDER BY created_at DESC LIMIT 4",
            (project_id,),
        ).fetchall()

        recent_activity = sorted(
            [dict(row) for row in recent_tasks] + [dict(row) for row in recent_discussions] + [dict(row) for row in recent_requests],
            key=lambda item: item["created_at"],
            reverse=True,
        )[:6]

        project_data["metrics"] = {
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "open_tasks": open_tasks,
            "overdue_tasks": overdue_tasks,
            "open_requests": open_requests,
            "progress": progress,
        }
        project_data["alerts"] = alerts
        project_data["recent_activity"] = recent_activity
        return jsonify(project_data)

    if request.method == "DELETE":
        if not has_project_edit_access(current_user, project_id):
            return jsonify({"error": "Sem permissão para remover este projeto."}), 403
        db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        db.commit()
        return jsonify({"success": True})

    if not has_project_edit_access(current_user, project_id):
        return jsonify({"error": "Sem permissão para editar este projeto."}), 403

    data = request.get_json() or {}
    name = (data.get("name", "") or "").strip()
    description = (data.get("description", "") or "").strip()
    status = (data.get("status", project["status"]) or project["status"]).strip()
    start_date = data.get("start_date")
    due_date = data.get("due_date")
    assembly_start = data.get("assembly_start_date")
    assembly_end = data.get("assembly_end_date")
    event_start = data.get("event_start_date")
    event_end = data.get("event_end_date")
    dismantle_start = data.get("dismantle_start_date")
    dismantle_end = data.get("dismantle_end_date")
    assembly_address = data.get("assembly_address")
    event_address = data.get("event_address")
    members = data.get("members")

    if not name:
        return jsonify({"error": "Nome do projeto é obrigatório."}), 400

    db.execute(
        "UPDATE projects SET name = ?, description = ?, status = ?, start_date = ?, due_date = ?, assembly_start_date = ?, assembly_end_date = ?, event_start_date = ?, event_end_date = ?, dismantle_start_date = ?, dismantle_end_date = ?, assembly_address = ?, event_address = ? WHERE id = ?",
        (name, description, status, start_date, due_date, assembly_start, assembly_end, event_start, event_end, dismantle_start, dismantle_end, assembly_address, event_address, project_id),
    )

    if isinstance(members, list):
        db.execute("DELETE FROM project_access WHERE project_id = ? AND user_id != ?", (project_id, project["owner_id"]))
        for member in members:
            user_id = parse_int(member.get("user_id"), 0)
            access = (member.get("access") or "view").strip()
            if access not in ("view", "edit"):
                access = "view"
            if user_id and user_id != project["owner_id"]:
                target_user = db.execute(
                    "SELECT id FROM users WHERE id = ? AND account_id = ?",
                    (user_id, account_id),
                ).fetchone()
                if target_user:
                    db.execute(
                        "INSERT OR REPLACE INTO project_access (project_id, user_id, access) VALUES (?, ?, ?)",
                        (project_id, user_id, access),
                    )

    db.commit()
    updated = db.execute(
        "SELECT p.*, u.username as owner_name FROM projects p LEFT JOIN users u ON u.id = p.owner_id WHERE p.id = ?",
        (project_id,),
    ).fetchone()
    return jsonify(dict(updated))


@app.route("/api/projects/<int:project_id>/timeline", methods=["GET"])
@login_required
@permission_required("projects")
def project_timeline(project_id):
    db = get_db()
    current_user = get_current_user()
    if not has_project_access(current_user, project_id):
        return jsonify({"error": "Projeto não encontrado."}), 404

    project = db.execute(
        "SELECT * FROM projects WHERE id = ? AND account_id = ?",
        (project_id, session["account_id"]),
    ).fetchone()
    if not project:
        return jsonify({"error": "Projeto não encontrado."}), 404

    timeline = []
    if project["start_date"]:
        timeline.append({
            "type": "start",
            "title": "Início do projeto",
            "detail": f"Status: {project['status']}",
            "date": project["start_date"],
        })
    if project["due_date"]:
        timeline.append({
            "type": "milestone",
            "title": "Entrega prevista",
            "detail": "Data de conclusão planejada",
            "date": project["due_date"],
        })

    tasks = db.execute(
        "SELECT id, name, status, due_date, created_at FROM tasks WHERE project_id = ? ORDER BY due_date IS NULL, due_date ASC, created_at ASC",
        (project_id,),
    ).fetchall()

    for task in tasks:
        timeline.append({
            "type": "task",
            "title": task["name"],
            "detail": task["status"] or "Tarefa",
            "date": task["due_date"] or task["created_at"],
        })

    timeline.sort(key=lambda item: item["date"] or "")
    return jsonify(timeline)


@app.route("/api/projects/<int:project_id>/tasks", methods=["GET", "POST"])
@login_required
def project_tasks(project_id):
    db = get_db()
    current_user = get_current_user()
    if not has_project_access(current_user, project_id):
        return jsonify({"error": "Projeto não encontrado."}), 404

    if request.method == "POST":
        data = request.get_json() or {}
        name = (data.get("name", "") or "").strip()
        description = (data.get("description", "") or "").strip()
        status = (data.get("status", "pendente") or "pendente").strip()
        priority = (data.get("priority", "média") or "média").strip()
        assigned_to = data.get("assigned_to")
        due_date = data.get("due_date")

        if not name:
            return jsonify({"error": "Nome da tarefa é obrigatório."}), 400

        db.execute(
            "INSERT INTO tasks (project_id, assigned_to, sector, name, description, status, priority, due_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (project_id, None if isinstance(assigned_to, list) else parse_int(assigned_to, None), data.get("sector"), name, description, status, priority, due_date),
        )
        db.commit()
        task_id = db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        # handle multiple assignees if provided
        if isinstance(assigned_to, list):
            # clear any existing
            db.execute("DELETE FROM task_assignees WHERE task_id = ?", (task_id,))
            for uid in assigned_to:
                try:
                    uid_i = int(uid)
                except Exception:
                    continue
                db.execute("INSERT OR IGNORE INTO task_assignees (task_id, user_id) VALUES (?, ?)", (task_id, uid_i))
            db.commit()

        task = db.execute(
            "SELECT t.* FROM tasks t WHERE t.id = ?",
            (task_id,),
        ).fetchone()
        return jsonify(dict(task)), 201

    rows = db.execute(
        "SELECT t.* FROM tasks t WHERE t.project_id = ? ORDER BY t.created_at DESC",
        (project_id,),
    ).fetchall()
    result = []
    for row in rows:
        task = dict(row)
        ass = db.execute(
            "SELECT u.id, u.username FROM task_assignees ta JOIN users u ON u.id = ta.user_id WHERE ta.task_id = ?",
            (task["id"],),
        ).fetchall()
        task["assignees"] = [dict(a) for a in ass]
        # fallback to single assigned_to column for compatibility
        if task.get("assigned_to") and not task["assignees"]:
            u = db.execute("SELECT id, username FROM users WHERE id = ?", (task["assigned_to"],)).fetchone()
            if u:
                task["assignees"] = [dict(u)]
        result.append(task)
    return jsonify(result)


@app.route("/api/projects/<int:project_id>/discussions", methods=["GET", "POST"])
@login_required
def project_discussions(project_id):
    db = get_db()
    current_user = get_current_user()
    if not has_project_access(current_user, project_id):
        return jsonify({"error": "Projeto não encontrado."}), 404

    if request.method == "POST":
        data = request.get_json() or {}
        kind = (data.get("kind", "chat") or "chat").strip()
        message = (data.get("message", "") or "").strip()

        if not message:
            return jsonify({"error": "Mensagem é obrigatória."}), 400

        db.execute(
            "INSERT INTO project_discussions (project_id, user_id, kind, message) VALUES (?, ?, ?, ?)",
            (project_id, session["user_id"], kind, message),
        )
        db.commit()
        return jsonify({"success": True}), 201

    kind = request.args.get("kind", "").strip()
    query = "SELECT d.*, u.username as author_name FROM project_discussions d JOIN users u ON u.id = d.user_id WHERE d.project_id = ?"
    params = [project_id]
    if kind:
        query += " AND d.kind = ?"
        params.append(kind)
    query += " ORDER BY d.created_at DESC"
    rows = db.execute(query, params).fetchall()
    return jsonify([dict(row) for row in rows])


@app.route("/api/projects/<int:project_id>/requests", methods=["GET", "POST"])
@login_required
def project_requests(project_id):
    db = get_db()
    current_user = get_current_user()
    if not has_project_access(current_user, project_id):
        return jsonify({"error": "Projeto não encontrado."}), 404

    if request.method == "POST":
        data = request.get_json() or {}
        request_type = (data.get("type", "compra") or "compra").strip()
        title = (data.get("title", "") or "").strip()
        description = (data.get("description", "") or "").strip()
        approver_id = parse_int(data.get("approver_id"), None) or parse_int(data.get("approverId"), None)

        if not title:
            return jsonify({"error": "Título da solicitação é obrigatório."}), 400

        db.execute(
            "INSERT INTO project_requests (project_id, user_id, type, title, description, approver_id) VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, session["user_id"], request_type, title, description, approver_id),
        )
        request_id = db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]

        if request_type == "compra":
            db.execute(
                "INSERT INTO purchase_orders (project_id, project_request_id, user_id, approver_id, title, description) VALUES (?, ?, ?, ?, ?, ?)",
                (project_id, request_id, session["user_id"], approver_id, title, description),
            )
        elif request_type == "material":
            db.execute(
                "INSERT INTO warehouse_requests (project_id, project_request_id, user_id, approver_id, title, description) VALUES (?, ?, ?, ?, ?, ?)",
                (project_id, request_id, session["user_id"], approver_id, title, description),
            )

        db.commit()
        return jsonify({"success": True}), 201

    rows = db.execute(
        "SELECT r.*, u.username as requester, a.username as approver_name FROM project_requests r JOIN users u ON u.id = r.user_id LEFT JOIN users a ON a.id = r.approver_id WHERE r.project_id = ? ORDER BY r.created_at DESC",
        (project_id,),
    ).fetchall()
    return jsonify([dict(row) for row in rows])


@app.route("/api/projects/<int:project_id>/requests/<int:request_id>", methods=["PUT"])
@login_required
@permission_required("projects")
def update_project_request(project_id, request_id):
    db = get_db()
    current_user = get_current_user()
    if not has_project_access(current_user, project_id):
        return jsonify({"error": "Projeto não encontrado."}), 404

    request_row = db.execute(
        "SELECT * FROM project_requests WHERE id = ? AND project_id = ?",
        (request_id, project_id),
    ).fetchone()
    if not request_row:
        return jsonify({"error": "Solicitação não encontrada."}), 404
    request_row = dict(request_row)

    # allow approver, project editors/owner/admin, or the requester to update (requester can cancel)
    approver_id = request_row.get("approver_id")
    if not (has_project_edit_access(current_user, project_id) or current_user["id"] == request_row["user_id"] or (approver_id and current_user["id"] == approver_id)):
        return jsonify({"error": "Sem permissão para atualizar esta solicitação."}), 403

    data = request.get_json() or {}
    status = (data.get("status") or request_row["status"]).strip()
    if status not in ("aberta", "aprovada", "atendida", "recusada", "cancelada"):
        return jsonify({"error": "Status inválido."}), 400

    db.execute("UPDATE project_requests SET status = ? WHERE id = ?", (status, request_id))
    db.commit()
    updated = db.execute("SELECT * FROM project_requests WHERE id = ?", (request_id,)).fetchone()
    return jsonify(dict(updated))


@app.route("/api/user/dashboard", methods=["GET"])
@login_required
def user_dashboard():
    db = get_db()
    user = get_current_user()
    today = datetime.utcnow().date().isoformat()
    soon = (datetime.utcnow().date() + timedelta(days=3)).isoformat()

    tasks = db.execute(
        "SELECT t.*, p.name AS project_name FROM tasks t LEFT JOIN projects p ON p.id = t.project_id "
        "WHERE t.assigned_to = ? AND t.status NOT IN ('concluído', 'concluida') ORDER BY t.due_date IS NULL, t.due_date ASC, t.created_at DESC LIMIT 10",
        (user["id"],),
    ).fetchall()

    reminders = db.execute(
        "SELECT * FROM user_reminders WHERE user_id = ? ORDER BY due_date IS NULL, due_date ASC, created_at DESC LIMIT 10",
        (user["id"],),
    ).fetchall()

    overdue_tasks = db.execute(
        "SELECT t.*, p.name AS project_name FROM tasks t LEFT JOIN projects p ON p.id = t.project_id "
        "WHERE t.assigned_to = ? AND t.status NOT IN ('concluído', 'concluida') AND date(t.due_date) < date(?) ORDER BY t.due_date ASC LIMIT 5",
        (user["id"], today),
    ).fetchall()

    low_stock_items = db.execute(
        "SELECT id, name, quantity, min_quantity, location FROM items WHERE account_id = ? AND quantity <= COALESCE(min_quantity, 5) ORDER BY quantity ASC LIMIT 5",
        (session["account_id"],),
    ).fetchall()

    alerts = []
    for row in overdue_tasks:
        alerts.append({
            "type": "task",
            "message": f"Tarefa atrasada: {row['name']} ({row['project_name'] or 'Sem projeto'})",
            "due_date": row["due_date"],
        })
    for item in low_stock_items:
        alerts.append({
            "type": "stock",
            "message": f"Estoque baixo: {item['name']} ({item['quantity']} / {item['min_quantity']})",
            "location": item["location"],
        })

    return jsonify({
        "tasks": [dict(task) for task in tasks],
        "reminders": [dict(rem) for rem in reminders],
        "alerts": alerts,
    })


@app.route("/api/user/reminders", methods=["GET", "POST"])
@login_required
@permission_required("dashboard")
def user_reminders():
    db = get_db()
    user = get_current_user()
    if request.method == "POST":
        data = request.get_json() or {}
        title = (data.get("title", "") or "").strip()
        note = (data.get("note", "") or "").strip()
        due_date = data.get("due_date")

        if not title:
            return jsonify({"error": "Título do lembrete é obrigatório."}), 400

        db.execute(
            "INSERT INTO user_reminders (user_id, title, note, due_date) VALUES (?, ?, ?, ?)",
            (user["id"], title, note, due_date),
        )
        db.commit()
        reminder_id = db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        reminder = db.execute("SELECT * FROM user_reminders WHERE id = ?", (reminder_id,)).fetchone()
        return jsonify(dict(reminder)), 201

    reminders = db.execute(
        "SELECT * FROM user_reminders WHERE user_id = ? ORDER BY due_date IS NULL, due_date ASC, created_at DESC",
        (user["id"],),
    ).fetchall()
    return jsonify([dict(reminder) for reminder in reminders])


@app.route("/api/purchases", methods=["GET"])
@login_required
@permission_required("purchases")
def purchases():
    db = get_db()
    account_id = session["account_id"]
    user = get_current_user()
    if user["role"] in ("owner", "admin"):
        rows = db.execute(
            "SELECT po.*, p.name AS project_name, u.username AS requester_name, a.username AS approver_name FROM purchase_orders po "
            "JOIN projects p ON p.id = po.project_id "
            "JOIN users u ON u.id = po.user_id "
            "LEFT JOIN users a ON a.id = po.approver_id "
            "WHERE p.account_id = ? "
            "ORDER BY po.created_at DESC",
            (account_id,),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT po.*, p.name AS project_name, u.username AS requester_name, a.username AS approver_name FROM purchase_orders po "
            "JOIN projects p ON p.id = po.project_id "
            "JOIN users u ON u.id = po.user_id "
            "LEFT JOIN users a ON a.id = po.approver_id "
            "WHERE p.account_id = ? AND (p.owner_id = ? OR po.project_id IN (SELECT project_id FROM project_access WHERE user_id = ?) OR po.approver_id = ?) "
            "ORDER BY po.created_at DESC",
            (account_id, user["id"], user["id"], user["id"]),
        ).fetchall()
    return jsonify([dict(row) for row in rows])


@app.route("/api/purchases/<int:purchase_id>", methods=["PUT"])
@login_required
@permission_required("purchases")
def update_purchase(purchase_id):
    db = get_db()
    user = get_current_user()
    account_id = session["account_id"]
    purchase = db.execute(
        "SELECT po.*, p.owner_id, p.id as project_id FROM purchase_orders po JOIN projects p ON p.id = po.project_id WHERE po.id = ? AND p.account_id = ?",
        (purchase_id, account_id),
    ).fetchone()
    try:
        approver_id = purchase["approver_id"]
    except Exception:
        approver_id = None
    if not purchase or not (has_project_edit_access(user, purchase["project_id"]) or user["id"] == approver_id):
        return jsonify({"error": "Solicitação não encontrada ou sem permissão."}), 404

    data = request.get_json() or {}
    status = (data.get("status") or purchase["status"]).strip()
    if status not in ("aberta", "aprovada", "atendida", "recusada", "cancelada"):
        return jsonify({"error": "Status inválido."}), 400

    db.execute("UPDATE purchase_orders SET status = ? WHERE id = ?", (status, purchase_id))
    db.commit()
    updated = db.execute("SELECT * FROM purchase_orders WHERE id = ?", (purchase_id,)).fetchone()
    return jsonify(dict(updated))


@app.route("/api/warehouse", methods=["GET"])
@login_required
@permission_required("warehouse")
def warehouse():
    db = get_db()
    account_id = session["account_id"]
    user = get_current_user()
    if user["role"] in ("owner", "admin"):
        rows = db.execute(
            "SELECT wr.*, p.name AS project_name, u.username AS requester_name, a.username AS approver_name FROM warehouse_requests wr "
            "JOIN projects p ON p.id = wr.project_id "
            "JOIN users u ON u.id = wr.user_id "
            "LEFT JOIN users a ON a.id = wr.approver_id "
            "WHERE p.account_id = ? "
            "ORDER BY wr.created_at DESC",
            (account_id,),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT wr.*, p.name AS project_name, u.username AS requester_name, a.username AS approver_name FROM warehouse_requests wr "
            "JOIN projects p ON p.id = wr.project_id "
            "JOIN users u ON u.id = wr.user_id "
            "LEFT JOIN users a ON a.id = wr.approver_id "
            "WHERE p.account_id = ? AND (p.owner_id = ? OR wr.project_id IN (SELECT project_id FROM project_access WHERE user_id = ?) OR wr.approver_id = ?) "
            "ORDER BY wr.created_at DESC",
            (account_id, user["id"], user["id"], user["id"]),
        ).fetchall()
    return jsonify([dict(row) for row in rows])


@app.route("/api/warehouse/<int:warehouse_id>", methods=["PUT"])
@login_required
@permission_required("warehouse")
def update_warehouse_request(warehouse_id):
    db = get_db()
    user = get_current_user()
    account_id = session["account_id"]
    warehouse = db.execute(
        "SELECT wr.*, p.owner_id, p.id as project_id FROM warehouse_requests wr JOIN projects p ON p.id = wr.project_id WHERE wr.id = ? AND p.account_id = ?",
        (warehouse_id, account_id),
    ).fetchone()
    try:
        wr_approver = warehouse["approver_id"]
    except Exception:
        wr_approver = None
    if not warehouse or not (has_project_edit_access(user, warehouse["project_id"]) or user["id"] == wr_approver):
        return jsonify({"error": "Solicitação não encontrada ou sem permissão."}), 404

    data = request.get_json() or {}
    status = (data.get("status") or warehouse["status"]).strip()
    if status not in ("aberta", "aprovada", "atendida", "recusada", "cancelada"):
        return jsonify({"error": "Status inválido."}), 400

    db.execute("UPDATE warehouse_requests SET status = ? WHERE id = ?", (status, warehouse_id))
    db.commit()
    updated = db.execute("SELECT * FROM warehouse_requests WHERE id = ?", (warehouse_id,)).fetchone()
    return jsonify(dict(updated))


@app.route("/api/romaneios", methods=["GET", "POST"])
@login_required
@permission_required("romaneios")
def romaneios():
    db = get_db()
    account_id = session["account_id"]
    user = get_current_user()

    if request.method == "POST":
        data = request.get_json() or {}
        project_id = parse_int(data.get("project_id"), 0)
        purchase_id = parse_int(data.get("purchase_id"), 0) or None
        warehouse_id = parse_int(data.get("warehouse_id"), 0) or None
        name = (data.get("name", "") or "").strip()
        note = (data.get("note", "") or "").strip()

        if not project_id or not name:
            return jsonify({"error": "Projeto e nome do romaneio são obrigatórios."}), 400

        project = db.execute(
            "SELECT * FROM projects WHERE id = ? AND account_id = ?",
            (project_id, account_id),
        ).fetchone()
        if not project or not has_project_access(user, project_id):
            return jsonify({"error": "Projeto não encontrado."}), 404

        if purchase_id:
            purchase = db.execute(
                "SELECT * FROM purchase_orders WHERE id = ? AND project_id = ?",
                (purchase_id, project_id),
            ).fetchone()
            if not purchase:
                return jsonify({"error": "Solicitação de compra inválida para este projeto."}), 400

        if warehouse_id:
            warehouse = db.execute(
                "SELECT * FROM warehouse_requests WHERE id = ? AND project_id = ?",
                (warehouse_id, project_id),
            ).fetchone()
            if not warehouse:
                return jsonify({"error": "Solicitação de almoxarifado inválida para este projeto."}), 400

        db.execute(
            "INSERT INTO romaneios (project_id, purchase_id, warehouse_id, name, note) VALUES (?, ?, ?, ?, ?)",
            (project_id, purchase_id, warehouse_id, name, note),
        )
        db.commit()
        return jsonify({"success": True}), 201

    if user["role"] in ("owner", "admin"):
        rows = db.execute(
            "SELECT r.*, p.name AS project_name, po.title AS purchase_title, wr.title AS warehouse_title "
            "FROM romaneios r "
            "JOIN projects p ON p.id = r.project_id "
            "LEFT JOIN purchase_orders po ON po.id = r.purchase_id "
            "LEFT JOIN warehouse_requests wr ON wr.id = r.warehouse_id "
            "WHERE p.account_id = ? "
            "ORDER BY r.created_at DESC",
            (account_id,),
        ).fetchall()
    else:
        rows = db.execute(
            "SELECT r.*, p.name AS project_name, po.title AS purchase_title, wr.title AS warehouse_title "
            "FROM romaneios r "
            "JOIN projects p ON p.id = r.project_id "
            "LEFT JOIN purchase_orders po ON po.id = r.purchase_id "
            "LEFT JOIN warehouse_requests wr ON wr.id = r.warehouse_id "
            "WHERE p.account_id = ? AND (p.owner_id = ? OR r.project_id IN (SELECT project_id FROM project_access WHERE user_id = ?)) "
            "ORDER BY r.created_at DESC",
            (account_id, user["id"], user["id"]),
        ).fetchall()
    return jsonify([dict(row) for row in rows])


@app.route("/api/romaneios/<int:romaneio_id>", methods=["PUT"])
@login_required
@permission_required("romaneios")
def update_romaneio_status(romaneio_id):
    db = get_db()
    user = get_current_user()
    account_id = session["account_id"]
    romaneio = db.execute(
        "SELECT r.*, p.id AS project_id FROM romaneios r JOIN projects p ON p.id = r.project_id WHERE r.id = ? AND p.account_id = ?",
        (romaneio_id, account_id),
    ).fetchone()
    if not romaneio or not has_project_edit_access(user, romaneio["project_id"]):
        return jsonify({"error": "Romaneio não encontrado ou sem permissão."}), 404

    data = request.get_json() or {}
    status = (data.get("status") or romaneio["status"]).strip()
    if status not in ("aberto", "concluído", "cancelado"):
        return jsonify({"error": "Status inválido."}), 400

    db.execute("UPDATE romaneios SET status = ? WHERE id = ?", (status, romaneio_id))
    db.commit()
    updated = db.execute("SELECT * FROM romaneios WHERE id = ?", (romaneio_id,)).fetchone()
    return jsonify(dict(updated))


@app.route("/api/tasks/<int:task_id>", methods=["PUT", "DELETE"])
@login_required
def task_detail(task_id):
    db = get_db()
    current_user = get_current_user()
    account_id = session["account_id"]
    task = db.execute(
        "SELECT t.*, t.project_id FROM tasks t JOIN projects p ON p.id = t.project_id WHERE t.id = ? AND p.account_id = ?",
        (task_id, account_id),
    ).fetchone()
    if not task or not has_project_access(current_user, task["project_id"]):
        return jsonify({"error": "Tarefa não encontrada."}), 404
    task = dict(task)

    # allow project editors/owners/admins or task assignees (including single assigned_to) to modify task
    assignees = db.execute("SELECT user_id FROM task_assignees WHERE task_id = ?", (task_id,)).fetchall()
    assignee_ids = [a["user_id"] for a in assignees] if assignees else []
    try:
        single_assigned = task["assigned_to"]
    except Exception:
        single_assigned = None
    allowed = (
        has_project_edit_access(current_user, task["project_id"]) or
        current_user["id"] in assignee_ids or
        (single_assigned is not None and current_user["id"] == single_assigned)
    )
    if not allowed:
        return jsonify({"error": "Sem permissão para modificar esta tarefa."}), 403

    if request.method == "DELETE":
        db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        db.commit()
        return jsonify({"success": True})

    data = request.get_json() or {}
    name = (data.get("name", task["name"]) or task["name"]).strip()
    description = (data.get("description", task.get("description", "")) or task.get("description", "")).strip()
    status = (data.get("status", task["status"]) or task["status"]).strip()
    priority = (data.get("priority", task["priority"]) or task["priority"]).strip()
    assigned_to = data.get("assigned_to")
    due_date = data.get("due_date")

    if not name:
        return jsonify({"error": "Nome da tarefa é obrigatório."}), 400

    db.execute(
        "UPDATE tasks SET name = ?, description = ?, status = ?, priority = ?, assigned_to = ?, due_date = ?, sector = ? WHERE id = ?",
        (name, description, status, priority, None if isinstance(assigned_to, list) else parse_int(assigned_to, task.get("assigned_to")), due_date, data.get("sector"), task_id),
    )
    db.commit()
    # update task_assignees table if a list of assignees provided
    if isinstance(assigned_to, list):
        db.execute("DELETE FROM task_assignees WHERE task_id = ?", (task_id,))
        for uid in assigned_to:
            try:
                uid_i = int(uid)
            except Exception:
                continue
            db.execute("INSERT OR IGNORE INTO task_assignees (task_id, user_id) VALUES (?, ?)", (task_id, uid_i))
        db.commit()
    updated = db.execute(
        "SELECT t.*, u.username as assigned_name FROM tasks t LEFT JOIN users u ON u.id = t.assigned_to WHERE t.id = ?",
        (task_id,),
    ).fetchone()
    return jsonify(dict(updated))


@app.route("/api/tasks/<int:task_id>/workspace", methods=["GET"])
@login_required
@permission_required("projects")
def task_workspace(task_id):
    db = get_db()
    current_user = get_current_user()
    task = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not task:
        return jsonify({"error": "Tarefa não encontrada."}), 404
    # assignees
    assignees = db.execute(
        "SELECT u.id, u.username FROM task_assignees ta JOIN users u ON u.id = ta.user_id WHERE ta.task_id = ?",
        (task_id,),
    ).fetchall()
    # comments
    comments = db.execute(
        "SELECT c.*, u.username as author FROM task_comments c JOIN users u ON u.id = c.user_id WHERE c.task_id = ? ORDER BY c.created_at ASC",
        (task_id,),
    ).fetchall()
    # subtasks
    subtasks = db.execute("SELECT * FROM task_subtasks WHERE task_id = ? ORDER BY id ASC", (task_id,)).fetchall()
    # checklist
    checklist = db.execute("SELECT * FROM task_checklist WHERE task_id = ? ORDER BY id ASC", (task_id,)).fetchall()

    return jsonify({
        "task": dict(task),
        "assignees": [dict(a) for a in assignees],
        "comments": [dict(c) for c in comments],
        "subtasks": [dict(s) for s in subtasks],
        "checklist": [dict(ch) for ch in checklist],
    })


@app.route("/api/tasks/<int:task_id>/comments", methods=["POST"])
@login_required
@permission_required("projects")
def add_task_comment(task_id):
    db = get_db()
    current_user = get_current_user()
    data = request.get_json() or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "Mensagem é obrigatória."}), 400
    task = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    task = db.execute(
        "SELECT t.*, t.project_id FROM tasks t JOIN projects p ON p.id = t.project_id WHERE t.id = ? AND p.account_id = ?",
        (task_id, session["account_id"]),
    ).fetchone()
    if not task or not has_project_access(current_user, task["project_id"]):
        return jsonify({"error": "Tarefa não encontrada."}), 404
    db.execute("INSERT INTO task_comments (task_id, user_id, message) VALUES (?, ?, ?)", (task_id, current_user["id"], message))
    db.commit()
    comment_id = db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
    comment = db.execute("SELECT c.*, u.username as author FROM task_comments c JOIN users u ON u.id = c.user_id WHERE c.id = ?", (comment_id,)).fetchone()
    return jsonify(dict(comment)), 201


if __name__ == "__main__":
    app.run(debug=True)
