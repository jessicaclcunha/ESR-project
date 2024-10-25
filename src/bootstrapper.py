# Bootstrap lê o ficheiro uma vez quando é iniciado
# Recebe o pedido dos clientes, vê qual é o cliente, e quais são os seus vizinhos
# Devolve essa lista de vizinhos

import sys
import socket
import threading
from typing import Tuple


class Bootstrapper:
    def __init__(self, ip:str, port:int=8080, filename:str='t1.imn') -> None:
        self.ip = ip
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connections = {}

        self.fillConections(filename)

    def fillConections(self, filename: str) -> None:
        """
        Função que percorre o ficheiro .imn e que preenche o dict self.connections, com os vizinhos de cada Node.
        """
        # Ler o ficheiro da topologia f"../topologias/{filename}"
        # Popular o self.connectios
        # parsing do ficheiro imn para cada nodo
        # fazer o parser e colocar na pasta utils/
        # neighbours dentro do network-config, retirar para uma lista 
        # neighbours = []
        # neighbours.append(newNeighbour)
        # Ex: self.connections[hostname] = neighbours
        pass

    # Função para lidar com nós que se conectam ao controlador
    def handleNode(self, nodeSocket:socket.socket, nodeAddress:Tuple[str,int]) -> None:
        """
        Função que envia a lista de vizinhos a cada Node.
        """
        print(f"[INFO] Node conectado: {nodeAddress}")
        
        # Envia a lista de vizinhos
        #neighbors = self.connections[node_address[0]] # TODO: Verificar se é a forma correta
        #response = neighbors.enco()
        #node_socket.send(response)
        #node_socket.close()
        pass

    def startBootstrapper(self) -> None:
        """
        Função que aceita as conexões dos Nodes e cria uma thread para lidar com cada uma.
        """
        self.socket.bind((self.ip, self.port))
        self.socket.listen()
        print(f"[INFO] Bootstrapper escutando em {self.ip}:{self.port}")

        while True:
            nodeSocket, addr = self.socket.accept()
            print(f"Node {addr} connected!")
            nodeHandler = threading.Thread(target=self.handleNode, args=(self, nodeSocket, addr))
            nodeHandler.start()

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python3 bootstrapper.py <bootstrapIp> <bootstrapPort> <bootstrapFilename>")
        sys.exit(1)
    bootstrapIp = sys.argv[1]
    bootstrapPort = int(sys.argv[2])
    bootstrapFilename = sys.argv[3]
    # TODO: Verificar se o ficheiro existe
    bs = Bootstrapper(bootstrapIp, bootstrapPort, bootstrapFilename)
    bs.startBootstrapper()
