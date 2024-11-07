import os
import sys
import time
import pickle
import socket
import threading

from typing import Tuple
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from packets.TcpPacket import TcpPacket
from utils.colors import greenPrint, redPrint
from utils.time import formattedTime


class oNode:
    def __init__(self, bootstrapIp: str, bootstrapPort: int, port: int = 8080) -> None:
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.ip = self.socket.getsockname()[0]
        self.port = port
        self.neighbours = []
        self.otherNeighbourOptions = []  # Em caso de falha dos vizinhos
        self.routingTable = {} 

        self.registerWithBootstrapper(bootstrapIp, bootstrapPort)

    # Função para lidar com conexões recebidas
    def handleClient(self, nodeSocket: socket.socket, clientAddress: Tuple[str, int]) -> None:
        # TODO: Change this to handle the connection with the client
        greenPrint(f"{formattedTime()} [INFO] Connection recieved: {clientAddress}")

    # Função do servidor para escutar por conexões
    def startNode(self) -> None:
        """
        Função responsável por esperar conexões e lidar com os pedidos que o Node recebe.
        """
        # TODO: Mudar a lógica, aqui criar threads diferentes para as funcionalidades do node
        # Falar com o cliente se for PoP
        # Falar com os vizinhos para monitorizar a rede
        # Falar com os vizinhos para pedir os vídeos por UDP
        self.socket.bind((self.ip, self.port))
        self.socket.listen()
        greenPrint(f"{formattedTime()} [INFO] Node listening in {self.ip}:{self.port}")

        # TODO: Criar threads diferentes para cada serviço dos nós, atribuir portas diferentes a cada (meter as portas num .env por exemplo)
        # clientHandler = threading.Thread(target=self.handleClient, args=(addr)) # Change the handleClient to only recieve the address and do the connection itself
        # neighbourConnectionManagement = threading.Thread(target=self.neighbourConnectionManagement) # Vê a lista de vizinhos e manda/recebe pacotes de controlo da ligação
        # neighbourRequests = threading.Thread(target=self.handleNeighbourRequest) # Recebe e faz pedidos relativos aos vídeos UDP

        while True:
            client_socket, addr = (self.socket.accept())  # Aceitar a cenexão de um cliente
            client_handler = threading.Thread(target=self.handleClient, args=(client_socket, addr,))  # Criar thread para lidar com o cliente
            client_handler.start()

    def neighbourConnectionManagement(self):
        while True:
            # Send a Hello Packet to all neighbours every 5 seconds (Maybe do this in another thread only responsible to send, this one just recieves)
            # Recieve a Packet from all neighbours
            # Update the values on the routing table (Use locks)
            # If any node doesn't reply in 15 seconds, remove it from the routing table
            # Check if i only have 1 neighbour
            # If yes, send a request for his neighbour
            # Update self.otherNeighbourOptions list
            pass

    def registerWithBootstrapper(self, bsIp: str, bsPort: int) -> None:
        """
        Função que popula a lista de vizinhos recebida pelo Bootstrapper.
        """
        greenPrint(f"{formattedTime()} [INFO] Node started")
        greenPrint(f"{formattedTime()} [INFO] Connecting to Bootstrapper")
        self.socket.connect((bsIp, bsPort))
        greenPrint(f"{formattedTime()} [INFO] Connected to the Bootstrapper")
        packet = TcpPacket("NLR")  # NLR = Neighbour List Request
        packet.addData(self.ip)
        self.socket.sendall(pickle.dumps(packet))  # Enviar o IP para receber a lista de vizinhos
        greenPrint(f"{formattedTime()} [INFO] Requested Neighbour list")
        response = pickle.loads(self.socket.recv(4096))
        self.neighbours = response.getData()
        greenPrint(f"{formattedTime()} [DATA] Neighbour list: {self.neighbours}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        redPrint("[ERROR] Usage: python3 oNode.py <bootstrapIp> <bootstrapPort>")
        sys.exit(1)
    bootstrapIp = sys.argv[1]
    bootstrapPort = int(sys.argv[2])

    node = oNode(bootstrapIp, bootstrapPort)
    node.startNode()
