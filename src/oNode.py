import os
import sys
import time
import pickle
import socket
import threading

from typing import Tuple
from tabulate import tabulate
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import utils.time as ut
import utils.ports as ports
from packets.TcpPacket import TcpPacket
from packets.RtpPacket import RtpPacket
from utils.colors import greenPrint, redPrint, greyPrint, yellowPrint


class oNode:
    def __init__(self) -> None:
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.ip = None
        # TODO: Maybe muda self.latency para self.connectionInfo = {"LT":, "hops":}, etc.
        self.connectionInfo:dict = {"LT": float("inf"), "hops": 2**31-1}  # Latência e nr de saltos do Node até ao Servidor
        self.connectionInfoLock = threading.Lock()
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
        self.streamedVideos = {} # "IP" : {"Streaming": "TRUE"|"FALSE"|"PENDING", "Neighbours": []}
        self.streamedVideosLock = threading.Lock()
        self.bestNeighbour = ""
        self.bestNeighbourLock = threading.Lock()

    def startNode(self) -> None:
        """
        Função responsável por esperar conexões e lidar com os pedidos que o Node recebe.
        """
        if self.isPoP:
            threading.Thread(target=self.clientConnectionManager).start()
        threading.Thread(target=self.neighbourConnectionManagement).start()
        threading.Thread(target=self.neighbourPingSender).start()
        threading.Thread(target=self.nodeVideoRequestManager).start()
        """ 
        TOREMOVE maybe
        threading.Thread(target=self.nodeGeneralRequestManager).start()
        """
        threading.Thread(target=self.routingTableMonitoring).start()
        threading.Thread(target=self.nodeVideoHandler).start()

    def clientConnectionManager(self):
        """
        Função responsável por aceitar as ligações dos clientes.
        """
        lUDPsocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        lUDPsocket.bind((self.ip, ports.NODE_CLIENT_LISTENING_PORT))
        greenPrint(f"Listening for client connections in {self.ip}:{ports.NODE_CLIENT_LISTENING_PORT}")

        try:
            while True:
                try:
                    data, addr = lUDPsocket.recvfrom(4096)  # Aceitar a cenexão de um cliente
                    greenPrint(f"[INFO] Packet recieved from {addr[0]}")
                    client_handler = threading.Thread(target=self.clientRequestHandler, args=(lUDPsocket,data,addr,))  # Criar thread para lidar com o cliente
                    client_handler.start() 
                except Exception as e:
                    redPrint(f"[ERROR] Error in client connection manager: {e}")
        finally:
            lUDPsocket.close()

    def clientRequestHandler(self, clientSocket: socket.socket, data: bytes, addr: Tuple[str,int]) -> None:
        """
        Função responsável por lidar com os pedidos de um client.

        :param clientSocket: Socket UDP.
        :param data: Pacote TcpPacket serializado.
        """
        packet = pickle.loads(data)
        messageType = packet.getMessageType()

        if messageType == "LR":  # Latency Request
            with self.connectionInfoLock:
                latency = {"Latency": self.connectionInfo["LT"], "hops": self.connectionInfo["hops"]}
            message = TcpPacket("R", latency)
            responseSerialized = pickle.dumps(message)
            clientSocket.sendto(responseSerialized, addr)
            greenPrint(f"[INFO] Latency sent to {addr[0]}")
        elif messageType == "VR":  # Video Request
            video_id = packet.getData().get("video_id", "")
            greenPrint(f"[INFO] Request for video {video_id} recieved from {addr[0]}")
            message = TcpPacket("VRACK")  # Video Request Acknowledgement
            responseSerialized = pickle.dumps(message)
            clientSocket.sendto(responseSerialized, addr)
            greyPrint(f"[INFO] VRACK sent to client {addr[0]}")
            self.startStreamingVideo([video_id], addr[0])
        elif messageType == "SVR":  # Stop Video Request
            video_id = packet.getData().get("video_id", "")
            greenPrint(f"[INFO] Request to stop video {video_id} recieved from {addr[0]}")
            message = TcpPacket("SVRACK")  # Stop Video Request Acknowledgement
            responseSerialized = pickle.dumps(message)
            clientSocket.sendto(responseSerialized, addr)
            greyPrint(f"[INFO] SVRACK sent to client {addr[0]}")
            self.stopStreamingVideo([video_id], addr[0])
    
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
                    with self.connectionInfoLock:
                        myLatency = self.connectionInfo["LT"]
                        numberOfHops = self.connectionInfo["hops"]
                    with self.bestNeighbourLock:
                        myBestNeighbour = self.bestNeighbour
                    data = {"Latency": myLatency, "hops": numberOfHops ,"BestNeighbour": myBestNeighbour}
                    helloPacket = TcpPacket("HP", data)
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

    def nodeVideoHandler(self) -> None:
        """
        Função responsável por receber e distribuir os vídeos.
        """
        lsocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        lsocket.bind((self.ip, ports.UDP_VIDEO_PORT))
        greenPrint(f"[INFO] Video distribution thread started on port {ports.UDP_VIDEO_PORT}")

        try:
            while True:
                try:
                    rtpPacketBytes, addr = lsocket.recvfrom(65535)
                    threading.Thread(target=self.videoPacketHandler, args=(lsocket, rtpPacketBytes)).start()
                except Exception as e:
                    redPrint(f"[ERROR] Error in video distribution: {e}")
        finally:
            lsocket.close()

    def videoPacketHandler(self, lsocket: socket.socket, rtpPacketBytes: bytes) -> None:
        """
        Função responsável por distribuir os pacotes RTP aos vizinhos.
        """
        rtpPacket = RtpPacket()
        rtpPacket.decode(rtpPacketBytes)
        video_id = rtpPacket.getVideoId()

        neighbours = []
        with self.streamedVideosLock:
            if video_id in self.streamedVideos.keys():
                if self.streamedVideos[video_id]["Streaming"] == "PENDING":
                    self.streamedVideos[video_id]["Streaming"] = "TRUE"
                if self.streamedVideos[video_id]["Streaming"] != "FALSE":
                    neighbours = self.streamedVideos[video_id]["Neighbours"]
        for neighbour in neighbours:
            try:
                lsocket.sendto(rtpPacketBytes, (neighbour, ports.UDP_VIDEO_PORT))
                yellowPrint(f"[INFO] Sending packet of video {video_id} to {neighbour}")
            except Exception as e:
                redPrint(f"[ERROR] Error in video distribution to neighbour {neighbour}: {e}")

    def neighbourConnectionManagement(self) -> None:
        """
        Função responsável por receber os Hello e Flood Packets dos vizinhos.
        """
        greenPrint(f"[INFO] Neighbour monitoring thread started on port {ports.NODE_MONITORING_PORT}")
        lsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            lsocket.bind((self.ip, ports.NODE_MONITORING_PORT))
            lsocket.listen()

            while True:
                try:
                    nodeSocket , addr = lsocket.accept()
                    neighbourHandler = threading.Thread(target=self.neighbourConnectionHandler, args=(nodeSocket, addr,))
                    neighbourHandler.start()
                except Exception as e:
                    redPrint(f"[ERROR] Error in neighbour monitoring: {e}")
        finally:
            lsocket.close()

    def neighbourConnectionHandler(self, nodeSocket: socket.socket, addr: Tuple[str, int]) -> None:
        """
        Função responsável por lidar com os Hello e Flood Packets dos vizinhos.
        """
        packet = pickle.loads(nodeSocket.recv(4096))
        recievingTime = time.time()
        messageType = packet.getMessageType()
        neighbour = addr[0]

        if messageType == "HP":
            latencyNeighbourToServer = packet.getData().get("Latency", float('inf'))
            latency = latencyNeighbourToServer + (recievingTime - packet.getTimestamp())
            hopsToServer = packet.getData().get("hops", 2**31-1)
            greenPrint(f"[INFO] Hello Packet received from  neighbour {neighbour}")
            greenPrint(f"[DATA] Latency to neighbour {neighbour}: {latency}")
            onlyNeighbour = False
            with self.neighboursLock:
                if neighbour not in self.neighbours:
                    self.neighbours.append(neighbour)
                    greenPrint(f"[DATA] Neighbour {neighbour} just appeared and was added to the active neighbour list.")
                if len(self.neighbours) == 1:
                    onlyNeighbour = True
            neighbourBestNeighbour = packet.getData().get("BestNeighbour", "")
            with self.routingTableLock:
                if neighbour not in self.routingTable.keys():
                    # TODO: Send and recieve number of hops too
                    self.routingTable[neighbour] = {"LT": latency,"LS": recievingTime, "hops": hopsToServer, "BN": neighbourBestNeighbour}
                else:
                    self.routingTable[neighbour]["LT"] = latency  # Latency
                    self.routingTable[neighbour]["hops"] = hopsToServer  # Hops to Server
                    self.routingTable[neighbour]["LS"] = recievingTime  # Last Seen
                    self.routingTable[neighbour]["BN"] = neighbourBestNeighbour  # Best Neighbour
            with self.bestNeighbourLock:
                bestNeighbour = self.bestNeighbour
            if bestNeighbour == neighbour:
                with self.connectionInfoLock:
                    self.connectionInfo["LT"] = latency
                    self.connectionInfo["hops"] = hopsToServer
            if onlyNeighbour:
                self.switchBestNeighbour(neighbour)
        elif messageType == "FLOOD":
            latency = recievingTime - packet.getData()["ServerTimestamp"]
            isBest = False
            with self.bestNeighbourLock:
                bestNeighbour = self.bestNeighbour
            with self.routingTableLock:
                if bestNeighbour == "" or latency < self.routingTable[bestNeighbour]["LT"]:
                    isBest = True
            with self.neighboursLock:
                if neighbour not in self.neighbours:
                    self.neighbours.append(neighbour)
            if isBest:
                data = packet.getData()
                data["hops"] += 1
                floodPacket = TcpPacket("FLOOD", data)
                self.propagateFlood(floodPacket, neighbour)
                with self.connectionInfoLock:
                    self.connectionInfo["LT"] = latency
                    self.connectionInfo["hops"] = data["hops"]
                self.switchBestNeighbour(neighbour)

            hops = packet.getData()["hops"]
            greenPrint(f"[INFO] FLOOD Packet received from neighbour {neighbour} with latency {latency} and {hops} hops")
            with self.routingTableLock:
                self.routingTable[neighbour] = {"LT": latency, "LS": recievingTime, "hops": hops, "BN": ""}

    def propagateFlood(self, floodPacket: TcpPacket, originNeighbour: str) -> None:
        """
        Função responsável por propagar o FLOOD para os vizinhos, exceto o que mandou o FLOOD.

        :param originNeighbour: IP do vizinho que enviou o FLOOD.
        """
        with self.neighboursLock:
            neighbours = self.neighbours.copy()
        if originNeighbour in neighbours:
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
            """
            TOREMOVE maybe
            startThread = False
            onlyOneNeighbour = False
            """
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
                with self.streamedVideosLock:
                    videosToRemoveNeighbourFrom = []
                    for video_id, videoInfo in self.streamedVideos.items():
                        if ip in videoInfo["Neighbours"]:
                            videosToRemoveNeighbourFrom.append(video_id)
                if videosToRemoveNeighbourFrom:
                    self.stopStreamingVideo(videosToRemoveNeighbourFrom, ip)
                redPrint(f"[WARN] Neighbor {ip} removed due to timeout")

            with self.bestNeighbourLock:
                currentBestNeighbour = self.bestNeighbour

            if currentBestNeighbour in neighboursToRemove:
                with self.otherNeighbourLock:
                    myONO = self.otherNeighbourOption
                if myONO != "":
                    with self.neighboursLock:
                        self.neighbours.append(myONO)
                    self.switchBestNeighbour(myONO)
            else:
                with self.neighboursLock:
                    """
                    if len(self.neighbours) == 1:
                        TOREMOVE maybe
                        onlyOneNeighbour = True
                        """
                    neighbours = self.neighbours.copy()
                noNeighbours = len(neighbours) == 0
                bestActiveNeighbour = self.determineBestNeighbour()
                newBestNeighbour = bestActiveNeighbour != currentBestNeighbour
                if newBestNeighbour:
                    self.switchBestNeighbour(bestActiveNeighbour)
                elif noNeighbours:
                    self.switchBestNeighbour("")

            self.verifyDangerSituation()
                 
                # TODO: DEBUG, depois remover
            with self.bestNeighbourLock:
                redPrint(f"[DATA] Best neighbour: {self.bestNeighbour}")
            with self.routingTableLock:
                headers = ["Neighbour"] + list(next(iter(self.routingTable.values())).keys())
                rows = [[neighbour] + list(neighbourInfo.values()) for neighbour, neighbourInfo in self.routingTable.items()]
                print(tabulate(rows, headers=headers, tablefmt="fancy_grid"))
            with self.streamedVideosLock:
                redPrint(f"[DATA] Streamed Videos: {self.streamedVideos}")
            time.sleep(ut.NODE_ROUTING_TABLE_MONITORING_INTERVAL)

    def switchBestNeighbour(self, newBestNeighbourIP: str) -> None:
        """
        Função responsável por trocar o melhor vizinho e requisitar os vídeos necessários.
        """
        with self.bestNeighbourLock:
            if newBestNeighbourIP == self.bestNeighbour:
                return
        bestNeighbourActive = True 
        empty = False
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
                # TODO: Enviar SVR para o antigo melhor vizinho, caso o mesmo esteja ativo ainda
                self.bestNeighbour = newBestNeighbourIP
                greenPrint(f"[INFO] New best neighbour: {self.bestNeighbour}")

        videoListToRequest = []
        with self.streamedVideosLock:
            for video, info in self.streamedVideos.items():
                if info["Streaming"] != "FALSE":
                    videoListToRequest.append(video)
        if videoListToRequest:
            self.requestVideoFromNeighbour(videoListToRequest)

        with self.bestNeighbourLock:
            bestNeighbourIP = self.bestNeighbour
        currentLatency = float("inf")
        numberOfHops = 2**31-1
        with self.routingTableLock:
            if bestNeighbourIP in self.routingTable.keys():
                currentLatency = self.routingTable[bestNeighbourIP]["LT"]
                numberOfHops = self.routingTable[bestNeighbourIP]["hops"]
        with self.connectionInfoLock:
            if currentLatency != float("inf"):
                self.connectionInfo["LT"] = currentLatency
                self.connectionInfo["hops"] = numberOfHops

    def determineBestNeighbour(self) -> str:
        """
        Função responsável por encontrar o melhor vizinho, dada a nossa tabela de routing.
        Parâmetros mais importantes: Latência, Saltos

        :returns: IP do melhor vizinho
        """
        # TODO: Maybe contar o número de saltos
        minLatency = float("inf")
        bestNeighbour = ""
        with self.routingTableLock:
            for neighbour, info in self.routingTable.items():
                if info["LT"] < minLatency:
                    minLatency = info["LT"]
                    bestNeighbour = neighbour
        with self.connectionInfoLock:
            if minLatency + ut.NOTICIBLE_LATENCY_DIFF < self.connectionInfo["LT"]:
                self.connectionInfo["LT"] = minLatency
                return bestNeighbour
        
        with self.bestNeighbourLock:
            return self.bestNeighbour
    
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
                
    def requestVideoFromNeighbour(self, videoList:list) -> None:
        """
        Solicita o video ao melhor vizinho.
        """
        neighbourIP = self.getBestNeighbour()
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as ssocket:
                ssocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,1)
                ssocket.bind((self.ip, ports.VIDEO_REQUEST_SENDER))
                ssocket.connect((neighbourIP, ports.NODE_VIDEO_REQUEST_PORT))
                data = {"videoList": videoList}
                videoRequestPacket = TcpPacket("VR", data)  # Video Request 
                ssocket.send(pickle.dumps(videoRequestPacket))
                greenPrint(f"[INFO] Requested video(s) {videoList} from {neighbourIP}")
        except Exception as e:
            redPrint(f"[ERROR] Failed to request video(s) {videoList} from {neighbourIP}: {e}")

    def requestStopVideoFromNeighbour(self, videoList:list) -> None:
        """
        Solicita a paragem da stream do video ao melhor vizinho.
        """
        # TODO: Change to get the neighbour from a input to the function
        neighbourIP = self.getBestNeighbour()
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as ssocket:
                ssocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,1)
                ssocket.bind((self.ip, ports.VIDEO_REQUEST_SENDER))
                ssocket.connect((neighbourIP, ports.NODE_VIDEO_REQUEST_PORT))
                data = {"videoList": videoList}
                videoRequestPacket = TcpPacket("SVR", data)  # Stop Video Request
                ssocket.send(pickle.dumps(videoRequestPacket))
                greenPrint(f"[INFO] Requested to stop recieving the video {videoList} from {neighbourIP}")
        except Exception as e:
            redPrint(f"[ERROR] Failed to request to stop video {videoList} from {neighbourIP}: {e}")
            
    def stopStreamingVideo(self, videoList:list, neighbourIP:str) -> None:
        """
        Para de transmitir o video para um vizinho e verifica se podemos parar de receber a transmissão do mesmo.
        """
        try:
            videoStopList = []
            for video_id in videoList:
                stopStream = False
                with self.streamedVideosLock:
                    if video_id in self.streamedVideos.keys():
                        self.streamedVideos[video_id]["Neighbours"].remove(neighbourIP)
                        greenPrint(f"[INFO] Stopped streaming video {video_id} to {neighbourIP}")
                        if len(self.streamedVideos[video_id]["Neighbours"]) == 0:
                            self.streamedVideos[video_id]["Streaming"] = "FALSE"
                            greenPrint(f"[INFO] Stopped streaming video {video_id}")
                            stopStream = True
                if stopStream:
                    videoStopList.append(video_id)
            if videoStopList:
                self.requestStopVideoFromNeighbour(videoStopList) 
        except Exception as e:
            redPrint(f"[ERROR] Failed to stop streaming video(s) {videoList}: {e}")

    def startStreamingVideo(self, videoList:list, neighbourIP:str) -> None:
        """
        Função responsável por iniciar a transmissão do video para um vizinho.
        """
        if neighbourIP == self.getBestNeighbour():
            return
        with self.streamedVideosLock:
            streamedVideos = self.streamedVideos.copy()
        videosToRequest = []
        for video_id in videoList:
            if video_id in streamedVideos.keys() and streamedVideos[video_id]["Streaming"] != "FALSE":
                greenPrint(f"[INFO] Forwarding video {video_id} to {neighbourIP}")
                with self.streamedVideosLock:
                    if neighbourIP not in self.streamedVideos[video_id]["Neighbours"]:
                        self.streamedVideos[video_id]["Neighbours"].append(neighbourIP)
            else:
                greenPrint(f"[INFO] Requesting video {video_id} from best neighbour")
                with self.streamedVideosLock:
                    self.streamedVideos[video_id] = {"Streaming": "PENDING", "Neighbours": [neighbourIP]}
                videosToRequest.append(video_id)
        if videosToRequest:
            self.requestVideoFromNeighbour(videosToRequest)
    
    def nodeVideoRequestManager(self) -> None:
        """
        Função responsável por receber os pedidos de vídeo dos vizinhos.
        """
        lsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            lsocket.bind((self.ip, ports.NODE_VIDEO_REQUEST_PORT))
            lsocket.listen()

            while True:
                nodeSocket, addr = lsocket.accept()
                nodeRequestHandler = threading.Thread(target=self.nodeVideoRequestHandler, args=(nodeSocket, addr,))
                nodeRequestHandler.start()
        finally:
            lsocket.close()

    def nodeVideoRequestHandler(self, lsocket: socket.socket, addr: Tuple[str, int]) -> None:
        """
        Função responsável por lidar com os pedidos de vídeo dos vizinhos.
        """
        data = lsocket.recv(4096)
        packet = pickle.loads(data)
        messageType = packet.getMessageType()
        videoList = packet.getData().get("videoList", [])
        ipAddr = addr[0]

        if messageType == "VR":  # Video Request
            self.startStreamingVideo(videoList, ipAddr)
        elif messageType == "SVR":  # Stop Video Request
            self.stopStreamingVideo(videoList, ipAddr)

        """
        TO REMOVE maybe
    def nodeGeneralRequestManager(self) -> None:
        """
        """
        Função responsável por receber os pedidos gerais dos vizinhos.
        lsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            lsocket.bind((self.ip, ports.NODE_GENERAL_REQUEST_PORT))
            lsocket.listen()

            while True:
                nodeSocket, addr = lsocket.accept()
                nodeRequestHandler = threading.Thread(target=self.nodeGeneralRequestHandler, args=(nodeSocket, addr))
                nodeRequestHandler.start()
        finally:
            lsocket.close()

    def nodeGeneralRequestHandler(self, nodeSocket: socket.socket, addr: Tuple[str, int]) -> None:
        """
    """
        Função responsável por lidar com os pedidos gerais dos vizinhos.
        packet = pickle.loads(nodeSocket.recv(4096))
        messageType = packet.getMessageType()
        greenPrint(f"[INFO] {messageType} request recieved from {addr[0]}")
        if messageType == "BNR":  # Best Neighbour Request
            self.sendBestNeighbour(nodeSocket)
    """

    def verifyDangerSituation(self) -> None:
        """
        Função responsável por verificar se o nó se encontra numa situação de perigo.
        """
        greyPrint("[INFO] Verifying danger situation")
        differentStreamOptions = []
        with self.bestNeighbourLock:
            myBN = self.bestNeighbour
        with self.routingTableLock:
            for neighbourIP, neighbourInfo in self.routingTable.items():
                if neighbourInfo["BN"] not in ["", myBN, self.ip] and neighbourInfo["LT"] != float('inf'):
                    differentStreamOptions.append(neighbourIP)
        streamOptions = len(differentStreamOptions)
        if streamOptions < 2:
            redPrint(f"[DANGER] {streamOptions} options to obtain the stream.")
            if streamOptions == 1:
                ono = ""
                with self.routingTableLock:
                    if differentStreamOptions[0] in self.routingTable.keys():
                        ono = self.routingTable[differentStreamOptions[0]]["BN"]
                if ono != "":
                    with self.otherNeighbourLock:
                        self.otherNeighbourOption = ono
                        greenPrint(f"[INFO] Updated otherNeighbourOption: {ono}")
        else:
            with self.otherNeighbourLock:
                self.otherNeighbourOption = ""
            greyPrint("[INFO] No danger situation")

    """ 
    TO REMOVE maybe
    def sendBestNeighbour(self, nodeSocket: socket.socket) -> None:
        """
    """
        Função que envia o melhor vizinho atual do Node.
        response = TcpPacket("R")
        with self.bestNeighbourLock:
            bestNeighbour = self.bestNeighbour
        response.addData({"BestNeighbour": bestNeighbour})
        nodeSocket.sendall(pickle.dumps(response))
        nodeSocket.close()
    """

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
