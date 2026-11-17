"""
Protocolo de comunicação da versão distribuída (TCP).

Cada mensagem tem um cabeçalho binário fixo de 5 bytes seguido do conteúdo:

    +--------+-------------------+----------------------+
    | tipo   | tamanho (uint32)  | conteúdo (tamanho B) |
    | 1 byte | 4 bytes, big-end. |                      |
    +--------+-------------------+----------------------+

TCP é um fluxo de bytes (não preserva fronteiras de mensagem), por isso o
cabeçalho com o tamanho é necessário: o receptor lê exatamente 5 bytes, depois
exatamente `tamanho` bytes (`receber_exato`).

Linhas da grade são enviadas como bytes crus (1 byte por pessoa), sem JSON:
uma linha de 1024 células = 1026 bytes (com moldura) + 5 de cabeçalho.
O trabalho antigo usava JSON, onde a mesma linha ocupava ~3.000 bytes e
ainda exigia parsing.
"""

import json
import socket
import struct

CABECALHO = struct.Struct("!BI")

# Tipos de mensagem
OLA = 1        # worker -> coordenador : {"ip", "porta"} onde o worker escuta os vizinhos
INIT = 2       # coordenador -> worker : metadados (JSON) + faixa inicial da grade
ESTAT = 3      # worker -> coordenador : contagens das gerações do ciclo
DECISAO = 4    # coordenador -> worker : continuar (1) ou parar (0)
FINAL = 5      # worker -> coordenador : métricas (JSON) + faixa final da grade
BORDA = 6      # worker -> worker      : linhas de fronteira (ghost rows)

CONTINUAR, PARAR = 1, 0


def configurar(sock):
    """Desliga o algoritmo de Nagle: mensagens pequenas saem imediatamente
    (latência menor na troca de bordas, que é sensível à latência)."""
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    return sock


def enviar(sock, tipo, dados=b""):
    sock.sendall(CABECALHO.pack(tipo, len(dados)) + bytes(dados))
    return CABECALHO.size + len(dados)


def receber_exato(sock, n):
    """Lê exatamente n bytes (recv pode devolver menos do que o pedido)."""
    buf = bytearray(n)
    mv = memoryview(buf)
    pos = 0
    while pos < n:
        k = sock.recv_into(mv[pos:])
        if k == 0:
            raise ConnectionError("conexão encerrada pelo outro lado")
        pos += k
    return buf


def receber(sock, tipo_esperado=None):
    tipo, n = CABECALHO.unpack(receber_exato(sock, CABECALHO.size))
    dados = receber_exato(sock, n) if n else bytearray()
    if tipo_esperado is not None and tipo != tipo_esperado:
        raise RuntimeError(f"mensagem inesperada: tipo {tipo}, esperado {tipo_esperado}")
    return tipo, dados


# ---- mensagens compostas: JSON + bloco binário ----
def empacotar(meta, binario=b""):
    j = json.dumps(meta).encode()
    return struct.pack("!I", len(j)) + j + bytes(binario)


def desempacotar(dados):
    (n,) = struct.unpack_from("!I", dados)
    return json.loads(bytes(dados[4:4 + n])), dados[4 + n:]
