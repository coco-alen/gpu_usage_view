import os
import io
import time
import csv
import subprocess

import pandas as pd

command = "nvidia-smi --query-gpu=gpu_name,timestamp,temperature.gpu,utilization.gpu,utilization.memory,memory.total,memory.free,memory.used --format=csv"


class SingleGPUServerWatcher:
    def __init__(self, ip, username, port=22, update_step = 3600):
        # update_step : 每隔多少秒更新一次状态
        self.ip = ip
        self.username = username
        self.port = port
        self.update_step = update_step

        self.message = ""
        self.state = None

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

        # 删除原始的内存列
        state.drop(columns=[' memory.total [MiB]', ' memory.free [MiB]', ' memory.used [MiB]'], inplace=True)

        return state

    def get_gpu_info(self):
        try:
            result = subprocess.run(
                f"ssh {self.username}@{self.ip} -p {self.port} {command}",
                capture_output=True,
                text=True,
                timeout=30,  # 设置超时时间为30秒
                shell=True
            )
            result = result.stdout

            if self.is_valid_csv(result):
                self.message = "Success: Command executed successfully."
                self.state = self.convert_gpu_info_to_dataframe(result)
            else:
                self.message = f"Error: Invalid output received from the command: \"{result}\""
                self.state = None

        except subprocess.TimeoutExpired:
            self.message = "Error: SSH command timed out."
            self.state = None
        except subprocess.CalledProcessError as e:
            self.message = f"Error: SSH command failed with error {e.returncode}."
            self.state = None
        except Exception as e:
            self.message = f"Error: An unexpected error occurred: {str(e)}"
            self.state = None

    def summerize_gpu_state(self):

        gpu_util_list = self.state[' utilization.gpu [%]'].str.rstrip('%').astype(float)
        memory_util_list = self.state[' utilization.memory [%]'].str.rstrip('%').astype(float)

        return {
            "gpu_name": set(self.state["name"]),
            "avg_gpu_util": gpu_util_list.mean(),
            "avg_memory_util": memory_util_list.mean(),
            "max_gpu_util": gpu_util_list.max(),
            "max_gpu_temp": memory_util_list.max()
        }




if __name__ == '__main__':
    # Set the title and the logo of the page
    import json
    def get_server_info(info_file = "server_info.json"):
        with open(info_file, "r") as f:
            data = json.load(f)
        return data
    server_info = get_server_info()
    server_info = server_info[0]
    watcher = SingleGPUServerWatcher(server_info["ip"], server_info["username"], server_info.get("port", 22))
    watcher.get_gpu_info()
    watcher.summerize_gpu_state()
