import logging
from logging.handlers import RotatingFileHandler
# 配置日志记录
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
log_file = 'logic_system.log'
log_level = logging.INFO

# 设置日志处理器，最大文件大小为5MB，保留3个备份
file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=1)
file_handler.setFormatter(log_formatter)
file_handler.setLevel(log_level)

console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
console_handler.setLevel(log_level)

logger = logging.getLogger()
logger.setLevel(log_level)
logger.addHandler(file_handler)
logger.addHandler(console_handler)
