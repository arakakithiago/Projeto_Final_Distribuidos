"""
Versão PARALELA (memória compartilhada) — dois "backends" com o MESMO algoritmo:

  backend="processos" : multiprocessing.Process + multiprocessing.shared_memory
                        -> paralelismo REAL (cada processo tem seu próprio GIL).
  backend="threads"   : threading.Thread + bytearray comum
                        -> no CPython com GIL as threads NÃO executam bytecode
                           Python ao mesmo tempo; serve para demonstrar
                           experimentalmente essa limitação (ver relatório).
                           Em um Python "free-threaded" (PEP 703, python3.Xt)
                           este mesmo backend passa a escalar.

----------------------------------------------------------------------
Esquema de sincronização (por geração g)
----------------------------------------------------------------------
Dois buffers compartilhados: buf[0] e buf[1] (dupla bufferização).
Na geração g todos LEEM de buf[g % 2] e ESCREVEM em buf[(g+1) % 2].

   coordenador (processo principal)            workers 0..n-1
   ---------------------------------           ------------------------------
   zera contador de blocos
   barreira_inicio.wait()  <---------------->  barreira_inicio.wait()
                                               pega blocos de linhas, calcula,
                                               grava SUAS linhas no buffer novo
   barreira_fim.wait()     <---------------->  barreira_fim.wait()
   soma as contagens; decide se para

Por que não há condição de corrida?
  * durante a geração ninguém escreve no buffer que está sendo lido;
  * cada linha do buffer de escrita pertence a exatamente um bloco, e cada
    bloco é calculado por exatamente um worker;
  * as barreiras garantem que a geração g+1 só começa quando TODA a geração g
    terminou (consistência entre gerações);
  * o único dado disputado é o contador de blocos, protegido por Lock.

----------------------------------------------------------------------
Divisão do trabalho (escalonamento)
----------------------------------------------------------------------
  "estatico" : cada worker recebe uma faixa contígua fixa de ~L/n linhas.
  "dinamico" : a grade é cortada em blocos de `bloco` linhas; cada worker
               pega o próximo bloco livre de um contador compartilhado
               (self-scheduling). Balanceia a carga quando algumas regiões
               dão mais trabalho que outras (ex.: otimizar_frente=True).
"""

import multiprocessing as mp
import threading
import time
from multiprocessing import shared_memory

from .modelo import Regras, criar_grade, passo, contar, dividir_linhas
from .resultado import Resultado

# posições no vetor de estatísticas de cada worker
_IGN, _ESP, _INAT, _TCALC, _NBLOCOS = range(5)
_NCAMPOS = 5


def _blocos(n_workers, L, escalonamento, bloco):
    """Lista de blocos [ini, fim) de linhas globais (0..L-1)."""
    if escalonamento == "estatico":
        return dividir_linhas(L, n_workers)
    return [(a, min(a + bloco, L)) for a in range(0, L, bloco)]


def _laco_worker(wid, n, bufs, cfg, escalonamento, bloco, sinc):
    """
    Laço executado por CADA worker (thread ou processo).

    bufs : [buf0, buf1] — bytearray (threads) ou memoryview da memória
           compartilhada (processos). Ambos aceitam fatiamento e atribuição.
    sinc : objeto com barreiras, flag de parada, contador de blocos e
           vetor de estatísticas.
    """
    regras = Regras(cfg)
    L, W = cfg.linhas, cfg.colunas + 2
    blocos = _blocos(n, L, escalonamento, bloco)
    sinc.pronto.wait()                      # todos inicializados

    g = 0
    while True:
        sinc.inicio.wait()                  # (1) aguarda liberação da geração
        if sinc.parar.value:
            break
        atual, nova = bufs[g % 2], bufs[(g + 1) % 2]
        ign = esp = inat = nb = 0
        t0 = time.perf_counter()

        while True:
            # ---- escolhe o próximo bloco ----
            if escalonamento == "estatico":
                if nb == 1:
                    break
                a, b = blocos[wid]
            else:
                with sinc.proximo.get_lock():        # seção crítica mínima
                    idx = sinc.proximo.value
                    sinc.proximo.value = idx + 1
                if idx >= len(blocos):
                    break
                a, b = blocos[idx]
            nb += 1

            # ---- calcula o bloco ----
            # Linhas globais a..b-1 ficam nas linhas a+1..b do buffer (moldura).
            # Copia a+0..b+1 (bloco + 1 linha vizinha de cada lado) para um
            # buffer local: leitura só do buffer "atual" -> sem corrida.
            local = bytearray(atual[a * W:(b + 2) * W])
            saida = bytearray(len(local))
            passo(local, saida, W, 1, b - a + 1, a - 1, g, regras)
            nova[(a + 1) * W:(b + 1) * W] = saida[W:(b - a + 1) * W]   # só as SUAS linhas
            ci, ce, cn = contar(saida, W, 1, b - a + 1, regras)
            ign += ci; esp += ce; inat += cn

        base = wid * _NCAMPOS
        sinc.stats[base + _IGN] = ign
        sinc.stats[base + _ESP] = esp
        sinc.stats[base + _INAT] = inat
        sinc.stats[base + _TCALC] += time.perf_counter() - t0
        sinc.stats[base + _NBLOCOS] += nb
        g += 1
        sinc.fim.wait()                     # (2) sinaliza fim da geração


def _worker_processo(wid, n, nomes_shm, tamanho, cfg, escalonamento, bloco, sinc):
    """Ponto de entrada de cada PROCESSO: anexa a memória compartilhada e roda o laço."""
    shms = [shared_memory.SharedMemory(name=nm) for nm in nomes_shm]
    try:
        bufs = [s.buf[:tamanho] for s in shms]
        _laco_worker(wid, n, bufs, cfg, escalonamento, bloco, sinc)
        for b in bufs:
            b.release()
    finally:
        for s in shms:
            s.close()


class _Sinc:
    """Primitivas de sincronização agrupadas (picklável no caso de processos)."""

    def __init__(self, modulo, n):
        self.pronto = modulo.Barrier(n + 1)
        self.inicio = modulo.Barrier(n + 1)
        self.fim = modulo.Barrier(n + 1)
        if modulo is threading:
            self.parar = _Valor(0)
            self.proximo = _Valor(0)
            self.stats = [0.0] * (n * _NCAMPOS)
        else:
            self.parar = mp.Value("b", 0, lock=False)
            self.proximo = mp.Value("i", 0)            # com Lock
            self.stats = mp.Array("d", n * _NCAMPOS, lock=False)


class _Valor:
    """Equivalente simples de mp.Value para threads."""

    def __init__(self, v):
        self.value = v
        self._lock = threading.Lock()

    def get_lock(self):
        return self._lock


def simular(cfg, n_workers=4, backend="processos", escalonamento="estatico", bloco=16):
    """
    Executa a simulação paralela com `n_workers` threads ou processos.
    Retorna um Resultado com tempo de simulação (só gerações) e tempo total
    (inclui criação dos workers e da memória compartilhada).
    """
    if backend not in ("processos", "threads"):
        raise ValueError("backend deve ser 'processos' ou 'threads'")
    if escalonamento not in ("estatico", "dinamico"):
        raise ValueError("escalonamento deve ser 'estatico' ou 'dinamico'")
    n_workers = max(1, min(n_workers, cfg.linhas))
    t_inicio = time.perf_counter()

    regras = Regras(cfg)
    L, W = cfg.linhas, cfg.colunas + 2
    grade = criar_grade(cfg)
    tamanho = len(grade)
    historico = [contar(grade, W, 1, L + 1, regras)]

    shms, procs = [], []
    try:
        if backend == "processos":
            ctx = mp.get_context("spawn")   # mesmo comportamento no Windows e Linux
            sinc = _Sinc(ctx, n_workers)
            shms = [shared_memory.SharedMemory(create=True, size=tamanho) for _ in range(2)]
            bufs = [s.buf[:tamanho] for s in shms]
            bufs[0][:] = grade
            bufs[1][:] = bytes(tamanho)
            for wid in range(n_workers):
                p = ctx.Process(target=_worker_processo,
                                args=(wid, n_workers, [s.name for s in shms], tamanho,
                                      cfg, escalonamento, bloco, sinc))
                p.start()
                procs.append(p)
        else:
            sinc = _Sinc(threading, n_workers)
            bufs = [grade, bytearray(tamanho)]
            for wid in range(n_workers):
                t = threading.Thread(target=_laco_worker,
                                     args=(wid, n_workers, bufs, cfg, escalonamento, bloco, sinc))
                t.start()
                procs.append(t)

        sinc.pronto.wait()
        t_criacao = time.perf_counter() - t_inicio

        # ---------------- laço do coordenador ----------------
        t_sim = time.perf_counter()
        t_espera = 0.0
        g = 0
        for g in range(1, cfg.geracoes + 1):
            sinc.proximo.value = 0
            sinc.inicio.wait()                   # libera a geração
            t0 = time.perf_counter()
            sinc.fim.wait()                      # espera todos terminarem
            t_espera += time.perf_counter() - t0
            soma = [0, 0, 0]
            for wid in range(n_workers):
                for c in range(3):
                    soma[c] += int(sinc.stats[wid * _NCAMPOS + c])
            historico.append(tuple(soma))
            if cfg.parar_sem_espalhadores and soma[1] == 0:
                break
        sinc.parar.value = 1
        sinc.inicio.wait()                       # última liberação: workers saem
        t_fim_sim = time.perf_counter()

        for p in procs:
            p.join()
        grade_final = bytearray(bufs[len(historico) - 1 & 1])   # buffer da última geração

        tcalc = [sinc.stats[w * _NCAMPOS + _TCALC] for w in range(n_workers)]
        nblocos = [int(sinc.stats[w * _NCAMPOS + _NBLOCOS]) for w in range(n_workers)]
        if backend == "processos":
            for b in bufs:
                b.release()
    finally:
        for s in shms:
            s.close()
            s.unlink()

    t_fim = time.perf_counter()
    t_simulacao = t_fim_sim - t_sim
    # Desbalanceamento: (maior tempo de cálculo / média) - 1. 0 = perfeito.
    media = sum(tcalc) / len(tcalc) if tcalc else 0
    desbalanceamento = (max(tcalc) / media - 1) if media > 0 else 0.0
    return Resultado(
        f"paralelo-{backend}-{escalonamento}", cfg, historico,
        tempo_simulacao=t_simulacao, tempo_total=t_fim - t_inicio,
        grade=grade_final, workers=n_workers,
        detalhes={
            "tempo_criacao": t_criacao,
            "tempo_calc_max": max(tcalc),
            "tempo_calc_medio": media,
            "desbalanceamento": desbalanceamento,
            # sobrecarga de sincronização ~ tempo de simulação - maior tempo de cálculo
            "tempo_sincronizacao": max(0.0, t_simulacao - max(tcalc)),
            "blocos_por_worker": nblocos,
            "tempo_calc_por_worker": tcalc,
        })
