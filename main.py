import json
import config
from gpu_watcher import SingleGPUServerWatcher
from i18n import I18nService
from pathlib import Path
from exec_hook import set_exechook
import streamlit as st

set_exechook()

# 加载国际化服务
i18n = I18nService()
i18n.set_lang(config.language)

def get_server_watcher(info_file=Path(__file__).parent / "server_info.json"):
    watchers = {}
    with open(info_file, "r") as f:
        server_info = json.load(f)
    for server in server_info:  # server is already a dictionary
        watcher = SingleGPUServerWatcher(
            name=server["name"],
            ip=server["ip"],
            username=server["username"],
            password=server["password"],
            port=server.get("port", 22),  # default port is 22 if not specified
            update_step=server.get("update_step", 10)  # default update step is 10 if not specified
        )
        watchers[server["name"]] = watcher
    return watchers

def display_single_server_page(name):
    watcher = st.session_state["watchers"][name]
    st.write(f"### {watcher.name}")
    message = watcher.message
    if message.startswith("Error"):
        st.error(message)
    elif message.startswith("Loading"):
        st.info(message)
    elif message.startswith("Success"):
        summerized_state = watcher.summerized_state
        st.metric("GPU", str(summerized_state["gpu_name"]), border=True)
        col1, col2, col3, col4 = st.columns(4)
        avg_gpu_util = summerized_state["avg_gpu_util"]
        avg_mem_util = summerized_state["avg_memory_util"]
        col1.metric(i18n.get_text("avg_gpu_util"), f"{avg_gpu_util:.2f}%", border=True)
        col2.metric(i18n.get_text("avg_mem_util"), f"{avg_mem_util:.2f}%", border=True)
        is_all_free = summerized_state["all_free"]
        is_have_free = summerized_state["have_free"]
        col3.metric(i18n.get_text("all_gpu_free"), "✅Yes" if is_all_free else "❌No", border=True)
        col4.metric(i18n.get_text("have_gpu_free"), "✅Yes" if is_have_free else "❌No", border=True)

        with st.expander(i18n.get_text("see_details")):
            state = watcher.state
            new_order = ["gpu_name", 'utilization.gpu', 'memory', 'timestamp']
            st.write(state[new_order])

    st.write(f"#### {i18n.get_text('button_part')}")

    if st.button(i18n.get_text("update_once"), key=name, icon="🔄"):
        watcher.restart_run(loop=watcher.is_looping)

def main():
    st.title(i18n.get_text("page_title"))
    st.session_state["watchers"] = get_server_watcher()
    
    # 确保所有watcher都已更新
    for watcher in st.session_state["watchers"].values():
        watcher.start_run(loop=False)
        for _ in range(10):
            watcher.update_once()
            if watcher.message.startswith("Success"):
                break

    if st.button(i18n.get_text("update_all"), type="primary", icon="🔄"):
        for watcher in st.session_state["watchers"].values():
            watcher.restart_run(loop=True)
            for _ in range(10):
                watcher.update_once()
                if watcher.message.startswith("Success"):
                    break

    for name in st.session_state["watchers"].keys():
        display_single_server_page(name)

if __name__ == '__main__':
    st.set_page_config(
        page_title=i18n.get_text("page_title"),
        layout="centered",
        initial_sidebar_state="auto",
    )
    main()