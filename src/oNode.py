import os
import sys
import time
import pickle
import socket
import threading

from typing import Tuple
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import utils.time as ut
import utils.ports as ports
from packets.TcpPacket import TcpPacket
from utils.colors import greenPrint, redPrint, greyPrint


class oNode:
    def __init__(self) -> None:
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.ip = self.socket.getsockname()[0]
        self.neighbours = [] # Vizinhos ativos
        self.neighboursLock = threading.Lock()
        self.topologyNeighbours = [] # Lista de vizinhos da topologia
        self.topologyNeighboursLock = threading.Lock()
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

    def clientConnectionManager(self):
       """
       Função responsável por aceitar as ligações dos clientes.
       """
       lsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
       lsocket.bind((self.ip, ports.NODE_CLIENT_LISTENING_PORT))
       greenPrint(f"Listening for client connections in {self.ip}:{ports.NODE_CLIENT_LISTENING_PORT}")
       lsocket.listen()
       while True:
            client_socket, addr = lsocket.accept()  # Aceitar a cenexão de um cliente
            greenPrint(f"[INFO] Client connection recieved: {addr[0]}")
            client_handler = threading.Thread(target=self.clientRequestHandler, args=(client_socket,))  # Criar thread para lidar com o cliente
            client_handler.start() 

    def startNode(self) -> None:
        """
        Função responsável por esperar conexões e lidar com os pedidos que o Node recebe.
        """
        if self.isPoP:
            threading.Thread(target=self.clientConnectionManager).start()
        threading.Thread(target=self.neighbourConnectionManagement).start()
        threading.Thread(target=self.neighbourPingSender).start()
        threading.Thread(target=self.nodeVideoRequestManager).start()
        threading.Thread(target=self.nodeGeneralRequestManager).start()
        threading.Thread(target=self.routingTableMonitoring).start()

    def clientRequestHandler(self, client_socket:socket.socket) -> None:
        """
        Função responsável por lidar com os pedidos de um client.
        """
        packet = pickle.loads(client_socket.recv(4096))
        messageType = packet.getMessageType()
        if messageType == "LR":  # Latency Request
            message = TcpPacket("R", time.time())
            # message.addData({"Latency": }) # TODO: Retornar o tempo de latência até ao servidor
            client_socket.sendall(pickle.dumps(message))
            client_socket.close()
    
    def neighbourPingSender(self) -> None:
        """
        Função responsável por enviar Hello Packets aos vizinhos de 3 em 3 segundos.
        """
        greenPrint(f"[INFO] Ping Thread started on port {ports.NODE_PING_PORT}")
        while True:
            with self.topologyNeighboursLock:
                topologyNeighbours = self.topologyNeighbours
            with self.neighboursLock:
                activeNeighbours = self.neighbours

            neighbours = list(set(topologyNeighbours) | set(activeNeighbours))  # Lista de vizinhos sem repetidos
            ssocket = None
            for neighbourIP in neighbours:
                try:
                    ssocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    ssocket.settimeout(2)
                    ssocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,1)
                    ssocket.bind((self.ip, ports.NODE_PING_PORT))
                    ssocket.connect((neighbourIP, ports.NODE_MONITORING_PORT))
                    helloPacket = TcpPacket("HP")
                    ssocket.send(pickle.dumps(helloPacket))
                except ConnectionRefusedError:
                    greyPrint(f"[WARN] Neighbour {neighbourIP} is not up.")
                except socket.timeout:
                    redPrint(f"[ERROR] Connection to neighbour {neighbourIP} timed out.")
                except Exception as e:
                    redPrint(f"[ERROR] Failed to send Hello Packet to {neighbourIP}: {e}")
                finally:
                    if ssocket:
                        ssocket.close()
            time.sleep(ut.NODE_PING_INTERVAL)

    def neighbourConnectionManagement(self) -> None:
        """
        Função responsável por receber os Hello Packets dos vizinhos.
        """
        greenPrint(f"[INFO] Neighbour monitoring thread started on port {ports.NODE_MONITORING_PORT}")
        lsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lsocket.bind((self.ip, ports.NODE_MONITORING_PORT))
        lsocket.listen()

        while True:
            try:
                nodeSocket , addr = lsocket.accept()
                neighbourHandler = threading.Thread(target=self.neighbourConnectionHandler, args=(nodeSocket, addr,))
                neighbourHandler.start()
            except Exception as e:
                redPrint(f"[ERROR] Error in neighbour monitoring: {e}")

    def neighbourConnectionHandler(self, nodeSocket: socket.socket, addr: Tuple[str, int]) -> None:
        """
        Função responsável por lidar com os Hello Packets dos vizinhos.
        """
        packet = pickle.loads(nodeSocket.recv(4096))
        messageType = packet.getMessageType()

        if messageType == "HP":
            neighbour = addr[0]
            greenPrint(f"[INFO] Hello Packet received from  neighbour {neighbour}")
            with self.neighboursLock:
                if neighbour not in self.neighbours:
                    self.neighbours.append(neighbour)
                    greenPrint(f"[DATA] Neighbour {neighbour} just appeared and was added to the active neighbour list.")
            with self.routingTableLock:
                self.routingTable[neighbour] = time.time()

    def routingTableMonitoring(self) -> None:
        """
        Função responsável por monitorizar a tabela de routing e remover vizinhos inativos.
        """
        while True:
            startThread = False
            onlyOneNeighbour = False
            neighboursToRemove = []

            with self.routingTableLock:
                for ip, last_seen in self.routingTable.items():
                    timeDiff = ut.nodePastTimeout(last_seen)
                    if timeDiff == "WARN":
                        greyPrint(f"[WARN] Neighbor {ip} is not responding. Trying again")
                    elif timeDiff == "NOTACTIVE":
                        neighboursToRemove.append(ip)

            for ip in neighboursToRemove:
                with self.routingTableLock:
                    self.routingTable.pop(ip, None)

                with self.neighboursLock:
                    if ip in self.neighbours:
                        self.neighbours.remove(ip)
                    if len(self.neighbours) == 1:
                        onlyOneNeighbour = True
                    neighbours = self.neighbours

                noNeighbours = False
                otherOption = None
                if not neighbours:
                    noNeighbours = True
                with self.otherNeighbourLock:
                    otherOption = self.otherNeighbourOption
                with self.bestNeighbourLock:
                    if noNeighbours and otherOption is not None:
                        self.bestNeighbour = otherOption
                        greenPrint(f"[INFO] New best neighbour: {self.bestNeighbour}")
                    elif noNeighbours and otherOption is None:
                        self.bestNeighbour = None
                        redPrint(f"[INFO] No neighbour available.")
                    elif self.bestNeighbour not in neighbours:
                        self.bestNeighbour = neighbours[0]
                        greenPrint(f"[INFO] New best neighbour: {self.bestNeighbour}")
                redPrint(f"[WARN] Neighbor {ip} removed due to timeout")

            with self.requestedOtherNeighbourLock:
                if onlyOneNeighbour and not self.requestedOtherNeighbour:
                    self.requestedOtherNeighbour = True
                    startThread = True

            if startThread:
                threading.Thread(target=self.requestAdditionalNeighbours).start()
                 
            time.sleep(ut.NODE_ROUTING_TABLE_MONITORING_INTERVAL)
                
                
    def requestAdditionalNeighbours(self) -> None:
        """
        Solicita o melhor vizinho do nosso único vizinho disponível.
        """
        greyPrint("Only one neighbour available. Requesting an additional neighbour.")
        with self.bestNeighbourLock:
            # neighbourIP = self.neighbours[0]
            neighbourIP = self.bestNeighbour
        ssocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            ssocket.connect((neighbourIP, ports.NODE_GENERAL_REQUEST_PORT))

            onlyOneNeighbour = True
            while onlyOneNeighbour:
                requestPacket = TcpPacket("BNR") # Best Neighbour Request
                ssocket.send(pickle.dumps(requestPacket))
                response = pickle.loads(ssocket.recv(4096))
                newNeighbour = response.getData().get("BestNeighbour", "")

                with self.otherNeighbourLock:
                    if self.otherNeighbourOption != newNeighbour:
                        self.otherNeighbourOption = newNeighbour
                        greenPrint(f"[INFO] Updated otherNeighbourOption: {newNeighbour}")
                
                with self.neighboursLock:
                    if len(self.neighbours) > 1:
                        onlyOneNeighbour = False

                if onlyOneNeighbour:
                    time.sleep(ut.BEST_NEIGHBOUR_REQUEST_INTERVAL)
                else:
                    with self.requestedOtherNeighbourLock:
                        self.requestedOtherNeighbour = False
        except Exception as e:
            redPrint(f"[ERROR] Failed to request additional neighbours from {neighbourIP}: {e}")
        finally:
            ssocket.close()
    
    def requestVideoFromNeighbour(self, video_id) -> None:
        """
        Solicita o video ao melhor vizinho.
        """
        neighbourIP = None
        while neighbourIP is None:
            with self.bestNeighbourLock:
                if self.bestNeighbour is not None:
                    neighbourIP = self.bestNeighbour
            if neighbourIP is None:
                greyPrint(f"[WARN] No neighbour available. Trying again in {ut.NODE_NO_NEIGHBOUR_WAIT_TIME} seconds.")
                time.sleep(ut.NODE_NO_NEIGHBOUR_WAIT_TIME)
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as ssocket:
                ssocket.connect((neighbourIP, ports.NODE_VIDEO_REQUEST_PORT))
                videoRequestPacket = TcpPacket("VR")  # Video Request 
                videoRequestPacket.addData({"video_id": video_id})
                ssocket.send(pickle.dumps(videoRequestPacket))
                greenPrint(f"[INFO] Requested video {video_id} from {neighbourIP}")
        except Exception as e:
            redPrint(f"[ERROR] Failed to request video {video_id} from {neighbourIP}: {e}")

    def requestStopVideoFromNeighbour(self, video_id) -> None:
        """
        Solicita a paragem da stream do video ao melhor vizinho.
        """
        neighbourIP = None
        while neighbourIP is None:
            with self.bestNeighbourLock:
                if self.bestNeighbour is not None:
                    neighbourIP = self.bestNeighbour
            if neighbourIP is None:
                greyPrint(f"[WARN] No neighbour available. Trying again in {ut.NODE_NO_NEIGHBOUR_WAIT_TIME} seconds.")
                time.sleep(ut.NODE_NO_NEIGHBOUR_WAIT_TIME)
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as ssocket:
                ssocket.connect((neighbourIP, ports.NODE_VIDEO_REQUEST_PORT))
                videoRequestPacket = TcpPacket("SVR")  # Stop Video Request
                videoRequestPacket.addData({"video_id": video_id})
                ssocket.send(pickle.dumps(videoRequestPacket))
                greenPrint(f"[INFO] Requested to stop recieving the video {video_id} from {neighbourIP}")
        except Exception as e:
            redPrint(f"[ERROR] Failed to request to stop video {video_id} from {neighbourIP}: {e}")
            
    def stopStreamingVideo(self, video_id, neighbourIP) -> None:
        """
        Para de transmitir o video para um vizinho e verifica se podemos parar de receber a transmissão do mesmo.
        """
        try:
            stopStream = False
            with self.streamedVideosLock:
                if video_id in self.streamedVideos.keys():
                    self.streamedVideos[video_id]["Neighbours"].remove(neighbourIP)
                    greenPrint(f"[INFO] Stopped streaming video {video_id} to {neighbourIP}")
                    if len(self.streamedVideos[video_id]["Neighbours"]) == 0:
                        self.streamedVideos[video_id]["Streaming"] = False
                        greenPrint(f"[INFO] Stopped streaming video {video_id}")
                        stopStream = True
            if stopStream:
                self.requestStopVideoFromNeighbour(video_id) 
        except Exception as e:
            redPrint(f"[ERROR] Failed to stop streaming video {video_id}: {e}")

    def startStreamingVideo(self, video_id, neighbourIP) -> None:
        """
        Função responsável por iniciar a transmissão do video para um vizinho.
        """
        with self.streamedVideosLock:
            streamedVideosList = self.streamedVideos.keys()
        if video_id in streamedVideosList:
            greenPrint(f"[INFO] Forwarding video {video_id} to {neighbourIP}")
            with self.streamedVideosLock:
                self.streamedVideos[video_id]["Neighbours"].append(neighbourIP)
        else:
            greenPrint(f"[INFO] Requesting video {video_id} from best neighbour")
            with self.streamedVideosLock:
                self.streamedVideos[video_id] = {"Streaming": True, "Neighbours": [neighbourIP]} # TODO: Verificar se é aqui que meto True ou mais tarde
            self.requestVideoFromNeighbour(video_id)
    
    def nodeVideoRequestManager(self) -> None:
        """
        Função responsável por receber os pedidos de vídeo dos vizinhos.
        """
        lsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lsocket.bind((self.ip, ports.NODE_VIDEO_REQUEST_PORT))
        lsocket.listen()

        while True:
            nodeSocket, addr = lsocket.accept()
            nodeRequestHandler = threading.Thread(target=self.nodeVideoRequestHandler, args=(nodeSocket, addr,))
            nodeRequestHandler.start()

    def nodeVideoRequestHandler(self, lsocket: socket.socket, addr: Tuple[str, int]) -> None:
        """
        Função responsável por lidar com os pedidos de vídeo dos vizinhos.
        """
        data = lsocket.recv(4096)
        packet = pickle.loads(data)
        messageType = packet.getMessageType()
        video_id = packet.getData().get("video_id", "")
        ipAddr = addr[0]

        if messageType == "VR":  # Video Request
            self.startStreamingVideo(video_id, ipAddr)
        elif messageType == "SVR":  # Stop Video Request
            self.stopStreamingVideo(video_id, ipAddr)

    def nodeGeneralRequestManager(self) -> None:
        """
        Função responsável por receber os pedidos gerais dos vizinhos.
        """
        lsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lsocket.bind((self.ip, ports.NODE_GENERAL_REQUEST_PORT))
        lsocket.listen()

        while True:
            nodeSocket, addr = lsocket.accept()
            nodeRequestHandler = threading.Thread(target=self.nodeGeneralRequestHandler, args=(nodeSocket, addr))
            nodeRequestHandler.start()

    def nodeGeneralRequestHandler(self, nodeSocket: socket.socket, addr: Tuple[str, int]) -> None:
        """
        Função responsável por lidar com os pedidos gerais dos vizinhos.
        """
        packet = pickle.loads(nodeSocket.recv(4096))
        messageType = packet.getMessageType()
        greenPrint(f"[INFO] {messageType} request recieved from {addr[0]}")

        if messageType == "BNR":  # Best Neighbour Request
            self.sendBestNeighbour(nodeSocket)

    def sendBestNeighbour(self, nodeSocket: socket.socket) -> None:
        """
        Função que envia o melhor vizinho atual do Node.
        """
        response = TcpPacket("R")
        with self.bestNeighbourLock:
            bestNeighbour = self.bestNeighbour
        response.addData({"BestNeighbour": bestNeighbour})
        nodeSocket.sendall(pickle.dumps(response))
        nodeSocket.close()

    def registerWithBootstrapper(self) -> None:
        """
        Função que popula a lista de vizinhos recebida pelo Bootstrapper, a flag isPoP e o IP onde devemos operar.
        """
        try:
            greenPrint(f"[INFO] Node started")
            greenPrint(f"[INFO] Connecting to Bootstrapper")
            self.socket.connect((ports.BOOTSTRAPPER_IP, ports.BOOTSTRAPPER_PORT))
            greenPrint(f"[INFO] Connected to the Bootstrapper")

            packet = TcpPacket("NLR") # NLR = Neighbour List Request
            self.socket.sendall(pickle.dumps(packet))   # Enviar o IP para receber a lista de vizinhos

            greenPrint(f"[INFO] Requested Neighbour list")
            response = pickle.loads(self.socket.recv(4096))

            responseDict = response.getData()
            self.ip = responseDict['IP']
            greenPrint(f"[DATA] My IP: {self.ip}")
            with self.topologyNeighboursLock:
                self.topologyNeighbours = responseDict['Neighbours']
                greenPrint(f"[DATA] Neighbour list: {self.topologyNeighbours}")
            self.isPoP = responseDict['isPoP']
            greenPrint(f"[DATA] PoP: {self.isPoP}")
        except Exception as e:
            redPrint(f"[ERROR] Failed to register with Bootstrapper: {e}")
            sys.exit(1)


if __name__ == "__main__":
    """
    if len(sys.argv) < 3:
        redPrint("[ERROR] Usage: python3 oNode.py <bootstrapIp> <bootstrapPort>")
        sys.exit(1)
    
    bootstrapIp = sys.argv[1]
    bootstrapPort = int(sys.argv[2])
    """

    node = oNode()
    node.registerWithBootstrapper()
    node.startNode()
