# Azure-Ready Streamlit MVP with Login, Roles, and Azure Blob Integration
# Triggering GitHub deployment

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
AZURE_CONNECTION_STRING = st.secrets["AZURE_CONNECTION_STRING"]
