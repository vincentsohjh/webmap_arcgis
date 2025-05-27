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