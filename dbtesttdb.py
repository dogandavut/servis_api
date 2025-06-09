import pyodbc

conn_str = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=185.84.182.228;"
    "DATABASE=servis_db;"
    "UID=sa;"
    "PWD=Dell1545*-"
)

try:
    conn = pyodbc.connect(conn_str)
    print("✅ Bağlantı başarılı!")
except Exception as e:
    print("❌ Hata:", e)
