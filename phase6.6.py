# Azure-Ready Streamlit MVP with Login, Roles, and Azure Blob Integration

import streamlit as st
import sqlite3
import datetime
import os
from pathlib import Path
from azure.storage.blob import BlobServiceClient

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
            st.rerun()
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
c.execute('''CREATE TABLE IF NOT EXISTS training_status (user TEXT, role TEXT, module TEXT, status TEXT, timestamp TEXT, due_date TEXT)''')
conn.commit()

# --- AZURE BLOB SETUP ---
AZURE_CONNECTION_STRING = os.environ["AZURE_CONNECTION_STRING"]
blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
container_name = "policyfiles"
container_client = blob_service_client.get_container_client(container_name)

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
    except Exception as e:
        st.error(f"Error fetching policies: {e}")

# --- POLICY UPLOAD ---
elif choice == "Upload Policies" and role in ["Admin", "Editor"]:
    st.header("📤 Upload New Policy")
    uploaded_file = st.file_uploader("Choose a .txt policy file", type="txt")
    if uploaded_file:
        container_client.upload_blob(uploaded_file.name, uploaded_file, overwrite=True)
        timestamp = datetime.datetime.now().isoformat()
        c.execute("INSERT INTO audit_log VALUES (?, ?)", (f"Uploaded policy: {uploaded_file.name}", timestamp))
        conn.commit()
        st.success("Policy uploaded successfully.")

# --- AI SUMMARY AND TRAINING ---
elif choice == "AI Summary & Training":
    st.header("🧠 AI Summary & Training Generator")
    blobs = container_client.list_blobs()
    for blob in blobs:
        if blob.name.endswith(".txt"):
            st.markdown(f"**{blob.name}**")
            assign_to = st.selectbox("Assign to:", ["admin", "editor", "analyst"], key=blob.name)
            if st.button(f"Assign Training - {blob.name}"):
                timestamp = datetime.datetime.now().isoformat()
                due = (datetime.date.today() + datetime.timedelta(days=7)).isoformat()
                c.execute("INSERT INTO training_status VALUES (?, ?, ?, ?, ?, ?)", (assign_to, users[assign_to]["role"], blob.name, "Pending", timestamp, due))
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
        if stat == "Pending" and st.button(f"Mark Completed - {mod}"):
            c.execute("UPDATE training_status SET status = 'Completed' WHERE user = ? AND module = ?", (username, mod))
            c.execute("INSERT INTO audit_log VALUES (?, ?)", (f"{username} completed {mod}", datetime.datetime.now().isoformat()))
            conn.commit()
            st.success(f"Marked {mod} as completed.")

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
