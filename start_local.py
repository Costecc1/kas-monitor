"""
Wrapper uruchamiający monitor z załadowaniem .env (do lokalnego testowania).
Na hostingu zmienne ustawiasz bezpośrednio w panelu — ten plik nie jest potrzebny.
"""
from dotenv import load_dotenv
load_dotenv()
import monitor  # noqa: F401 — uruchamia monitor.py
