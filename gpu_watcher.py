import os
import io
import time
import csv
import subprocess
import threading

import pandas as pd

from logger import logger

import config
from ding_notify import ding_print_txt
if config.language == 'cn':
    import text.cn as text
elif config.language == 'en':
    import text.en as text
else:
    raise ValueError('Language setting in config.py not supported')
COMMAND = "nvidia-smi --query-gpu=gpu_name,timestamp,temperature.gpu,utilization.gpu,utilization.memory,memory.total,memory.free,memory.used --format=csv"


class SingleGPUServerWatcher:
    def __init__(self, name, ip, username, port=22, update_step = 3600):
        # update_step : 每隔多少秒更新一次状态
        self.name = name
        self.ip = ip
        self.username = username
        self.port = port
        self.update_step = update_step

        self.message = ""
        self.state = None
        self.summerized_state = None

        self.is_looping = False

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
            # 尝试解析字符串
            csv.reader(io.StringIO(data))
            return True
        except csv.Error:
            return False

    def convert_gpu_info_to_dataframe(self, info):
        state = pd.read_csv(io.StringIO(info))
        # 将内存信息统一存储为一列，以 used/total 的方式存储
        state[' memory.total [MiB]'] = state[' memory.total [MiB]'].str.rstrip(' MiB').astype(int)
        state[' memory.used [MiB]'] = state[' memory.used [MiB]'].str.rstrip(' MiB').astype(int)
        state[' memory'] = state.apply(lambda row: f"{row[' memory.used [MiB]']} MiB / {row[' memory.total [MiB]']} MiB", axis=1)

        state[' utilization.memory [%]'] = state.apply(lambda row: "{} %".format(row[' memory.used [MiB]'] / row[' memory.total [MiB]'] * 100), axis=1)

        # 删除原始的内存列
        state.drop(columns=[' memory.total [MiB]', ' memory.free [MiB]', ' memory.used [MiB]'], inplace=True)

        return state

    def get_gpu_info(self):
        self.message = "Loading: Executing SSH command to get GPU information..."
        self.state = None
        try:
            result = subprocess.run(
                f"ssh {self.username}@{self.ip} -p {self.port} {COMMAND}",
                capture_output=True,
                text=True,
                timeout=30,  # 设置超时时间为30秒
                shell=True
            )
            result = result.stdout
            logger.info(f"'{self.name}' --  Received output: {result}")

            if self.is_valid_csv(result):
                self.message = "Success: Command executed successfully."
                self.state = self.convert_gpu_info_to_dataframe(result)
                self.remind_through_dingding()

            else:
                self.message = f"Error: Invalid output received from the command: \"{result}\""
                logger.error(f"'{self.name}' -- Invalid output received from the command: \"{result}\"")
                self.state = None
                self.summerized_state = None

        except subprocess.TimeoutExpired:
            self.message = "Error: SSH command timed out."
            logger.error(f"'{self.name}' --  SSH command timed out.")
            self.state = None
            self.summerized_state = None
        except subprocess.CalledProcessError as e:
            self.message = f"Error: SSH command failed with error {e.returncode}."
            logger.error(f"'{self.name}' --  SSH command failed with error {e.returncode}.")
            self.state = None
            self.summerized_state = None
        except Exception as e:
            self.message = f"Error: An unexpected error occurred: {str(e)}"
            logger.error(f"'{self.name}' --  An unexpected error occurred: {str(e)}")
            self.state = None
            self.summerized_state = None

    def summerize_gpu_state(self):

        gpu_util_list = self.state[' utilization.gpu [%]'].str.rstrip('%').astype(float)
        memory_util_list = self.state[' utilization.memory [%]'].str.rstrip('%').astype(float)

        max_gpu_util = gpu_util_list.max()
        max_gpu_memory = memory_util_list.max()
        min_gpu_util = gpu_util_list.min()
        min_gpu_memory = memory_util_list.min()

        return {
            "gpu_name": set(self.state["name"]),
            "avg_gpu_util": gpu_util_list.mean(),
            "avg_memory_util": memory_util_list.mean(),
            "all_free": max_gpu_util<1e-2 and max_gpu_memory<1e-2,
            "have_free": min_gpu_util<1e-2 and min_gpu_memory<1e-2,
            "dead_process": min_gpu_memory > 0 and max_gpu_util<1e-2,
        }
    def remind_through_dingding(self):
        new_summerized_state = self.summerize_gpu_state()
        if self.summerized_state is not None:
            if not self.summerized_state['all_free'] and new_summerized_state['all_free']:
                self.remind_state['all_from_busy_to_free'] = True
            else:
                self.remind_state['all_from_busy_to_free'] = False

            if not self.summerized_state['have_free'] and new_summerized_state['have_free']:
                self.remind_state['have_from_busy_to_free'] = True
            else:
                self.remind_state['have_from_busy_to_free'] = False


        if self.remind_config["remind_if_have_free"]:
            if self.remind_state['have_from_busy_to_free'] or (new_summerized_state['have_free'] and self.remind_config["remind_every_update"]):
                self.send_have_empty_remind()
                
        elif self.remind_config["remind_if_all_free"]:
            if self.remind_state['all_from_busy_to_free'] or (new_summerized_state['all_free'] and self.remind_config["remind_every_update"]):
                self.send_all_empty_remind()
                
        self.summerized_state = new_summerized_state

    def set_update_step(self, update_step):
        logger.info(f"Set update step for {self.name} to {update_step}")
        self.update_step = update_step
        if self.thread is not None:
            self.restart_run(loop=True)
        else:
            self.start_run(loop=True)

    def update_loop(self): # 循环更新所有蓝图中的计算结果
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
            logger.info(f"{self.name} is already running, Kill the old thread")
            self.stop_run()

        if loop:
            target_func = self.update_loop
            self.is_looping = True
        else:
            target_func = self.update_once

        self.running.set()
        self.thread = threading.Thread(target=target_func)
        self.thread.daemon = True  # 设置为守护线程
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

    def send_all_empty_remind(self):
        logger.info(f"Send all free remind for {self.name}")
        ding_print_txt(text.all_free_remind.format(self.name))

    def send_have_empty_remind(self):
        logger.info(f"Send have free remind for {self.name}")
        ding_print_txt(text.have_free_remind.format(self.name))



# class MultiGPUServerWatcher:

#     def __init__(self, server_info):
#         self.watchers = {}
#         for server in server_info:
#             watcher = SingleGPUServerWatcher(server["name"], server["ip"], server["username"], server.get("port", 22), server.get("update_step", 3600))
#             self.watchers[server["name"]] = watcher
    
#     def start_all(self):
#         for watcher in self.watchers.values():
#             watcher.start_run()
#             logger.info(f"Started watching {watcher.name}")

#     def stop_all(self):
#         for watcher in self.watchers.values():
#             watcher.stop_run()
#             logger.info(f"Stopped watching {watcher.name}")
    
#     def set_update_step(self, name, update_step):
#         self.watchers[name].set_update_step(update_step)
#         logger.info(f"Set update step for {name} to {update_step}")
    
#     def get_gpu_info(self, name):
#         self.watchers[name].get_gpu_info()
#         logger.info(f"Get GPU info for {name}")

if __name__ == '__main__':
    # Set the title and the logo of the page
    import json
    def get_server_info(info_file = "server_info.json"):
        with open(info_file, "r") as f:
            data = json.load(f)
        return data
    server_info = get_server_info()
    server_info = server_info[0]
    watcher = SingleGPUServerWatcher(server_info["name"], server_info["ip"], server_info["username"], server_info.get("port", 22))
    watcher.get_gpu_info()