# Personal Expense Tracker

A web application that helps you track and manage your personal expenses. Built with Flask (a Python web framework) and supports both SQLite and MySQL databases.

---

## Table of Contents
1. [What is Flask?](#what-is-flask)
2. [Project Structure](#project-structure)
3. [Prerequisites](#prerequisites)
4. [Database Setup](#database-setup)
5. [How to Run](#how-to-run)
6. [Features](#features)

---

## What is Flask?

**Flask** is a lightweight Python web framework used to build web applications. Think of it as a tool that helps you create websites and web apps.

### Key Points About Flask:
- **Easy to Learn**: Simple syntax and structure, perfect for beginners
- **Flexible**: You can use it for small projects or large applications
- **Lightweight**: Doesn't require much setup compared to other frameworks
- **Backend Framework**: Handles the server-side logic (database, routing, processing)

### How Flask Works (Simple Explanation):
```
1. User visits your website (e.g., http://localhost:5000)
2. Flask receives the request
3. Flask processes the request (checks database, runs code)
4. Flask sends back an HTML page or data (JSON)
5. Browser displays the page or processes the data
```

### In This Project:
- Flask handles routes (URLs like `/`, `/login`, `/add-expense`)
- Flask manages the database connection
- Flask serves HTML templates and static files (CSS, JavaScript)

---

## Project Structure

```
Personal Expense Tracker/
├── app.py                  # Main Flask application (server code)
├── requirements.txt       # Python packages/dependencies
├── .env                  # Environment variables (database config)
├── README.md             # This file
├── templates/            # HTML pages
│   ├── home.html        # Home page
│   ├── index.html       # Main app page
│   └── login.html       # Login page
└── static/              # CSS, JavaScript, images
    ├── css/
    │   └── style.css    # Website styling
    └── js/
        └── app.js       # JavaScript for interactivity
```

---

## Prerequisites

Before you start, make sure you have:

- **Python 3.8+** installed ([Download here](https://www.python.org/downloads/))
- **MySQL Server** (if using MySQL) or **SQLite** (included with Python)
- **PowerShell** or Command Prompt on Windows
- A text editor (VS Code, Notepad++, etc.)

---

## Database Setup

This application uses **MySQL** database for storing user accounts and expense records.

### What is MySQL?
- A powerful relational database server
- Requires a running MySQL service
- Professional choice for production applications
- Secure user authentication and data management

**How to Connect to MySQL:**

#### Step 1: Install MySQL Server
- Download from [MySQL Official Website](https://dev.mysql.com/downloads/mysql/)
- Install and note your password

#### Step 2: Create Database and User
Open PowerShell and connect to MySQL:

```powershell
# Connect to MySQL (enter password when prompted)
mysql -u root -p
```

Run these SQL commands:

```sql
-- Create the database
CREATE DATABASE expense_tracker;

-- Create a user for this app
CREATE USER 'expense_user'@'localhost' IDENTIFIED BY 'YourStrongPassword123!';

-- Give permissions to the user
GRANT ALL PRIVILEGES ON expense_tracker.* TO 'expense_user'@'localhost';

-- Apply changes
FLUSH PRIVILEGES;

-- Exit MySQL
EXIT;
```

#### Step 3: Configure Connection in `.env` File
Create or edit `.env` file in your project folder:

```
# MySQL Configuration
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=expense_user
DB_PASSWORD=YourStrongPassword123!
DB_NAME=expense_tracker
SECRET_KEY=your-secret-key-here
```

#### Step 4: Flask Code to Connect to MySQL
In your Flask app (`app.py`), use this to connect:

```python
from flask_mysqldb import MySQL
import MySQLdb

app = Flask(__name__)
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'expense_user'
app.config['MYSQL_PASSWORD'] = 'YourStrongPassword123!'
app.config['MYSQL_DB'] = 'expense_tracker'

mysql = MySQL(app)

# Now you can query the database
@app.route('/expenses')
def get_expenses():
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM expenses")
    expenses = cursor.fetchall()
    cursor.close()
    return data
```

#### Connection String Explanation:
```
DB_HOST=127.0.0.1      ← Where MySQL is running (localhost)
DB_PORT=3306           ← Default MySQL port
DB_USER=expense_user   ← Username you created
DB_PASSWORD=password   ← Password you set
DB_NAME=expense_tracker ← Database name
```

---

## How to Run

### Step 1: Install Python Dependencies

Open PowerShell in your project folder and run:

```powershell
# Create a virtual environment (isolated Python space)
python -m venv .venv

# Activate it
.\.venv\Scripts\Activate.ps1

# Install required packages
pip install -r requirements.txt
```

**What does this do?**
- `venv` = Creates an isolated Python environment (like a container for your project)
- `Activate` = Tells your system to use this isolated environment
- `pip install` = Downloads and installs the packages listed in requirements.txt

### Step 2: Set Up Environment Variables

Create a `.env` file in your project root with your database info:

**For SQLite:**
```
DATABASE_URL=sqlite:///expenses.db
SECRET_KEY=dev-secret-key
```

**For MySQL:**
```
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=expense_user
DB_PASSWORD=MyPassword123
DB_NAME=expense_tracker
SECRET_KEY=dev-secret-key
```

### Step 3: Start the Application

```powershell
# Make sure your virtual environment is activated
# Then run:
python app.py
```

**What you should see:**
```
* Running on http://127.0.0.1:5000
```

### Step 4: Open in Browser

Open your web browser and go to:
```
http://localhost:5000
```

---

## Features

✅ User login system
✅ Add and track expenses
✅ View expense history
✅ Filter expenses by category
✅ Download expense reports
✅ Mobile-friendly design

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError: No module named 'flask'` | Run `pip install -r requirements.txt` |
| `Connection refused - MySQL` | Check MySQL is running: `mysql -u root -p` |
| `Syntax error near 'localhost'` | Make sure you're running SQL commands in MySQL prompt, not PowerShell |
| `Permission denied: .venv` | Run PowerShell as Administrator |

---

## Tips for Success

1. **Always activate the virtual environment** before running the app
2. **Start MySQL service** before running the app (for MySQL option)
3. **Keep your password safe** - don't share `.env` files
4. **Test the connection** - run a simple query to verify database works
5. **Read error messages** - Flask gives helpful error descriptions

---

## Learning Resources

- [Flask Official Docs](https://flask.palletsprojects.com/)
- [MySQL Tutorials](https://www.w3schools.com/sql/)
- [SQLite Documentation](https://www.sqlite.org/docs.html)
- [Python Virtual Environments Guide](https://docs.python.org/3/tutorial/venv.html)

4. Create the database and a dedicated DB user (MySQL shell)

```sql
-- run: mysql -u root -p
CREATE DATABASE IF NOT EXISTS expense_tracker;
CREATE USER IF NOT EXISTS 'expense_user'@'localhost' IDENTIFIED BY 'securepass';
GRANT ALL PRIVILEGES ON expense_tracker.* TO 'expense_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

If you already have a DB and user, set the env vars to match those credentials.

5. Run the application

```powershell
# The app calls init_db() on startup to create required tables.
python app.py

# OR use Flask CLI for development
$env:FLASK_APP='app.py'
$env:FLASK_ENV='development'
flask run
```

Open http://127.0.0.1:5000/ to view the app.

---

## Templates (how the frontend is organized)

- `templates/` contains Jinja2 templates used by Flask. Key files:
  - `login.html` — login page
  - `index.html` — main dashboard UI
- `static/` contains subfolders `css/` and `js/` for styles and client-side logic.

How it works:
- The frontend loads `index.html` for the dashboard and calls the JSON API endpoints under `/api/` to get expenses, stats, and to add/delete items.
- When you modify templates or static files in development mode, Flask auto-reloads the server (if running with `FLASK_ENV=development`).

---

## Database details

- The app uses MySQL with two tables:
  - `users` (id, username, password_hash, created_at)
  - `expenses` (id, user_id, date, category, amount, description, created_at)
- The SQL tables are created automatically by `init_db()` when the app starts.

Best practices:
- Avoid using `root` in production — create a dedicated DB user with minimal required privileges.
- Keep DB credentials secret and provide them via environment variables.

---

## API Endpoints (summary)
- `GET /` → redirect to dashboard or login
- `GET /login`, `POST /login` → login page and authentication
- `POST /register` → register new user
- `GET /api/expenses` → list current user's expenses (JSON)
- `POST /api/add` → add an expense (JSON body: `date`, `category`, `amount`, `description`)
- `DELETE /api/expenses/<id>` → delete an expense
- `GET /api/stats` → category totals
- `GET /api/timeseries?days=N` → daily totals for last N days
- `GET /api/monthly` → monthly totals

For full request/response examples, inspect `app.py` which builds the payloads.

---

## SECRET_KEY (what it is and how to generate)

- `SECRET_KEY` is a random string Flask uses to sign session cookies. Keep it secret in production.
- Generate a strong key locally:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Set the generated string as `SECRET_KEY` in your env vars before running the app.

---

## Troubleshooting

- "Access denied" / Authentication errors from MySQL:
  - Confirm `DB_USER` and `DB_PASSWORD` are correct.
  - Ensure MySQL server is running. Start it on Windows with e.g. `net start MySQL` or `net start MySQL80` (service name varies).
- If the app errors on startup, read the terminal traceback — missing env vars and DB connectivity are the most common issues.

If you prefer to avoid installing MySQL locally for development, I can add a SQLite fallback that stores data to a local file for quick testing.

---

## Next steps / optional improvements

- Add a `.env.example` file and a tiny script to load env vars for local dev
- Add logging to write server errors to `error.log`
- Add migrations (Alembic) and tests

---

If you'd like, I can add a `.env.example`, a script to bootstrap the DB, or a SQLite fallback — tell me which and I will add it.
