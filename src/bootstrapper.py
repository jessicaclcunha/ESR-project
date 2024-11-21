import sys
import os
import json
import pickle
import socket
import threading

from typing import Tuple
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.time import formattedTime
from utils.colors import greenPrint, redPrint
from packets.TcpPacket import TcpPacket

class Bootstrapper:
    def __init__(self, ip: str, port: int = 8080, filename: str = "cenario_2.json") -> None:
        self.ip = ip
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.nodes = {}
        self.pops = []

        self.fillConnections(filename)

    def fillConnections(self, filename: str) -> None:
        """
        Função que percorre o ficheiro JSON e preenche os dados de nodes e PoPs.
        """
        try:
            with open(f"../topologias/{filename}", "r") as file:
                data = json.load(file)

            self.nodes = data.get("Nodes", {})
            self.pops = data.get("PoPs", [])

            greenPrint(f"{formattedTime()} [DATA] PoPs: {self.pops}")
            greenPrint(f"{formattedTime()} [DATA] Nodes: {self.nodes}")

        except FileNotFoundError:
            redPrint(f"[ERROR] File {filename} not found in ../topologias/")
            sys.exit(1)
        

    def handleNode(
        self, nodeSocket: socket.socket, nodeAddress: Tuple[str, int], nodeMessage: str
    ) -> None:
        """
        Função que envia a lista de vizinhos a cada Node.
        """
        
        try:
            nodeIP = nodeAddress[0] # TODO: Verificar se o IP se obtém assim, a message contém o IP
            data = {}

            if nodeMessage == "PLR":  # PLR = Pop List Request
                data = { "PoPs" : self.pops }
            elif nodeMessage == "NLR":  # NLR = Neighbours List Request
                for key,info in self.nodes.items():
                    if nodeIP in key.split('|'):
                        data = info
                        nodeIP = info['IP']
                data['isPoP'] = nodeIP in self.pops
                # Retorna um dict { "IP": ipPredefinido, "Neighbours": [IpNeighbours], "isPoP": Bool}

            response = TcpPacket("R")
            response.addData(data)

            nodeSocket.send(pickle.dumps(response))
        except Exception as e:
            redPrint(f"[ERROR] Failed to handle node {nodeAddress}: {e}")
        finally:
            nodeSocket.close()

    def startBootstrapper(self) -> None:
        """
        Função que aceita as conexões dos Nodes e cria uma thread para lidar com cada uma.
        """
        self.socket.bind((self.ip, self.port))
        self.socket.listen()
        greenPrint(f"[INFO] Bootstrapper listening in {self.ip}:{self.port}")

        try: 
            while True:
                nodeSocket, addr = self.socket.accept()
                greenPrint(f"[INFO] Node connected: {nodeSocket}")
                try: 
                    packet = pickle.loads(self.socket.recv(4096))
                    messageType = packet.getMessageType()
                    greenPrint(f"[INFO] Message received: {messageType}")
                    nodeHandler = threading.Thread(
                        target=self.handleNode, args=(
                            self, nodeSocket, addr, messageType)
                    )
                    nodeHandler.start()
                    
                except (pickle.UnpicklingError, AttributeError) as e:
                    redPrint(f"[ERROR] Failed to process message from {addr}: {e}")
                    nodeSocket.close()

        except Exception as e:
            redPrint(f"[ERROR] Could not start Bootstrapper: {e}")
            self.socket.close()


if __name__ == "__main__":
    if len(sys.argv) < 4:
        redPrint(
            "[ERROR] Usage: python3 bootstrapper.py <bootstrapIP> <bootstrapPort> <bootstrapFilename>")
        sys.exit(1)
    
    bootstrapIp = sys.argv[1]
    bootstrapPort = int(sys.argv[2])
    bootstrapFilename = sys.argv[3]

    if not os.path.isfile(f"../topologias/{bootstrapFilename}"):
        redPrint(f"[ERROR] File {bootstrapFilename} not found")
        sys.exit(1)

    bs = Bootstrapper(bootstrapIp, bootstrapPort, bootstrapFilename)
    bs.startBootstrapper()
