import streamlit as st
import os

def main():
    st.set_page_config(page_title="Full HTML Page in Iframe", page_icon="🌐")

    st.title("Full HTML Page Embedded in Streamlit via Iframe")

    st.markdown("""
    This example shows how to embed a full HTML page in Streamlit using an iframe.
    Your HTML file needs to be served from a local HTTP server or remotely accessible URL.
    """)

    # Example: local server URL pointing to your HTML file
    # You need to run a local HTTP server in the folder containing your HTML file first:
    # python -m http.server 8000
    # Then update the url accordingly:
    url ="arcgis-multi-feature-layer-service-search-with-feature-search.html"  # Make sure this file is in the same directory as this script
    

    st.markdown(f"<iframe src='{url}' width='100%' height='100%' frameborder='0'></iframe>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()

