import streamlit as st
import google.generativeai as genai

st.title("API Key Diagnostic Test")

try:
    # Authenticate
    genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
    st.success("✅ API Key Accepted by Google")
    
    # Ask Google for available models
    st.markdown("### 🔍 Models Available to Your Key:")
    
    available_models = []
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            available_models.append(m.name)
            
    st.write(available_models)
    
except Exception as e:
    st.error(f"❌ Connection Failed: {e}")
