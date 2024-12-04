import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.time import formattedTime

YELLOW = "\033[93m"
GREEN = "\033[92m"
RED = "\033[91m"
GREY= "\033[90m"
RESET = "\033[0m"


def greenPrint(text: str) -> None:
	"""
	Função que imprime a string em verde.
	"""
	print(f"{GREEN}[{formattedTime()}] {text}{RESET}")

def redPrint(text: str) -> None:
	"""
	Função que imprime a string em vermelho.
	"""
	print(f"{RED}[{formattedTime()}] {text}{RESET}")

def greyPrint(text: str) -> None:
	"""
	Função que imprime a string em cinza.
	"""
	print(f"{GREY}[{formattedTime()}] {text}{RESET}")

def yellowPrint(text: str) -> None:
	"""
	Função que imprime a string em amarelo.
	"""
	print(f"{YELLOW}[{formattedTime()}] {text}{RESET}")
