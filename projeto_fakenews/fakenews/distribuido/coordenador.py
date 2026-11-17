"""
Coordenador da versão distribuída.

Topologia (exemplo com 3 workers):

                       +-------------------+
          OLA/INIT     |   COORDENADOR     |   ESTAT -> soma -> DECISAO
        +------------->|  (redução global) |<-------------+
        |              +-------------------+              |
        |                ^              ^                 |
   +----------+  BORDA  +----------+  BORDA  +----------+
   | worker 0 |<------->| worker 1 |<------->| worker 2 |
   | linhas   |  (TCP   | linhas   |  (TCP   | linhas   |
   | 0..k-1   | direto) | k..2k-1  | direto) | 2k..L-1  |
   +----------+         +----------+         +----------+

Particionamento: decomposição 1D por FAIXAS DE LINHAS. Cada worker só
precisa trocar linhas com no máximo 2 vizinhos, e cada linha é um bloco
contíguo de memória (envio sem cópia/serialização). Volume trocado por
geração por worker = 2·(C+2) bytes, independente do nº de linhas da faixa.

As fronteiras trafegam DIRETAMENTE entre workers vizinhos (peer-to-peer),
sem passar pelo coordenador; o coordenador só recebe 3 inteiros por
geração de cada worker (redução das contagens) — isso evita que ele vire
gargalo de banda.

Modos de execução:
  * local (padrão): o coordenador lança `n` processos worker nesta máquina
    (comunicação real via TCP pela interface de loopback);
  * várias máquinas: `--locais 0` (ou menos que n) e rode o worker em cada
    máquina apontando para o IP do coordenador.
"""

import os
import socket
import struct
import subprocess
import sys
import time

from ..modelo import Regras, criar_grade, contar, dividir_linhas
from ..resultado import Resultado
from . import protocolo as P

RAIZ_PROJETO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def simular(cfg, n_workers=4, halo=1, host="127.0.0.1", porta=0, locais=None,
            ip_para_locais=None, verbose=False):
    """
    n_workers      : total de workers (processos) que participarão
    halo           : profundidade do halo H (linhas fantasmas trocadas a cada H gerações)
    host, porta    : onde o coordenador escuta (porta 0 = escolhida pelo SO)
    locais         : quantos workers lançar nesta máquina (padrão: todos)
    ip_para_locais : IP que os workers locais usam para conectar
                     (com workers remotos, use o IP da rede, não 127.0.0.1)
    """
    if locais is None:
        locais = n_workers
    n_workers = max(1, min(n_workers, cfg.linhas))
    faixas = dividir_linhas(cfg.linhas, n_workers)
    menor = min(b - a for a, b in faixas)
    if n_workers > 1 and halo > menor:
        raise ValueError(f"halo={halo} maior que a menor faixa ({menor} linhas)")
    halo = max(1, halo)

    t_inicio = time.perf_counter()
    servidor = socket.create_server((host, porta), backlog=max(16, n_workers))
    porta = servidor.getsockname()[1]
    destino = ip_para_locais or ("127.0.0.1" if host in ("0.0.0.0", "") else host)
    if verbose:
        print(f"[coordenador] escutando em {host}:{porta}; aguardando {n_workers} workers "
              f"({locais} locais)", flush=True)

    # ---------------- (1) lança workers locais ----------------
    procs = []
    saida = None if verbose else subprocess.DEVNULL
    for _ in range(min(locais, n_workers)):
        procs.append(subprocess.Popen(
            [sys.executable, "-m", "fakenews.distribuido.worker",
             "--coordenador", f"{destino}:{porta}"],
            cwd=RAIZ_PROJETO, stdout=saida))

    conexoes = []
    try:
        # ---------------- (2) aguarda os OLA ----------------
        servidor.settimeout(120)
        for _ in range(n_workers):
            c, addr = servidor.accept()
            P.configurar(c)
            c.settimeout(None)
            _, d = P.receber(c, P.OLA)
            info, _ = P.desempacotar(d)
            conexoes.append((c, info["ip"], info["porta"]))
            if verbose:
                print(f"[coordenador] worker conectado de {addr[0]} (escuta {info['porta']})",
                      flush=True)
        t_conexao = time.perf_counter() - t_inicio

        # ---------------- (3) distribui a grade ----------------
        t0 = time.perf_counter()
        regras = Regras(cfg)
        L, W = cfg.linhas, cfg.colunas + 2
        grade = criar_grade(cfg)
        historico = [contar(grade, W, 1, L + 1, regras)]
        for wid, (c, _, _) in enumerate(conexoes):
            a, b = faixas[wid]
            meta = {
                "id": wid, "n": n_workers, "inicio": a, "fim": b, "halo": halo,
                "cfg": cfg.para_dict(),
                "tem_cima": wid > 0,
                "vizinho_baixo": ([conexoes[wid + 1][1], conexoes[wid + 1][2]]
                                  if wid < n_workers - 1 else None),
            }
            P.enviar(c, P.INIT, P.empacotar(meta, grade[(a + 1) * W:(b + 1) * W]))
        t_distribuicao = time.perf_counter() - t0

        # ---------------- (4) laço de ciclos: redução + decisão ----------------
        t_sim = time.perf_counter()
        g, parar = 0, False
        bytes_controle = msgs_controle = 0
        while g < cfg.geracoes and not parar:
            passos = min(halo, cfg.geracoes - g)
            soma = [0] * (3 * passos)
            for c, _, _ in conexoes:
                _, d = P.receber(c, P.ESTAT)
                bytes_controle += len(d) + P.CABECALHO.size
                msgs_controle += 1
                for i, v in enumerate(struct.unpack(f"!{3 * passos}I", d)):
                    soma[i] += v
            for s in range(passos):
                historico.append(tuple(soma[3 * s:3 * s + 3]))
                if cfg.parar_sem_espalhadores and soma[3 * s + 1] == 0:
                    # Os workers podem ter calculado gerações extras dentro do
                    # ciclo, mas sem espalhadores nada muda: grade idêntica.
                    parar = True
                    break
            g += passos
            decisao = P.PARAR if (parar or g >= cfg.geracoes) else P.CONTINUAR
            for c, _, _ in conexoes:
                bytes_controle += P.enviar(c, P.DECISAO, bytes([decisao]))
                msgs_controle += 1
        t_fim_sim = time.perf_counter()

        # ---------------- (5) coleta o resultado ----------------
        final = bytearray(len(grade))
        metricas = []
        for wid, (c, _, _) in enumerate(conexoes):
            _, d = P.receber(c, P.FINAL)
            m, linhas = P.desempacotar(d)
            a, b = faixas[wid]
            final[(a + 1) * W:(b + 1) * W] = linhas
            metricas.append(m)
        t_fim = time.perf_counter()
    finally:
        for c, _, _ in conexoes:
            c.close()
        servidor.close()
        for p in procs:
            try:
                p.wait(timeout=30)
            except subprocess.TimeoutExpired:
                p.kill()

    t_calc = [m["t_calc"] for m in metricas]
    bytes_bordas = sum(m["bytes_bordas"] for m in metricas)
    msgs_bordas = sum(m["msgs_bordas"] for m in metricas)
    return Resultado(
        f"distribuido-h{halo}", cfg, historico,
        tempo_simulacao=t_fim_sim - t_sim, tempo_total=t_fim - t_inicio,
        grade=final, workers=n_workers,
        detalhes={
            "tempo_conexao": t_conexao,
            "tempo_distribuicao": t_distribuicao,
            "tempo_coleta": t_fim - t_fim_sim,
            "tempo_calc_max": max(t_calc),
            "tempo_calc_medio": sum(t_calc) / len(t_calc),
            "tempo_comm_bordas_medio": sum(m["t_comm"] for m in metricas) / len(metricas),
            "tempo_sinc_medio": sum(m["t_sinc"] for m in metricas) / len(metricas),
            "bytes_bordas": bytes_bordas,
            "msgs_bordas": msgs_bordas,
            "bytes_controle": bytes_controle,
            "msgs_controle": msgs_controle,
            "halo": halo,
            "metricas_workers": metricas,
        })
