"""
Atalho para rodar um worker da versão distribuída em OUTRA máquina.

    python worker_remoto.py --coordenador 192.168.0.10:5000

(Equivale a: python -m fakenews.distribuido.worker --coordenador ...)
A pasta do projeto precisa estar copiada na máquina remota.
"""

from fakenews.distribuido.worker import main

if __name__ == "__main__":
    main()
