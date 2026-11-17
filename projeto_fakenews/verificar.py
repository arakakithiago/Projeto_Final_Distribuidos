"""
Verificação de CORREÇÃO: prova que as versões paralela e distribuída
preservam o comportamento lógico da versão sequencial (requisito da proposta).

Testes:
  1. Sequencial refatorado == FakeNews.py ORIGINAL (gerações e grade final)
  2. Para vários cenários (modos clássico/estendido, otimização, foco inicial,
     tamanhos que não dividem igualmente), compara com o sequencial:
       - paralelo (processos e threads, escalonamento estático e dinâmico)
       - distribuído (1, 2, 3, 5 workers; halo 1, 2, 4)
     Igualdade exigida: histórico de contagens E hash SHA-256 da grade final.

Uso:  python verificar.py
"""

import os
import sys
import time

from fakenews.config import Config
from fakenews.modelo import interior
from fakenews import sequencial, paralelo
from fakenews.distribuido import coordenador

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "referencia"))


def comparar_com_original():
    import FakeNews_original as orig
    print("1) Sequencial refatorado x FakeNews.py original")
    ok_total = True
    for L, C, lim, perc, G in [(100, 100, 3, 0.05, 50), (60, 90, 2, 0.10, 40), (50, 50, 2, 0.02, 60)]:
        g = orig.criar_grade(L, C, perc)
        hist = [tuple(orig.contar_estados(g)[s] for s in (0, 1, 2))]
        for _ in range(G):
            g = orig.proxima_geracao(g, lim)
            c = orig.contar_estados(g)
            hist.append((c[0], c[1], c[2]))
            if c[1] == 0:
                break
        r = sequencial.simular(Config(linhas=L, colunas=C, geracoes=G,
                                      percentual_espalhadores=perc, limiar=lim))
        ok = r.historico == hist and interior(r.grade, L, C) == bytes(x for lin in g for x in lin)
        ok_total &= ok
        print(f"   {L}x{C} limiar={lim} esp={perc:.0%}: {'OK' if ok else 'FALHOU'} "
              f"({len(hist) - 1} gerações)")
    return ok_total


CENARIOS = [
    dict(linhas=97, colunas=83, geracoes=25, limiar=2),
    dict(linhas=120, colunas=64, geracoes=30, limiar=3, percentual_espalhadores=0.15),
    dict(linhas=90, colunas=90, geracoes=30, limiar=2, otimizar_frente=True, foco_inicial=True),
    dict(linhas=101, colunas=77, geracoes=30, modo="estendido"),
    dict(linhas=80, colunas=80, geracoes=40, modo="estendido", otimizar_frente=True,
         parar_sem_espalhadores=False),
]


def main():
    t0 = time.perf_counter()
    ok_geral = comparar_com_original()
    print("\n2) Paralelo e distribuído x sequencial")
    for kw in CENARIOS:
        cfg = Config(**kw)
        ref = sequencial.simular(cfg)
        print(f"   cenário {kw}  -> {ref.geracoes_executadas} gerações, assinatura {ref.assinatura}")
        execucoes = []
        for n in (1, 3, 4):
            for esc in ("estatico", "dinamico"):
                execucoes.append((f"processos n={n} {esc}",
                                  lambda n=n, esc=esc: paralelo.simular(cfg, n, "processos", esc, 7)))
        execucoes.append(("threads n=3 dinamico",
                          lambda: paralelo.simular(cfg, 3, "threads", "dinamico", 5)))
        for n, h in ((1, 1), (2, 1), (3, 2), (5, 4)):
            execucoes.append((f"distribuido n={n} halo={h}",
                              lambda n=n, h=h: coordenador.simular(cfg, n, h)))
        for nome, f in execucoes:
            r = f()
            ok = r.historico == ref.historico and r.assinatura == ref.assinatura
            ok_geral &= ok
            if not ok:
                print(f"      FALHOU: {nome}")
        print(f"      {len(execucoes)} execuções comparadas")
    print(f"\nResultado: {'TODAS AS VERSÕES SÃO EQUIVALENTES' if ok_geral else 'HÁ DIVERGÊNCIAS'} "
          f"({time.perf_counter() - t0:.1f} s)")
    return 0 if ok_geral else 1


if __name__ == "__main__":
    sys.exit(main())
