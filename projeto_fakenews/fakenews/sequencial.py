"""
Versão SEQUENCIAL — linha de base para o cálculo de speedup.

É o FakeNews.py original refatorado:
  * mesma regra (modo clássico) e mesma grade inicial;
  * grade em bytearray com moldura em vez de lista de listas;
  * dupla bufferização (troca de referências) em vez de deepcopy a cada geração;
  * o cálculo de uma geração é a função `modelo.passo`, a mesma usada pelas
    versões paralela e distribuída — assim a comparação de desempenho mede
    apenas o efeito da paralelização/distribuição, não diferenças de algoritmo.

Fluxo:
    criar grade -> [para cada geração: passo -> trocar buffers -> contar] -> resultado
"""

import time

from .modelo import Regras, criar_grade, passo, contar
from .resultado import Resultado


def simular(cfg, ao_fim_da_geracao=None):
    """
    Executa a simulação sequencial.

    ao_fim_da_geracao(g, grade): callback opcional (usado pela visualização
    para capturar quadros). Recebe o nº da geração e a grade atual.
    """
    t_inicio = time.perf_counter()
    regras = Regras(cfg)
    L, W = cfg.linhas, cfg.colunas + 2

    atual = criar_grade(cfg)
    nova = bytearray(len(atual))           # segundo buffer (moldura já zerada)
    historico = [contar(atual, W, 1, L + 1, regras)]
    if ao_fim_da_geracao:
        ao_fim_da_geracao(0, atual)

    t_sim = time.perf_counter()
    for g in range(cfg.geracoes):
        # linhas 1..L do buffer são a matriz; desloc=-1 converte para índice 0..L-1
        passo(atual, nova, W, 1, L + 1, -1, g, regras)
        atual, nova = nova, atual          # troca de buffers: O(1), sem cópia
        historico.append(contar(atual, W, 1, L + 1, regras))
        if ao_fim_da_geracao:
            ao_fim_da_geracao(g + 1, atual)
        if cfg.parar_sem_espalhadores and historico[-1][1] == 0:
            break
    t_fim = time.perf_counter()

    return Resultado("sequencial", cfg, historico,
                     tempo_simulacao=t_fim - t_sim,
                     tempo_total=t_fim - t_inicio,
                     grade=atual, workers=1)
