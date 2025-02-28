import os
import json
import streamlit as st



def get_server_info(info_file = "server_info.json"):
    with open(info_file, "r") as f:
        data = json.load(f)
    return data

def main():
    # Set the title and the logo of the page
    st.title('GPU使用情况监视平台')
    server_info = get_server_info()

    



if __name__ == '__main__':
    print(" ======  main  =======")
    st.set_page_config(
        page_title="GPU使用情况监视平台",
        layout="centered",
        initial_sidebar_state="auto",
    )
    main()