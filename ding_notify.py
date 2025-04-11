import json
import requests
from logger import logger
from interfaces import IBotAnnouncer

from DingDingBot.DDBOT import DingDing # type: ignore

class DingDingBot(IBotAnnouncer):
    def __init__(self, webhook: str):
        self.webhook = webhook
        self.dd = DingDing(webhook=webhook)

    def send(self, message: str) -> None:
        result = self.dd.Send_Text_Msg(Content="通知：" + message)
        if isinstance(result, str):
            result = json.loads(result)
        if result.get("errcode", 0) != 0:
            logger.error(f"Failed to send message: {result.get('errmsg', '')}")
        else:
            logger.info("Message sent successfully")

    def validate(self) -> str:
        error = None
        try:
            if not self.webhook or self.webhook == "<your dingding webhook url>":
                return "钉钉机器人webhook为空，请检查dingtalk_token.txt文件"
            result = self.send("钉钉消息发送测试成功")
            if result.get("errcode", 0) != 0:
                error = result.get("errmsg", "")
        except requests.RequestException as e:
            logger.warning(f"Error validating DingDing webhook: {e}")
            error = str(e)
        return error