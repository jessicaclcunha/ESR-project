import os
import sys
import time
import pickle
import socket
import threading
import tkinter as tk

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import utils.time as ut
import utils.ports as ports
from packets.TcpPacket import TcpPacket
from packets.RtpPacket import RtpPacket
import ClienteGUI as cg
from utils.colors import greenPrint, redPrint, greyPrint


class Client:
    def __init__(self, video:str) -> None: 
        self.ip = None
        self.video = video
        self.popList = []
        self.bestPoP = ""
        self.bestPoPLock = threading.Lock()

    def startClient(self) -> None:
        """
        Função que inicia todos os processos do cliente.
        """
        greenPrint(f"[INFO] Client started")
        self.registerWithBootstrapper()
        threading.Thread(target=self.findBestPoP).start()
        threading.Thread(target=self.requestVideo).start()
        threading.Thread(target=self.displayVideo).start()

    def registerWithBootstrapper(self) -> None:
        greenPrint(f"[INFO] Connecting to Bootstrapper")
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as ssocket:
                ssocket.connect((ports.BOOTSTRAPPER_IP, ports.BOOTSTRAPPER_PORT))
                greenPrint(f"[INFO] Connected to the Bootstrapper")
                message = TcpPacket("PLR")  # PLR = PoP List Request
                ssocket.sendall(pickle.dumps(message))
                greenPrint(f"[INFO] Requested PoP list")
                packet = pickle.loads(ssocket.recv(4096))
                packetData = packet.getData()
                self.ip = packetData.get("IP", ssocket.getsockname()[0])
                greenPrint(f"[DATA] IP: {self.ip}")
                self.popList = packetData.get("PoPList", []) 
                greenPrint(f"[DATA] PoP list: {self.popList}")
        except ConnectionRefusedError:
            redPrint(f"[ERROR] Could not connect to the Bootstrapper")
            sys.exit(1)
        except socket.error as e:
            redPrint(f"[ERROR] {e}")
            sys.exit(1)


    def findBestPoP(self) -> None:
        """
        Função que comunica com os PoPs e escolhe o que tem a menor latência.
        """
        noPoP = True
        while noPoP:
            popLatencies = {}
            for popIp in self.popList:
                greenPrint(f"[INFO] Connecting to {popIp}:{ports.NODE_CLIENT_LISTENING_PORT}")
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sUDPsocket:
                        message = TcpPacket("LR")
                        serializedMessage = pickle.dumps(message)
                        sUDPsocket.sendto(serializedMessage, (popIp, ports.NODE_CLIENT_LISTENING_PORT))

                        sUDPsocket.settimeout(2)
                        data, _ = sUDPsocket.recvfrom(4096)
                        packet = pickle.loads(data)
                        # TODO: Adicionar a esta latency a latency do PoP para mim, pode ser obtifo com o packet.getTimestamp(), verificar
                        latency = packet.getData().get('Latency', float('inf'))
                        greenPrint(f"[DATA] Latency to {popIp}: {latency}")
                        popLatencies[popIp] = latency
                except socket.timeout:
                    greyPrint(f"[WARN] PoP {popIp} did not respond.")
                except socket.error as e:
                    redPrint(f"[ERROR] {e}")

            if popLatencies:
                noPoP = False
                bestPoP = None
                lowestLatency = float("inf")
                
                for popIp, latency in popLatencies.items():
                    if latency <= lowestLatency:
                        lowestLatency = latency
                        bestPoP = popIp

                with self.bestPoPLock:
                    if bestPoP is not None:
                        self.bestPoP = bestPoP
                    greenPrint(f"[DATA] Best PoP: {self.bestPoP}")
            else:
                greyPrint(f"[WARN] No valid latencies received. Trying again in {ut.CLIENT_NO_POP_WAIT_TIME} seconds.")
                time.sleep(ut.CLIENT_NO_POP_WAIT_TIME)

    def requestVideo(self) -> None:
        """
        Função que realiza o pedido do vídeo ao melhor PoP.
        """
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sUDPsocket:
            sUDPsocket.settimeout(2)
            data = { 'video_id' : self.video }
            packet = TcpPacket("VR", data)
            serializedPacket = pickle.dumps(packet)

            notAcknowledged = True
            while notAcknowledged:
                bestPoP = self.getBestPoP()
                greenPrint(f"[INFO] Requesting video {self.video} to {bestPoP}")
                try:
                    sUDPsocket.sendto(serializedPacket, (bestPoP, ports.NODE_CLIENT_LISTENING_PORT))

                    data, addr = sUDPsocket.recvfrom(4096)
                    response = pickle.loads(data)

                    if response.getMessageType() == "VRACK" and addr[0] == bestPoP:
                        greenPrint(f"[INFO] VRACK recieved from {bestPoP}.")
                        notAcknowledged = False
                except socket.timeout:
                    greyPrint(f"[WARN] Video request to {bestPoP} timed out. Trying again in {ut.CLIENT_VIDEO_REQUEST_WAIT_TIME} seconds.")
                    time.sleep(ut.CLIENT_VIDEO_REQUEST_WAIT_TIME)
                except Exception as e:
                    redPrint(f"[ERROR] Error during video request: {e}")
                    break

    def requestStopVideo(self, bestPoP:str) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sUDPsocket:
            sUDPsocket.settimeout(2)
            data = { 'video_id' : self.video }
            packet = TcpPacket("SVR", data)
            serializedPacket = pickle.dumps(packet)

            notAcknowledged = True
            while notAcknowledged:
                greenPrint(f"[INFO] Requesting video stop to {bestPoP}")
                try:
                    sUDPsocket.sendto(serializedPacket, (bestPoP, ports.NODE_CLIENT_LISTENING_PORT))
                    data, addr = sUDPsocket.recvfrom(4096)
                    response = pickle.loads(data)

                    if response.getMessageType() == "SVRACK" and addr[0] == bestPoP:
                        greenPrint(f"[INFO] VRACK recieved from {bestPoP}.")
                        notAcknowledged = False

                    greenPrint(f"[INFO] Video stop request sent to {bestPoP}.")
                except socket.timeout:
                    greyPrint(f"[WARN] Video stop request to {bestPoP} timed out. Trying again in {ut.CLIENT_VIDEO_REQUEST_WAIT_TIME} seconds.")
                    time.sleep(ut.CLIENT_VIDEO_REQUEST_WAIT_TIME)

    def getBestPoP(self) -> str:
        while True:
            with self.bestPoPLock:
                if self.bestPoP != "":
                    return self.bestPoP
            time.sleep(ut.CLIENT_NO_POP_WAIT_TIME)

    def displayVideo(self) -> None:
        os.environ["DISPLAY"] = ":0"
        r = tk.Tk()
        r.title(self.video) # video_id
        try:
            cg.ClienteGUI(r, self.ip, ports.DISPLAY_PORT)
            r.mainloop()
        finally:
            greenPrint(f"[INFO] Video a terminar.")
            self.requestStopVideo(self.getBestPoP())
    

if __name__ == "__main__":
    if len(sys.argv) < 2:
        redPrint(f"[ERROR] Usage: python3 oClient.py <video>")
        sys.exit(1)

    video = sys.argv[1]

    client = Client(video)
    client.startClient()
