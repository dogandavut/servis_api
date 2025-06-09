# db.py
import pyodbc
from config import DB_CONFIG

def get_connection():
    print("⚙️ DB bağlantısı deneniyor:", DB_CONFIG["server"])
    conn_str = (
        f"DRIVER={{{DB_CONFIG['driver']}}};"
        f"SERVER={DB_CONFIG['server']};"
        f"DATABASE={DB_CONFIG['database']};"
        f"UID={DB_CONFIG['username']};"
        f"PWD={DB_CONFIG['password']}"
    )
    print("🔗 Conn string:", conn_str)
    return pyodbc.connect(conn_str)
