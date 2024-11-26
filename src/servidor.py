import os
import sys
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
        self.videos = {} # "IP" : {"Streaming": True/False, "Neighbours": []}

    def startServer(self) -> None:
        """
        Função responsável por iniciar as threads que executam as funcionalidades do sistema.
        """
        # TODO:
        # Thread para aceitar conexões dos vizinhos
        # Thread para lidar com os pedidos dos vizinhos
        # Thread para dividir os vídeos em pacates e enviar os mesmos para os vizinhos
        pass

    def loadVideos(self) -> None:
        """
        Carregar os vídeos do hardware para o servidor.
        """
        videoDirectory = "../videos"

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


    # Estratégia de flood da rede
    # Distribuição dos vídeos quando pedido, mas estar sempre a criar os pacotes


if __name__ == '__main__':
    server = Servidor()
    server.loadVideos()
    server.startServer()
