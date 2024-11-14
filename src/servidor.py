import socket

import bootstrapper as bs

class Servidor:

    def __init__(self) -> None:
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.neighbours = []
        self.videos = []

    def startServer(self) -> None:
        pass

    # Estratégia de flood da rede
    # Distribuição dos vídeos quando pedido, mas estar sempre a criar os pacotes


if __name__ == '__main__':
    server = Servidor()
    server.startServer()
