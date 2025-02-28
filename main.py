import os
import json
import streamlit as st
import config
import functools

from gpu_watcher import SingleGPUServerWatcher

if config.language == 'cn':
    import text.cn as text
elif config.language == 'en':
    import text.en as text
else:
    raise ValueError('Language setting in config.py not supported')

def get_server_watcher(info_file = "server_info.json"):
    watchers = {}
    with open(info_file, "r") as f:
        server_info = json.load(f)
    for server in server_info:
        watchers[server["name"]] = SingleGPUServerWatcher(**server)
    return watchers

def display_single_server_icons(name):
    name = st.session_state["watchers"][name].name
    st.write(f"### {name}")
    message = st.session_state["watchers"][name].message
    if message.startswith("Error"):
        st.error(message)
    elif message.startswith("Loading"):
        st.info(st.session_state["watchers"][name].message)
    elif message.startswith("Success"):
        summerized_state = st.session_state["watchers"][name].summerized_state
        st.metric("GPU", str(summerized_state["gpu_name"]), border=True)
        col1, col2, col3, col4 = st.columns(4)
        avg_gpu_util = summerized_state["avg_gpu_util"] * 100
        avg_mem_util = summerized_state["avg_memory_util"] * 100
        col1.metric("Avg_GPU_Util", f"{avg_gpu_util}%", border=True)
        col2.metric("Avg_Mem_Util", f"{avg_mem_util}%", border=True)
        is_all_free = summerized_state["all_free"]
        is_have_free = summerized_state["have_free"]
        col3.metric("All_GPU_Free", "✅Yes" if is_all_free else "❌No", border=True)
        col4.metric("Have_Free_GPU", "✅Yes" if is_have_free else "❌No", border=True)

        with st.expander("See details"):
            state = st.session_state["watchers"][name].state
            new_order = ["name", ' utilization.gpu [%]',' memory', ' timestamp']
            st.write(state[new_order])

        
@st.fragment(run_every=1)
def display_server_state_icons():
    st.button("Update")
    for name in st.session_state["watchers"].keys():
        st.divider()
        display_single_server_icons(name)

def main():
    # Set the title and the logo of the page
    st.title(text.page_title)

    st.session_state["watchers"] = get_server_watcher()
    for watcher in st.session_state["watchers"].values():
        watcher.start_run()
    display_server_state_icons()
    



if __name__ == '__main__':
    print(" ======  main  =======")
    st.set_page_config(
        page_title=text.page_title,
        layout="centered",
        initial_sidebar_state="auto",
    )
    main()