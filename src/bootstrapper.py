# Bootstrap lê o ficheiro uma vez quando é iniciado
# Recebe o pedido dos clientes, vê qual é o cliente, e quais são os seus vizinhos
# Devolve essa lista de vizinhos

import socket
import threading


class Bootstrapper:
    def __init__(self, filename: str, host='', port=6000) -> None:
        self.host = host
        self.port = port
        self.socket = None
        self.connections = {}

        self.fillConections(filename)
        self.createSocket()

    def fill_conections(self, filename: str) -> None:
        # Ler o ficheiro da topologia f"../topologias/{filename}"
        # Popular o self.connectios
        # parsing do ficheiro imn para cada nodo
        # fazer o parser e colocar na pasta utils/
        # neighbours dentro do network-config, retirar para uma lista 
        # neighbours = []
        # neighbours.append(newNeighbour)
        # Ex: self.connections[hostname] = neighbours
        pass

    def createSocket(self) -> None:
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind(self.host, self.port)


    # Função para lidar com nós que se conectam ao controlador
    def handle_node(self, node_socket, node_address) -> None:
        print(f"[INFO] Node conectado: {node_address}")
        
        # Envia a lista de vizinhos (neste exemplo, os dois primeiros nós)
        #neighbors = self.connections[node_address[0]] # TODO: Verificar se é a forma correta
        #response = neighbors.enco()
        #node_socket.send(response)
        #node_socket.close()
        pass

# Gerir os nós que se vão ligando
    def start_bootstrapper(self) -> None:
        self.socket.listen(5)
        print(f"[INFO] Bootstrapper escutando em {self.host}:{self.port}")

        while True:
            node_socket, addr = self.socket.accept()
            node_handler = threading.Thread(target=self.handle_node, args=(self, node_socket, addr))
            node_handler.start()

# Executar o Bootstrapper
if __name__ == "__main__":
    filename = input("Nome do ficheiro da topologia: ")
    bs = Bootstrapper(filename)
    bs.start_bootstrapper()