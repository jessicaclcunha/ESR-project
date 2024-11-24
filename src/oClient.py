import os
import sys
import time
import pickle
import socket

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import utils.ports as ports
from packets.TcpPacket import TcpPacket
from utils.colors import greenPrint, redPrint


class Client:
    def __init__(self):
        self.pops = []
        self.bestPop = None
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def startClient(self) -> None:
        """
        Função que comunica com o Bootstrapper e recebe a lista de PoPs.
        """
        greenPrint(f"[INFO] Client started")
        greenPrint(f"[INFO] Connecting to Bootstrapper")
            
        try:
            self.socket.connect((ports.BOOTSTRAPPER_IP, ports.BOOTSTRAPPER_PORT))
        except ConnectionRefusedError:
            redPrint(f"[ERROR] Could not connect to the Bootstrapper")
            sys.exit(1)
        except socket.timeout:
            redPrint(f"[ERROR] Timeout while connecting to the Bootstrapper")
            sys.exit(1)
        except socket.error as e:
            redPrint(f"[ERROR] {e}")
            sys.exit(1)

        greenPrint(f"[INFO] Connected to the Bootstrapper")
        message = TcpPacket("PLR")  # PLR = Pop List Request
        self.socket.sendall(pickle.dumps(message))
        greenPrint(f"[INFO] Requested PoP list")
        packet = pickle.loads(self.socket.recv(4096))
        packetData = packet.getData()
        self.pops = packetData["PoPs"] or []
        greenPrint(f"[DATA] PoP list: {self.pops}")
        self.socket.close()

    def findBestPoP(self) -> None:
        """
        Função que comunica com os PoPs e escolhe o que tem a menor latência.
        """
        popLatencies = {}
        for pop in self.pops:
            greenPrint(f"[INFO] Connecting to {pop}")

            try:
                self.socket.connect((pop, 8080))
            except ConnectionRefusedError:
                redPrint(f"[ERROR] Could not connect to {pop}")
            except socket.timeout:
                redPrint(f"[ERROR] Timeout while connecting to {pop}")
            except socket.error as e:
                redPrint(f"[ERROR] {e}")

            greenPrint(f"[INFO] Connected to {pop}")
            message = TcpPacket("LR", time.time())
            self.socket.sendall(pickle.dumps(message))
            packet = pickle.loads(self.socket.recv(4096))
            greenPrint(f"[DATA] Latency to {pop}: {float(packet.data)}")
            popLatencies[pop] = float(packet.data)

        if popLatencies:
            bestPop = None
            lowestLatency = float("inf")
            
            for pop, latency in popLatencies.items():
                if latency < lowestLatency:
                    lowestLatency = latency
                    bestPop = pop

            self.bestPop = bestPop
            greenPrint(f"[DATA] Best Pop: {self.bestPop}")
        else:
            redPrint(f"[ERROR] No valid latencies received. Cannot determine best PoP")

    def requestVideo(self, video:str) -> None:
        """
        Função que realiza o pedido do vídeo ao melhor PoP.
        """
        self.socket.connect((self.bestPop, 8080))
        greenPrint(f"[INFO] Requesting video to {self.bestPop}")
        packet = TcpPacket("VR")
        data = { 'video_id' : video }
        packet.addData(data)
        self.socket.sendall(pickle.dumps(packet))
        self.socket.close()

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
