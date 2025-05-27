import streamlit as st
import os
def load_html(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    else:
        return "<p>HTML file not found.</p>"
def main():
    st.set_page_config(page_title="Embedded HTML page", page_icon="🌐")
    st.title("Streamlit HTML Embed Example")
    # Method 2: Load external HTML file you have (change 'example.html' to your filename)
    html_file = "arcgis-multi-feature-layer-service-search-with-feature-search.html"  # Make sure this file is in the same directory as this script
    st.subheader("Embedded External HTML File")
    html_content = load_html(html_file)
    st.components.v1.html(html_content)
if __name__ == "__main__":
    main()