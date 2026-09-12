from flask import Flask, render_template, request, session, redirect, url_for
import sqlite3
import os
from datetime import datetime
import joblib
import pandas as pd

app = Flask(__name__)
app.secret_key = "fraud_detection_admin_secret"

# =========================================================
# RANDOM FOREST ML MODEL
# =========================================================

MODEL_FILE = "random_forest_fraud_model.pkl"

model_package = joblib.load(MODEL_FILE)

ml_model = model_package["model"]
encoders = model_package["encoders"]
model_features = model_package["features"]

DATABASE = "transactions.db"
UPLOAD_FOLDER = "uploads"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# =========================================================
# DATABASE INITIALIZATION + COLUMN MIGRATION
# =========================================================

def init_database():

    conn = get_db()

    # Original table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT,
            receiver TEXT,
            account_type TEXT,
            transaction_type TEXT,
            payment_category TEXT,
            game_name TEXT,
            amount REAL,
            payment_received TEXT,
            screenshot TEXT,
            risk_score INTEGER,
            result TEXT,
            rules TEXT,
            created_at TEXT
        )
    """)

    # Check existing columns
    columns = [
        row["name"]
        for row in conn.execute("PRAGMA table_info(transactions)").fetchall()
    ]

    # New columns required for Transaction History
    new_columns = {
        "payment_method": "TEXT",
        "merchant_category": "TEXT",
        "location": "TEXT",
        "device": "TEXT",
        "transaction_status": "TEXT",
        "risk_level": "TEXT",
        "confidence": "REAL"
    }

    for column, datatype in new_columns.items():

        if column not in columns:

            conn.execute(
                f"ALTER TABLE transactions ADD COLUMN {column} {datatype}"
            )

    conn.commit()
    conn.close()


init_database()


# =========================================================
# ADMIN LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if username == "admin" and password == "admin123":

            session["admin_logged_in"] = True

            return redirect(url_for("home"))

        return render_template(
            "login.html",
            error="Invalid username or password"
        )

    return render_template("login.html")


@app.route("/logout")
def logout():

    session.clear()

    return redirect(url_for("login"))


# =========================================================
# STATISTICS
# =========================================================

def get_stats():

    conn = get_db()

    total = conn.execute(
        "SELECT COUNT(*) FROM transactions"
    ).fetchone()[0]

    fraud = conn.execute(
        """
        SELECT COUNT(*)
        FROM transactions
        WHERE result = 'FRAUD DETECTED'
        """
    ).fetchone()[0]

    suspicious = conn.execute(
        """
        SELECT COUNT(*)
        FROM transactions
        WHERE result = 'SUSPICIOUS TRANSACTION'
        """
    ).fetchone()[0]

    genuine = conn.execute(
        """
        SELECT COUNT(*)
        FROM transactions
        WHERE result = 'GENUINE TRANSACTION'
        """
    ).fetchone()[0]

    conn.close()

    return total, fraud, suspicious, genuine


# =========================================================
# HOME / DASHBOARD
# =========================================================

@app.route("/")
def home():

    if not session.get("admin_logged_in"):
        return redirect(url_for("login"))

    total, fraud, suspicious, genuine = get_stats()

    conn = get_db()

    transactions = conn.execute("""
        SELECT *
        FROM transactions
        ORDER BY id DESC
        LIMIT 10
    """).fetchall()

    conn.close()

    return render_template(
        "index.html",
        total=total,
        fraud=fraud,
        suspicious=suspicious,
        genuine=genuine,
        transactions=transactions
    )

# =========================
# REPORTS
# =========================

@app.route("/reports")
def reports():

    if not session.get("admin_logged_in"):
        return redirect(url_for("login"))

    # Get statistics
    total, fraud, suspicious, genuine = get_stats()

    # Get recent transactions
    conn = get_db()

    transactions = conn.execute("""
        SELECT
            id,
            created_at,
            sender,
            receiver,
            amount,
            transaction_type,
            payment_category,
            risk_score,
            result
        FROM transactions
        ORDER BY id DESC
        LIMIT 10
    """).fetchall()

    conn.close()

    return render_template(
        "reports.html",
        total=total,
        fraud=fraud,
        suspicious=suspicious,
        genuine=genuine,
        transactions=transactions
    )
# =========================================================
# FRAUD DETECTION
# =========================================================

@app.route("/detect", methods=["POST"])
def detect():

    if not session.get("admin_logged_in"):
        return redirect(url_for("login"))

    # -----------------------------------------------------
    # FORM DATA
    # -----------------------------------------------------

    sender = request.form.get(
        "sender", ""
    ).strip()

    receiver = request.form.get(
        "receiver", ""
    ).strip()

    account_type = request.form.get(
        "account_type",
        "Personal"
    )

    transaction_type = request.form.get(
        "transaction_type",
        "PAYMENT"
    )

    payment_category = request.form.get(
        "payment_category",
        "Bank Transfer"
    )

    # Existing field in your design
    game_name = request.form.get(
        "game_name",
        ""
    ).strip()

    payment_received = request.form.get(
        "payment_received",
        "Yes"
    )

    # -----------------------------------------------------
    # NEW HISTORY FIELDS
    # -----------------------------------------------------

    # If these fields exist in your HTML, their values will be used.
    # Otherwise safe default values are used.

    payment_method = request.form.get(
        "payment_method",
        ""
    ).strip()

    merchant_category = request.form.get(
        "merchant_category",
        ""
    ).strip()

    location = request.form.get(
        "location",
        "India"
    ).strip()

    device = request.form.get(
        "device",
        "Mobile"
    ).strip()

    # If payment method is not separately present,
    # use the service/platform value if available.
    if not payment_method:

        payment_method = request.form.get(
            "service_platform",
            ""
        ).strip()

    if not payment_method:
        payment_method = "UPI"

    # If merchant category is not separately present,
    # use payment category.
    if not merchant_category:
        merchant_category = payment_category

    # -----------------------------------------------------
    # AMOUNT
    # -----------------------------------------------------

    try:

        amount = float(
            request.form.get(
                "amount",
                "0"
            )
        )

    except (ValueError, TypeError):

        amount = 0


    # =====================================================
    # SCREENSHOT UPLOAD
    # =====================================================

    screenshot = request.files.get("screenshot")

    screenshot_name = ""

    if screenshot and screenshot.filename:

        screenshot_name = screenshot.filename

        screenshot.save(
            os.path.join(
                UPLOAD_FOLDER,
                screenshot_name
            )
        )


    # =====================================================
    # DATABASE CONNECTION
    # =====================================================

    conn = get_db()


    # =====================================================
    # PREVIOUS TRANSACTIONS
    # =====================================================

    previous_transactions = 0

    if sender:

        previous_transactions = conn.execute(
            """
            SELECT COUNT(*)
            FROM transactions
            WHERE sender = ?
            """,
            (sender,)
        ).fetchone()[0]


    # =====================================================
    # INTERNATIONAL TRANSACTION
    # =====================================================

    international = (
        "Yes"
        if "international" in payment_category.lower()
        else "No"
    )


    # =====================================================
    # PREPARE ML DATA
    # =====================================================

    ml_data = pd.DataFrame([{

        "account_type": account_type,

        "transaction_type": transaction_type,

        "payment_category": payment_category,

        "amount": amount,

        "payment_received": payment_received,

        "international": international,

        "previous_transactions": previous_transactions

    }])


    # =====================================================
    # APPLY ENCODERS
    # =====================================================

    categorical_columns = [

        "account_type",

        "transaction_type",

        "payment_category",

        "payment_received",

        "international"

    ]


    for column in categorical_columns:

        value = ml_data.loc[0, column]

        if value in encoders[column].classes_:

            ml_data[column] = encoders[column].transform(
                [value]
            )

        else:

            ml_data[column] = encoders[column].transform(
                [encoders[column].classes_[0]]
            )


    # =====================================================
    # FEATURE ORDER
    # =====================================================

    ml_data = ml_data[model_features]


    # =====================================================
    # RANDOM FOREST PREDICTION
    # =====================================================

    prediction = int(
        ml_model.predict(ml_data)[0]
    )

    probabilities = ml_model.predict_proba(ml_data)[0]

    fraud_probability = float(
        probabilities[1] * 100
    )

    genuine_probability = float(
        probabilities[0] * 100
    )


    # =====================================================
    # RISK SCORE
    # =====================================================

    risk_score = round(
        fraud_probability
    )

    risk_score = min(
        max(risk_score, 0),
        100
    )


    # =====================================================
    # RISK LEVEL
    # =====================================================

    if risk_score >= 70:

        risk_level = "High"

    elif risk_score >= 40:

        risk_level = "Medium"

    else:

        risk_level = "Low"


    # =====================================================
    # CONFIDENCE
    # =====================================================

    confidence = max(
        fraud_probability,
        genuine_probability
    )


    # =====================================================
    # FINAL RESULT
    # =====================================================

    if prediction == 1:

        result = "FRAUD DETECTED"

        rules = [

            "Random Forest predicted FRAUD",

            f"Fraud Probability: {fraud_probability:.2f}%"

        ]

    else:

        result = "GENUINE TRANSACTION"

        rules = [

            "Random Forest predicted GENUINE",

            f"Fraud Probability: {fraud_probability:.2f}%"

        ]


    rules_text = " | ".join(rules)


    # =====================================================
    # TRANSACTION STATUS
    # =====================================================

    if payment_received.lower() == "yes":

        transaction_status = "Completed"

    else:

        transaction_status = "Pending"


    # =====================================================
    # SAVE TRANSACTION
    # =====================================================

    conn.execute("""
        INSERT INTO transactions (

            sender,

            receiver,

            account_type,

            transaction_type,

            payment_category,

            game_name,

            amount,

            payment_received,

            screenshot,

            risk_score,

            result,

            rules,

            created_at,

            payment_method,

            merchant_category,

            location,

            device,

            transaction_status,

            risk_level,

            confidence

        )

        VALUES (

            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,

            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?

        )

    """, (

        sender,

        receiver,

        account_type,

        transaction_type,

        payment_category,

        game_name,

        amount,

        payment_received,

        screenshot_name,

        risk_score,

        result,

        rules_text,

        datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        ),

        payment_method,

        merchant_category,

        location,

        device,

        transaction_status,

        risk_level,

        confidence

    ))


    conn.commit()
    conn.close()


    # =====================================================
    # UPDATED DATA
    # =====================================================

    total, fraud, suspicious, genuine = get_stats()

    conn = get_db()

    transactions = conn.execute("""
        SELECT *
        FROM transactions
        ORDER BY id DESC
        LIMIT 10
    """).fetchall()

    conn.close()


    # =====================================================
    # DISPLAY RESULT
    # =====================================================

    return render_template(

        "index.html",

        total=total,

        fraud=fraud,

        suspicious=suspicious,

        genuine=genuine,

        transactions=transactions,

        result=result,

        risk_score=risk_score,

        risk_level=risk_level,

        confidence=confidence,

        rules=rules

    )


# =========================================================
# TRANSACTION HISTORY
# =========================================================

@app.route("/transaction-history")
def transaction_history():

    if not session.get("admin_logged_in"):
        return redirect(url_for("login"))

    conn = get_db()

    transactions = conn.execute("""
        SELECT
            id,
            sender,
            receiver,
            transaction_type,
            payment_category,
            amount,
            risk_score,
            result,
            created_at
        FROM transactions
        ORDER BY id DESC
    """).fetchall()

    conn.close()

    return render_template(
        "transaction_history.html",
        transactions=transactions
    )

    # -----------------------------------------------------
    # RECENT TRANSACTIONS
    # -----------------------------------------------------

    conn = get_db()

    recent_transactions = conn.execute("""
        SELECT *
        FROM transactions
        ORDER BY id DESC
        LIMIT 10
    """).fetchall()

    conn.close()


    return render_template(

        "reports.html",

        total=total,

        fraud=fraud,

        suspicious=suspicious,

        genuine=genuine,

        model_accuracy=model_accuracy,

        recent_transactions=recent_transactions

    )


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    app.run(debug=True)