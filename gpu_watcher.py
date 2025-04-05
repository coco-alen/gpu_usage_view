import io
import time
import csv
import pandas as pd
import paramiko
from paramiko import SSHClient, AutoAddPolicy
import threading
from i18n import I18nService
from logger import logger
from exec_hook import ExtractException

# 加载国际化服务
i18n = I18nService()

COMMAND = "nvidia-smi --query-gpu=gpu_name,timestamp,temperature.gpu,utilization.gpu,utilization.memory,memory.total,memory.free,memory.used --format=csv"

class SingleGPUServerWatcher:
    def __init__(self, name: str, ip: str, username: str,password: str | None = None, port: int = 22, update_step: int = 10):
        self.name = name
        self.ip = ip
        self.username = username
        self.password = password
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
            csv.reader(io.StringIO(data))
            return True
        except csv.Error:
            return False

    def convert_gpu_info_to_dataframe(self, info):
        state = pd.read_csv(io.StringIO(info))
        logger.debug(f"Parsed DataFrame:\n{state}")

        # 清理列名，去除多余的空格
        state.columns = [col.strip() for col in state.columns]

        # 动态处理列名
        column_mapping = {
            'name': 'gpu_name',
            'timestamp': 'timestamp',
            'temperature.gpu': 'temperature.gpu',
            'utilization.gpu [%]': 'utilization.gpu',  # 确保列名与输出一致
            'utilization.memory [%]': 'utilization.memory',  # 确保列名与输出一致
            'memory.total [MiB]': 'memory.total',
            'memory.used [MiB]': 'memory.used',
            'memory.free [MiB]': 'memory.free'
        }

        # 检查实际列名并进行映射
        actual_columns = state.columns
        for actual_col, expected_col in column_mapping.items():
            if actual_col in actual_columns:
                state.rename(columns={actual_col: expected_col}, inplace=True)
            else:
                logger.warning(f"Column '{actual_col}' not found in the output. Skipping...")

        # 检查是否所有必需的列都已映射
        required_columns = ['gpu_name', 'timestamp', 'temperature.gpu', 'utilization.gpu', 'utilization.memory', 'memory.total', 'memory.used', 'memory.free']
        if not all(col in state.columns for col in required_columns):
            missing_columns = [col for col in required_columns if col not in state.columns]
            raise ValueError(f"Missing required columns: {missing_columns}")

        # 转换列数据类型
        state['memory.total'] = state['memory.total'].str.rstrip(' MiB').astype(int)
        state['memory.used'] = state['memory.used'].str.rstrip(' MiB').astype(int)
        state['memory'] = state.apply(lambda row: f"{row['memory.used']} MiB / {row['memory.total']} MiB", axis=1)
        state['utilization.memory'] = state.apply(lambda row: f"{row['memory.used'] / row['memory.total'] * 100:.2f} %", axis=1)
        state.drop(columns=['memory.total', 'memory.free', 'memory.used'], inplace=True)
        return state

    def get_gpu_info(self):
        self.message = i18n.get_text("loading_message")
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
                self.state = self.convert_gpu_info_to_dataframe(result)
                self.remind_through_dingding()
            else:
                self.message = i18n.get_text("invalid_output_message").format(result)
                logger.error(self.message)
                self.state = None
                self.summerized_state = None

        except paramiko.AuthenticationException:
            self.message = i18n.get_text("ssh_authentication_error")
            logger.error(self.message)
        except paramiko.SSHException as e:
            self.message = i18n.get_text("ssh_connection_error").format(e)
            logger.error(self.message)
        except Exception as e:
            err_stack = ExtractException(type(e), e, e.__traceback__, panel=False)
            logger.error(f"Error while getting GPU info for {self.name}: {err_stack}")
            self.state = i18n.get_text("display_error")
            self.summerized_state = None

    def summerize_gpu_state(self):
        # 使用映射后的列名
        gpu_util_list = self.state['utilization.gpu'].str.rstrip('%').astype(float)
        memory_util_list = self.state['utilization.memory'].str.rstrip('%').astype(float)
        max_gpu_util = gpu_util_list.max()
        max_gpu_memory = memory_util_list.max()
        min_gpu_util = gpu_util_list.min()
        min_gpu_memory = memory_util_list.min()
        return {
            "gpu_name": set(self.state["gpu_name"]),
            "avg_gpu_util": gpu_util_list.mean(),
            "avg_memory_util": memory_util_list.mean(),
            "all_free": max_gpu_util < 1e-2 and max_gpu_memory < 1e-2,
            "have_free": min_gpu_util < 1e-2 and min_gpu_memory < 1e-2,
            "dead_process": min_gpu_memory > 0 and max_gpu_util < 1e-2,
        }

    def remind_through_dingding(self):
        new_summerized_state = self.summerize_gpu_state()
        if self.summerized_state is not None:
            self.remind_state['all_from_busy_to_free'] = not self.summerized_state['all_free'] and new_summerized_state['all_free']
            self.remind_state['have_from_busy_to_free'] = not self.summerized_state['have_free'] and new_summerized_state['have_free']

        if self.remind_config["remind_if_have_free"] and (self.remind_state['have_from_busy_to_free'] or (new_summerized_state['have_free'] and self.remind_config["remind_every_update"])):
            self.send_have_empty_remind()
        elif self.remind_config["remind_if_all_free"] and (self.remind_state['all_from_busy_to_free'] or (new_summerized_state['all_free'] and self.remind_config["remind_every_update"])):
            self.send_all_empty_remind()

        self.summerized_state = new_summerized_state

    def send_all_empty_remind(self):
        logger.info(f"Send all free remind for {self.name}")
        from ding_notify import ding_print_txt
        ding_print_txt(i18n.get_text("all_free_remind").format(self.name))

    def send_have_empty_remind(self):
        logger.info(f"Send have free remind for {self.name}")
        from ding_notify import ding_print_txt
        ding_print_txt(i18n.get_text("have_free_remind").format(self.name))

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

        target_func = self.update_loop if loop else self.update_once
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