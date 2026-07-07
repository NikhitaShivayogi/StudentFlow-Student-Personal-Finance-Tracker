import os
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

def get_conn():
    """Get a database connection."""
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", "Nikita@2004"),
        database=os.getenv("DB_NAME", "expense_tracker")
    )

def init_db():
    """Initialize the database and create tables if they don't exist."""
    conn = mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", "")
    )
    cur = conn.cursor()
    db_name = os.getenv("DB_NAME", "expense_tracker")
    cur.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
    conn.commit()
    cur.close()
    conn.close()

    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(255) NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # transactions table supports both income and expense
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS transactions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            type ENUM('income','expense') NOT NULL DEFAULT 'expense',
            date DATE NOT NULL,
            category VARCHAR(255) NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )

    # budget_goals: monthly budget limit per user
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS budget_goals (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL UNIQUE,
            monthly_limit DECIMAL(10,2) NOT NULL DEFAULT 0.00,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )

    # Migrate old 'expenses' table data if it exists
    try:
        cur.execute("SHOW TABLES LIKE 'expenses'")
        if cur.fetchone():
            cur.execute(
                """
                INSERT IGNORE INTO transactions (id, user_id, type, date, category, amount, description, created_at)
                SELECT id, user_id, 'expense', date, category, amount, description, created_at
                FROM expenses
                """
            )
            conn.commit()
    except Exception:
        pass

    try:
        cur.execute("CREATE INDEX idx_user_date ON transactions (user_id, date)")
    except mysql.connector.Error:
        pass

    # user_profiles: optional student profile info
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id INT NOT NULL PRIMARY KEY,
            display_name VARCHAR(100) DEFAULT '',
            college VARCHAR(150) DEFAULT '',
            course VARCHAR(100) DEFAULT '',
            year_of_study VARCHAR(20) DEFAULT '',
            monthly_allowance DECIMAL(10,2) DEFAULT 0.00,
            bio VARCHAR(300) DEFAULT '',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )

    conn.commit()
    cur.close()
    conn.close()
