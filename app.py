from datetime import date, datetime, timedelta
import io
import os
from functools import wraps
from typing import Any, TypedDict, cast

from dotenv import load_dotenv
import mysql.connector
import xlsxwriter
from flask import Flask, jsonify, redirect, render_template, request, send_file, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from db import get_conn, init_db

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv()


class CurrentUser(TypedDict):
    id: int
    username: str


app = Flask(
    __name__,
    template_folder=os.path.join(_BASE_DIR, "templates"),
    static_folder=os.path.join(_BASE_DIR, "static"),
)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-this-in-production")
db_ready = False


@app.before_request
def ensure_db_ready():
    global db_ready
    if not db_ready:
        try:
            init_db()
            db_ready = True
        except Exception as e:
            missing = [v for v in ["DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME"] if not os.getenv(v)]
            hint = (f"Missing env vars: {', '.join(missing)}" if missing else f"DB connection failed: {e}")
            return (
                f"<h2>⚠️ Database not configured</h2><p>{hint}</p>"
                f"<p>Set the required environment variables.</p>",
                503,
            )


def get_current_user() -> "CurrentUser | None":
    uid = session.get("user_id")
    username = session.get("username")
    if not isinstance(uid, int) or not isinstance(username, str) or not username:
        return None
    return {"id": uid, "username": username}


def require_current_user() -> CurrentUser:
    user = get_current_user()
    if user is None:
        raise RuntimeError("authenticated user not found in session")
    return user


def login_required(view_fn):
    @wraps(view_fn)
    def wrapped(*args, **kwargs):
        if not get_current_user():
            return redirect(url_for("login_page"))
        return view_fn(*args, **kwargs)
    return wrapped


def login_required_api(view_fn):
    @wraps(view_fn)
    def wrapped(*args, **kwargs):
        if not get_current_user():
            return jsonify({"error": "unauthorized"}), 401
        return view_fn(*args, **kwargs)
    return wrapped


def parse_amount(raw):
    try:
        if raw is None:
            return 0.0
        val = str(raw).strip().replace(",", "").replace("$", "").replace("Rs", "").replace("₹", "")
        return float(val) if val else 0.0
    except Exception:
        return 0.0


# ─── Pages ────────────────────────────────────────────────────────────────────

@app.route("/")
def root():
    user = get_current_user()
    return render_template("home.html", username=user["username"] if user else None)


@app.route("/login", methods=["GET", "POST"])
def login_page():
    if request.method == "GET":
        if get_current_user():
            return redirect(url_for("user_home"))
        return render_template("login.html")

    payload = cast(dict[str, Any], request.form or request.json or {})
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""
    if not username or not password:
        return jsonify({"ok": False, "error": "Username and password are required."}), 400

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, username, password_hash FROM users WHERE username=%s", (username,))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if row is None:
        return jsonify({"ok": False, "error": "Invalid credentials."}), 401

    user_id, db_username, password_hash = cast(tuple[Any, ...], row)
    if not check_password_hash(password_hash, password):
        return jsonify({"ok": False, "error": "Invalid credentials."}), 401

    session["user_id"] = user_id
    session["username"] = db_username
    return jsonify({"ok": True, "redirect": url_for("user_home")})


@app.route("/register", methods=["POST"])
def register():
    payload = cast(dict[str, Any], request.form or request.json or {})
    username = (payload.get("username") or "").strip()
    password = payload.get("password") or ""

    if len(username) < 3:
        return jsonify({"ok": False, "error": "Username must be at least 3 characters."}), 400
    if len(password) < 6:
        return jsonify({"ok": False, "error": "Password must be at least 6 characters."}), 400

    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
            (username, generate_password_hash(password)),
        )
        conn.commit()
    except mysql.connector.IntegrityError:
        cur.close()
        conn.close()
        return jsonify({"ok": False, "error": "Username already exists."}), 409
    cur.close()
    conn.close()
    return jsonify({"ok": True, "message": "Account created. Please login."})


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("root"))


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("index.html", username=session.get("username", "Student"))


@app.route("/home")
@login_required
def user_home():
    user_data = require_current_user()
    conn = get_conn()
    cur = conn.cursor()

    # profile
    cur.execute("SELECT display_name, college, course, year_of_study, monthly_allowance, bio FROM user_profiles WHERE user_id=%s", (user_data["id"],))
    profile_row = cur.fetchone()
    profile = {
        "display_name":     str(profile_row[0] or "") if profile_row else "",
        "college":          str(profile_row[1] or "") if profile_row else "",
        "course":           str(profile_row[2] or "") if profile_row else "",
        "year_of_study":    str(profile_row[3] or "") if profile_row else "",
        "monthly_allowance":float(profile_row[4] or 0) if profile_row else 0.0,
        "bio":              str(profile_row[5] or "") if profile_row else "",
    }

    # all-time summary
    cur.execute("SELECT type, SUM(amount) FROM transactions WHERE user_id=%s GROUP BY type", (user_data["id"],))
    totals = {"income": 0.0, "expense": 0.0}
    for r in cur.fetchall():
        totals[str(r[0])] = float(r[1] or 0)

    # this month
    month_start = date.today().replace(day=1)
    cur.execute("SELECT type, SUM(amount) FROM transactions WHERE user_id=%s AND date>=%s GROUP BY type", (user_data["id"], month_start))
    month_totals = {"income": 0.0, "expense": 0.0}
    for r in cur.fetchall():
        month_totals[str(r[0])] = float(r[1] or 0)

    # total tx count
    cur.execute("SELECT COUNT(*) FROM transactions WHERE user_id=%s", (user_data["id"],))
    tx_count = int(cur.fetchone()[0] or 0)

    # recent 5 transactions
    cur.execute(
        "SELECT type, DATE_FORMAT(date,'%d %b'), category, amount FROM transactions WHERE user_id=%s ORDER BY id DESC LIMIT 5",
        (user_data["id"],)
    )
    recent = [{"type": str(r[0]), "date": str(r[1]), "category": str(r[2]), "amount": float(r[3] or 0)} for r in cur.fetchall()]

    # member since
    cur.execute("SELECT DATE_FORMAT(created_at,'%d %b %Y') FROM users WHERE id=%s", (user_data["id"],))
    member_since_row = cur.fetchone()
    member_since = str(member_since_row[0]) if member_since_row else "—"

    cur.close()
    conn.close()

    return render_template("myhome.html",
        username=user_data["username"],
        profile=profile,
        member_since=member_since,
        stats={
            "balance":        round(totals["income"] - totals["expense"], 2),
            "total_income":   round(totals["income"], 2),
            "total_expense":  round(totals["expense"], 2),
            "month_income":   round(month_totals["income"], 2),
            "month_expense":  round(month_totals["expense"], 2),
            "tx_count":       tx_count,
        },
        recent=recent,
    )


# ─── API: Profile ──────────────────────────────────────────────────────────────

@app.route("/api/profile", methods=["GET", "POST"])
@login_required_api
def profile_api():
    user_data = require_current_user()
    conn = get_conn()
    cur = conn.cursor()

    if request.method == "POST":
        payload = cast(dict[str, Any], request.json or {})
        display_name     = (payload.get("display_name") or "").strip()[:100]
        college          = (payload.get("college") or "").strip()[:150]
        course           = (payload.get("course") or "").strip()[:100]
        year_of_study    = (payload.get("year_of_study") or "").strip()[:20]
        monthly_allowance= parse_amount(payload.get("monthly_allowance"))
        bio              = (payload.get("bio") or "").strip()[:300]

        cur.execute(
            """INSERT INTO user_profiles (user_id, display_name, college, course, year_of_study, monthly_allowance, bio)
               VALUES (%s,%s,%s,%s,%s,%s,%s)
               ON DUPLICATE KEY UPDATE
                 display_name=%s, college=%s, course=%s,
                 year_of_study=%s, monthly_allowance=%s, bio=%s, updated_at=NOW()""",
            (user_data["id"], display_name, college, course, year_of_study, monthly_allowance, bio,
             display_name, college, course, year_of_study, monthly_allowance, bio),
        )
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"ok": True})

    cur.execute("SELECT display_name, college, course, year_of_study, monthly_allowance, bio FROM user_profiles WHERE user_id=%s", (user_data["id"],))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return jsonify({"display_name":"","college":"","course":"","year_of_study":"","monthly_allowance":0,"bio":""})
    return jsonify({"display_name":str(row[0] or ""),"college":str(row[1] or ""),"course":str(row[2] or ""),
                    "year_of_study":str(row[3] or ""),"monthly_allowance":float(row[4] or 0),"bio":str(row[5] or "")})


@app.route("/api/change-username", methods=["POST"])
@login_required_api
def change_username():
    user_data = require_current_user()
    payload = cast(dict[str, Any], request.json or {})
    new_username = (payload.get("new_username") or "").strip()
    password     = payload.get("password") or ""

    if len(new_username) < 3:
        return jsonify({"ok": False, "error": "Username must be at least 3 characters."}), 400
    if not new_username.replace("_", "").replace("-", "").isalnum():
        return jsonify({"ok": False, "error": "Username can only contain letters, numbers, _ and -."}), 400
    if new_username == user_data["username"]:
        return jsonify({"ok": False, "error": "That is already your current username."}), 400

    conn = get_conn()
    cur = conn.cursor()

    # Verify password
    cur.execute("SELECT password_hash FROM users WHERE id=%s", (user_data["id"],))
    row = cur.fetchone()
    if not row or not check_password_hash(str(row[0]), password):
        cur.close(); conn.close()
        return jsonify({"ok": False, "error": "Password is incorrect."}), 401

    # Check uniqueness
    cur.execute("SELECT id FROM users WHERE username=%s AND id != %s", (new_username, user_data["id"]))
    if cur.fetchone():
        cur.close(); conn.close()
        return jsonify({"ok": False, "error": "That username is already taken."}), 409

    cur.execute("UPDATE users SET username=%s WHERE id=%s", (new_username, user_data["id"]))
    conn.commit()
    cur.close()
    conn.close()

    # Update session so navbar stays correct immediately
    session["username"] = new_username
    return jsonify({"ok": True, "new_username": new_username})


@app.route("/api/change-password", methods=["POST"])
@login_required_api
def change_password():
    user_data = require_current_user()
    payload = cast(dict[str, Any], request.json or {})
    current_pw  = payload.get("current_password") or ""
    new_pw      = payload.get("new_password") or ""

    if len(new_pw) < 6:
        return jsonify({"ok": False, "error": "New password must be at least 6 characters."}), 400

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT password_hash FROM users WHERE id=%s", (user_data["id"],))
    row = cur.fetchone()
    if not row or not check_password_hash(str(row[0]), current_pw):
        cur.close(); conn.close()
        return jsonify({"ok": False, "error": "Current password is incorrect."}), 401

    cur.execute("UPDATE users SET password_hash=%s WHERE id=%s",
                (generate_password_hash(new_pw), user_data["id"]))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"ok": True})


# ─── API: Transactions ─────────────────────────────────────────────────────────

@app.route("/api/transactions")
@login_required_api
def get_transactions():
    user_data = require_current_user()
    tx_type = request.args.get("type")  # 'income', 'expense', or None for all

    conn = get_conn()
    cur = conn.cursor()
    if tx_type in ("income", "expense"):
        cur.execute(
            """
            SELECT id, type, DATE_FORMAT(date,'%Y-%m-%d'), category, amount, COALESCE(description,'')
            FROM transactions WHERE user_id=%s AND type=%s ORDER BY id DESC
            """,
            (user_data["id"], tx_type),
        )
    else:
        cur.execute(
            """
            SELECT id, type, DATE_FORMAT(date,'%Y-%m-%d'), category, amount, COALESCE(description,'')
            FROM transactions WHERE user_id=%s ORDER BY id DESC
            """,
            (user_data["id"],),
        )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    return jsonify([
        {
            "id": int(r[0]),
            "type": str(r[1]),
            "date": str(r[2]),
            "category": str(r[3]),
            "amount": float(r[4] or 0),
            "description": str(r[5] or ""),
        }
        for r in rows
    ])


@app.route("/api/add", methods=["POST"])
@login_required_api
def add_transaction():
    user_data = require_current_user()
    payload = cast(dict[str, Any], request.json or {})

    tx_type = (payload.get("type") or "expense").strip().lower()
    if tx_type not in ("income", "expense"):
        tx_type = "expense"
    tx_date = payload.get("date") or date.today().isoformat()
    category = (payload.get("category") or "").strip()
    amount = parse_amount(payload.get("amount"))
    description = (payload.get("description") or "").strip()

    if not category:
        return jsonify({"error": "Category is required."}), 400
    if amount <= 0:
        return jsonify({"error": "Amount must be greater than 0."}), 400

    try:
        parsed_date = datetime.strptime(tx_date, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "Date must be in YYYY-MM-DD format."}), 400

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO transactions (user_id, type, date, category, amount, description) VALUES (%s,%s,%s,%s,%s,%s)",
        (user_data["id"], tx_type, parsed_date, category, amount, description),
    )
    conn.commit()
    item_id = cur.lastrowid
    cur.close()
    conn.close()

    return jsonify({
        "id": item_id,
        "type": tx_type,
        "date": parsed_date.isoformat(),
        "category": category,
        "amount": round(amount, 2),
        "description": description,
    })


@app.route("/api/transactions/<int:item_id>", methods=["DELETE"])
@login_required_api
def delete_transaction(item_id: int):
    user_data = require_current_user()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM transactions WHERE id=%s AND user_id=%s", (item_id, user_data["id"]))
    conn.commit()
    deleted = cur.rowcount
    cur.close()
    conn.close()
    if deleted == 0:
        return jsonify({"ok": False, "error": "not_found"}), 404
    return jsonify({"ok": True, "deleted": item_id})


@app.route("/api/transactions/<int:item_id>", methods=["PUT"])
@login_required_api
def edit_transaction(item_id: int):
    user_data = require_current_user()
    payload = cast(dict[str, Any], request.json or {})

    tx_type = (payload.get("type") or "expense").strip().lower()
    if tx_type not in ("income", "expense"):
        tx_type = "expense"
    tx_date  = payload.get("date") or date.today().isoformat()
    category = (payload.get("category") or "").strip()
    amount   = parse_amount(payload.get("amount"))
    description = (payload.get("description") or "").strip()

    if not category:
        return jsonify({"error": "Category is required."}), 400
    if amount <= 0:
        return jsonify({"error": "Amount must be greater than 0."}), 400
    try:
        parsed_date = datetime.strptime(tx_date, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "Date must be YYYY-MM-DD."}), 400

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """UPDATE transactions
           SET type=%s, date=%s, category=%s, amount=%s, description=%s
           WHERE id=%s AND user_id=%s""",
        (tx_type, parsed_date, category, amount, description, item_id, user_data["id"]),
    )
    conn.commit()
    updated = cur.rowcount
    cur.close()
    conn.close()
    if updated == 0:
        return jsonify({"ok": False, "error": "not_found"}), 404
    return jsonify({
        "ok": True,
        "id": item_id,
        "type": tx_type,
        "date": parsed_date.isoformat(),
        "category": category,
        "amount": round(amount, 2),
        "description": description,
    })


# ─── API: Summary ──────────────────────────────────────────────────────────────

@app.route("/api/summary")
@login_required_api
def summary():
    """Return total income, total expense, balance for current month and all time."""
    user_data = require_current_user()
    today = date.today()
    month_start = today.replace(day=1)

    conn = get_conn()
    cur = conn.cursor()

    # All-time
    cur.execute(
        """
        SELECT type, SUM(amount) FROM transactions
        WHERE user_id=%s GROUP BY type
        """,
        (user_data["id"],),
    )
    rows = cur.fetchall()
    totals = {"income": 0.0, "expense": 0.0}
    for r in rows:
        totals[str(r[0])] = float(r[1] or 0)

    # Current month
    cur.execute(
        """
        SELECT type, SUM(amount) FROM transactions
        WHERE user_id=%s AND date >= %s GROUP BY type
        """,
        (user_data["id"], month_start),
    )
    month_totals = {"income": 0.0, "expense": 0.0}
    for r in cur.fetchall():
        month_totals[str(r[0])] = float(r[1] or 0)

    # Budget goal
    try:
        cur.execute(
            "SELECT monthly_limit, goal_type, from_date, to_date FROM budget_goals WHERE user_id=%s",
            (user_data["id"],)
        )
        goal_row = cur.fetchone()
        budget_limit = float(goal_row[0]) if goal_row else 0.0
        goal_type    = str(goal_row[1]) if goal_row else "monthly"
        goal_from    = goal_row[2] if goal_row else None
        goal_to      = goal_row[3] if goal_row else None
    except Exception:
        cur.execute("SELECT monthly_limit FROM budget_goals WHERE user_id=%s", (user_data["id"],))
        goal_row = cur.fetchone()
        budget_limit = float(goal_row[0]) if goal_row else 0.0
        goal_type = "monthly"; goal_from = None; goal_to = None

    # Compute spent against the correct period
    if goal_type == "custom" and goal_from and goal_to:
        cur.execute(
            "SELECT COALESCE(SUM(amount),0) FROM transactions WHERE user_id=%s AND type='expense' AND date BETWEEN %s AND %s",
            (user_data["id"], goal_from, goal_to),
        )
        budget_spent = float(cur.fetchone()[0] or 0)
    else:
        budget_spent = month_totals["expense"]

    cur.close()
    conn.close()

    return jsonify({
        "all_time": {
            "income": round(totals["income"], 2),
            "expense": round(totals["expense"], 2),
            "balance": round(totals["income"] - totals["expense"], 2),
        },
        "this_month": {
            "income": round(month_totals["income"], 2),
            "expense": round(month_totals["expense"], 2),
            "balance": round(month_totals["income"] - month_totals["expense"], 2),
        },
        "budget_limit": budget_limit,
        "budget_used_pct": round((budget_spent / budget_limit * 100) if budget_limit > 0 else 0, 1),
        "budget_spent": round(budget_spent, 2),
        "goal_type": goal_type,
        "goal_from": goal_from.isoformat() if goal_from else None,
        "goal_to":   goal_to.isoformat()   if goal_to   else None,
    })


# ─── API: Stats by category ────────────────────────────────────────────────────

@app.route("/api/stats")
@login_required_api
def stats():
    user_data = require_current_user()
    tx_type = request.args.get("type", "expense")

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT category, SUM(amount) AS total
        FROM transactions WHERE user_id=%s AND type=%s
        GROUP BY category ORDER BY total DESC
        """,
        (user_data["id"], tx_type),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    labels = [str(r[0]) for r in rows]
    values = [round(float(r[1] or 0), 2) for r in rows]
    summary = [{"category": labels[i], "total": values[i]} for i in range(len(labels))]
    return jsonify({"labels": labels, "values": values, "summary": summary})


# ─── API: Time series ──────────────────────────────────────────────────────────

@app.route("/api/timeseries")
@login_required_api
def timeseries():
    user_data = require_current_user()
    try:
        days = max(1, min(int(request.args.get("days", 30)), 365))
    except Exception:
        days = 30

    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)

    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT DATE_FORMAT(date,'%Y-%m-%d'), type, SUM(amount)
        FROM transactions
        WHERE user_id=%s AND date BETWEEN %s AND %s
        GROUP BY date, type ORDER BY date ASC
        """,
        (user_data["id"], start_date, end_date),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    income_map: dict[str, float] = {}
    expense_map: dict[str, float] = {}
    for r in rows:
        day, t, amt = str(r[0]), str(r[1]), float(r[2] or 0)
        if t == "income":
            income_map[day] = round(amt, 2)
        else:
            expense_map[day] = round(amt, 2)

    labels, income_vals, expense_vals = [], [], []
    for i in range(days):
        key = (start_date + timedelta(days=i)).isoformat()
        labels.append(key)
        income_vals.append(income_map.get(key, 0.0))
        expense_vals.append(expense_map.get(key, 0.0))

    return jsonify({"labels": labels, "income": income_vals, "expense": expense_vals})


# ─── API: Monthly ─────────────────────────────────────────────────────────────

@app.route("/api/monthly")
@login_required_api
def monthly():
    user_data = require_current_user()
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT DATE_FORMAT(date,'%Y-%m') AS month, type, SUM(amount)
        FROM transactions WHERE user_id=%s
        GROUP BY month, type ORDER BY month ASC
        """,
        (user_data["id"],),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    month_data: dict[str, dict[str, float]] = {}
    for r in rows:
        m, t, amt = str(r[0]), str(r[1]), float(r[2] or 0)
        if m not in month_data:
            month_data[m] = {"income": 0.0, "expense": 0.0}
        month_data[m][t] = round(amt, 2)

    summary = [
        {
            "month": m,
            "income": v["income"],
            "expense": v["expense"],
            "balance": round(v["income"] - v["expense"], 2),
        }
        for m, v in sorted(month_data.items())
    ]
    return jsonify({"summary": summary})


# ─── API: Budget Goal ──────────────────────────────────────────────────────────

@app.route("/api/budget", methods=["GET", "POST"])
@login_required_api
def budget():
    user_data = require_current_user()
    conn = get_conn()
    cur = conn.cursor()

    if request.method == "POST":
        payload = cast(dict[str, Any], request.json or {})
        limit      = parse_amount(payload.get("monthly_limit"))
        goal_type  = (payload.get("goal_type") or "monthly").strip()   # 'monthly' | 'custom'
        from_str   = (payload.get("from_date") or "").strip()
        to_str     = (payload.get("to_date")   or "").strip()

        if goal_type not in ("monthly", "custom"):
            goal_type = "monthly"

        from_date: "date | None" = None
        to_date:   "date | None" = None
        if goal_type == "custom":
            try:
                from_date = datetime.strptime(from_str, "%Y-%m-%d").date()
                to_date   = datetime.strptime(to_str,   "%Y-%m-%d").date()
            except ValueError:
                cur.close(); conn.close()
                return jsonify({"error": "Invalid dates. Use YYYY-MM-DD."}), 400
            if from_date > to_date:
                cur.close(); conn.close()
                return jsonify({"error": "from_date must be before to_date."}), 400

        if limit < 0:
            cur.close(); conn.close()
            return jsonify({"error": "Limit must be 0 or positive."}), 400

        # Ensure columns exist (safe migration)
        try:
            cur.execute("ALTER TABLE budget_goals ADD COLUMN goal_type VARCHAR(10) NOT NULL DEFAULT 'monthly'")
            conn.commit()
        except Exception:
            pass
        try:
            cur.execute("ALTER TABLE budget_goals ADD COLUMN from_date DATE NULL")
            conn.commit()
        except Exception:
            pass
        try:
            cur.execute("ALTER TABLE budget_goals ADD COLUMN to_date DATE NULL")
            conn.commit()
        except Exception:
            pass

        cur.execute(
            """
            INSERT INTO budget_goals (user_id, monthly_limit, goal_type, from_date, to_date)
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
              monthly_limit=%s, goal_type=%s, from_date=%s, to_date=%s, updated_at=NOW()
            """,
            (user_data["id"], limit, goal_type, from_date, to_date,
             limit, goal_type, from_date, to_date),
        )
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({
            "ok": True,
            "monthly_limit": round(limit, 2),
            "goal_type": goal_type,
            "from_date": from_date.isoformat() if from_date else None,
            "to_date":   to_date.isoformat()   if to_date   else None,
        })

    # GET
    try:
        cur.execute(
            "SELECT monthly_limit, goal_type, from_date, to_date FROM budget_goals WHERE user_id=%s",
            (user_data["id"],)
        )
    except Exception:
        cur.execute("SELECT monthly_limit FROM budget_goals WHERE user_id=%s", (user_data["id"],))
        row = cur.fetchone()
        cur.close(); conn.close()
        return jsonify({"monthly_limit": float(row[0]) if row else 0.0, "goal_type": "monthly"})

    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return jsonify({"monthly_limit": 0.0, "goal_type": "monthly", "from_date": None, "to_date": None})
    return jsonify({
        "monthly_limit": float(row[0] or 0),
        "goal_type":     str(row[1] or "monthly"),
        "from_date":     row[2].isoformat() if row[2] else None,
        "to_date":       row[3].isoformat() if row[3] else None,
    })


# ─── API: Custom Date Range Report ────────────────────────────────────────────

@app.route("/api/range")
@login_required_api
def range_report():
    """
    Returns transactions + summary for a custom date range.
    Query params: from_date (YYYY-MM-DD), to_date (YYYY-MM-DD)
    """
    user_data = require_current_user()

    from_str = request.args.get("from_date", "")
    to_str   = request.args.get("to_date", "")

    try:
        from_date = datetime.strptime(from_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "Invalid from_date. Use YYYY-MM-DD."}), 400

    try:
        to_date = datetime.strptime(to_str, "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "Invalid to_date. Use YYYY-MM-DD."}), 400

    if from_date > to_date:
        return jsonify({"error": "from_date must be before or equal to to_date."}), 400

    conn = get_conn()
    cur = conn.cursor()

    # All transactions in range
    cur.execute(
        """
        SELECT id, type, DATE_FORMAT(date,'%Y-%m-%d'), category, amount, COALESCE(description,'')
        FROM transactions
        WHERE user_id=%s AND date BETWEEN %s AND %s
        ORDER BY date DESC, id DESC
        """,
        (user_data["id"], from_date, to_date),
    )
    rows = cur.fetchall()

    # Summary totals in range
    cur.execute(
        """
        SELECT type, SUM(amount)
        FROM transactions
        WHERE user_id=%s AND date BETWEEN %s AND %s
        GROUP BY type
        """,
        (user_data["id"], from_date, to_date),
    )
    totals = {"income": 0.0, "expense": 0.0}
    for r in cur.fetchall():
        totals[str(r[0])] = float(r[1] or 0)

    # Category breakdown in range
    cur.execute(
        """
        SELECT type, category, SUM(amount) AS total
        FROM transactions
        WHERE user_id=%s AND date BETWEEN %s AND %s
        GROUP BY type, category
        ORDER BY type, total DESC
        """,
        (user_data["id"], from_date, to_date),
    )
    cat_rows = cur.fetchall()
    cur.close()
    conn.close()

    transactions = [
        {
            "id": int(r[0]),
            "type": str(r[1]),
            "date": str(r[2]),
            "category": str(r[3]),
            "amount": float(r[4] or 0),
            "description": str(r[5] or ""),
        }
        for r in rows
    ]

    income_cats  = [{"category": str(r[1]), "total": round(float(r[2] or 0), 2)} for r in cat_rows if str(r[0]) == "income"]
    expense_cats = [{"category": str(r[1]), "total": round(float(r[2] or 0), 2)} for r in cat_rows if str(r[0]) == "expense"]

    return jsonify({
        "from_date": from_date.isoformat(),
        "to_date":   to_date.isoformat(),
        "summary": {
            "income":  round(totals["income"], 2),
            "expense": round(totals["expense"], 2),
            "balance": round(totals["income"] - totals["expense"], 2),
            "tx_count": len(transactions),
        },
        "income_categories":  income_cats,
        "expense_categories": expense_cats,
        "transactions": transactions,
    })


# ─── API: Excel Report ────────────────────────────────────────────────────────

@app.route("/api/report/excel")
@login_required_api
def excel_report():
    """
    Generate a formatted .xlsx report.
    Query params: from_date, to_date (YYYY-MM-DD). Both required.
    """
    user_data = require_current_user()
    from_str = request.args.get("from_date", "")
    to_str   = request.args.get("to_date",   "")

    try:
        from_date = datetime.strptime(from_str, "%Y-%m-%d").date()
        to_date   = datetime.strptime(to_str,   "%Y-%m-%d").date()
    except ValueError:
        return jsonify({"error": "Pass from_date and to_date as YYYY-MM-DD."}), 400

    if from_date > to_date:
        return jsonify({"error": "from_date must be ≤ to_date."}), 400

    # ── Fetch data ────────────────────────────────────────────────────────────
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute(
        """
        SELECT DATE_FORMAT(date,'%d-%m-%Y'), type, category, amount, COALESCE(description,'')
        FROM transactions
        WHERE user_id=%s AND date BETWEEN %s AND %s
        ORDER BY date ASC, id ASC
        """,
        (user_data["id"], from_date, to_date),
    )
    rows = cur.fetchall()

    cur.execute(
        """
        SELECT type, category, SUM(amount) AS total
        FROM transactions
        WHERE user_id=%s AND date BETWEEN %s AND %s
        GROUP BY type, category ORDER BY type, total DESC
        """,
        (user_data["id"], from_date, to_date),
    )
    cat_rows = cur.fetchall()
    cur.close()
    conn.close()

    # ── Totals ────────────────────────────────────────────────────────────────
    total_income  = sum(float(r[3]) for r in rows if r[1] == "income")
    total_expense = sum(float(r[3]) for r in rows if r[1] == "expense")
    net_savings   = total_income - total_expense

    # ── Build workbook in memory ──────────────────────────────────────────────
    output = io.BytesIO()
    wb = xlsxwriter.Workbook(output, {"in_memory": True, "remove_timezone": True})

    # ── Define formats ────────────────────────────────────────────────────────
    def fmt(**kw):
        return wb.add_format(kw)

    # Base
    base    = {"font_name": "Calibri", "font_size": 11, "valign": "vcenter"}
    def f(**kw): return wb.add_format({**base, **kw})

    # Title / branding
    fmt_title   = f(font_size=18, bold=True, font_color="#FFFFFF",
                    bg_color="#0F172A", border=0, left=0)
    fmt_subtitle= f(font_size=10, font_color="#94A3B8", bg_color="#0F172A")
    fmt_empty   = f(bg_color="#0F172A")

    # Section headers
    fmt_sec_hdr = f(bold=True, font_size=10, font_color="#06B6D4",
                    bg_color="#1E293B", top=2, top_color="#06B6D4",
                    bottom=2, bottom_color="#06B6D4", border_color="#06B6D4")

    # Column headers
    fmt_col_hdr = f(bold=True, font_size=10, font_color="#F1F5F9",
                    bg_color="#1E3A5F", align="center",
                    top=1, bottom=1, border_color="#334155")

    # Income rows
    fmt_income_label  = f(font_color="#065F46", bg_color="#D1FAE5", bold=True, font_size=10)
    fmt_income_type   = f(font_color="#059669", bg_color="#D1FAE5", bold=True,
                          align="center", font_size=10)
    fmt_income_cell   = f(font_color="#064E3B", bg_color="#D1FAE5", font_size=10)
    fmt_income_amt    = f(font_color="#059669", bg_color="#D1FAE5", bold=True,
                          num_format='₹#,##0.00', align="right", font_size=11)

    # Expense rows
    fmt_expense_label = f(font_color="#7F1D1D", bg_color="#FEE2E2", bold=True, font_size=10)
    fmt_expense_type  = f(font_color="#DC2626", bg_color="#FEE2E2", bold=True,
                          align="center", font_size=10)
    fmt_expense_cell  = f(font_color="#450A0A", bg_color="#FEE2E2", font_size=10)
    fmt_expense_amt   = f(font_color="#DC2626", bg_color="#FEE2E2", bold=True,
                          num_format='₹#,##0.00', align="right", font_size=11)

    # Alternate income (slightly lighter)
    fmt_income_alt_lbl = f(font_color="#065F46", bg_color="#ECFDF5", font_size=10)
    fmt_income_alt_cel = f(font_color="#064E3B", bg_color="#ECFDF5", font_size=10)
    fmt_income_alt_amt = f(font_color="#059669", bg_color="#ECFDF5",
                           num_format='₹#,##0.00', align="right", font_size=10)

    fmt_expense_alt_lbl= f(font_color="#7F1D1D", bg_color="#FFF5F5", font_size=10)
    fmt_expense_alt_cel= f(font_color="#450A0A", bg_color="#FFF5F5", font_size=10)
    fmt_expense_alt_amt= f(font_color="#DC2626", bg_color="#FFF5F5",
                           num_format='₹#,##0.00', align="right", font_size=10)

    # Summary section
    fmt_sum_title  = f(bold=True, font_size=13, font_color="#FFFFFF",
                       bg_color="#0C4A6E", top=2, top_color="#06B6D4")
    fmt_sum_label  = f(font_size=11, font_color="#E2E8F0", bg_color="#1E3A5F")
    fmt_sum_income = f(bold=True, font_size=12, font_color="#34D399",
                       bg_color="#064E3B", num_format='₹#,##0.00', align="right")
    fmt_sum_expense= f(bold=True, font_size=12, font_color="#F87171",
                       bg_color="#450A0A", num_format='₹#,##0.00', align="right")
    fmt_sum_saving_pos = f(bold=True, font_size=12, font_color="#FFFFFF",
                           bg_color="#0E7490", num_format='₹#,##0.00', align="right")
    fmt_sum_saving_neg = f(bold=True, font_size=12, font_color="#FFFFFF",
                           bg_color="#7F1D1D", num_format='₹#,##0.00', align="right")
    fmt_sum_count  = f(font_size=11, font_color="#94A3B8", bg_color="#1E293B",
                       align="right")

    # Category breakdown
    fmt_cat_hdr    = f(bold=True, font_size=10, font_color="#F1F5F9",
                       bg_color="#1E3A5F", align="center",
                       top=1, bottom=1, border_color="#334155")
    fmt_cat_name   = f(font_size=10, font_color="#E2E8F0", bg_color="#1E293B")
    fmt_cat_inc_amt= f(font_size=10, font_color="#34D399", bg_color="#1E293B",
                       num_format='₹#,##0.00', align="right")
    fmt_cat_exp_amt= f(font_size=10, font_color="#F87171", bg_color="#1E293B",
                       num_format='₹#,##0.00', align="right")
    fmt_cat_pct    = f(font_size=10, font_color="#94A3B8", bg_color="#1E293B",
                       num_format='0.0"%"', align="right")

    # ─── Sheet 1: Transactions ─────────────────────────────────────────────────
    ws = wb.add_worksheet("Transactions")
    ws.set_zoom(90)
    ws.hide_gridlines(2)

    # Column widths
    ws.set_column("A:A", 16)   # Date
    ws.set_column("B:B", 13)   # Type
    ws.set_column("C:C", 28)   # Category
    ws.set_column("D:D", 16)   # Amount
    ws.set_column("E:E", 36)   # Description
    ws.set_row(0, 40)
    ws.set_row(1, 18)
    ws.set_row(2, 18)
    ws.set_row(3, 8)
    ws.set_row(4, 22)

    # Title banner (row 0, merged A–E)
    ws.merge_range("A1:E1",
        f"StudentFlow  |  {user_data['username']} – Transaction Report",
        fmt_title)
    ws.merge_range("A2:E2",
        f"Period:   {from_date.strftime('%d %b %Y')}  →  {to_date.strftime('%d %b %Y')}",
        fmt_subtitle)
    ws.merge_range("A3:E3",
        f"Generated: {datetime.now().strftime('%d %b %Y, %I:%M %p')}",
        fmt_subtitle)
    ws.merge_range("A4:E4", "", fmt_empty)

    # Column headers (row 4 = index 4)
    for col, header in enumerate(["Date", "Type", "Category", "Amount (₹)", "Description"]):
        ws.write(4, col, header, fmt_col_hdr)

    # Transaction rows
    income_count  = {k: 0 for k in []}  # track alternating per type
    inc_alt = expense_alt = False

    for i, row in enumerate(rows):
        r = 5 + i
        ws.set_row(r, 20)
        date_str, tx_type, category, amount, description = (
            str(row[0]), str(row[1]), str(row[2]),
            float(row[3] or 0), str(row[4] or "")
        )
        is_income = tx_type == "income"

        if is_income:
            inc_alt = not inc_alt
            lf  = fmt_income_label  if inc_alt else fmt_income_alt_lbl
            tf  = fmt_income_type   if inc_alt else fmt_income_type
            cf  = fmt_income_cell   if inc_alt else fmt_income_alt_cel
            af  = fmt_income_amt    if inc_alt else fmt_income_alt_amt
            type_label = "⬇ Income"
        else:
            expense_alt = not expense_alt
            lf  = fmt_expense_label if expense_alt else fmt_expense_alt_lbl
            tf  = fmt_expense_type  if expense_alt else fmt_expense_type
            cf  = fmt_expense_cell  if expense_alt else fmt_expense_alt_cel
            af  = fmt_expense_amt   if expense_alt else fmt_expense_alt_amt
            type_label = "⬆ Expense"

        ws.write(r, 0, date_str,   lf)
        ws.write(r, 1, type_label, tf)
        ws.write(r, 2, category,   cf)
        ws.write(r, 3, amount,     af)
        ws.write(r, 4, description,cf)

    # Blank separator
    sep = 5 + len(rows)
    ws.set_row(sep, 10)
    for c in range(5): ws.write(sep, c, "", fmt_empty)

    # ─── Summary block ─────────────────────────────────────────────────────────
    sr = sep + 1
    ws.set_row(sr, 28)
    ws.merge_range(sr, 0, sr, 4, "  SUMMARY", fmt_sum_title)

    labels  = ["Total Income", "Total Expense", "Net Savings", "Transactions"]
    amounts = [total_income, total_expense, net_savings, len(rows)]
    amt_fmts= [fmt_sum_income, fmt_sum_expense,
               fmt_sum_saving_pos if net_savings >= 0 else fmt_sum_saving_neg,
               fmt_sum_count]

    for j, (lbl, val, afmt) in enumerate(zip(labels, amounts, amt_fmts)):
        rr = sr + 1 + j
        ws.set_row(rr, 22)
        ws.merge_range(rr, 0, rr, 2, f"  {lbl}", fmt_sum_label)
        ws.merge_range(rr, 3, rr, 4, val, afmt)

    # ─── Sheet 2: Category Breakdown ──────────────────────────────────────────
    ws2 = wb.add_worksheet("Category Breakdown")
    ws2.set_zoom(90)
    ws2.hide_gridlines(2)
    ws2.set_column("A:A", 8)
    ws2.set_column("B:B", 28)
    ws2.set_column("C:C", 16)
    ws2.set_column("D:D", 12)
    ws2.set_row(0, 36)
    ws2.set_row(1, 8)
    ws2.set_row(2, 22)

    ws2.merge_range("A1:D1",
        f"StudentFlow  |  Category Breakdown  |  {from_date.strftime('%d %b %Y')} → {to_date.strftime('%d %b %Y')}",
        fmt_title)
    ws2.merge_range("A2:D2",
        f"Generated: {datetime.now().strftime('%d %b %Y, %I:%M %p')}",
        fmt_subtitle)

    # Headers
    for col, hdr in enumerate(["Type", "Category", "Amount (₹)", "% of Total"]):
        ws2.write(2, col, hdr, fmt_cat_hdr)

    expense_cats = [(str(r[1]), float(r[2] or 0)) for r in cat_rows if str(r[0]) == "expense"]
    income_cats  = [(str(r[1]), float(r[2] or 0)) for r in cat_rows if str(r[0]) == "income"]

    rr = 3
    # Expense section
    ws2.set_row(rr, 20)
    ws2.merge_range(rr, 0, rr, 3, "  EXPENSES", fmt_sec_hdr)
    rr += 1
    for cat, amt in expense_cats:
        ws2.set_row(rr, 19)
        pct = (amt / total_expense * 100) if total_expense else 0
        ws2.write(rr, 0, "⬆", fmt_expense_cell)
        ws2.write(rr, 1, cat,  fmt_cat_name)
        ws2.write(rr, 2, amt,  fmt_cat_exp_amt)
        ws2.write(rr, 3, pct,  fmt_cat_pct)
        rr += 1
    # Expense total
    ws2.set_row(rr, 20)
    ws2.merge_range(rr, 0, rr, 1, "  Total Expenses", fmt_sum_label)
    ws2.merge_range(rr, 2, rr, 3, total_expense, fmt_sum_expense)
    rr += 2  # blank gap

    # Income section
    ws2.set_row(rr, 20)
    ws2.merge_range(rr, 0, rr, 3, "  INCOME", fmt_sec_hdr)
    rr += 1
    for cat, amt in income_cats:
        ws2.set_row(rr, 19)
        pct = (amt / total_income * 100) if total_income else 0
        ws2.write(rr, 0, "⬇", fmt_income_cell)
        ws2.write(rr, 1, cat,  fmt_cat_name)
        ws2.write(rr, 2, amt,  fmt_cat_inc_amt)
        ws2.write(rr, 3, pct,  fmt_cat_pct)
        rr += 1
    # Income total
    ws2.set_row(rr, 20)
    ws2.merge_range(rr, 0, rr, 1, "  Total Income", fmt_sum_label)
    ws2.merge_range(rr, 2, rr, 3, total_income, fmt_sum_income)

    # ─── Finalize ─────────────────────────────────────────────────────────────
    wb.close()
    output.seek(0)

    filename = (
        f"StudentFlow_{user_data['username']}_"
        f"{from_date.strftime('%d%b')}_to_{to_date.strftime('%d%b%Y')}.xlsx"
    )
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
