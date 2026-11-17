"""
Gera gráficos (PNG) e tabelas (Markdown) a partir de resultados/benchmark.csv.

    speedup     S(n) = T_sequencial / T_versão(n)
    eficiência  E(n) = S(n) / n

T = MEDIANA das repetições de `tempo_simulacao` (laço de gerações).
As tabelas também trazem o speedup pelo `tempo_total` (inclui inicialização).

Uso:  python graficos.py            (depois de rodar benchmark.py)
Saída: resultados/graficos/*.png  e  resultados/tabelas.md
"""

import csv
import os
import statistics
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import sys

RAIZ = os.path.dirname(os.path.abspath(__file__))
PASTA = sys.argv[1] if len(sys.argv) > 1 else os.path.join(RAIZ, "resultados")
PASTA_G = os.path.join(PASTA, "graficos")

# Paleta categórica em ordem fixa (cada versão tem sempre a mesma cor).
COR = {
    "paralelo-processos-estatico": "#2a78d6",
    "paralelo-processos-dinamico": "#eb6834",
    "paralelo-threads-estatico": "#1baf7a",
    "distribuido": "#eda100",
    "sequencial": "#52514e",
}
NOME = {
    "paralelo-processos-estatico": "Paralelo (processos, estático)",
    "paralelo-processos-dinamico": "Paralelo (processos, dinâmico)",
    "paralelo-threads-estatico": "Paralelo (threads + GIL)",
    "distribuido": "Distribuído (sockets TCP)",
    "sequencial": "Sequencial",
}
MARCA = {"paralelo-processos-estatico": "o", "paralelo-processos-dinamico": "s",
         "paralelo-threads-estatico": "^", "distribuido": "D", "sequencial": "x"}

plt.rcParams.update({
    "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb",
    "axes.edgecolor": "#b5b4ad", "axes.labelcolor": "#0b0b0b",
    "xtick.color": "#52514e", "ytick.color": "#52514e", "text.color": "#0b0b0b",
    "axes.grid": True, "axes.axisbelow": True, "grid.color": "#e4e3df", "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False,
    "font.size": 11, "axes.titlesize": 13, "axes.titleweight": "bold",
    "lines.linewidth": 2, "lines.markersize": 8, "legend.frameon": False,
})


def chave_versao(r):
    if r["versao"] == "paralelo":
        return f"paralelo-{r['backend']}-{r['escalonamento']}"
    return r["versao"]


def carregar():
    with open(os.path.join(PASTA, "benchmark.csv"), encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    for r in linhas:
        for k in ("tempo_simulacao", "tempo_total", "tempo_calc_max", "tempo_calc_medio",
                  "desbalanceamento", "tempo_comm", "tempo_sinc", "espalhadores"):
            r[k] = float(r[k])
        for k in ("workers", "tamanho", "geracoes", "bytes_bordas", "msgs_bordas", "correto"):
            r[k] = int(r[k])
        r["halo"] = int(r["halo"]) if r["halo"] else 0
        r["v"] = chave_versao(r)
        # desbalanceamento recalculado de forma uniforme: (cálculo máx / médio) - 1
        r["desbalanceamento"] = (r["tempo_calc_max"] / r["tempo_calc_medio"] - 1
                                 if r["tempo_calc_medio"] > 0 else 0.0)
    return linhas


def cenario(r):
    return (r["experimento"], r["tamanho"], r["geracoes"], r["espalhadores"], r["modo"],
            r["otimizar"], r["foco"])


def agrupar(linhas):
    """(cenário, versão, workers, halo, bloco) -> medianas."""
    g = defaultdict(list)
    for r in linhas:
        g[(cenario(r), r["v"], r["workers"], r["halo"], r["bloco"])].append(r)
    out = {}
    for k, rs in g.items():
        med = lambda c: statistics.median(x[c] for x in rs)
        out[k] = {c: med(c) for c in ("tempo_simulacao", "tempo_total", "tempo_calc_max",
                                      "desbalanceamento", "tempo_comm", "tempo_sinc",
                                      "bytes_bordas", "msgs_bordas")}
        out[k]["correto"] = all(x["correto"] for x in rs)
        out[k]["n_rep"] = len(rs)
    return out


def seq(ag, cen):
    for (c, v, *_), m in ag.items():
        if c == cen and v == "sequencial":
            return m
    return None


def salvar(fig, nome):
    os.makedirs(PASTA_G, exist_ok=True)
    for ax in fig.axes:          # gráficos de barra: só grade horizontal
        if ax.patches:
            ax.grid(axis="x", visible=False)
    fig.tight_layout()
    fig.savefig(os.path.join(PASTA_G, nome), dpi=150)
    plt.close(fig)
    print("  gráfico:", nome)


def series(ag, exp, x_de, filtro=lambda c, v, n, h, b: True):
    """Retorna {versão: [(x, mediana, chave_cenario)]} para um experimento."""
    s = defaultdict(list)
    for (c, v, n, h, b), m in ag.items():
        if c[0] == exp and filtro(c, v, n, h, b):
            x = x_de(c, n, h, b)
            if x is not None:
                s[v].append((x, m, c))
    for v in s:
        s[v].sort(key=lambda t: t[0])
    return s


# ----------------------------------------------------------------------
def grafico_escalabilidade(ag, exp, titulo, md):
    s = series(ag, exp, lambda c, n, h, b: n, lambda c, v, n, h, b: v != "sequencial")
    if not s:
        return
    cen = next(iter(s.values()))[0][2]
    ts = seq(ag, cen)["tempo_simulacao"]
    nmax = max(x for pts in s.values() for x, _, _ in pts)

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5))
    a1.plot([1, nmax], [1, nmax], ls="--", color="#9a9992", lw=1.5, label="Speedup ideal (linear)")
    rotulados = []   # rótulos seletivos: evita números sobrepostos no fim das linhas
    for v in COR:
        if v not in s:
            continue
        xs = [x for x, _, _ in s[v]]
        sp = [ts / m["tempo_simulacao"] for _, m, _ in s[v]]
        a1.plot(xs, sp, marker=MARCA[v], color=COR[v], label=NOME[v])
        if all(abs(sp[-1] - y) > 0.5 for y in rotulados):
            rotulados.append(sp[-1])
            a1.annotate(f"{sp[-1]:.1f}x", (xs[-1], sp[-1]), textcoords="offset points",
                        xytext=(6, 0), va="center", fontsize=10, color="#0b0b0b")
        a2.plot(xs, [100 * p / x for p, x in zip(sp, xs)], marker=MARCA[v], color=COR[v],
                label=NOME[v])
    a1.set(title=f"Speedup — {titulo}", xlabel="Nº de threads / processos", ylabel="Speedup")
    a2.set(title=f"Eficiência — {titulo}", xlabel="Nº de threads / processos",
           ylabel="Eficiência (%)", ylim=(0, 110))
    a2.axhline(100, ls="--", color="#9a9992", lw=1.5)
    for a in (a1, a2):
        a.set_xticks(sorted({x for pts in s.values() for x, _, _ in pts}))
    a1.legend(loc="upper left", fontsize=9)
    salvar(fig, f"{exp}_speedup_eficiencia.png")

    md.append(f"\n### {exp} — {titulo}\n")
    md.append(f"Cenário: {cen[1]}x{cen[1]}, {cen[2]} gerações, {cen[3]:.0%} espalhadores, "
              f"modo {cen[4]}. Sequencial: **{ts:.3f} s**.\n")
    md.append("| Versão | n | Tempo sim. (s) | Speedup | Eficiência | Speedup c/ inicialização | Correto |")
    md.append("|---|---:|---:|---:|---:|---:|:-:|")
    tt = seq(ag, cen)["tempo_total"]
    for v in COR:
        for x, m, _ in s.get(v, []):
            sp = ts / m["tempo_simulacao"]
            md.append(f"| {NOME[v]} | {x} | {m['tempo_simulacao']:.3f} | {sp:.2f} | "
                      f"{100 * sp / x:.0f}% | {tt / m['tempo_total']:.2f} | "
                      f"{'sim' if m['correto'] else 'NÃO'} |")

    # decomposição do tempo da versão distribuída
    if "distribuido" in s:
        pts = s["distribuido"]
        xs = [str(x) for x, _, _ in pts]
        calc = [m["tempo_calc_max"] for _, m, _ in pts]
        comm = [m["tempo_comm"] for _, m, _ in pts]
        sinc = [m["tempo_sinc"] for _, m, _ in pts]
        fig, ax = plt.subplots(figsize=(8, 4.8))
        ax.bar(xs, calc, color="#2a78d6", label="Cálculo (worker mais lento)",
               edgecolor="#fcfcfb", linewidth=2)
        ax.bar(xs, comm, bottom=calc, color="#eb6834", label="Troca de bordas (média)",
               edgecolor="#fcfcfb", linewidth=2)
        ax.bar(xs, sinc, bottom=[a + b for a, b in zip(calc, comm)], color="#eda100",
               label="Redução global + espera (média)", edgecolor="#fcfcfb", linewidth=2)
        ax.set(title=f"Distribuído: para onde vai o tempo — {titulo}",
               xlabel="Nº de processos worker", ylabel="Tempo (s)")
        ax.legend()
        salvar(fig, f"{exp}_distribuido_decomposicao.png")
        md.append("\n| n | Cálculo máx (s) | Bordas (s) | Sincronização (s) | % comunicação+sinc. | Bytes de borda | Mensagens de borda |")
        md.append("|---:|---:|---:|---:|---:|---:|---:|")
        for (x, m, _), c, o, si in zip(pts, calc, comm, sinc):
            tot = c + o + si
            md.append(f"| {x} | {c:.3f} | {o:.3f} | {si:.3f} | {100 * (o + si) / tot:.1f}% | "
                      f"{int(m['bytes_bordas']):,} | {int(m['msgs_bordas']):,} |")


def grafico_fator(ag, exp, titulo, rotulo_x, x_de, md, logx=False, fmt=str):
    s = series(ag, exp, lambda c, n, h, b: x_de(c), lambda c, v, n, h, b: True)
    if not s:
        return
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5))
    linhas_md = []
    for v in COR:
        if v not in s:
            continue
        xs = [x for x, _, _ in s[v]]
        a1.plot(xs, [m["tempo_simulacao"] for _, m, _ in s[v]], marker=MARCA[v],
                color=COR[v], label=NOME[v])
        if v != "sequencial":
            sp = []
            for x, m, c in s[v]:
                ref = seq(ag, c)
                sp.append(ref["tempo_simulacao"] / m["tempo_simulacao"])
                linhas_md.append((v, x, m, ref, sp[-1]))
            a2.plot(xs, sp, marker=MARCA[v], color=COR[v], label=NOME[v])
    for a in (a1, a2):
        if logx:
            a.set_xscale("log")
        a.set_xticks(sorted({x for pts in s.values() for x, _, _ in pts}))
        a.set_xticklabels([fmt(x) for x in a.get_xticks()])
        a.minorticks_off()
    if exp == "E4":
        # referência: sequencial SEM a otimização de frente (custo independe do %)
        sem = [m for (c, v, *_), m in ag.items() if c[0] == "E4" and c[5] == "0"]
        if sem:
            a1.axhline(sem[0]["tempo_simulacao"], ls=":", color="#52514e", lw=1.5,
                       label="Sequencial sem otimização")
    a1.set(title=f"Tempo — {titulo}", xlabel=rotulo_x, ylabel="Tempo de simulação (s)")
    a2.set(title=f"Speedup — {titulo}", xlabel=rotulo_x, ylabel="Speedup")
    a1.legend(fontsize=9, loc="best")
    salvar(fig, f"{exp}_tempo_speedup.png")

    n_w = next((n for (c, v, n, h, b) in ag if c[0] == exp and v != "sequencial"), "?")
    md.append(f"\n### {exp} — {titulo} (n = {n_w})\n")
    md.append(f"| {rotulo_x} | Versão | Sequencial (s) | Versão (s) | Speedup | Eficiência |")
    md.append("|---:|---|---:|---:|---:|---:|")
    for v, x, m, ref, sp in sorted(linhas_md, key=lambda t: (t[1], t[0])):
        md.append(f"| {fmt(x)} | {NOME[v]} | {ref['tempo_simulacao']:.3f} | "
                  f"{m['tempo_simulacao']:.3f} | {sp:.2f} | {100 * sp / n_w:.0f}% |")


def grafico_halo(ag, md):
    s = defaultdict(list)
    for (c, v, n, h, b), m in ag.items():
        if c[0] == "E5" and v == "distribuido":
            s[c].append((h, m))
    if not s:
        return
    fig, axs = plt.subplots(1, len(s), figsize=(6.5 * len(s), 4.8), squeeze=False)
    md.append("\n### E5 — Profundidade do halo (custo de comunicação)\n")
    md.append("| Matriz | Halo H | Tempo sim. (s) | Speedup | Bordas (s) | Sinc. (s) | Mensagens de borda | Bytes de borda |")
    md.append("|---:|---:|---:|---:|---:|---:|---:|---:|")
    for ax, (c, pts) in zip(axs[0], sorted(s.items(), key=lambda t: t[0][1])):
        pts.sort()
        ref = seq(ag, c)["tempo_simulacao"]
        hs = [str(h) for h, _ in pts]
        calc = [m["tempo_calc_max"] for _, m in pts]
        comm = [m["tempo_comm"] for _, m in pts]
        sinc = [m["tempo_sinc"] for _, m in pts]
        ax.bar(hs, calc, color="#2a78d6", label="Cálculo (incl. redundante)", edgecolor="#fcfcfb", linewidth=2)
        ax.bar(hs, comm, bottom=calc, color="#eb6834", label="Troca de bordas", edgecolor="#fcfcfb", linewidth=2)
        ax.bar(hs, sinc, bottom=[a + b for a, b in zip(calc, comm)], color="#eda100",
               label="Redução global + espera", edgecolor="#fcfcfb", linewidth=2)
        ax.set(title=f"Halo profundo — matriz {c[1]}x{c[1]}", xlabel="Profundidade do halo H",
               ylabel="Tempo (s)")
        for h, m in pts:
            md.append(f"| {c[1]} | {h} | {m['tempo_simulacao']:.3f} | {ref / m['tempo_simulacao']:.2f} | "
                      f"{m['tempo_comm']:.4f} | {m['tempo_sinc']:.4f} | {int(m['msgs_bordas']):,} | "
                      f"{int(m['bytes_bordas']):,} |")
    h, l = axs[0][0].get_legend_handles_labels()
    fig.legend(h, l, loc="lower center", ncol=3, frameon=False)
    fig.tight_layout(rect=(0, 0.08, 1, 1))
    fig.savefig(os.path.join(PASTA_G, "E5_halo.png"), dpi=150)
    plt.close(fig)
    print("  gráfico: E5_halo.png")


def grafico_balanceamento(ag, md):
    itens = []
    for (c, v, n, h, b), m in ag.items():
        if c[0] == "E6":
            nome = {"sequencial": "Sequencial",
                    "paralelo-processos-estatico": "Estático",
                    "distribuido": "Distribuído\n(estático)"}.get(v, f"Dinâmico\nbloco={b}")
            itens.append((v, b, nome, m, c))
    if not itens:
        return
    ordem = ["sequencial", "paralelo-processos-estatico", "paralelo-processos-dinamico", "distribuido"]
    itens.sort(key=lambda t: (ordem.index(t[0]), int(t[1] or 0)))
    ref = seq(ag, itens[0][4])["tempo_simulacao"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 4.8))
    nomes = [t[2] for t in itens]
    a1.bar(nomes, [t[3]["tempo_simulacao"] for t in itens], color=[COR[t[0]] for t in itens],
           edgecolor="#fcfcfb", linewidth=2)
    a1.set(title="Carga concentrada: tempo de simulação", ylabel="Tempo (s)")
    par = [t for t in itens if t[0] != "sequencial"]
    a2.bar([t[2] for t in par], [100 * t[3]["desbalanceamento"] for t in par],
           color=[COR[t[0]] for t in par], edgecolor="#fcfcfb", linewidth=2)
    a2.set(title="Desbalanceamento (máx/média − 1)", ylabel="%")
    for a in (a1, a2):
        a.tick_params(axis="x", labelsize=9)
    salvar(fig, "E6_balanceamento.png")
    md.append("\n### E6 — Balanceamento de carga (espalhadores só no 1/4 superior + otimização de frente)\n")
    md.append("| Estratégia | Tempo sim. (s) | Speedup | Desbalanceamento |")
    md.append("|---|---:|---:|---:|")
    for v, b, nome, m, c in itens:
        md.append(f"| {nome.replace(chr(10), ' ')} | {m['tempo_simulacao']:.3f} | "
                  f"{ref / m['tempo_simulacao']:.2f} | "
                  f"{'-' if v == 'sequencial' else f'{100 * m['desbalanceamento']:.0f}%'} |")


def grafico_original(md):
    caminho = os.path.join(PASTA, "original_vs_refatorado.csv")
    if not os.path.exists(caminho):
        return
    with open(caminho) as f:
        rs = list(csv.DictReader(f))
    to = statistics.median(float(r["tempo_original"]) for r in rs)
    tr = statistics.median(float(r["tempo_refatorado"]) for r in rs)
    fig, ax = plt.subplots(figsize=(6.5, 4))
    ax.barh(["Refatorado\n(bytearray + moldura)", "FakeNews.py\noriginal"], [tr, to],
            color=["#2a78d6", "#9a9992"], edgecolor="#fcfcfb", linewidth=2, height=0.55)
    for y, t in enumerate([tr, to]):
        ax.text(t, y, f"  {t:.2f} s", va="center")
    ax.set(title=f"Sequencial: original x refatorado ({rs[0]['tamanho']}², {rs[0]['geracoes']} ger.)",
           xlabel="Tempo (s)")
    salvar(fig, "E7_original_vs_refatorado.png")
    md.append("\n### E7 — Código original x sequencial refatorado\n")
    md.append(f"Matriz {rs[0]['tamanho']}x{rs[0]['tamanho']}, {rs[0]['geracoes']} gerações: "
              f"original **{to:.3f} s**, refatorado **{tr:.3f} s** → **{to / tr:.2f}x** mais rápido, "
              f"com resultado idêntico.\n")


def main():
    linhas = carregar()
    ag = agrupar(linhas)
    errados = sum(1 for r in linhas if not r["correto"])
    md = ["# Tabelas de resultados", "",
          f"Gerado automaticamente por `graficos.py` a partir de {len(linhas)} execuções. "
          f"Execuções com resultado diferente do sequencial: **{errados}**.", "",
          "Tempos = mediana das repetições do laço de gerações. Speedup = T_seq / T_versão; "
          "eficiência = speedup / n."]
    grafico_escalabilidade(ag, "E1", "modo clássico", md)
    grafico_escalabilidade(ag, "E1b", "modo estendido", md)
    grafico_fator(ag, "E2", "tamanho da matriz", "Lado da matriz (N x N)",
                  lambda c: c[1], md, logx=True, fmt=lambda x: f"{int(x)}")
    grafico_fator(ag, "E3", "número de gerações", "Gerações", lambda c: c[2], md,
                  logx=True, fmt=lambda x: f"{int(x)}")
    grafico_fator(ag, "E4", "% inicial de espalhadores (otimização de frente)",
                  "Espalhadores iniciais", lambda c: c[3] if c[5] == "1" else None, md,
                  logx=True, fmt=lambda x: f"{100 * x:g}%")
    grafico_halo(ag, md)
    grafico_balanceamento(ag, md)
    grafico_original(md)
    with open(os.path.join(PASTA, "tabelas.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print("  tabelas: resultados/tabelas.md")


if __name__ == "__main__":
    main()
