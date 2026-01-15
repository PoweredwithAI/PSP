import streamlit as st
import hashlib

# In a real application, the passwords should be securely hashed and stored.
# Here we use SHA-256 for demonstration purposes only.
USERS = {
    "admin": hashlib.sha256("your_password".encode()).hexdigest(),
    "researcher": hashlib.sha256("research123".encode()).hexdigest(),
}                                                        

def check_password():
    """Returns True if the user had the correct password."""
    
    def password_entered():
        username = st.session_state["username"]
        password = st.session_state["password"]
        
        if username in USERS and USERS[username] == hashlib.sha256(password.encode()).hexdigest():
            st.session_state["authenticated"] = True
            st.session_state["current_user"] = username
            del st.session_state["password"]  # Password deleted after use
        else:
            st.session_state["authenticated"] = False

    if st.session_state.get("authenticated", False):
        return True

    st.title("🔐 TargetScraper Login")
    st.text_input("Username", key="username")
    st.text_input("Password", type="password", key="password")
    st.markdown("Use default credentials: researcher / research123")
    st.button("Login", on_click=password_entered)
    
    if "authenticated" in st.session_state and not st.session_state["authenticated"]:
        st.error("😕 User not known or password incorrect")
    
    return False