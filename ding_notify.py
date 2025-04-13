import json
import requests
from DingDingBot.DDBOT import DingDing

from config import dingding_keyText
from logger import logger
from i18n_service import i18n

with open('dingtalk_token.txt', 'r') as f:
    webhook = f.read()
dd = DingDing(webhook=webhook)
def ding_print_txt(content:str):
    error = None
    try:
        if webhook == "" or webhook == "<your dingding webhook url>":
            return i18n.get_text("dingdingTest_emptyToken")
        
        result=dd.Send_Text_Msg(Content=dingding_keyText + ": " + content)
        if isinstance(result, str):
            result = json.loads(result)  # 将字符串转换为字典
            if result.get("errcode",0) !=0:
                error = result.get("errmsg","")
            elif result.get("status", True) != True:
                error = result.get("message","")
    except Exception as e:
        logger.warning(f"Error validating DingDing webhook: {e}")
        error = e
    return error
    
if __name__ == '__main__':
    print(ding_print_txt("test"))