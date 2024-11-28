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

class Servidor:
    def __init__(self) -> None:
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.ip = None
        self.neighbours = []
        self.neighboursLock = threading.Lock()
        self.topologyNeighbours = []
        self.topologyNeighboursLock = threading.Lock()
        self.videos = {} # "IP" : {"Streaming": True/False, "Neighbours": []}
        self.videosLock = threading.Lock()

    def startServer(self) -> None:
        """
        Função responsável por iniciar as threads que executam as funcionalidades do sistema.
        """
        threading.Thread(target=self.startFlood).start()
        threading.Thread(target=self.neighbourPingSender).start()
        threading.Thread(target=self.nodeRequestManager).start()
        # TODO:
        # Thread para dividir os vídeos em pacates e enviar os mesmos para os vizinhos

    def nodeRequestManager(self):
        """
        Função responsável por aceitar as ligações dos vizinhos.
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as lsocket:
                lsocket.bind((self.ip, ports.NODE_VIDEO_REQUEST_PORT))
                while True:
                    nodeSocket, addr = lsocket.accept()
                    nodeRequestHandler = threading.Thread(target=self.nodeRequestHandler, args=(nodeSocket, addr,))
                    nodeRequestHandler.start()
        except KeyboardInterrupt:
            redPrint("[SHUTDOWN] Shutting down server...")
        except Exception as e:
            redPrint(f"[ERROR] Could not start Server: {e}")

    def nodeRequestHandler(self, nodeSocket: socket.socket, nodeAddress: Tuple[str, int]) -> None:
        """
        Função responsável por lidar com os pedidos dos vizinhos.
        """
        packet = pickle.loads(nodeSocket.recv(4096)) 
        greenPrint(f"[INFO] Message received: {packet.getMessageType()} from {nodeAddress[0]}")
        messageType = packet.getMessageType()
        # TODO: Check if the neighbour is already in the list, if not add it
        
        if messageType == "VR":  # Video Request
            self.handleVideoRequest(nodeAddress, packet.getData().get("video_id", ""))
        elif messageType == "SVR":  # Stop Video Request
            self.handleStopVideoRequest(nodeAddress, packet.getData().get("video_id", ""))
    
    def handleVideoRequest(self, nodeAddress: Tuple[str, int], video_id: str) -> None:
        """
        Função responsável por lidar com os pedidos de vídeo dos vizinhos.
        """
        with self.videosLock:
            if video_id in self.videos.keys():
                self.videos[video_id]["Streaming"] = True
                self.videos[video_id]["Neighbours"].append(nodeAddress)
    
    def handleStopVideoRequest(self, nodeAddress: Tuple[str, int], video_id: str) -> None:
        """
        Função responsável por lidar com os pedidos de paragem de video dos vizinhos.
        """
        with self.videosLock:
            if video_id in self.videos.keys():
                self.videos[video_id]["Neighbours"].remove(nodeAddress)
                if len(self.videos[video_id]["Neighbours"]) == 0:
                    self.videos[video_id]["Streaming"] = False

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


    def loadVideoList(self) -> None:
        """
        Criar a lista de vídeos do hardware para o servidor.
        """
        videoDirectory = "../videos/"

        if not os.path.exists(videoDirectory):
            redPrint(f"[ERROR] Directory {videoDirectory} not found")
            return

        try:
            for video in os.listdir(videoDirectory):
                if os.path.isfile(os.path.join(videoDirectory, video)):
                    self.videos[video] = {"Streaming": False, "Neighbours": []}
                    greyPrint(f"[DATA] Loaded video {video}")
            greenPrint("[INFO] Loaded videos")
        except Exception as e:
            redPrint(f"[ERROR] Failed to load videos: {e}")

    def startFlood(self):
        """
        Função que inicia o flood da rede para os nós conhecerem o melhor caminho até ao servidor.
        """
        with self.topologyNeighboursLock:
            topologyNeighbours = self.topologyNeighbours

        ssocket = None
        for neighbour in topologyNeighbours:
            try:
                ssocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                ssocket.settimeout(2)
                ssocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,1)
                ssocket.bind((self.ip, ports.NODE_PING_PORT))
                ssocket.connect((neighbour, ports.NODE_MONITORING_PORT))
                floodPacket = TcpPacket("FLOOD")
                floodPacket.addData({"ServerTimestamp": time.time(), "hops": 0})
                ssocket.sendall(pickle.dumps(floodPacket))
            except ConnectionRefusedError:
                greyPrint(f"[WARN] Neighbour {neighbour} is not up.")
            except socket.timeout:
                redPrint(f"[ERROR] Connection to neighbour {neighbour} timed out.")
            except Exception as e:
                redPrint(f"[ERROR] Failed to send Flood Packet to {neighbour}: {e}")
            finally:
                if ssocket:
                    ssocket.close()
            
    # TODO: Distribuição dos vídeos quando pedido, mas estar sempre a criar os pacotes
    def registerWithBootstrapper(self) -> None:
        try:
            greenPrint(f"[INFO] Server started")
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
        except Exception as e:
            redPrint(f"[ERROR] Failed to register with Bootstrapper: {e}")
            sys.exit(1)


if __name__ == '__main__':
    server = Servidor()
    server.loadVideoList()
    server.registerWithBootstrapper()
    server.startServer()
