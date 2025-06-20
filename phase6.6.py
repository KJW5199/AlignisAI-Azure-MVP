# Azure-Ready Streamlit MVP with Login, Roles, and Azure Blob Integration

import streamlit as st
import sqlite3
import datetime
import os
from pathlib import Path
from azure.storage.blob import BlobServiceClient
from transformers import pipeline

st.set_page_config(page_title="KYC Compliance MVP", layout="wide")

# --- LOGIN SETUP ---
users = {
    "admin": {"password": "admin123", "role": "Admin"},
    "editor": {"password": "editor123", "role": "Editor"},
    "analyst": {"password": "analyst123", "role": "Analyst"},
}

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.role = None
    st.session_state.username = None

if not st.session_state.logged_in:
    st.title("🔐 Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        user = users.get(username)
        if user and user["password"] == password:
            st.session_state.logged_in = True
            st.session_state.role = user["role"]
            st.session_state.username = username
            st.experimental_rerun()
        else:
            st.error("Invalid credentials")
    st.stop()

if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.session_state.role = None
    st.session_state.username = None
    st.rerun()

# --- DATABASE SETUP ---
conn = sqlite3.connect("kyc_training.db", check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS audit_log (entry TEXT, timestamp TEXT)''')
c.execute('''CREATE TABLE IF NOT EXISTS training_status (user TEXT, role TEXT, module TEXT, status TEXT, timestamp TEXT, due_date TEXT, score INTEGER)''')
conn.commit()

# --- AZURE BLOB SETUP ---
AZURE_CONNECTION_STRING = os.environ.get("AZURE_CONNECTION_STRING")
blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
container_name = "policy-files"
container_client = blob_service_client.get_container_client(container_name)

# --- SUMMARIZATION MODEL ---
summarizer = pipeline("summarization", model="sshleifer/distilbart-cnn-12-6")

# --- SIDEBAR MENU ---
role = st.session_state.role
menu_options = ["Dashboard", "Upload Policies", "AI Summary & Training", "User Portal", "Audit Log"]
if role in ["Admin"]:
    menu_options.append("Vision & Roadmap")
choice = st.sidebar.radio("Go to", menu_options)

# --- DASHBOARD ---
if choice == "Dashboard":
    st.header("📊 Dashboard Summary")
    pending = c.execute("SELECT COUNT(*) FROM training_status WHERE status = 'Pending'").fetchone()[0]
    completed = c.execute("SELECT COUNT(*) FROM training_status WHERE status = 'Completed'").fetchone()[0]
    overdue = c.execute("SELECT COUNT(*) FROM training_status WHERE status = 'Pending' AND due_date < ?", (datetime.date.today().isoformat(),)).fetchone()[0]
    st.metric("Pending Trainings", pending)
    st.metric("Completed Trainings", completed)
    st.metric("Overdue Trainings", overdue)
    st.markdown("---")
    st.subheader("📂 Stored Policies")
    try:
        blobs = container_client.list_blobs()
        for blob in blobs:
            st.text(f"{blob.name} — Uploaded {blob.last_modified.strftime('%Y-%m-%d %H:%M:%S')}")
            if role == "Admin":
                if st.button(f"❌ Delete {blob.name}", key=f"delete_{blob.name}"):
                    container_client.delete_blob(blob.name)
                    c.execute("INSERT INTO audit_log VALUES (?, ?)", (f"Deleted policy: {blob.name}", datetime.datetime.now().isoformat()))
                    conn.commit()
                    st.success(f"{blob.name} has been deleted.")
                    st.rerun()
    except Exception as e:
        st.error(f"Error fetching policies: {e}")

# --- AI SUMMARY & TRAINING ---
elif choice == "AI Summary & Training":
    st.header("🧠 AI Summary & Training Generator")
    blobs = container_client.list_blobs()
    for blob in blobs:
        if blob.name.endswith(".txt"):
            st.markdown(f"### 📄 {blob.name}")
            blob_client = container_client.get_blob_client(blob.name)
            policy_text = blob_client.download_blob().readall().decode("utf-8")

            if role in ["Admin", "Editor"]:
                edited_text = st.text_area("Edit Policy Text:", value=policy_text, height=200, key=f"edit_{blob.name}")
                if st.button("Save Changes", key=f"save_{blob.name}"):
                    container_client.upload_blob(blob.name, edited_text.encode("utf-8"), overwrite=True)
                    st.success("Changes saved.")
            else:
                st.text_area("Policy Text:", value=policy_text, height=200, disabled=True)

            with st.spinner("Generating AI Summary..."):
                try:
                    summary = summarizer(policy_text, max_length=120, min_length=30, do_sample=False)[0]['summary_text']
                except Exception as e:
                    summary = f"Error generating summary: {str(e)}"

            st.text_area("AI-Generated Summary & Key Takeaways:", value=summary, height=150, disabled=True, key=f"summary_{blob.name}")

            assign_to = st.selectbox("Assign to:", list(users.keys()), key=f"user_{blob.name}")
            if st.button(f"Assign Training - {blob.name}", key=f"btn_{blob.name}"):
                timestamp = datetime.datetime.now().isoformat()
                due = (datetime.date.today() + datetime.timedelta(days=7)).isoformat()
                c.execute("INSERT INTO training_status VALUES (?, ?, ?, ?, ?, ?, ?)", (assign_to, users[assign_to]["role"], blob.name, "Pending", timestamp, due, 0))
                c.execute("INSERT INTO audit_log VALUES (?, ?)", (f"Assigned {blob.name} to {assign_to}", timestamp))
                conn.commit()
                st.success(f"Training assigned to {assign_to}.")

# --- USER PORTAL ---
elif choice == "User Portal":
    st.header("🧑‍💼 User Training Portal")
    username = st.session_state.username
    st.subheader(f"Training for: {username}")
    records = c.execute("SELECT module, status, timestamp, due_date FROM training_status WHERE user = ?", (username,)).fetchall()
    for mod, stat, ts, due in records:
        st.markdown(f"**{mod}** — *{stat}*, Assigned: {ts}, Due: {due}")
        if stat == "Pending":
            st.markdown("**Quiz** (pass with 80% or more)")
            q1 = st.radio(f"1. What is the main purpose of {mod}?", ["Entertainment", "Policy enforcement", "Games"], key=f"{mod}_q1")
            q2 = st.radio("2. Who must comply with the policy?", ["Executives only", "Everyone", "No one"], key=f"{mod}_q2")
            q3 = st.radio("3. When is the review due?", ["Monthly", "Annually", "Never"], key=f"{mod}_q3")
            score = sum([q1 == "Policy enforcement", q2 == "Everyone", q3 == "Annually"])
            if st.button(f"Submit Quiz - {mod}"):
                if score >= 2:
                    c.execute("UPDATE training_status SET status = 'Completed', score = ? WHERE user = ? AND module = ?", (score, username, mod))
                    c.execute("INSERT INTO audit_log VALUES (?, ?)", (f"{username} completed {mod} with score {score}/3", datetime.datetime.now().isoformat()))
                    conn.commit()
                    st.success(f"Marked {mod} as completed.")
                else:
                    st.warning("You need 2 or more correct answers to pass.")

# --- AUDIT LOG ---
elif choice == "Audit Log":
    st.header("📜 Audit Trail")
    logs = c.execute("SELECT * FROM audit_log ORDER BY timestamp DESC").fetchall()
    for entry, ts in logs:
        st.text(f"{ts} — {entry}")

# --- VISION & ROADMAP ---
elif choice == "Vision & Roadmap" and role == "Admin":
    st.header("🚀 Vision & Roadmap")
    st.markdown("""
    - Phase 1: Manual Upload & Role-based Assignment ✅
    - Phase 2: AI-Powered Summaries & Audit Logging ✅
    - Phase 3: Dashboard Insights + Overdue Tracking ✅
    - Phase 4: Azure Integration for Deployment ✅
    - Phase 5: Pilot with Small FinTech Clients 🔜
    - Phase 6: Add Alert Logic + Role-Specific Views 🔜
    - Phase 7: Secure Sign-In + Multi-Region Scaling 🔜
    """)
