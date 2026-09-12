import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score, classification_report
import joblib

# --------------------------------------------------
# 1. CREATE TRAINING DATA
# --------------------------------------------------

np.random.seed(42)

n = 2000

data = {
    "account_type": np.random.choice(
        ["Personal", "Business"], n
    ),

    "transaction_type": np.random.choice(
        ["PAYMENT", "TRANSFER", "DEPOSIT", "WITHDRAWAL"], n
    ),

    "payment_category": np.random.choice(
        ["Shopping", "Online Payment", "Bank Transfer",
         "Gaming", "Bills", "Food"], n
    ),

    "amount": np.random.randint(
        100, 100000, n
    ),

    "payment_received": np.random.choice(
        ["Yes", "No"], n
    ),

    "international": np.random.choice(
        ["Yes", "No"], n
    ),

    "previous_transactions": np.random.randint(
        0, 20, n
    )
}

df = pd.DataFrame(data)

# --------------------------------------------------
# 2. CREATE FRAUD LABEL
# --------------------------------------------------

df["fraud"] = 0

# High transaction amount
df.loc[df["amount"] > 50000, "fraud"] = 1

# Payment not received
df.loc[df["payment_received"] == "No", "fraud"] = 1

# International transaction
df.loc[df["international"] == "Yes", "fraud"] = 1

# Gaming transactions with high amount
df.loc[
    (df["payment_category"] == "Gaming") &
    (df["amount"] > 20000),
    "fraud"
] = 1

# Very few previous transactions + high amount
df.loc[
    (df["previous_transactions"] < 3) &
    (df["amount"] > 30000),
    "fraud"
] = 1

# --------------------------------------------------
# 3. ENCODE CATEGORICAL DATA
# --------------------------------------------------

encoders = {}

categorical_columns = [
    "account_type",
    "transaction_type",
    "payment_category",
    "payment_received",
    "international"
]

for column in categorical_columns:
    encoder = LabelEncoder()
    df[column] = encoder.fit_transform(df[column])
    encoders[column] = encoder

# --------------------------------------------------
# 4. FEATURES AND TARGET
# --------------------------------------------------

X = df.drop("fraud", axis=1)
y = df["fraud"]

# --------------------------------------------------
# 5. TRAIN TEST SPLIT
# --------------------------------------------------

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=42,
    stratify=y
)

# --------------------------------------------------
# 6. RANDOM FOREST MODEL
# --------------------------------------------------

model = RandomForestClassifier(
    n_estimators=200,
    random_state=42,
    class_weight="balanced"
)

model.fit(X_train, y_train)

# --------------------------------------------------
# 7. MODEL EVALUATION
# --------------------------------------------------

y_pred = model.predict(X_test)

accuracy = accuracy_score(y_test, y_pred)

print("\n======================================")
print(" RANDOM FOREST FRAUD DETECTION MODEL")
print("======================================")

print(f"\nModel Accuracy: {accuracy * 100:.2f}%")

print("\nClassification Report:")
print(classification_report(y_test, y_pred))

# --------------------------------------------------
# 8. SAVE MODEL
# --------------------------------------------------

model_package = {
    "model": model,
    "encoders": encoders,
    "features": list(X.columns)
}

joblib.dump(
    model_package,
    "random_forest_fraud_model.pkl"
)

print("\n======================================")
print("Model saved successfully!")
print("File: random_forest_fraud_model.pkl")
print("======================================")