from DingDingBot.DDBOT import DingDing

with open('dingtalk_token.txt', 'r') as f:
    webhook = f.read()
dd = DingDing(webhook=webhook)

def ding_print_txt(content:str):
    dd.Send_Text_Msg(Content="通知：" + content)

def ding_print_markdown(content:str):
    dd.Send_MardDown_Msg(Content="通知：" + content)