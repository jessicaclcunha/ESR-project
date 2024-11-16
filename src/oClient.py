import os
import sys
import time
import pickle
import socket

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from packets.TcpPacket import TcpPacket
from utils.colors import greenPrint, redPrint
from utils.time import formattedTime


class Client:
    def __init__(self, video: str):
        self.pops = []
        self.bestPop = None
        self.video = video
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def startClient(self, bootstrapIp: str, bootstrapPort: int) -> None:
        """
        Função que comunica com o Bootstrapper e recebe a lista de PoPs.
        """
        greenPrint(f"{formattedTime()} [INFO] Client started")
        greenPrint(f"{formattedTime()} [INFO] Connecting to Bootstrapper")
            
        try:
            self.socket.connect((bootstrapIp, bootstrapPort))
        except ConnectionRefusedError:
            redPrint(f"{formattedTime()} [ERROR] Could not connect to the Bootstrapper")
            sys.exit(1)
        except socket.timeout:
            redPrint(f"{formattedTime()} [ERROR] Timeout while connecting to the Bootstrapper")
            sys.exit(1)
        except socket.error as e:
            redPrint(f"{formattedTime()} [ERROR] {e}")
            sys.exit(1)

        greenPrint(f"{formattedTime()} [INFO] Connected to the Bootstrapper")
        message = TcpPacket("PLR")  # PLR = Pop List Request
        self.socket.sendall(pickle.dumps(message))
        greenPrint(f"{formattedTime()} [INFO] Requested PoP list")
        packet = pickle.loads(self.socket.recv(4096))
        packetData = packet.getData()
        self.pops = packetData["PoPs"] or []
        greenPrint(f"{formattedTime()} [DATA] PoP list: {self.pops}")
        self.socket.close()

    def findBestPoP(self) -> None:
        """
        Função que comunica com os PoPs e escolhe o que tem a menor latência.
        """
        popLatencies = {}
        for pop in self.pops:
            greenPrint(f"{formattedTime()} [INFO] Connecting to {pop}")

            try:
                self.socket.connect((pop, 8080))
            except ConnectionRefusedError:
                redPrint(f"{formattedTime()} [ERROR] Could not connect to {pop}")
            except socket.timeout:
                redPrint(f"{formattedTime()} [ERROR] Timeout while connecting to {pop}")
            except socket.error as e:
                redPrint(f"{formattedTime()} [ERROR] {e}")

            greenPrint(f"{formattedTime()} [INFO] Connected to {pop}")
            message = TcpPacket("LR", time.time())
            self.socket.sendall(pickle.dumps(message))
            packet = pickle.loads(self.socket.recv(4096))
            greenPrint(f"{formattedTime()} [DATA] Latency to {pop}: {float(packet.data)}")
            popLatencies[pop] = float(packet.data)

        if popLatencies:
            bestPop = None
            lowestLatency = float("inf")
            
            for pop, latency in popLatencies.items():
                if latency < lowestLatency:
                    lowestLatency = latency
                    bestPop = pop

            self.bestPop = bestPop
            greenPrint(f"{formattedTime()} [DATA] Best Pop: {self.bestPop}")
        else:
            redPrint(f"{formattedTime()} [ERROR] No valid latencies received. Cannot determine best PoP")

    def requestVideo(self) -> None:
        """
        Função que realiza o pedido do vídeo ao melhor PoP.
        """
        self.socket.connect((self.bestPop, 8080))
        greenPrint(f"{formattedTime()} [INFO] Requesting video to {self.bestPop}")
        packet = TcpPacket("VR")
        data = { "video" : self.video }
        packet.addData(data)
        self.socket.sendall(pickle.dumps(packet))
        # TODO: Process of recieving and displaying the video

######################

        while True:
            data = self.socket.recv(4096)
            if not data:
                break
            video_packet = pickle.loads(data)
            self.displayVideo(video_packet)
           
            
    def displayVideo(self, video_packet: TcpPacket) -> None:
        """
        Função que recebe e exibe o vídeo em chunks simulados.
        """
        video_chunk = video_packet.getData().get('chunk', 'No data')
        #imprime 10 primeiros caracteres do chunk
        greenPrint(f"{formattedTime()} [INFO] Received video chunk: {video_chunk[:10]}...")

######################


if __name__ == "__main__":
    if len(sys.argv) < 2:
        redPrint(f"{formattedTime()} [ERROR] Usage: python3 oClient.py <video> <bootstrapIp> <bootstrapPort>")
        sys.exit(1)

    video = sys.argv[1]
    bootstrapIp = sys.argv[2]
    bootstrapPort = int(sys.argv[3])

    client = Client(video)
    client.startClient(bootstrapIp, bootstrapPort)
    client.findBestPoP()
    client.requestVideo()
