import sqlite3

conn = sqlite3.connect("transactions.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS transactions (

    id INTEGER PRIMARY KEY AUTOINCREMENT,

    account_type TEXT,
    sender TEXT,
    receiver TEXT,

    transaction_type TEXT,
    payment_method TEXT,
    merchant_category TEXT,

    location TEXT,
    device TEXT,

    amount REAL,

    transaction_time TEXT,

    transaction_status TEXT,

    result TEXT,
    risk_level TEXT,
    confidence REAL,

    payment_received TEXT,
    screenshot TEXT

)
""")

conn.commit()
conn.close()

print("Database Created Successfully")