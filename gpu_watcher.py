import io
import time
import csv
import paramiko
import threading
from paramiko import SSHClient, AutoAddPolicy
import streamlit as st
import pandas as pd

import config
from i18n_service import i18n
from logger import logger
from exec_hook import ExtractException
from ding_notify import ding_print_txt
# language service
COMMAND = "nvidia-smi --query-gpu=gpu_name,timestamp,temperature.gpu,utilization.gpu,utilization.memory,memory.total,memory.free,memory.used --format=csv"
SSH_STATUS_LUT = {
    "success": 0,
    "loading": 1,
    "error": -1,
}
FREE_PERSETNAGE = 1  # 1%  free GPU memory and utilization percentage to be considered as free

class SingleGPUServerWatcher:
    def __init__(self, name: str, ip: str, username: str,password: str | None = None, port: int = 22, update_step: int = 10):
        self.name = name
        self.ip = ip
        self.username = username
        self.password = password
        self.port = port
        self.update_step = update_step

        self.message = ""
        self.gpu_state = None # gpu state dataframe
        self.ssh_state = SSH_STATUS_LUT["loading"]  # ssh connection state
        self.summerized_gpu_state = None

        self.is_looping = False # if the watcher is running in a looping watch mode
        self.remind_config = {
            "remind_if_all_free": False,
            "remind_if_have_free": False,
            "remind_every_update": False,
        }
        self.remind_state = {
            "have_from_busy_to_free": False,
            "all_from_busy_to_free": False,
        }

        self.running = threading.Event()
        self.thread = None

    def is_valid_csv(self, data):
        try:
            csv.reader(io.StringIO(data))
            return True
        except csv.Error:
            return False

    def convert_gpu_info_to_dataframe(self, info):
        state = pd.read_csv(io.StringIO(info))
        logger.debug(f"Parsed DataFrame:\n{state}")

        state.columns = [col.strip() for col in state.columns]

        column_mapping = {
            'name': 'gpu_name',
            'timestamp': 'timestamp',
            'temperature.gpu': 'temperature.gpu',
            'utilization.gpu [%]': 'utilization.gpu',
            'utilization.memory [%]': 'utilization.memory',
            'memory.total [MiB]': 'memory.total',
            'memory.used [MiB]': 'memory.used',
            'memory.free [MiB]': 'memory.free'
        }

        actual_columns = state.columns
        for actual_col, expected_col in column_mapping.items():
            if actual_col in actual_columns:
                state.rename(columns={actual_col: expected_col}, inplace=True)
            else:
                logger.warning(f"Column '{actual_col}' not found in the output. Skipping...")

        # check column existence
        required_columns = ['gpu_name', 'timestamp', 'temperature.gpu', 'utilization.gpu', 'utilization.memory', 'memory.total', 'memory.used', 'memory.free']
        if not all(col in state.columns for col in required_columns):
            missing_columns = [col for col in required_columns if col not in state.columns]
            raise ValueError(f"Missing required columns: {missing_columns}")

        # convert columns to appropriate types
        state['memory.total'] = state['memory.total'].str.rstrip(' MiB').astype(int)
        state['memory.used'] = state['memory.used'].str.rstrip(' MiB').astype(int)
        state['memory'] = state.apply(lambda row: f"{row['memory.used']} MiB / {row['memory.total']} MiB", axis=1)
        state['utilization.memory'] = state.apply(lambda row: f"{row['memory.used'] / row['memory.total'] * 100:.2f} %", axis=1)
        state.drop(columns=['memory.total', 'memory.free', 'memory.used'], inplace=True)
        return state

    def get_gpu_info(self):
        self.message = i18n.get_text("loading_message")
        self.ssh_state = SSH_STATUS_LUT["loading"]
        try:
            ssh = SSHClient()
            ssh.set_missing_host_key_policy(AutoAddPolicy())
            ssh.connect(self.ip, port=self.port, username=self.username, password=self.password)
            stdin, stdout, stderr = ssh.exec_command(COMMAND)
            result = stdout.read().decode('utf-8')
            ssh.close()

            logger.info(f"'{self.name}' -- Received output: {result}")

            if self.is_valid_csv(result):
                self.message = i18n.get_text("success_message")
                self.ssh_state = SSH_STATUS_LUT["success"]
                self.gpu_state = self.convert_gpu_info_to_dataframe(result)
                self.remind_through_dingding()
            else:
                self.message = i18n.get_text("invalid_output_message").format(result)
                self.ssh_state = SSH_STATUS_LUT["error"]
                logger.error(self.message)
                self.gpu_state = None
                self.summerized_gpu_state = None

        except paramiko.AuthenticationException:
            self.message = i18n.get_text("ssh_authentication_error")
            self.ssh_state = SSH_STATUS_LUT["error"]
            logger.error(self.message)
        except paramiko.SSHException as e:
            self.message = i18n.get_text("ssh_connection_error").format(e)
            self.ssh_state = SSH_STATUS_LUT["error"]
            logger.error(self.message)
        except Exception as e:
            err_stack = ExtractException(type(e), e, e.__traceback__, panel=False)
            self.ssh_state = SSH_STATUS_LUT["error"]
            logger.error(f"Error while getting GPU info for {self.name}: {err_stack}")
            self.gpu_state = i18n.get_text("display_error")
            self.summerized_gpu_state = None

    def summerize_gpu_state(self):
        # extract the GPU name and utilization from the dataframe, check if the GPU is free
        def convert_set_to_str(s):
            return ", ".join(sorted(s))
        gpu_util_list = self.gpu_state['utilization.gpu'].str.rstrip('%').astype(float)
        memory_util_list = self.gpu_state['utilization.memory'].str.rstrip('%').astype(float)
        max_gpu_util = gpu_util_list.max()
        max_gpu_memory = memory_util_list.max()
        min_gpu_util = gpu_util_list.min()
        min_gpu_memory = memory_util_list.min()
        return {
            "gpu_name": convert_set_to_str(set(self.gpu_state["gpu_name"])),
            "avg_gpu_util": gpu_util_list.mean(),
            "avg_memory_util": memory_util_list.mean(),
            "all_free": max_gpu_util < FREE_PERSETNAGE and max_gpu_memory < FREE_PERSETNAGE,
            "have_free": min_gpu_util < FREE_PERSETNAGE and min_gpu_memory < FREE_PERSETNAGE,
            "dead_process": min_gpu_memory > 0 and max_gpu_util < FREE_PERSETNAGE,
        }

    def remind_through_dingding(self):
        new_summerized_gpu_state = self.summerize_gpu_state()
        if self.summerized_gpu_state is not None:
            self.remind_state['all_from_busy_to_free'] = not self.summerized_gpu_state['all_free'] and new_summerized_gpu_state['all_free']
            self.remind_state['have_from_busy_to_free'] = not self.summerized_gpu_state['have_free'] and new_summerized_gpu_state['have_free']

        if self.remind_config["remind_if_have_free"] and (self.remind_state['have_from_busy_to_free'] or (new_summerized_gpu_state['have_free'] and self.remind_config["remind_every_update"])):
            self.send_have_empty_remind()
        elif self.remind_config["remind_if_all_free"] and (self.remind_state['all_from_busy_to_free'] or (new_summerized_gpu_state['all_free'] and self.remind_config["remind_every_update"])):
            self.send_all_empty_remind()

        self.summerized_gpu_state = new_summerized_gpu_state

    def send_all_empty_remind(self):
        logger.info(f"Send all free remind for {self.name}")
        error = ding_print_txt(i18n.get_text("all_free_remind").format(self.name))
        if error is not None:
            st.session_state["dingAvailable"] = False
        else:
            st.session_state["dingAvailable"] = True

    def send_have_empty_remind(self):
        logger.info(f"Send have free remind for {self.name}")
        error = ding_print_txt(i18n.get_text("have_free_remind").format(self.name))
        if error is not None:
            st.session_state["dingAvailable"] = False
        else:
            st.session_state["dingAvailable"] = True
    def set_update_step(self, update_step):
        logger.info(f"Set update step for {self.name} to {update_step}")
        self.update_step = update_step
        if self.thread is not None:
            self.restart_run(loop=True)
        else:
            self.start_run(loop=True)

    def update_loop(self):
        while self.running.is_set():
            self.get_gpu_info()
            logger.info(f"Updated GPU info for {self.name}")
            time.sleep(self.update_step)

    def update_once(self):
        if self.running.is_set():
            self.get_gpu_info()
            logger.info(f"Updated GPU info for {self.name}")
            self.running.clear()
            self.thread = None

    def start_run(self, loop=False):
        if self.thread is not None:
            logger.info(f"{self.name} is already running, stopping the old thread")
            self.stop_run()

        if loop:
            target_func = self.update_loop
            self.is_looping = True
        else:
            target_func = self.update_once

        self.running.set()
        self.thread = threading.Thread(target=target_func)
        self.thread.daemon = True
        self.thread.start()
        logger.info(f"Started watching {self.name}")

    def stop_run(self):
        if self.thread is not None:
            self.running.clear()
            self.thread.join()
            self.thread = None
            logger.info(f"Stopped watching {self.name}")
        else:
            logger.info(f"{self.name} is not running")
        self.is_looping = False

    def restart_run(self, loop=False):
        self.stop_run()
        self.start_run(loop=loop)