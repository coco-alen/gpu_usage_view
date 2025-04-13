import json
from pathlib import Path
import streamlit as st

import config
from exec_hook import set_exechook
from ding_notify import ding_print_txt
from gpu_watcher import SingleGPUServerWatcher, SSH_STATUS_LUT
from i18n_service import i18n

# set_exechook()

def get_server_watcher(info_file=Path(__file__).parent / "server_info.json"):
    watchers = {}
    with open(info_file, "r") as f:
        server_info = json.load(f)
    for server in server_info:  # server is already a dictionary
        watcher = SingleGPUServerWatcher(
            name=server["name"],
            ip=server["ip"],
            username=server["username"],
            password=server.get("password", ""),
            port=server.get("port", 22),  # default port is 22 if not specified
            update_step=server.get("update_step", 10)  # default update step is 10 if not specified
        )
        watchers[server["name"]] = watcher
    return watchers

def display_single_server_page(name):
    watcher = st.session_state["watchers"][name]
    st.write(f"### {watcher.name}")
    message = watcher.message
    ssh_state = watcher.ssh_state
    if ssh_state == SSH_STATUS_LUT["error"]:
        st.error(message)
    elif ssh_state == SSH_STATUS_LUT["loading"]:
        st.info(message)
    elif ssh_state == SSH_STATUS_LUT["success"]:
        summerized_gpu_state = watcher.summerized_gpu_state
        st.metric("GPU", str(summerized_gpu_state["gpu_name"]), border=True)
        col1, col2, col3, col4 = st.columns(4)
        avg_gpu_util = summerized_gpu_state["avg_gpu_util"]
        avg_mem_util = summerized_gpu_state["avg_memory_util"]
        col1.metric(i18n.get_text("avg_gpu_util"), f"{avg_gpu_util:.2f}%", border=True)
        col2.metric(i18n.get_text("avg_mem_util"), f"{avg_mem_util:.2f}%", border=True)
        is_all_free = summerized_gpu_state["all_free"]
        is_have_free = summerized_gpu_state["have_free"]
        col3.metric(i18n.get_text("all_gpu_free"), "✅Yes" if is_all_free else "❌No", border=True)
        col4.metric(i18n.get_text("have_gpu_free"), "✅Yes" if is_have_free else "❌No", border=True)

        with st.expander(i18n.get_text("see_details")):
            state = watcher.gpu_state
            new_order = ["gpu_name", 'utilization.gpu', 'memory', 'timestamp']
            st.write(state[new_order])

    st.write(f"##### {i18n.get_text('button_part')}")

    col1, col2 = st.columns(2)
    with col1:
        if st.button(i18n.get_text("update_once"), key=name, icon="🔂"):
            st.session_state["watchers"][name].restart_run(loop=st.session_state["watchers"][name].is_looping)
    with col2:
        if st.button(i18n.get_text("loop_watch_setting")):
            loop_setting_page(name)


@st.dialog(i18n.get_text("loop_watch_setting"))
def loop_setting_page(server_name):
    st.write("### " + server_name)
    watcher = st.session_state["watchers"][server_name]
    # get current settings
    current_settings = {
        "update_step": watcher.update_step,
        "need_loop_watch": int(watcher.is_looping),
        "dingding_remind_mode": int(watcher.remind_config["remind_every_update"]),
    }
    if not watcher.remind_config["remind_if_all_free"] and not watcher.remind_config["remind_if_have_free"]:
        current_settings["need_dingding_remind"] = i18n.get_text("no_dingding_remind")
    elif watcher.remind_config["remind_if_have_free"]:
        current_settings["need_dingding_remind"] = i18n.get_text("dingding_remind_have_free")
    elif watcher.remind_config["remind_if_all_free"]:
        current_settings["need_dingding_remind"] = i18n.get_text("dingding_remind_all_free")
    
    # show input fields for each setting
    need_loop_watch = st.toggle(i18n.get_text("is_need_loop_watch"), value=current_settings["need_loop_watch"])
    update_step = st.number_input(i18n.get_text("update_step_hint"), 
                        min_value=1, value=current_settings["update_step"], 
                        disabled = not need_loop_watch)
    st.divider()

    need_dingding_remind = st.segmented_control(i18n.get_text("is_need_dingding_remind"), 
                        options = [i18n.get_text("no_dingding_remind"), i18n.get_text("dingding_remind_have_free"), i18n.get_text("dingding_remind_all_free")], 
                        selection_mode="single", 
                        default=current_settings["need_dingding_remind"],
                        disabled = not need_loop_watch)
    
    if not st.session_state["dingAvailable"]:
        st.caption(i18n.get_text("validate_dingding_hint"))
    else:
        st.caption("")

    if st.button(i18n.get_text("validate_ding"), 
                 disabled = need_dingding_remind == i18n.get_text("no_dingding_remind") or st.session_state["dingAvailable"],
                 help=i18n.get_text("validate_dingding_help")):
        result = ding_print_txt(i18n.get_text("dingdingTest_success"))
        if result is not None:
            st.error(i18n.get_text("dingdingTest_fail").format(result))
            st.session_state["dingAvailable"] = False
        else:
            st.success(i18n.get_text("dingdingTest_success"))
            st.session_state["dingAvailable"] = True
    
    dingding_remind_mode = st.radio("", 
            [i18n.get_text("dingding_remind_once"), i18n.get_text("dingding_remind_every")], index=0,  
            disabled = need_dingding_remind == i18n.get_text("no_dingding_remind") or not st.session_state["dingAvailable"])

    st.divider()

    _, _, col = st.columns(3)
    with col:
        confirm = st.button(i18n.get_text("confirm"), icon="✅")
        if confirm:
            watcher.remind_config["remind_if_all_free"] = need_dingding_remind == i18n.get_text("dingding_remind_all_free")
            watcher.remind_config["remind_if_have_free"] = need_dingding_remind == i18n.get_text("dingding_remind_have_free")
            watcher.remind_config["remind_every_update"] = dingding_remind_mode == i18n.get_text("dingding_remind_every")
            watcher.update_step = update_step
            watcher.restart_run(loop=need_loop_watch)
    if confirm:
        st.success(i18n.get_text("confirm_success"))

    
        
@st.fragment(run_every=config.page_update_freq) # keep updating gpu page
def display_server_state_page():
    for name in st.session_state["watchers"].keys():
        st.divider()
        display_single_server_page(name)

def main():
    st.title(i18n.get_text("page_title"))
    st.session_state["watchers"] = get_server_watcher()
    st.session_state["dingAvailable"] = False
    
    for watcher in st.session_state["watchers"].values():
        watcher.start_run(loop=False)

    if st.button(i18n.get_text("update_all"), type="primary", icon="🔁"):
        for watcher in st.session_state["watchers"].values():
            watcher.restart_run(loop=watcher.is_looping)

    display_server_state_page()

if __name__ == '__main__':
    st.set_page_config(
        page_title=i18n.get_text("page_title"),
        layout="centered",
        initial_sidebar_state="auto",
    )
    main()