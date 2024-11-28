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
        self.ip = None
        # TODO: Maybe muda self.latency para self.connectionInfo = {"LT":, "hops":}, etc.
        self.latency = float("inf")  # Tempo de latência do Node até ao Servidor
        self.latencyLock = threading.Lock()
        self.neighbours = [] # Vizinhos ativos
        self.neighboursLock = threading.Lock()
        self.topologyNeighbours = [] # Lista de vizinhos da topologia
        self.topologyNeighboursLock = threading.Lock()
        self.otherNeighbourOption = "" # Em caso de falha dos vizinhos
        self.otherNeighbourLock = threading.Lock()
        self.requestedOtherNeighbour = False
        self.requestedOtherNeighbourLock = threading.Lock()
        self.routingTable = {} # "IP": {"LS":Time, "LT":Time} LS = Last Seen, LT = Latency
        self.routingTableLock = threading.Lock()
        self.isPoP = False
        self.streamedVideos = {} # "IP" : {"Streaming": True/False, "Neighbours": []}
        self.streamedVideosLock = threading.Lock()
        self.bestNeighbour = ""
        self.bestNeighbourLock = threading.Lock()

    def clientConnectionManager(self):
       """
       Função responsável por aceitar as ligações dos clientes.
       """
       lUDPsocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
       lUDPsocket.bind((self.ip, ports.NODE_CLIENT_LISTENING_PORT))
       greenPrint(f"Listening for client connections in {self.ip}:{ports.NODE_CLIENT_LISTENING_PORT}")

       while True:
            try:
                data, addr = lUDPsocket.recvfrom(4096)  # Aceitar a cenexão de um cliente
                greenPrint(f"[INFO] Packet recieved from {addr[0]}")
                client_handler = threading.Thread(target=self.clientRequestHandler, args=(lUDPsocket,data,addr,))  # Criar thread para lidar com o cliente
                client_handler.start() 
            except Exception as e:
                redPrint(f"[ERROR] Error in client connection manager: {e}")

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

    def clientRequestHandler(self, clientSocket: socket.socket, data: bytes, addr: Tuple[str,int]) -> None:
        """
        Função responsável por lidar com os pedidos de um client.

        :param clientSocket: Socket UDP.
        :param data: Pacote TcpPacket serializado.
        """
        packet = pickle.loads(data)
        messageType = packet.getMessageType()

        if messageType == "LR":  # Latency Request
            message = TcpPacket("R", time.time())
            # message.addData({"Latency": }) # TODO: Retornar o tempo de latência até ao servidor
            responseSerialized = pickle.dumps(message)
            clientSocket.sendto(responseSerialized, addr)
            greenPrint(f"[INFO] Latency sent to {addr[0]}")
        elif messageType == "VR":  # Video Request
            video_id = packet.getData().get("video_id", "")
            greenPrint(f"[INFO] Request for video {video_id} recieved from {addr[0]}")
            message = TcpPacket("ACK")
            responseSerialized = pickle.dumps(message)
            clientSocket.sendto(responseSerialized, addr)
            greyPrint(f"[INFO] ACK sent to client {addr[0]}")
            self.startStreamingVideo(video_id, addr[0])
    
    def neighbourPingSender(self) -> None:
        """
        Função responsável por enviar Hello Packets periodicamente aos vizinhos.
        """
        greenPrint(f"[INFO] Ping Thread started on port {ports.NODE_PING_PORT}")
        while True:
            with self.topologyNeighboursLock:
                topologyNeighbours = self.topologyNeighbours.copy()
            with self.neighboursLock:
                activeNeighbours = self.neighbours.copy()

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
                    with self.latencyLock:
                        data = {"Latency": self.latency}
                    helloPacket.addData(data)
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
        neighbour = addr[0]

        if messageType == "HP":
            greenPrint(f"[INFO] Hello Packet received from  neighbour {neighbour}")
            inTopology = True
            onlyNeighbour = False
            with self.topologyNeighboursLock:
                if neighbour not in self.topologyNeighbours:
                    redPrint(f"[ATTENTION] Non expected Hello Packet recieved from {neighbour}")
                    inTopology = False
            if inTopology:
                with self.neighboursLock:
                    if neighbour not in self.neighbours:
                        self.neighbours.append(neighbour)
                        greenPrint(f"[DATA] Neighbour {neighbour} just appeared and was added to the active neighbour list.")
                    if len(self.neighbours) == 1:
                        onlyNeighbour = True
                with self.routingTableLock:
                    latency = packet.getData().get("Latency", float('inf'))
                    if neighbour not in self.routingTable.keys():
                        self.routingTable[neighbour] = {"LT": latency,"LS":time.time(), "hops": 2**31-1}
                    else:
                        self.routingTable[neighbour]["LT"] = latency
                        self.routingTable[neighbour]["LS"] = time.time()
            if onlyNeighbour:
                self.switchBestNeighbour(neighbour)
        elif messageType == "FLOOD":
            latency = time.time() - packet.getData()["ServerTimestamp"]
            hops = packet.getData()["hops"]
            greenPrint(f"[INFO] FLOOD Packet received from neighbour {neighbour} with latency {latency} and {hops} hops")
            with self.routingTableLock:
                self.routingTable[neighbour] = {"LT": latency, "LS": time.time(), "hops": hops}
            with self.neighboursLock:
                if neighbour not in self.neighbours:
                    self.neighbours.append(neighbour)

            isBest = False
            with self.bestNeighbourLock:
                bestNeighbour = self.bestNeighbour
            with self.routingTableLock:
                if bestNeighbour == "" or latency <= self.routingTable[bestNeighbour]["LT"]:
                    isBest = True
                print(self.routingTable)  # TODO: Debug, eliminar ou meter um print mais bonito
            if isBest:
                self.switchBestNeighbour(neighbour)
                data = packet.getData()
                data["hops"] += 1
                floodPacket = TcpPacket("FLOOD")
                floodPacket.addData(data)
                self.propagateFlood(floodPacket, neighbour)

    def propagateFlood(self, floodPacket: TcpPacket, originNeighbour: str) -> None:
        """
        Função responsável por propagar o FLOOD para os vizinhos, exceto o que mandou o FLOOD.

        :param originNeighbour: IP do vizinho que enviou o FLOOD.
        """
        with self.neighboursLock:
            neighbours = self.neighbours.copy()
        neighbours.remove(originNeighbour)
        
        ssocket = None
        for neighbour in neighbours:
            try:
                ssocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                ssocket.settimeout(2)
                ssocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,1)
                ssocket.bind((self.ip, ports.NODE_FLOOD_SENDING_PORT))
                ssocket.connect((neighbour, ports.NODE_MONITORING_PORT))
                ssocket.sendall(pickle.dumps(floodPacket))
            except ConnectionRefusedError:
                redPrint(f"[ERROR] Neighbour {neighbour} is not up.")
            except socket.timeout:
                redPrint(f"[ERROR] Connection to neighbour {neighbour} timed out.")
            except Exception as e:
                redPrint(f"[ERROR] Failed to send Flood Packet to {neighbour}: {e}")
            finally:
                if ssocket:
                    ssocket.close()

    def routingTableMonitoring(self) -> None:
        """
        Função responsável por monitorizar a tabela de routing e remover vizinhos inativos.
        """
        while True:
            startThread = False
            onlyOneNeighbour = False
            neighboursToRemove = []

            with self.routingTableLock:
                for ip, neighbourInfo in self.routingTable.items():
                    timeDiff = ut.nodePastTimeout(neighbourInfo["LS"])  # LS = Last Seen
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
                redPrint(f"[WARN] Neighbor {ip} removed due to timeout")

            neighbours = []
            with self.neighboursLock:
                if len(self.neighbours) == 1:
                    onlyOneNeighbour = True
                neighbours = self.neighbours.copy()

            noNeighbours = len(neighbours) == 0
            bestActiveNeighbour = self.determineBestNeighbour()
            with self.bestNeighbourLock:
                currentBestNeighbour = self.bestNeighbour
            newBestNeighbour = bestActiveNeighbour != currentBestNeighbour
            if newBestNeighbour:
                self.switchBestNeighbour(bestActiveNeighbour)
            elif noNeighbours:
                self.switchBestNeighbour("")

            with self.requestedOtherNeighbourLock:
                if onlyOneNeighbour and not self.requestedOtherNeighbour:
                    self.requestedOtherNeighbour = True
                    startThread = True

            if startThread:
                threading.Thread(target=self.requestAdditionalNeighbours).start()
                 
            time.sleep(ut.NODE_ROUTING_TABLE_MONITORING_INTERVAL)

    def switchBestNeighbour(self, newBestNeighbourIP: str) -> None:
        """
        Função responsável por trocar o melhor vizinho e requisitar os vídeos necessários.
        """
        bestNeighbourActive = True 
        empty = False
        if newBestNeighbourIP != "":
            with self.neighboursLock:
                empty = len(self.neighbours) == 0
                bestNeighbourActive = newBestNeighbourIP in self.neighbours
        with self.otherNeighbourLock:
            otherNeighbour = self.otherNeighbourOption
        with self.bestNeighbourLock:
            if empty:
                if otherNeighbour != "":
                    self.bestNeighbour = otherNeighbour
                    greenPrint(f"[INFO] New best neighbour: {self.bestNeighbour}")
                else:
                    self.bestNeighbour = ""
                    redPrint("[ERROR] No neighbours available.")
            elif not bestNeighbourActive:
                self.bestNeighbour = self.determineBestNeighbour()
                greenPrint(f"[INFO] New best neighbour: {self.bestNeighbour}")
            else:
                self.bestNeighbour = newBestNeighbourIP
                greenPrint(f"[INFO] New best neighbour: {self.bestNeighbour}")

        videoListToRequest = []
        with self.streamedVideosLock:
            for video, info in self.streamedVideos.items():
                if info["Streaming"]:
                    videoListToRequest.append(video)

        for video in videoListToRequest:
            self.requestVideoFromNeighbour(video)

        bestNeighbourIP = self.getBestNeighbour()
        currentLatency = float("inf")
        with self.routingTableLock:
            currentLatency = self.routingTable[bestNeighbourIP]["LT"]
        with self.latencyLock:
            self.latency = currentLatency

    def determineBestNeighbour(self) -> str:
        """
        Função responsável por encontrar o melhor vizinho, dada a nossa tabela de routing.
        Parâmetros mais importantes: Latência, Saltos

        :returns: IP do melhor vizinho
        """
        # TODO: Maybe contar o número de saltos, se a latência estiver entre x%
        minLatency = float("inf")
        bestNeighbour = ""
        with self.routingTableLock:
            for neighbour, info in self.routingTable.items():
                if info["LT"] < minLatency:
                    minLatency = info["LT"]
                    bestNeighbour = neighbour
        return bestNeighbour
    
    def getBestNeighbour(self) -> str:
        """
        Função que retorna o melhor vizinho atual do Node.
        Se não houver vizinho disponível, aguarda um intervalo de tempo.

        :returns: IP do melhor vizinho
        """
        bestNeighbour:str = ""
        while bestNeighbour == "":
            with self.bestNeighbourLock:
                if self.bestNeighbour != "":
                    bestNeighbour = self.bestNeighbour
                    return bestNeighbour
            greyPrint(f"[WARN] No neighbour available. Trying again in {ut.NODE_NO_NEIGHBOUR_WAIT_TIME} seconds.")
            time.sleep(ut.NODE_NO_NEIGHBOUR_WAIT_TIME)
                
    def requestAdditionalNeighbours(self) -> None:
        """
        Solicita o melhor vizinho do nosso único vizinho disponível.
        """
        greyPrint("Only one neighbour available. Requesting an additional neighbour.")
        onlyOneNeighbour = True

        while onlyOneNeighbour:
            with self.neighboursLock:
                if len(self.neighbours) == 1:
                    onlyOneNeighbour = True
            if not onlyOneNeighbour:
                with self.requestedOtherNeighbourLock:
                    self.requestedOtherNeighbour = False
                break

            neighbourIP = self.getBestNeighbour()
            ssocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                ssocket.settimeout(2)
                ssocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,1)
                ssocket.bind((self.ip, ports.ONLY_NEIGHBOUR_REQUESTS))
                ssocket.connect((neighbourIP, ports.NODE_GENERAL_REQUEST_PORT))
                requestPacket = TcpPacket("BNR") # Best Neighbour Request
                ssocket.send(pickle.dumps(requestPacket))
                response = pickle.loads(ssocket.recv(4096))
                newNeighbour = response.getData().get("BestNeighbour", "")


                if newNeighbour == self.ip:
                    redPrint("[WARN] I'm the best neighbour of my only neighbour. Skipping...")
                else:
                    with self.otherNeighbourLock:
                        if self.otherNeighbourOption != newNeighbour:
                            self.otherNeighbourOption = newNeighbour
                            greenPrint(f"[INFO] Updated otherNeighbourOption: {newNeighbour}")
                
            except Exception as e:
                redPrint(f"[ERROR] Failed to request additional neighbours from {neighbourIP}: {e}")
            finally:
                ssocket.close()
                time.sleep(ut.BEST_NEIGHBOUR_REQUEST_INTERVAL)
    
    def requestVideoFromNeighbour(self, video_id:str) -> None:
        """
        Solicita o video ao melhor vizinho.
        """
        neighbourIP = self.getBestNeighbour()
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as ssocket:
                ssocket.connect((neighbourIP, ports.NODE_VIDEO_REQUEST_PORT))
                videoRequestPacket = TcpPacket("VR")  # Video Request 
                videoRequestPacket.addData({"video_id": video_id})
                ssocket.send(pickle.dumps(videoRequestPacket))
                greenPrint(f"[INFO] Requested video {video_id} from {neighbourIP}")
        except Exception as e:
            redPrint(f"[ERROR] Failed to request video {video_id} from {neighbourIP}: {e}")

    def requestStopVideoFromNeighbour(self, video_id:str) -> None:
        """
        Solicita a paragem da stream do video ao melhor vizinho.
        """
        neighbourIP = self.getBestNeighbour()
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as ssocket:
                ssocket.connect((neighbourIP, ports.NODE_VIDEO_REQUEST_PORT))
                videoRequestPacket = TcpPacket("SVR")  # Stop Video Request
                videoRequestPacket.addData({"video_id": video_id})
                ssocket.send(pickle.dumps(videoRequestPacket))
                greenPrint(f"[INFO] Requested to stop recieving the video {video_id} from {neighbourIP}")
        except Exception as e:
            redPrint(f"[ERROR] Failed to request to stop video {video_id} from {neighbourIP}: {e}")
            
    def stopStreamingVideo(self, video_id:str, neighbourIP:str) -> None:
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

    def startStreamingVideo(self, video_id:str, neighbourIP:str) -> None:
        """
        Função responsável por iniciar a transmissão do video para um vizinho.
        """
        with self.streamedVideosLock:
            streamedVideosList = self.streamedVideos.keys()
        if video_id in streamedVideosList:
            greenPrint(f"[INFO] Forwarding video {video_id} to {neighbourIP}")
            with self.streamedVideosLock:
                if neighbourIP not in self.streamedVideos[video_id]["Neighbours"]:
                    self.streamedVideos[video_id]["Neighbours"].append(neighbourIP)
        else:
            greenPrint(f"[INFO] Requesting video {video_id} from best neighbour")
            with self.streamedVideosLock:
                self.streamedVideos[video_id] = {"Streaming": True, "Neighbours": [neighbourIP]} # FIX: Verificar se é aqui que meto True ou mais tarde, deve ser só quando receber o vídeo por UDP
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
            # TODO: Maybe avisar o nó que demos o IP dele, para ele estar à espera

    def sendBestNeighbour(self, nodeSocket: socket.socket) -> None:
        """
        Função que envia o melhor vizinho atual do Node.
        """
        response = TcpPacket("R")
        bestNeighbour = self.getBestNeighbour()
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
