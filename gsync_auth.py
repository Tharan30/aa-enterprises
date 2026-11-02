import streamlit as st


def get_credentials_info():
    """Load service-account credentials from deployment secrets only."""
    return dict(st.secrets["gcp_service_account"])
