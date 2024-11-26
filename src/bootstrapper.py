import os
import sys
import json
import pickle
import socket
import threading

from typing import Tuple
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import utils.ports as ports
from packets.TcpPacket import TcpPacket
from utils.colors import greenPrint, greyPrint, redPrint

class Bootstrapper:
    def __init__(self, filename: str = "cenario_2.json") -> None:
        self.ip = ports.BOOTSTRAPPER_IP
        self.port = ports.BOOTSTRAPPER_PORT
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.nodes = {}
        self.popList = []

        self.fillConnections(filename)

    def fillConnections(self, filename: str) -> None:
        """
        Função que percorre o ficheiro JSON e preenche os dados de nodes e PoPs.
        """
        try:
            with open(f"../topologias/{filename}", "r") as file:
                data = json.load(file)

            self.nodes = data.get("Nodes", {})
            self.popList = data.get("PoPs", [])

            greenPrint(f"[DATA] PoPs: {self.popList}")
            greenPrint(f"[DATA] Nodes: {self.nodes}")

        except FileNotFoundError:
            redPrint(f"[ERROR] File {filename} not found in ../topologias/")
            sys.exit(1)
        

    def handleNode(self, nodeSocket: socket.socket, nodeAddress: Tuple[str, int]) -> None:
        """
        Função que envia a lista de vizinhos a cada Node.
        """
        packet = pickle.loads(nodeSocket.recv(4096))
        messageType = packet.getMessageType()
        greenPrint(f"[INFO] Message received: {messageType}")
        try:
            nodeIP = nodeAddress[0]
            data = {}

            if messageType == "PLR":  # PLR = Pop List Request
                data = { "PoPList" : self.popList }
            elif messageType == "NLR":  # NLR = Neighbours List Request
                for key,info in self.nodes.items():
                    if nodeIP in key.split('|'):
                        data = info
                        nodeIP = info['IP']
                        break
                data['isPoP'] = nodeIP in self.popList

            response = TcpPacket("R")  # Response
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
                nodeHandler = threading.Thread(target=self.handleNode, args=(nodeSocket, addr))
                nodeHandler.start()
        except KeyboardInterrupt:
            redPrint("[SHUTDOWN] Shutting down bootstrapper...")
        except Exception as e:
            redPrint(f"[ERROR] Could not start Bootstrapper: {e}")
        finally:
            self.socket.close()
            greyPrint("[SHUTDOWN] Bootstrapper socket closed.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        redPrint("[ERROR] Usage: python3 bootstrapper.py <topologyJsonFilename>")
        sys.exit(1)
    
    bootstrapFilename = sys.argv[1]

    if not os.path.isfile(f"../topologias/{bootstrapFilename}"):
        redPrint(f"[ERROR] File {bootstrapFilename} not found")
        sys.exit(1)

    bs = Bootstrapper(bootstrapFilename)
    bs.startBootstrapper()
