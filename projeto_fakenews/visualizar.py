"""
Visualização gráfica da propagação (melhoria): gera um GIF animado da grade
e as curvas de evolução dos estados (estilo modelo SIR/Daley-Kendall).

    python visualizar.py                               # clássico e estendido, 200x200
    python visualizar.py --modo estendido --tamanho 300 --geracoes 80
    python visualizar.py --modo classico --limiar 2 --foco-inicial

Saída: resultados/visualizacao/
"""

import argparse
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from PIL import Image

from fakenews.config import Config
from fakenews.modelo import BOT, MASCARA_TIPO, interior
from fakenews import sequencial

PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resultados", "visualizacao")

# cor por estado; bots ganham cor própria para aparecerem no mapa
CORES = {"ignorante": (232, 231, 227), "espalhador": (227, 73, 72),
         "inativo": (42, 120, 214), "bot": (98, 80, 214)}


def paleta_bytes():
    """Tabela byte -> RGB (o mesmo truque de translate do modelo)."""
    tab = []
    for b in range(256):
        if (b & MASCARA_TIPO) == (BOT << 2):
            tab.append(CORES["bot"])
        else:
            tab.append([CORES["ignorante"], CORES["espalhador"], CORES["inativo"],
                        CORES["ignorante"]][b & 3])
    return tab


def gerar(cfg, nome, escala, a_cada):
    os.makedirs(PASTA, exist_ok=True)
    tab = paleta_bytes()
    quadros = []

    def capturar(g, grade):
        if g % a_cada == 0:
            dados = interior(grade, cfg.linhas, cfg.colunas)
            img = Image.frombytes("RGB", (cfg.colunas, cfg.linhas),
                                  b"".join(bytes(tab[b]) for b in dados))
            quadros.append(img.resize((cfg.colunas * escala, cfg.linhas * escala), Image.NEAREST))

    r = sequencial.simular(cfg, ao_fim_da_geracao=capturar)
    caminho_gif = os.path.join(PASTA, f"{nome}.gif")
    quadros[0].save(caminho_gif, save_all=True, append_images=quadros[1:] + [quadros[-1]] * 8,
                    duration=120, loop=0)
    print(f"  {caminho_gif} ({len(quadros)} quadros)")
    return r


def curvas(resultados, caminho):
    fig, axs = plt.subplots(1, len(resultados), figsize=(6.5 * len(resultados), 4.5),
                            squeeze=False)
    for ax, (titulo, r) in zip(axs[0], resultados):
        total = r.cfg.linhas * r.cfg.colunas
        gs = range(len(r.historico))
        for idx, (rot, cor) in enumerate([("Ignorantes", "#9a9992"), ("Espalhadores", "#e34948"),
                                          ("Inativos", "#2a78d6")]):
            ys = [100 * h[idx] / total for h in r.historico]
            ax.plot(gs, ys, color=cor, label=rot)
            ax.annotate(f"{ys[-1]:.0f}%", (gs[-1], ys[-1]), textcoords="offset points",
                        xytext=(5, 0), va="center", fontsize=9)
        st = r.estatisticas()
        ax.axvline(st["geracao_do_pico"], ls=":", color="#52514e", lw=1)
        ax.set(title=titulo, xlabel="Geração", ylabel="% da população", ylim=(0, 105))
        ax.grid(True, color="#e4e3df")
        ax.spines[["top", "right"]].set_visible(False)
        ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    fig.savefig(caminho, dpi=150)
    plt.close(fig)
    print(f"  {caminho}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--modo", choices=["classico", "estendido", "ambos"], default="ambos")
    ap.add_argument("--tamanho", type=int, default=200)
    ap.add_argument("--geracoes", type=int, default=60)
    ap.add_argument("--limiar", type=int, default=2)
    ap.add_argument("--espalhadores", type=float, default=0.01)
    ap.add_argument("--foco-inicial", action="store_true")
    ap.add_argument("--escala", type=int, default=3)
    ap.add_argument("--a-cada", type=int, default=1, help="salva 1 quadro a cada N gerações")
    a = ap.parse_args()

    modos = ["classico", "estendido"] if a.modo == "ambos" else [a.modo]
    res = []
    for m in modos:
        cfg = Config(linhas=a.tamanho, colunas=a.tamanho, geracoes=a.geracoes,
                     percentual_espalhadores=a.espalhadores, limiar=a.limiar, modo=m,
                     foco_inicial=a.foco_inicial)
        r = gerar(cfg, f"propagacao_{m}", a.escala, a.a_cada)
        st = r.estatisticas()
        print(f"    alcance final {st['alcance_final_%']:.1f}% | pico {st['pico_espalhadores']:,} "
              f"espalhadores na geração {st['geracao_do_pico']}")
        res.append((f"Modo {m}", r))
    curvas(res, os.path.join(PASTA, "curvas_estados.png"))


if __name__ == "__main__":
    main()
