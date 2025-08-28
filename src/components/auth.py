# src/components/auth.py
import sqlite3, bcrypt
from pathlib import Path
import streamlit as st

DB = Path("artifacts") / "auth.db"
DB.parent.mkdir(parents=True, exist_ok=True)

def _conn():
    con = sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash BLOB NOT NULL
    )""")
    return con

def create_user(username: str, password: str) -> tuple[bool,str]:
    if not username or not password:
        return False, "Username and password required."
    pw_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    try:
        with _conn() as con:
            con.execute("INSERT INTO users(username, password_hash) VALUES (?,?)", (username, pw_hash))
        return True, "Account created."
    except sqlite3.IntegrityError:
        return False, "Username already exists."

def verify_user(username: str, password: str) -> bool:
    with _conn() as con:
        cur = con.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
        row = cur.fetchone()
        if not row: return False
        return bcrypt.checkpw(password.encode("utf-8"), row[0])

def login_ui():
    st.subheader("Login")
    u = st.text_input("Username", key="login_user")
    p = st.text_input("Password", type="password", key="login_pass")
    if st.button("Sign in", type="primary"):
        if verify_user(u, p):
            st.session_state.user = {"username": u}
            st.success(f"Welcome, {u}!")
            st.rerun()
        else:
            st.error("Invalid credentials.")

def signup_ui():
    st.subheader("Create account")
    u = st.text_input("New username", key="signup_user")
    p1 = st.text_input("Password", type="password", key="signup_pass1")
    p2 = st.text_input("Confirm password", type="password", key="signup_pass2")
    if st.button("Sign up"):
        if p1 != p2:
            st.error("Passwords do not match.")
            return
        ok, msg = create_user(u, p1)
        (st.success if ok else st.error)(msg)

def require_auth(page_name: str):
    """
    Gate a page: if not logged in, show account forms and stop.
    """
    if st.session_state.get("user"):
        st.caption(f"Signed in as {st.session_state['user']['username']}")
        if st.button("Log out"):
            st.session_state.pop("user", None); st.rerun()
        return True
    st.info(f"Please sign in to access {page_name}.")
    with st.expander("Login / Signup", expanded=True):
        tabs = st.tabs(["Login", "Signup"])
        with tabs[0]: login_ui()
        with tabs[1]: signup_ui()
    st.stop()