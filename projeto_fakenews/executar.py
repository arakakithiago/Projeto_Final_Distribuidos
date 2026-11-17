"""
Ponto de entrada único para rodar qualquer versão pela linha de comando.

Exemplos:
    python executar.py sequencial --tamanho 512 --geracoes 50
    python executar.py paralelo   --tamanho 1024 --workers 8
    python executar.py paralelo   --tamanho 1024 --workers 8 --escalonamento dinamico --otimizar-frente
    python executar.py paralelo   --tamanho 512  --workers 4 --backend threads
    python executar.py distribuido --tamanho 1024 --workers 4 --halo 4
    python executar.py sequencial --modo estendido --mostrar-geracoes

Distribuído em várias máquinas (ver README):
    máquina A:  python executar.py distribuido --workers 4 --host 0.0.0.0 --porta 5000 --locais 2 --ip-local 192.168.0.10
    máquina B:  python worker_remoto.py --coordenador 192.168.0.10:5000      (2x)
"""

import argparse

from fakenews.config import Config
from fakenews import sequencial, paralelo
from fakenews.distribuido import coordenador


def construir_parser():
    ap = argparse.ArgumentParser(description="Simulação de propagação de Fake News")
    ap.add_argument("versao", choices=["sequencial", "paralelo", "distribuido"])
    g = ap.add_argument_group("modelo")
    g.add_argument("--tamanho", type=int, help="atalho para linhas = colunas = N")
    g.add_argument("--linhas", type=int, default=100)
    g.add_argument("--colunas", type=int, default=100)
    g.add_argument("--geracoes", type=int, default=50)
    g.add_argument("--espalhadores", type=float, default=0.05, help="fração inicial (0.05 = 5%%)")
    g.add_argument("--limiar", type=int, default=3)
    g.add_argument("--semente", type=int, default=42)
    g.add_argument("--modo", choices=["classico", "estendido"], default="classico")
    g.add_argument("--nao-parar", action="store_true",
                   help="executa todas as gerações mesmo sem espalhadores")
    g.add_argument("--otimizar-frente", action="store_true",
                   help="pula linhas sem espalhadores por perto")
    g.add_argument("--foco-inicial", action="store_true",
                   help="espalhadores iniciais só no 1/4 superior (gera desbalanceamento)")
    e = ap.add_argument_group("modo estendido")
    e.add_argument("--prob-contagio", type=float, default=0.30)
    e.add_argument("--prob-esquecer", type=float, default=0.50)
    e.add_argument("--resistencia-max", type=float, default=0.90)
    e.add_argument("--influenciadores", type=float, default=0.01)
    e.add_argument("--peso-influenciador", type=int, default=4)
    e.add_argument("--bots", type=float, default=0.002)
    p = ap.add_argument_group("paralelo / distribuído")
    p.add_argument("--workers", type=int, default=4, help="nº de threads/processos")
    p.add_argument("--backend", choices=["processos", "threads"], default="processos")
    p.add_argument("--escalonamento", choices=["estatico", "dinamico"], default="estatico")
    p.add_argument("--bloco", type=int, default=16, help="linhas por bloco (escalonamento dinâmico)")
    p.add_argument("--halo", type=int, default=1, help="profundidade do halo (distribuído)")
    p.add_argument("--host", default="127.0.0.1", help="interface onde o coordenador escuta")
    p.add_argument("--porta", type=int, default=0, help="porta do coordenador (0 = automática)")
    p.add_argument("--locais", type=int, help="quantos workers lançar nesta máquina")
    p.add_argument("--ip-local", help="IP desta máquina, usado pelos workers locais")
    ap.add_argument("--mostrar-geracoes", action="store_true")
    return ap


def config_de_args(a):
    linhas, colunas = (a.tamanho, a.tamanho) if a.tamanho else (a.linhas, a.colunas)
    return Config(
        linhas=linhas, colunas=colunas, geracoes=a.geracoes,
        percentual_espalhadores=a.espalhadores, limiar=a.limiar, semente=a.semente,
        modo=a.modo, parar_sem_espalhadores=not a.nao_parar,
        otimizar_frente=a.otimizar_frente, foco_inicial=a.foco_inicial,
        prob_contagio=a.prob_contagio, prob_esquecer=a.prob_esquecer,
        resistencia_max=a.resistencia_max, perc_influenciadores=a.influenciadores,
        peso_influenciador=a.peso_influenciador, perc_bots=a.bots)


def main():
    a = construir_parser().parse_args()
    cfg = config_de_args(a)
    if a.versao == "sequencial":
        r = sequencial.simular(cfg)
    elif a.versao == "paralelo":
        r = paralelo.simular(cfg, a.workers, a.backend, a.escalonamento, a.bloco)
    else:
        r = coordenador.simular(cfg, a.workers, a.halo, a.host, a.porta,
                                locais=a.locais, ip_para_locais=a.ip_local, verbose=True)
    r.imprimir(mostrar_geracoes=a.mostrar_geracoes)


if __name__ == "__main__":
    main()
