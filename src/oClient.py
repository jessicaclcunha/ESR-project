import sys
import time
import pickle
import socket

from packets.TcpPacket import TcpPacket


class Client:
    def __init__(self, video: str):
        self.pops = []
        self.bestPop = None
        self.video = video
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def startClient(self, bootstrapIp: str, bootstrapPort: int) -> None:
        """
        Função que inicia o client, comunica com o Bootstrapper e recebe a lista de PoPs.
        """
        print("[INFO] Client started")
        self.socket.connect((bootstrapIp, bootstrapPort))
        message = TcpPacket("PLR")  # PLR = Pop List Request
        self.socket.sendall(pickle.dumps(message))
        packet = pickle.loads(self.socket.recv(4096))
        self.pops = packet.getData()
        print(f"[DATA] PoP list: {self.pops}")
        self.socket.close()

    def findBestPop(self) -> None:
        """
        Função que comunica com os PoPs e escolhe o que tem a menor latência.
        """
        popLatencies = {}
        for pop in self.pops:
            self.socket.connect((pop, 8080))
            message = TcpPacket("LR", time.time())
            self.socket.sendall(pickle.dumps(message))
            packet = pickle.loads(self.socket.recv(4096))
            popLatencies[pop] = float(packet.data)

        # self.bestPop = min(popLatencies, key=popLatencies.get)
        # print("[DATA] Best Pop: ", self.bestPop)

    def requestVideo(self) -> None:
        """
        Função que realiza o pedido do vídeo ao melhor PoP.
        """
        self.socket.connect((self.bestPop, 8080))
        print("[INFO] Requesting video")
        packet = TcpPacket("VR")
        packet.addData(self.video)
        self.socket.sendall(pickle.dumps(packet))
        # TODO: Process of recieving and displaying the video


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 oClient.py <video> <bootstrapIp> <bootstrapPort>")
        sys.exit(1)

    video = sys.argv[1]
    bootstrapIp = sys.argv[2]
    bootstrapPort = int(sys.argv[3])

    client = Client(video)
    client.startClient(bootstrapIp, bootstrapPort)
    client.findBestPop()
    client.requestVideo()
