GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"


def greenPrint(text: str) -> None:
	"""
	Função que imprime a string em verde.
	"""
	print(f"{GREEN}{text}{RESET}")

def redPrint(text: str) -> None:
	"""
	Função que imprime a string em vermelho.
	"""
	print(f"{RED}{text}{RESET}")
