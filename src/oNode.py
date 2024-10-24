import socket
import threading
import bootstrapper as bs

class oNode:
    def __init__(self, host, port) -> None:
        self.host = host
        self.port = port
        self.socket = None
        self.neighbours = []
        
        self.createSocket()
        self.register_with_bootstrapper()

    def createSocket(self) -> None:
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind((self.host, self.port))
    
    # Função para lidar com conexões recebidas
    def handle_client(client_socket, address):
        # TODO: Change this to handle the connection with the client
        print(f"[INFO] Conexão recebida de {address}")
        pass

    # Função do servidor para escutar por conexões
    def start_node(self) -> None:
        self.socket.listen(5)  # Pode aceitar até 5 conexões simultâneas
        print(f"[INFO] Node escutando em {self.host}:{self.port}")

        while True:
            client_socket, addr = self.socket.accept()
            client_handler = threading.Thread(target=self.handle_client, args=(client_socket, addr))
            client_handler.start()

    # Receber a lista de vizinhos do bootstrapper
    def register_with_bootstrapper(self) -> None:
        self.socket.connect((bs.host, bs.port))
        response = self.socket.recv(4096)
        print(f"[INFO] Lista de vizinhos recebida: {response.decode()}")
        self.neighbours = response.decode()

if __name__ == "__main__":
    node = oNode()
    node.start_node()
