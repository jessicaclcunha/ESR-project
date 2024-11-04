# MESSAGE TYPES
# "R" (Response)
# "VR"(Video Request)
# "LR"(Latency Request)
# "PLR" (Pop List Request)
# "NLR" (Neighbours List Request)
#

import time


class TcpPacket:
    def __init__(self, messageType: str, timestamp: float = time.time()) -> None:
        self.messageType = messageType
        self.timestamp = timestamp
        self.data = None

    def getMessageType(self) -> str:
        """
        Returns the message type of the packet.
        """
        return self.messageType

    def getTimestamp(self) -> float:
        """
        Returns the timestamp of the criation of the packet.
        """
        return self.timestamp

    def getData(self):
        """
        Returns the data of the packet.
        """
        return self.data

    def addData(self, data) -> None:
        """
        Adds data to the packet. No specific type is assigned.
        """
        self.data = data
