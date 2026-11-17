"""
Experimentos de desempenho (seção "Medição de Desempenho" da proposta).

Cada experimento varia UM fator e mantém os demais fixos. Todas as versões
rodam exatamente os mesmos cenários, e cada execução é conferida contra o
sequencial (coluna `correto` do CSV).

  E1 escalabilidade : nº de workers (threads/processos/hosts)   — modo clássico
  E1b escal.-estend.: nº de workers no modo estendido (mais custo por célula)
  E2 tamanho        : tamanho da matriz
  E3 geracoes       : número de gerações
  E4 espalhadores   : percentual inicial de espalhadores (com otimização de frente)
  E5 halo           : profundidade do halo na versão distribuída (custo de comunicação)
  E6 balanceamento  : escalonamento estático x dinâmico com carga desigual
  E7 original       : FakeNews.py original x sequencial refatorado

Métrica principal: tempo do laço de gerações (`tempo_simulacao`); também é
salvo `tempo_total` (inclui criar processos/conexões e distribuir a grade).
Cada ponto é repetido REPETICOES vezes; os gráficos usam a mediana.

Uso:
    python benchmark.py                  # completo (~10 min num Ryzen 7 5700X)
    python benchmark.py --rapido         # versão reduzida (~3 min) para testar
    python benchmark.py --so E1 E5       # só alguns experimentos
Saída: resultados/benchmark.csv  (+ resultados/ambiente.json)
"""

import argparse
import csv
import json
import os
import sys
import time

import ambiente
from fakenews.config import Config
from fakenews import sequencial, paralelo
from fakenews.distribuido import coordenador

RAIZ = os.path.dirname(os.path.abspath(__file__))
PASTA = os.path.join(RAIZ, "resultados")

COLUNAS = ["experimento", "versao", "backend", "escalonamento", "bloco", "workers", "halo",
           "tamanho", "geracoes", "espalhadores", "modo", "otimizar", "foco", "repeticao",
           "tempo_simulacao", "tempo_total", "tempo_calc_max", "tempo_calc_medio",
           "desbalanceamento", "tempo_comm", "tempo_sinc", "bytes_bordas", "msgs_bordas",
           "msgs_controle", "geracoes_exec", "correto"]


class Bench:
    def __init__(self, caminho, repeticoes):
        self.rep = repeticoes
        self.ref = {}              # cache do sequencial por cenário -> (assinatura, historico)
        novo = not os.path.exists(caminho)
        self.f = open(caminho, "a", newline="", encoding="utf-8")
        self.w = csv.DictWriter(self.f, COLUNAS)
        if novo:
            self.w.writeheader()

    def cfg(self, tamanho, geracoes=20, esp=0.05, modo="classico", otim=False, foco=False):
        # parar_sem_espalhadores=False -> o nº de gerações é exatamente o pedido,
        # tornando o trabalho comparável entre cenários.
        return Config(linhas=tamanho, colunas=tamanho, geracoes=geracoes,
                      percentual_espalhadores=esp, limiar=2, modo=modo,
                      otimizar_frente=otim, foco_inicial=foco, parar_sem_espalhadores=False)

    def rodar(self, exp, cfg, versao, workers=1, backend="", escalonamento="", bloco=16, halo=""):
        chave = (cfg.linhas, cfg.geracoes, cfg.percentual_espalhadores, cfg.modo,
                 cfg.otimizar_frente, cfg.foco_inicial)
        for rep in range(self.rep):
            if versao == "sequencial":
                r = sequencial.simular(cfg)
                self.ref.setdefault(chave, (r.assinatura, r.historico))
            elif versao == "paralelo":
                r = paralelo.simular(cfg, workers, backend, escalonamento, bloco)
            else:
                r = coordenador.simular(cfg, workers, halo)
            if chave not in self.ref:
                s = sequencial.simular(cfg)
                self.ref[chave] = (s.assinatura, s.historico)
            correto = (r.assinatura, r.historico) == self.ref[chave]
            d = r.detalhes
            self.w.writerow({
                "experimento": exp, "versao": versao, "backend": backend,
                "escalonamento": escalonamento, "bloco": bloco if escalonamento == "dinamico" else "",
                "workers": workers, "halo": halo, "tamanho": cfg.linhas,
                "geracoes": cfg.geracoes, "espalhadores": cfg.percentual_espalhadores,
                "modo": cfg.modo, "otimizar": int(cfg.otimizar_frente), "foco": int(cfg.foco_inicial),
                "repeticao": rep,
                "tempo_simulacao": f"{r.tempo_simulacao:.5f}", "tempo_total": f"{r.tempo_total:.5f}",
                "tempo_calc_max": f"{d.get('tempo_calc_max', r.tempo_simulacao):.5f}",
                "tempo_calc_medio": f"{d.get('tempo_calc_medio', r.tempo_simulacao):.5f}",
                "desbalanceamento": f"{d.get('desbalanceamento', 0):.4f}",
                "tempo_comm": f"{d.get('tempo_comm_bordas_medio', 0):.5f}",
                "tempo_sinc": f"{d.get('tempo_sinc_medio', d.get('tempo_sincronizacao', 0)):.5f}",
                "bytes_bordas": d.get("bytes_bordas", 0), "msgs_bordas": d.get("msgs_bordas", 0),
                "msgs_controle": d.get("msgs_controle", 0),
                "geracoes_exec": r.geracoes_executadas, "correto": int(correto),
            })
            self.f.flush()
            rot = f"{versao}{'-' + backend if backend else ''}{'-' + escalonamento if escalonamento else ''}"
            print(f"  [{exp}] {rot:<30} n={workers:<3} h={halo!s:<3} {cfg.linhas}² "
                  f"g={cfg.geracoes} esp={cfg.percentual_espalhadores} {cfg.modo[:5]} "
                  f"otim={int(cfg.otimizar_frente)} -> {r.tempo_simulacao:8.3f}s "
                  f"{'OK' if correto else 'ERRO'}", flush=True)

    def todas(self, exp, cfg, n, threads=False, dinamico=True, halo=1):
        """Roda o conjunto padrão de versões paralelas/distribuídas para n workers."""
        self.rodar(exp, cfg, "paralelo", n, "processos", "estatico")
        if dinamico:
            self.rodar(exp, cfg, "paralelo", n, "processos", "dinamico")
        if threads:
            self.rodar(exp, cfg, "paralelo", n, "threads", "estatico")
        self.rodar(exp, cfg, "distribuido", n, halo=halo)


def experimento_original(rep, tamanho, geracoes):
    """E7: tempo do código fornecido x sequencial refatorado (mesma saída)."""
    sys.path.insert(0, os.path.join(RAIZ, "referencia"))
    import FakeNews_original as orig
    linhas = []
    for r in range(rep):
        t0 = time.perf_counter()
        g = orig.criar_grade(tamanho, tamanho, 0.05)
        for _ in range(geracoes):
            g = orig.proxima_geracao(g, 2)
            orig.contar_estados(g)
        t_orig = time.perf_counter() - t0
        res = sequencial.simular(Config(linhas=tamanho, colunas=tamanho, geracoes=geracoes,
                                        limiar=2, parar_sem_espalhadores=False))
        linhas.append({"repeticao": r, "tamanho": tamanho, "geracoes": geracoes,
                       "tempo_original": round(t_orig, 4),
                       "tempo_refatorado": round(res.tempo_total, 4)})
        print(f"  [E7] original {t_orig:.3f}s | refatorado {res.tempo_total:.3f}s", flush=True)
    with open(os.path.join(PASTA, "original_vs_refatorado.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, list(linhas[0]))
        w.writeheader()
        w.writerows(linhas)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rapido", action="store_true")
    ap.add_argument("--so", nargs="*", help="experimentos a rodar (ex.: E1 E5)")
    ap.add_argument("--repeticoes", type=int)
    ap.add_argument("--saida", default=os.path.join(PASTA, "benchmark.csv"))
    a = ap.parse_args()

    os.makedirs(PASTA, exist_ok=True)
    with open(os.path.join(PASTA, "ambiente.json"), "w", encoding="utf-8") as f:
        json.dump(ambiente.coletar(), f, indent=2, ensure_ascii=False)

    rep = a.repeticoes or (1 if a.rapido else 3)
    n_cpu = os.cpu_count() or 4
    if a.rapido:
        base, workers, tamanhos, gens, n_fixo = 256, [1, 2, 4], [128, 256], [10, 20], 4
    else:
        base, workers, tamanhos, gens, n_fixo = 1024, [1, 2, 4, 6, 8, 12, 16], \
            [256, 512, 1024, 2048], [10, 20, 40, 80], 8
    workers = [n for n in workers if n <= max(n_cpu, 4)]
    quer = lambda e: not a.so or e in a.so
    b = Bench(a.saida, rep)
    t0 = time.perf_counter()

    if quer("E1"):
        print("E1: escalabilidade (nº de workers)")
        c = b.cfg(base, 20)
        b.rodar("E1", c, "sequencial")
        for n in workers:
            b.todas("E1", c, n, threads=n <= 8)
    if quer("E1b"):
        print("E1b: escalabilidade no modo estendido")
        c = b.cfg(base, 20, modo="estendido")
        b.rodar("E1b", c, "sequencial")
        for n in workers:
            b.todas("E1b", c, n, dinamico=False)
    if quer("E2"):
        print("E2: tamanho da matriz")
        for t in tamanhos:
            c = b.cfg(t, 20)
            b.rodar("E2", c, "sequencial")
            b.todas("E2", c, n_fixo, dinamico=False)
    if quer("E3"):
        print("E3: número de gerações")
        for g in gens:
            c = b.cfg(base, g)
            b.rodar("E3", c, "sequencial")
            b.todas("E3", c, n_fixo, dinamico=False)
    if quer("E4"):
        print("E4: percentual inicial de espalhadores (com otimização de frente)")
        for esp in [0.001, 0.01, 0.05, 0.20, 0.50]:
            c = b.cfg(base, 30, esp=esp, otim=True)
            b.rodar("E4", c, "sequencial")
            b.todas("E4", c, n_fixo)
        c = b.cfg(base, 30, esp=0.05, otim=False)
        b.rodar("E4", c, "sequencial")
    if quer("E5"):
        print("E5: profundidade do halo (distribuído)")
        for t in ([128] if a.rapido else [256, 1024]):
            c = b.cfg(t, 32)
            b.rodar("E5", c, "sequencial")
            for h in [1, 2, 4, 8, 16]:
                if h <= t // n_fixo:
                    b.rodar("E5", c, "distribuido", n_fixo, halo=h)
    if quer("E6"):
        print("E6: balanceamento de carga (carga concentrada no topo)")
        c = b.cfg(base, 40, esp=0.05, otim=True, foco=True)
        b.rodar("E6", c, "sequencial")
        b.rodar("E6", c, "paralelo", n_fixo, "processos", "estatico")
        for blk in [4, 16, 64]:
            b.rodar("E6", c, "paralelo", n_fixo, "processos", "dinamico", bloco=blk)
        b.rodar("E6", c, "distribuido", n_fixo, halo=1)
    if quer("E7"):
        print("E7: código original x refatorado")
        experimento_original(rep, 256 if a.rapido else 512, 10)

    print(f"\nConcluído em {(time.perf_counter() - t0) / 60:.1f} min -> {a.saida}")


if __name__ == "__main__":
    main()
