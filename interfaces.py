
from abc import ABC, abstractmethod

class IBotAnnouncer(ABC):
    """ 机器人播报接口 """
    
    @abstractmethod
    def send(self, message: str) -> None:
        """ 机器人通知用户 """
        pass