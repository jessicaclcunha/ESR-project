import sys
import pickle
import socket
import threading

from typing import Tuple
from packets.TcpPacket import TcpPacket


class oNode:
    def __init__(self, bootstrapIp: str, bootstrapPort: int, port: int = 8080) -> None:
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.ip = self.socket.getsockname()[0]
        self.port = port
        self.neighbours = []

        self.registerWithBootstrapper(bootstrapIp, bootstrapPort)

    # Função para lidar com conexões recebidas
    def handleClient(self, nodeSocket: socket.socket, clientAddress: Tuple[str, int]) -> None:
        # TODO: Change this to handle the connection with the client
        print(f"[INFO] Connection recieved: {clientAddress}")

    # Função do servidor para escutar por conexões
    def startNode(self) -> None:
        """
        Função responsável por esperar conexões e lidar com os pedidos que o Node recebe.
        """
        self.socket.bind((self.ip, self.port))
        self.socket.listen()
        print(f"[INFO] Node listening in {self.ip}:{self.port}")

        while True:
            client_socket, addr = (self.socket.accept())  # Aceitar a cenexão de um cliente
            client_handler = threading.Thread(target=self.handleClient, args=(client_socket, addr,))  # Criar thread para lidar com o cliente
            client_handler.start()

    def registerWithBootstrapper(self, bsIp: str, bsPort: int) -> None:
        """
        Função que popula a lista de vizinhos recebida pelo Bootstrapper.
        """
        self.socket.connect((bsIp, bsPort))
        packet = TcpPacket("NLR")  # NLR = Neighbour List Request
        packet.addData(self.ip)
        self.socket.send(pickle.dumps(packet))  # Enviar o IP para receber a lista de vizinhos
        response = pickle.loads(self.socket.recv(4096))
        print(f"[INFO] Lista de vizinhos recebida: {response.getData()}")
        self.neighbours = response.getData()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 oNode.py <bootstrapIp> <bootstrapPort>")
        sys.exit(1)
    bootstrapIp = sys.argv[1]
    bootstrapPort = int(sys.argv[2])

    node = oNode(bootstrapIp, bootstrapPort)
    node.startNode()
