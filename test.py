import re

# 示例输出
message = """
Fri Feb 28 07:21:43 2025
+---------------------------------------------------------------------------------------+
| NVIDIA-SMI 535.54.03              Driver Version: 535.54.03    CUDA Version: 12.2     |
|-----------------------------------------+----------------------+----------------------+
| GPU  Name                 Persistence-M | Bus-Id        Disp.A | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |         Memory-Usage | GPU-Util  Compute M. |
|                                         |                      |               MIG M. |
|=========================================+======================+======================|
|   0  NVIDIA TITAN RTX               On  | 00000000:1A:00.0 Off |                  N/A |
| 41%   42C    P8              18W / 280W |      0MiB / 24576MiB |      0%      Default |
|                                         |                      |                  N/A |
+-----------------------------------------+----------------------+----------------------+
|   1  NVIDIA TITAN RTX               On  | 00000000:1B:00.0 Off |                  N/A |
| 41%   35C    P8              17W / 280W |      0MiB / 24576MiB |      0%      Default |
|                                         |                      |                  N/A |
+-----------------------------------------+----------------------+----------------------+
|   2  NVIDIA TITAN RTX               On  | 00000000:3D:00.0 Off |                  N/A |
| 41%   37C    P8              24W / 280W |      0MiB / 24576MiB |      0%      Default |
|                                         |                      |                  N/A |
+-----------------------------------------+----------------------+----------------------+
|   3  NVIDIA TITAN RTX               On  | 00000000:3E:00.0 Off |                  N/A |
| 41%   35C    P8               1W / 280W |      0MiB / 24576MiB |      0%      Default |
|                                         |                      |                  N/A |
+-----------------------------------------+----------------------+----------------------+
|   4  NVIDIA TITAN RTX               On  | 00000000:88:00.0 Off |                  N/A |
| 41%   34C    P8               2W / 280W |      0MiB / 24576MiB |      0%      Default |
|                                         |                      |                  N/A |
+-----------------------------------------+----------------------+----------------------+
|   5  NVIDIA TITAN RTX               On  | 00000000:89:00.0 Off |                  N/A |
| 41%   39C    P8              30W / 280W |      0MiB / 24576MiB |      0%      Default |
|                                         |                      |                  N/A |
+-----------------------------------------+----------------------+----------------------+
|   6  NVIDIA TITAN RTX               On  | 00000000:B1:00.0 Off |                  N/A |
| 41%   36C    P8              13W / 280W |      0MiB / 24576MiB |      0%      Default |
|                                         |                      |                  N/A |
+-----------------------------------------+----------------------+----------------------+
|   7  NVIDIA TITAN RTX               On  | 00000000:B2:00.0 Off |                  N/A |
| 41%   40C    P8              21W / 280W |      0MiB / 24576MiB |      0%      Default |
|                                         |                      |                  N/A |
+-----------------------------------------+----------------------+----------------------+

+---------------------------------------------------------------------------------------+
| Processes:                                                                            |
|  GPU   GI   CI        PID   Type   Process name                            GPU Memory |
|        ID   ID                                                             Usage      |
|=======================================================================================|
|  No running processes found                                                           |
+---------------------------------------------------------------------------------------+
"""
def check_nvidiasmi_output(message):
    return "NVIDIA-SMI" in message

def resolve_gpu_message(message):
    # Resolve the message of the nvidia-smi command
    if not check_nvidiasmi_output(message):
        return []

    lines = message.split("\n")
    gpu_info = []
    
    for line in lines:
        if re.match(r"\|\s+\d+\s+NVIDIA", line):
            print(line)
            parts = line.split("|")
            name = parts[1].strip()
            power = parts[3].strip().split()[0]
            memory = parts[4].strip().split()[0]
            utilization = parts[5].strip().split()[0]
            gpu_info.append({
                "name": name,
                "power": power,
                "memory": memory,
                "utilization": utilization
            })
    
    return gpu_info

resolve_gpu_message(message)