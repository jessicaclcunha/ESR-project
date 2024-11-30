# MESSAGE TYPES
# "R" (Response)
# "FLOOD"
# "ACK" (Acknowledgement)
# "VR"(Video Request)
# "SVR" (Stop Video Request)
# "LR"(Latency Request)
# "PLR" (Pop List Request)
# "NLR" (Neighbours List Request)
# "HP" (Hello Packet)
# "BNR" (Best Neighbour Request)

import time


class TcpPacket:
    def __init__(self, messageType: str, data: dict = {}) -> None:
        self.messageType = messageType
        self.data = data
        self.timestamp = time.time()

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

    def getData(self) -> dict:
        """
        Returns the data of the packet.
        """
        return self.data

    def addData(self, data:dict) -> None:
        """
        Adds data to the packet. No specific type is assigned.
        """
        self.data = data
