"""
Worker da versão distribuída.

Uso (normalmente lançado pelo coordenador; para várias máquinas, rode à mão):
    python -m fakenews.distribuido.worker --coordenador 192.168.0.10:5000

----------------------------------------------------------------------
Memória local do worker  (faixa de n linhas, profundidade de halo H)
----------------------------------------------------------------------
    linhas locais 0 .. H-1        : fantasmas de CIMA  (cópia do vizinho de cima)
    linhas locais H .. H+n-1      : linhas PRÓPRIAS (globais ini .. fim-1)
    linhas locais H+n .. H+n+H-1  : fantasmas de BAIXO (cópia do vizinho de baixo)

Se o worker está na borda da matriz (primeiro/último), os fantasmas daquele
lado ficam sempre zerados = moldura (ninguém fora da matriz).

----------------------------------------------------------------------
Halo profundo / "ghost cell expansion" (Ding & He, 2001)  (melhoria)
----------------------------------------------------------------------
Com H = 1 os workers trocam 1 linha com cada vizinho A CADA geração.
Com H > 1 trocam H linhas a cada H gerações: depois da troca o worker calcula
gerações seguidas sem comunicar, recalculando de forma redundante uma parte
dos fantasmas (que "estragam" 1 linha por geração a partir da ponta):

    passo s (0..H-1) calcula as linhas  [H-(H-1-s) , H+n+(H-1-s))
    -> no passo H-1 sobram exatamente as linhas próprias, corretas.

Troca-se latência (nº de mensagens ÷ H) por cálculo extra (~H² linhas por ciclo).

----------------------------------------------------------------------
Ciclo de vida
----------------------------------------------------------------------
  1. conecta ao coordenador, abre um socket de escuta e envia OLA(ip, porta)
  2. recebe INIT (id, faixa, endereço do vizinho de baixo, grade inicial)
  3. conecta ao vizinho de BAIXO e aceita o vizinho de CIMA (conexões
     persistentes, abertas uma única vez — o trabalho antigo abria uma
     conexão nova a cada mensagem)
  4. para cada ciclo de H gerações:
        troca bordas -> calcula H gerações -> ESTAT -> espera DECISAO
  5. envia FINAL (métricas + faixa final)
"""

import argparse
import socket
import struct
import threading
import time

from ..config import Config
from ..modelo import Regras, passo, contar
from . import protocolo as P


def _conectar(endereco, tentativas=100):
    """Conecta com novas tentativas (o outro lado pode ainda estar subindo)."""
    for t in range(tentativas):
        try:
            return P.configurar(socket.create_connection(endereco, timeout=30))
        except OSError:
            if t == tentativas - 1:
                raise
            time.sleep(0.05)


class Worker:
    def __init__(self, host, porta):
        # (1) conexão com o coordenador
        self.coord = _conectar((host, porta))
        self.coord.settimeout(None)
        meu_ip = self.coord.getsockname()[0]   # IP pelo qual sou alcançável
        self.escuta = socket.create_server((meu_ip, 0))
        P.enviar(self.coord, P.OLA, P.empacotar(
            {"ip": meu_ip, "porta": self.escuta.getsockname()[1]}))

        # (2) configuração inicial
        _, dados = P.receber(self.coord, P.INIT)
        meta, linhas = P.desempacotar(dados)
        self.id = meta["id"]
        self.cfg = Config.de_dict(meta["cfg"])
        self.regras = Regras(self.cfg)
        self.ini, self.fim = meta["inicio"], meta["fim"]
        self.H = meta["halo"]
        self.n = self.fim - self.ini
        self.W = self.cfg.colunas + 2

        H, n, W = self.H, self.n, self.W
        self.atual = bytearray((n + 2 * H) * W)
        self.atual[H * W:(H + n) * W] = linhas
        self.nova = bytearray(len(self.atual))

        # (3) conexões persistentes com os vizinhos.
        # Primeiro CONECTO no de baixo, depois ACEITO o de cima: como todos já
        # estão escutando antes do INIT, o connect completa pela fila do listen
        # e não há deadlock (ninguém espera alguém que está esperando).
        self.baixo = _conectar(tuple(meta["vizinho_baixo"])) if meta["vizinho_baixo"] else None
        self.cima = None
        if meta["tem_cima"]:
            self.escuta.settimeout(60)
            c, _ = self.escuta.accept()
            self.cima = P.configurar(c)
            self.cima.settimeout(None)
        self.escuta.close()
        if self.baixo:
            self.baixo.settimeout(None)

        self.t_calc = self.t_comm = self.t_sinc = 0.0
        self.bytes_bordas = self.msgs_bordas = 0

    # ------------------------------------------------------------------
    def trocar_bordas(self):
        """
        Envia minhas H primeiras linhas para cima e H últimas para baixo;
        recebe os fantasmas. O envio roda em uma thread auxiliar enquanto a
        principal recebe: se ambos os lados fizessem sendall() de mensagens
        maiores que o buffer do socket antes de receber, haveria deadlock.
        """
        H, n, W = self.H, self.n, self.W
        envios = []
        if self.cima:
            envios.append((self.cima, self.atual[H * W:2 * H * W]))
        if self.baixo:
            envios.append((self.baixo, self.atual[n * W:(n + H) * W]))

        def enviar_todos():
            for sock, d in envios:
                self.bytes_bordas += P.enviar(sock, P.BORDA, d)
                self.msgs_bordas += 1

        t = threading.Thread(target=enviar_todos)
        t.start()
        if self.cima:
            _, d = P.receber(self.cima, P.BORDA)
            self.atual[0:H * W] = d
        if self.baixo:
            _, d = P.receber(self.baixo, P.BORDA)
            self.atual[(n + H) * W:(n + 2 * H) * W] = d
        t.join()

    # ------------------------------------------------------------------
    def executar(self):
        H, n, W, cfg = self.H, self.n, self.W, self.cfg
        desloc = self.ini - H          # linha global = linha local + desloc
        g = 0
        t_inicio = time.perf_counter()
        while g < cfg.geracoes:
            passos = min(H, cfg.geracoes - g)

            t0 = time.perf_counter()
            self.trocar_bordas()
            t1 = time.perf_counter()
            self.t_comm += t1 - t0

            contagens = []
            for s in range(passos):
                extra = passos - 1 - s   # quantas linhas fantasmas ainda vale calcular
                r0 = H - extra if self.cima else H
                r1 = H + n + extra if self.baixo else H + n
                passo(self.atual, self.nova, W, r0, r1, desloc, g + s, self.regras)
                self.atual, self.nova = self.nova, self.atual
                contagens.extend(contar(self.atual, W, H, H + n, self.regras))
            t2 = time.perf_counter()
            self.t_calc += t2 - t1

            # redução global: coordenador soma as contagens e decide a parada
            P.enviar(self.coord, P.ESTAT, struct.pack(f"!{len(contagens)}I", *contagens))
            _, d = P.receber(self.coord, P.DECISAO)
            self.t_sinc += time.perf_counter() - t2
            g += passos
            if d[0] == P.PARAR:
                break

        metricas = {
            "id": self.id, "linhas": n,
            "t_calc": self.t_calc, "t_comm": self.t_comm, "t_sinc": self.t_sinc,
            "t_laco": time.perf_counter() - t_inicio,
            "bytes_bordas": self.bytes_bordas, "msgs_bordas": self.msgs_bordas,
        }
        P.enviar(self.coord, P.FINAL, P.empacotar(metricas, self.atual[H * W:(H + n) * W]))
        for s in (self.cima, self.baixo, self.coord):
            if s:
                s.close()


def main():
    ap = argparse.ArgumentParser(description="Worker da simulação distribuída de fake news")
    ap.add_argument("--coordenador", required=True, help="IP:PORTA do coordenador")
    a = ap.parse_args()
    host, porta = a.coordenador.rsplit(":", 1)
    w = Worker(host, int(porta))
    print(f"[worker {w.id}] linhas {w.ini}..{w.fim - 1} | halo {w.H}", flush=True)
    w.executar()


if __name__ == "__main__":
    main()
