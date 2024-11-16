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
import utils.ports as ports


class oNode:
    def __init__(self, bootstrapIp: str, bootstrapPort: int, port: int = 8080) -> None:
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.ip = self.socket.getsockname()[0]
        self.port = port
        self.neighbours = []
        self.otherNeighbourOptions = []  # Em caso de falha dos vizinhos
        self.routingTable = {} # "IP": Time
        self.isPoP = False

        self.registerWithBootstrapper(bootstrapIp, bootstrapPort)

    def handleClient(self, nodeSocket: socket.socket, clientAddress: Tuple[str, int]) -> None:
        """
        Função responsável por lidar com os pedidos do cliente.
        """
        # TODO: Change this to handle the connection with the client
        greenPrint(f"{formattedTime()} [INFO] Connection recieved: {clientAddress}")
    
    def clientConnectionManager(self):
       """
       Função responsável por aceitar as ligações dos clientes.
       """
       lsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
       lsocket.bind((self.ip, ports.NODE_CLIENT_LISTENING_PORT))
       while True:
            client_socket, addr = (self.socket.accept())  # Aceitar a cenexão de um cliente
            client_handler = threading.Thread(target=self.handleClient, args=(client_socket, addr,))  # Criar thread para lidar com o cliente
            client_handler.start() 

    def startNode(self) -> None:
        """
        Função responsável por esperar conexões e lidar com os pedidos que o Node recebe.
        """
        # Falar com o cliente se for PoP
        # Falar com os vizinhos para monitorizar a rede (Enviar e receber)
        # Falar com os vizinhos para pedir os vídeos por UDP

        if self.isPoP:
            threading.Thread(target=self.clientConnectionManager)
        threading.Thread(target=self.neighbourConnectionManagement)
        threading.Thread(target=self.neighbourPingSender)
        threading.Thread(target=self.nodeRequestManager)
    
    def neighbourPingSender(self):
        """
        Função responsável por enviar Hello Packets aos vizinhos de 5 em 5 segundos.
        """
        greenPrint(f"{formattedTime()} [INFO] Ping Thread started on port {ports.NODE_PING_PORT}")
        ssocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ssocket.bind((self.ip,ports.NODE_PING_PORT))
        while True:
            for neighbourIP in self.neighbours:
                helloPacket =TcpPacket("HP")
                ssocket.connect((neighbourIP, ports.NODE_MONITORING_PORT))
                ssocket.send(pickle.dumps(helloPacket))
            time.sleep(5)

        
    def neighbourConnectionManagement(self):
        """
        Função responsável por receber os Hello Packets dos vizinhos.
        """
        greenPrint(f"{formattedTime()} [INFO] Neighbour monitoring thread started on port {ports.NODE_MONITORING_PORT}")
        lsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lsocket.bind((self.ip, ports.NODE_MONITORING_PORT))
        lsocket.listen()

        while True:
            neighbourSocket, addr = lsocket.accept()

            packet = pickle.loads(lsocket.recv(4096))
            messageType = packet.getMessageType()

            if messageType == "HP":
                greenPrint(f"{formattedTime()} [INFO] Hello Packet received from {addr[0]}")
                self.routingTable[addr[0]] = time.time() # Atualizar tempo do vizinho??
            # Update the values on the routing table (Use locks)
            # If any node doesn't reply in 15 seconds, remove it from the routing table
            # Check if i only have 1 neighbour
            # If yes, send a request for his neighbour
            # Update self.otherNeighbourOptions list
            
######################
            else:
                redPrint(f"{formattedTime()} [ERROR] Unknown message type from {addr[0]}")

            # Remover vizinhos inativos
            current_time = time.time()
            inactive_neighbors = [
                ip for ip, last_seen in self.routingTable.items() if current_time - last_seen > 15
            ]
            for ip in inactive_neighbors:
                redPrint(f"{formattedTime()} [WARN] Neighbor {ip} removed due to timeout")
                self.routingTable.pop(ip, None)
                self.neighbours.remove(ip)
                self.reconnectNeighbors()
######################
    
    def nodeRequestManager(self):
        """
        Função responsável por receber os pedidos de vídeo dos vizinhos.
        """
        lsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lsocket.bind((self.ip, ports.NODE_REQUEST_PORT))

        # TODO:
        # Message Type
        # -- VR (Video Request)
        # Receber um video request
        # Verificar se estamos a fazer ou não stream do vídeo
        # Se sim, encaminhar, se não, pedir ao nosso melhor vizinho o vídeo
        # -- SVR (Stop Video Request)
        # Verificar se é só para esse node que estou a enviar o vídeo
        # Se sim, enviar mensagem ao meu melhor node a dizer que não preciso do video e atualizar a tabela de videos
        # Se não, só deixar de enviar para ele

######################
        while True:
            data, addr = lsocket.recvfrom(4096)
            packet = pickle.loads(data)
            messageType = packet.getMessageType()

            if messageType == "VR":  # Video Request
                video_id = packet.getData()['video_id']
                if video_id in self.streamedVideos:
                    greenPrint(f"{formattedTime()} [INFO] Forwarding video {video_id} to {addr[0]}")
                    # Encaminha para o vizinho
                    best_neighbour = self.getBestNeighbour()
                    if best_neighbour:
                        self.forwardVideoRequest(video_id, best_neighbour)
                else:
                    greenPrint(f"{formattedTime()} [INFO] Requesting video {video_id} from best neighbour")
                    # Pede ao vizinho
                    best_neighbour = self.getBestNeighbour()
                    if best_neighbour:
                        self.requestVideoFromNeighbour(video_id, best_neighbour)

            elif messageType == "SVR":  # Stop Video Request
                video_id = packet.getData()['video_id']
                # Verifica se precisa parar o envio
                self.stopStreamingVideo(video_id, addr[0])

######################

    def registerWithBootstrapper(self, bsIp: str, bsPort: int) -> None:
        """
        Função que popula a lista de vizinhos recebida pelo Bootstrapper.
        """
        greenPrint(f"{formattedTime()} [INFO] Node started")
        greenPrint(f"{formattedTime()} [INFO] Connecting to Bootstrapper")
        self.socket.connect((bsIp, bsPort))
        greenPrint(f"{formattedTime()} [INFO] Connected to the Bootstrapper")
        packet = TcpPacket("NLR")  # NLR = Neighbour List Request
        packet.addData(self.ip) # Ver se é necessário
        self.socket.sendall(pickle.dumps(packet))  # Enviar o IP para receber a lista de vizinhos
        greenPrint(f"{formattedTime()} [INFO] Requested Neighbour list")
        response = pickle.loads(self.socket.recv(4096))
        responseDict = response.getData()
        self.ip = responseDict['IP']
        self.neighbours = responseDict['Neighbours']
        self.isPoP = responseDict['isPoP']
        greenPrint(f"{formattedTime()} [DATA] Neighbour list: {self.neighbours}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        redPrint("[ERROR] Usage: python3 oNode.py <bootstrapIp> <bootstrapPort>")
        sys.exit(1)
    
    bootstrapIp = sys.argv[1]
    bootstrapPort = int(sys.argv[2])

    node = oNode(bootstrapIp, bootstrapPort)
    node.startNode()
