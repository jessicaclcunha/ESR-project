import os
import sys
import time
import pickle
import socket

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import utils.time as ut
import utils.ports as ports
from packets.TcpPacket import TcpPacket
from utils.colors import greenPrint, redPrint, greyPrint


class Client:
    def __init__(self):
        self.popList = []
        self.bestPoP = None

    def startClient(self) -> None:
        """
        Função que comunica com o Bootstrapper e recebe a lista de PoPs.
        """
        greenPrint(f"[INFO] Client started")
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
                self.popList = packetData["PoPList"] or []
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
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as ssocket:
                        ssocket.connect((popIp, ports.NODE_CLIENT_LISTENING_PORT))
                        greenPrint(f"[INFO] Connected to {popIp}")
                        message = TcpPacket("LR", time.time())
                        ssocket.sendall(pickle.dumps(message))
                        packet = pickle.loads(ssocket.recv(4096))
                        latency = packet.getData()['Latency']
                        greenPrint(f"[DATA] Latency to {popIp}: {latency}")
                        popLatencies[popIp] = latency
                except ConnectionRefusedError:
                    greyPrint(f"[WARN] PoP {popIp} not available.")
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

                self.bestPoP = bestPoP
                greenPrint(f"[DATA] Best PoP: {self.bestPoP}")
            else:
                greyPrint(f"[WARN] No valid latencies received. Trying again in {ut.CLIENT_NO_POP_WAIT_TIME} seconds.")
                time.sleep(ut.CLIENT_NO_POP_WAIT_TIME)

    def requestVideo(self, video:str) -> None:
        """
        Função que realiza o pedido do vídeo ao melhor PoP.
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as ssocket:
            ssocket.connect((self.bestPoP, ports.NODE_VIDEO_REQUEST_PORT))
            greenPrint(f"[INFO] Requesting video to {self.bestPoP}")
            packet = TcpPacket("VR")
            data = { 'video_id' : video }
            packet.addData(data)
            ssocket.sendall(pickle.dumps(packet))

    # TODO: Process of recieving and displaying the video over UDP/RTP


if __name__ == "__main__":
    if len(sys.argv) < 2:
        redPrint(f"[ERROR] Usage: python3 oClient.py <video>")
        sys.exit(1)

    video = sys.argv[1]

    client = Client()
    client.startClient()
    client.findBestPoP()
    client.requestVideo(video)
