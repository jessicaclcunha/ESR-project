import os
import sys
import json
import pickle
import socket
import threading

from typing import Tuple
from packets.TcpPacket import TcpPacket


class Bootstrapper:
    def __init__(self, ip: str, port: int = 8080, filename: str = "t1.json") -> None:
        self.ip = ip
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connections = {}
        self.pops = []

        self.fillConections(filename)

    def fillConections(self, filename: str) -> None:
        """
        Função que percorre o ficheiro json e que preenche o dict self.connections, com os vizinhos de cada Node.
        """
        with open(f"../topologias/{filename}", "r") as file:
            data = json.load(file)

        self.connections = data["Neighbours"]
        self.pops = data["PoPs"]

        print("[DATA] PoPs: ", self.pops)
        print("[DATA] Neighbours: ", self.connections)

    def handleNode(
        self, nodeSocket: socket.socket, nodeAddress: Tuple[str, int], nodeMessage: bool
    ) -> None:
        """
        Função que envia a lista de vizinhos a cada Node.
        """
        if nodeMessage == "PLR":  # PLR = Pop List Request
            data = self.pops
        elif nodeMessage == "NLR":  # NLR = Neighbours List Request
            # TODO: Verificar se o IP se obtém assim, a message contém o IP
            data = self.connections[nodeAddress[0]]
        else:
            data = None

        response = TcpPacket("R")
        response.addData(data)

        nodeSocket.send(pickle.dumps(response))
        nodeSocket.close()

    def startBootstrapper(self) -> None:
        """
        Função que aceita as conexões dos Nodes e cria uma thread para lidar com cada uma.
        """
        self.socket.bind((self.ip, self.port))
        self.socket.listen()
        print(f"[INFO] Bootstrapper listening in {self.ip}:{self.port}")

        while True:
            nodeSocket, addr = self.socket.accept()
            print(f"[INFO] Node connected: {nodeSocket}")
            packet = pickle.loads(self.socket.recv(4096))
            messageType = packet.getMessageType()
            print(f"[INFO] Message received: {messageType}")
            nodeHandler = threading.Thread(
                target=self.handleNode, args=(self, nodeSocket, addr, messageType)
            )
            nodeHandler.start()


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(
            "Usage: python3 bootstrapper.py <bootstrapIp> <bootstrapPort> <bootstrapFilename>"
        )
        sys.exit(1)
    bootstrapIp = sys.argv[1]
    bootstrapPort = int(sys.argv[2])
    bootstrapFilename = sys.argv[3]

    if not os.path.isfile(f"../topologias/{bootstrapFilename}"):
        print(f"File {bootstrapFilename} not found")
        sys.exit(1)

    bs = Bootstrapper(bootstrapIp, bootstrapPort, bootstrapFilename)
    bs.startBootstrapper()
