import os
import json
import streamlit as st
import config
import functools

from gpu_watcher import SingleGPUServerWatcher
from ding_notify import validate_ding_print

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

def display_single_server_page(name):
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
        avg_gpu_util = summerized_state["avg_gpu_util"]
        avg_mem_util = summerized_state["avg_memory_util"]
        col1.metric(text.avg_gpu_util, f"{avg_gpu_util}%", border=True)
        col2.metric(text.avg_mem_util, f"{avg_mem_util}%", border=True)
        is_all_free = summerized_state["all_free"]
        is_have_free = summerized_state["have_free"]
        col3.metric(text.all_gpu_free, "✅Yes" if is_all_free else "❌No", border=True)
        col4.metric(text.have_gpu_free, "✅Yes" if is_have_free else "❌No", border=True)

        with st.expander("See details"):
            state = st.session_state["watchers"][name].state
            new_order = ["name", ' utilization.gpu [%]',' memory', ' timestamp']
            st.write(state[new_order])

    st.write(f"#### {text.button_part}")

    # col1, col2 = st.columns(2)
    # with col1:
    #     if st.button(text.update_once, key=name, icon="🔂"):
    #         st.session_state["watchers"][name].restart_run(loop=st.session_state["watchers"][name].is_looping)
    # with col2:
    #     if st.button(text.loop_watch_setting):
    #         loop_setting_page()


@st.dialog(text.loop_watch_setting)
def loop_setting_page():
    need_loop_watch = st.toggle(text.is_need_loop_watch)
    update_stpe = st.number_input(text.update_step_hint, min_value=1, value=3600, disabled = not need_loop_watch)
    st.divider()
    need_dingding_remind = st.toggle(text.is_need_dingding_remind, disabled = not need_loop_watch)
    
    st.caption("")
    if st.button(text.validate_ding, disabled=need_dingding_remind):
        result = validate_ding_print()
        if result is not None:
            st.error(f"DingDing Error: {result}")
            st.session_state["dingAvailable"] = False
        else:
            st.success("DingDing is available")
            st.session_state["dingAvailable"] = True


        
@st.fragment(run_every=config.page_update_freq)
def display_server_state_page():
    for name in st.session_state["watchers"].keys():
        st.divider()
        display_single_server_page(name)

def main():
    # Set the title and the logo of the page
    st.title(text.page_title)
    st.session_state["dingAvailable"] = False
    st.session_state["watchers"] = get_server_watcher()
    for watcher in st.session_state["watchers"].values():
        watcher.start_run(loop=False)
    if st.button(text.update_all, type="primary",icon="🔁"):
        for watcher in st.session_state["watchers"].values():
            watcher.restart_run(loop=watcher.is_looping)
    display_server_state_page()
    



if __name__ == '__main__':
    print(" ======  main  =======")
    st.set_page_config(
        page_title=text.page_title,
        layout="centered",
        initial_sidebar_state="auto",
    )
    main()