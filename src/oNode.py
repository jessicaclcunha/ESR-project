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
from utils.time import formattedTime, nodePastTimeout
import utils.ports as ports


class oNode:
    def __init__(self, bootstrapIp: str, bootstrapPort: int, port: int = 8080) -> None:
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.ip = self.socket.getsockname()[0]
        self.port = port
        self.neighbours = []
        self.neighboursLock = threading.Lock()
        self.otherNeighbourOption = None # Em caso de falha dos vizinhos
        self.otherNeighbourLock = threading.Lock()
        self.requestedOtherNeighbour = False
        self.requestedOtherNeighbourLock = threading.Lock()
        self.routingTable = {} # "IP": Time
        self.routingTableLock = threading.Lock()
        self.isPoP = False
        self.streamedVideos = {} # "IP" : {"Streaming": True/False, "Neighbours": []}
        self.streamedVideosLock = threading.Lock()
        self.bestNeighbour = None
        self.bestNeighbourLock = threading.Lock()

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
       lsocket.listen()
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
            threading.Thread(target=self.clientConnectionManager).start()
        threading.Thread(target=self.neighbourConnectionManagement).start()
        threading.Thread(target=self.neighbourPingSender).start()
        threading.Thread(target=self.nodeRequestManager).start()
        threading.Thread(target=self.routingTableMonitoring).start()
    
    def neighbourPingSender(self):
        """
        Função responsável por enviar Hello Packets aos vizinhos de 3 em 3 segundos.
        """
        greenPrint(f"{formattedTime()} [INFO] Ping Thread started on port {ports.NODE_PING_PORT}")
        while True:
            with self.neighboursLock:
                neighbours = self.neighbours
            for neighbourIP in neighbours:
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as ssocket:
                        ssocket.connect((neighbourIP, ports.NODE_MONITORING_PORT))
                        helloPacket = TcpPacket("HP")
                        ssocket.send(pickle.dumps(helloPacket))
                except Exception as e:
                    redPrint(f"[ERROR] Failed to send Hello Packet to {neighbourIP}: {e}")
            time.sleep(3)

        
    def neighbourConnectionManagement(self):
        """
        Função responsável por receber os Hello Packets dos vizinhos.
        """
        greenPrint(f"{formattedTime()} [INFO] Neighbour monitoring thread started on port {ports.NODE_MONITORING_PORT}")
        lsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lsocket.bind((self.ip, ports.NODE_MONITORING_PORT))
        lsocket.listen()


        while True:
            try:
                _ , addr = lsocket.accept()

                packet = pickle.loads(lsocket.recv(4096))
                messageType = packet.getMessageType()

                if messageType == "HP":
                    greenPrint(f"{formattedTime()} [INFO] Hello Packet received from {addr[0]}")
                    with self.routingTableLock:  # TODO: Verificar se o vizinho está na routing table e na lista de vizinhos
                        self.routingTable[addr[0]] = time.time() # Atualizar tempo do vizinho??

            except Exception as e:
                redPrint(f"[ERROR] Error in neighbour monitoring: {e}")

    def routingTableMonitoring(self):
        while True:
            time.sleep(3)
            startThread = False
            onlyOneNeighbour = False

            with self.routingTableLock:
                neighboursToRemove = []
                for ip, last_seen in self.routingTable.items():
                    if nodePastTimeout(last_seen):
                        neighboursToRemove.append(ip)

                for ip in neighboursToRemove:
                    redPrint(f"[WARN] Neighbor {ip} removed due to timeout")
                    self.routingTable.pop(ip, None)
                    with self.neighboursLock:
                        if ip in self.neighbours:
                            self.neighbours.remove(ip)
                        if len(self.neighbours) == 1:
                            onlyOneNeighbour = True

            with self.requestedOtherNeighbourLock:
                if onlyOneNeighbour and not self.requestedOtherNeighbour:
                    self.requestedOtherNeighbour = True
                    startThread = True

            if startThread:
                threading.Thread(target=self.requestAdditionalNeighbours).start()
                
                
    def requestAdditionalNeighbours(self):
        """
        Solicita o melhor vizinho do nosso único vizinho disponível.
        """
        with self.neighboursLock:
            neighbourIP = self.neighbours[0]
        ssocket = None
        try:
            ssocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            ssocket.connect((neighbourIP, ports.NODE_REQUEST_PORT))

            # TODO: While true cycle to keep requesting and updating the best neighbour until it is no longer lonely or etc
            requestPacket = TcpPacket("BNR") # Best Neighbour Request
            ssocket.send(pickle.dumps(requestPacket))

            response = pickle.loads(ssocket.recv(4096))
            newNeighbour = response.getData().get("Neighbour", "")

            with self.otherNeighbourLock:
                self.otherNeighbourOption = newNeighbour
            greenPrint(f"{formattedTime()} [INFO] Updated otherNeighbourOption: {newNeighbour}")

        except Exception as e:
            redPrint(f"[ERROR] Failed to request additional neighbours from {neighbourIP}: {e}")
        finally:
            if ssocket:
                ssocket.close()
    
    def requestVideoFromNeighbour(self, video_id, neighbourIP):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as ssocket:
                ssocket.connect((neighbourIP, ports.NODE_REQUEST_PORT))
                videoRequestPacket = TcpPacket("VR")
                videoRequestPacket.addData({"video_id": video_id})
                ssocket.send(pickle.dumps(videoRequestPacket))
                greenPrint(f"{formattedTime()} [INFO] Requested video {video_id} from {neighbourIP}")
        except Exception as e:
            redPrint(f"[ERROR] Failed to request video {video_id} from {neighbourIP}: {e}")
            
    
    def stopStreamingVideo(self, video_id, neighbourIP):
        try:
            with self.streamedVideosLock:
                if video_id in self.streamedVideos.keys():
                    self.streamedVideos[video_id]["Neighbours"].remove(neighbourIP)
                    greenPrint(f"{formattedTime()} [INFO] Stopped streaming video {video_id} to {neighbourIP}")
                    if len(self.streamedVideos[video_id]["Neighbours"]) == 1:
                        self.streamedVideos[video_id]["Streaming"] = False
                        # TODO: Ask my neighbour to stop sending the video
                        greenPrint(f"{formattedTime()} [INFO] Stopped streaming video {video_id}")
        except Exception as e:
            redPrint(f"[ERROR] Failed to stop streaming video {video_id}: {e}")

######################
    
    # FIX: Verificar como é que funciona
    # Se for só enviar o pedido, pode ser no mesmo
    # Se for preciso receber algo, dividir em nodeRequestManager & nodeRequestHandler
    # Mudar nome maybe para nodeVideoRequestManager
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
                with self.streamedVideosLock:
                    streamedVideosList = self.streamedVideos.keys()
                if video_id in streamedVideosList:
                    greenPrint(f"{formattedTime()} [INFO] Forwarding video {video_id} to {addr[0]}")
                    # TODO: Pedir o bestNeighbour dentro da função provavelmente
                    with self.bestNeighbourLock:
                        best_neighbour = self.bestNeighbour
                    if best_neighbour:
                        self.requestVideoFromNeighbour(video_id, best_neighbour)
                else:
                    greenPrint(f"{formattedTime()} [INFO] Requesting video {video_id} from best neighbour")
                    # TODO: Pedir o bestNeighbour dentro da função provavelmente
                    with self.streamedVideosLock:
                        self.streamedVideos[video_id] = {"Streaming": True, "Neighbours": [video_id]} # TODO: Verificar se é aqui que meto True ou mais tarde
                    with self.bestNeighbourLock:
                        best_neighbour = self.bestNeighbour
                    if best_neighbour:
                        self.requestVideoFromNeighbour(video_id, best_neighbour)

            elif messageType == "SVR":  # Stop Video Request
                video_id = packet.getData()['video_id']
                self.stopStreamingVideo(video_id, addr[0])

######################

    def registerWithBootstrapper(self, bsIp: str, bsPort: int) -> None:
        """
        Função que popula a lista de vizinhos recebida pelo Bootstrapper, a flag isPoP e o IP onde devemos operar.
        """
        try:
            greenPrint(f"{formattedTime()} [INFO] Node started")
            greenPrint(f"{formattedTime()} [INFO] Connecting to Bootstrapper")
            self.socket.connect((bsIp, bsPort))
            greenPrint(f"{formattedTime()} [INFO] Connected to the Bootstrapper")

            packet = TcpPacket("NLR") # NLR = Neighbour List Request
            packet.addData(self.ip) # Ver se é necessário
            self.socket.sendall(pickle.dumps(packet))   # Enviar o IP para receber a lista de vizinhos

            greenPrint(f"{formattedTime()} [INFO] Requested Neighbour list")
            response = pickle.loads(self.socket.recv(4096))

            responseDict = response.getData()
            self.ip = responseDict['IP']
            greenPrint(f"{formattedTime()} [DATA] My IP: {self.ip}")
            with self.neighboursLock:
                self.neighbours = responseDict['Neighbours']
                greenPrint(f"{formattedTime()} [DATA] Neighbour list: {self.neighbours}")
            self.isPoP = responseDict['isPoP']
            greenPrint(f"{formattedTime()} [DATA] PoP: {self.isPoP}")
        except Exception as e:
            redPrint(f"[ERROR] Failed to register with Bootstrapper: {e}")
            sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        redPrint("[ERROR] Usage: python3 oNode.py <bootstrapIp> <bootstrapPort>")
        sys.exit(1)
    
    bootstrapIp = sys.argv[1]
    bootstrapPort = int(sys.argv[2])

    node = oNode(bootstrapIp, bootstrapPort)
    node.startNode()
