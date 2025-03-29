import json
import requests
from DingDingBot.DDBOT import DingDing

from logger import logger

with open('dingtalk_token.txt', 'r') as f:
    webhook = f.read()
dd = DingDing(webhook=webhook)
def ding_print_txt(content:str):
    return dd.Send_Text_Msg(Content="通知：" + content)

def ding_print_markdown(content:str):
    return dd.Send_MardDown_Msg(Content="通知：" + content)

def validate_ding_print():
    error = None
    try:
        if webhook == "" or webhook == "<your dingding webhook url>":
            return "钉钉机器人webhook为空，请检查dingtalk_token.txt文件"
        
        result=ding_print_txt("钉钉消息发送测试成功")
        if isinstance(result, str):
            result = json.loads(result)  # 将字符串转换为字典
        if result.get("errcode",0) !=0:
            error = result.get("errmsg","")
        elif result.get("status", True) != True:
            error = result.get("message","")
    except requests.RequestException as e:
        logger.warning(f"Error validating DingDing webhook: {e}")
        error = e
    return error
    
if __name__ == '__main__':
    print(validate_ding_print())