# Tabelas de resultados

Gerado automaticamente por `graficos.py` a partir de 315 execuções. Execuções com resultado diferente do sequencial: **0**.

Tempos = mediana das repetições do laço de gerações. Speedup = T_seq / T_versão; eficiência = speedup / n.

### E1 — modo clássico

Cenário: 1024x1024, 20 gerações, 5% espalhadores, modo classico. Sequencial: **3.122 s**.

| Versão | n | Tempo sim. (s) | Speedup | Eficiência | Speedup c/ inicialização | Correto |
|---|---:|---:|---:|---:|---:|:-:|
| Paralelo (processos, estático) | 1 | 3.132 | 1.00 | 100% | 0.95 | sim |
| Paralelo (processos, estático) | 2 | 1.625 | 1.92 | 96% | 1.75 | sim |
| Paralelo (processos, estático) | 4 | 0.902 | 3.46 | 87% | 2.89 | sim |
| Paralelo (processos, estático) | 6 | 0.657 | 4.75 | 79% | 3.56 | sim |
| Paralelo (processos, estático) | 8 | 0.695 | 4.49 | 56% | 3.34 | sim |
| Paralelo (processos, estático) | 12 | 0.527 | 5.92 | 49% | 3.77 | sim |
| Paralelo (processos, estático) | 16 | 0.533 | 5.86 | 37% | 3.47 | sim |
| Paralelo (processos, dinâmico) | 1 | 3.114 | 1.00 | 100% | 0.96 | sim |
| Paralelo (processos, dinâmico) | 2 | 1.609 | 1.94 | 97% | 1.77 | sim |
| Paralelo (processos, dinâmico) | 4 | 0.898 | 3.48 | 87% | 2.90 | sim |
| Paralelo (processos, dinâmico) | 6 | 0.630 | 4.95 | 83% | 3.69 | sim |
| Paralelo (processos, dinâmico) | 8 | 0.585 | 5.33 | 67% | 3.80 | sim |
| Paralelo (processos, dinâmico) | 12 | 0.509 | 6.13 | 51% | 3.84 | sim |
| Paralelo (processos, dinâmico) | 16 | 0.464 | 6.72 | 42% | 3.77 | sim |
| Paralelo (threads + GIL) | 1 | 3.196 | 0.98 | 98% | 0.98 | sim |
| Paralelo (threads + GIL) | 2 | 3.461 | 0.90 | 45% | 0.90 | sim |
| Paralelo (threads + GIL) | 4 | 3.452 | 0.90 | 23% | 0.90 | sim |
| Paralelo (threads + GIL) | 6 | 3.351 | 0.93 | 16% | 0.93 | sim |
| Paralelo (threads + GIL) | 8 | 3.346 | 0.93 | 12% | 0.93 | sim |
| Distribuído (sockets TCP) | 1 | 3.181 | 0.98 | 98% | 0.95 | sim |
| Distribuído (sockets TCP) | 2 | 1.667 | 1.87 | 94% | 1.76 | sim |
| Distribuído (sockets TCP) | 4 | 0.918 | 3.40 | 85% | 3.01 | sim |
| Distribuído (sockets TCP) | 6 | 0.695 | 4.49 | 75% | 3.75 | sim |
| Distribuído (sockets TCP) | 8 | 0.699 | 4.47 | 56% | 3.72 | sim |
| Distribuído (sockets TCP) | 12 | 0.536 | 5.82 | 48% | 4.38 | sim |
| Distribuído (sockets TCP) | 16 | 0.551 | 5.67 | 35% | 4.01 | sim |

| n | Cálculo máx (s) | Bordas (s) | Sincronização (s) | % comunicação+sinc. | Bytes de borda | Mensagens de borda |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 3.171 | 0.007 | 0.002 | 0.3% | 0 | 0 |
| 2 | 1.648 | 0.008 | 0.025 | 2.0% | 41,240 | 40 |
| 4 | 0.871 | 0.007 | 0.060 | 7.1% | 123,720 | 120 |
| 6 | 0.633 | 0.008 | 0.075 | 11.6% | 206,200 | 200 |
| 8 | 0.576 | 0.008 | 0.143 | 20.8% | 288,680 | 280 |
| 12 | 0.490 | 0.010 | 0.055 | 11.8% | 453,640 | 440 |
| 16 | 0.443 | 0.028 | 0.114 | 24.3% | 618,600 | 600 |

### E1b — modo estendido

Cenário: 1024x1024, 20 gerações, 5% espalhadores, modo estendido. Sequencial: **6.312 s**.

| Versão | n | Tempo sim. (s) | Speedup | Eficiência | Speedup c/ inicialização | Correto |
|---|---:|---:|---:|---:|---:|:-:|
| Paralelo (processos, estático) | 1 | 6.508 | 0.97 | 97% | 0.95 | sim |
| Paralelo (processos, estático) | 2 | 3.385 | 1.86 | 93% | 1.78 | sim |
| Paralelo (processos, estático) | 4 | 1.642 | 3.84 | 96% | 3.45 | sim |
| Paralelo (processos, estático) | 6 | 1.235 | 5.11 | 85% | 4.42 | sim |
| Paralelo (processos, estático) | 8 | 1.169 | 5.40 | 68% | 4.48 | sim |
| Paralelo (processos, estático) | 12 | 1.012 | 6.24 | 52% | 4.80 | sim |
| Paralelo (processos, estático) | 16 | 0.883 | 7.15 | 45% | 5.00 | sim |
| Distribuído (sockets TCP) | 1 | 6.195 | 1.02 | 102% | 1.01 | sim |
| Distribuído (sockets TCP) | 2 | 3.278 | 1.93 | 96% | 1.87 | sim |
| Distribuído (sockets TCP) | 4 | 1.632 | 3.87 | 97% | 3.62 | sim |
| Distribuído (sockets TCP) | 6 | 1.212 | 5.21 | 87% | 4.71 | sim |
| Distribuído (sockets TCP) | 8 | 1.152 | 5.48 | 68% | 4.86 | sim |
| Distribuído (sockets TCP) | 12 | 1.023 | 6.17 | 51% | 5.27 | sim |
| Distribuído (sockets TCP) | 16 | 0.890 | 7.09 | 44% | 5.75 | sim |

| n | Cálculo máx (s) | Bordas (s) | Sincronização (s) | % comunicação+sinc. | Bytes de borda | Mensagens de borda |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 6.184 | 0.007 | 0.003 | 0.2% | 0 | 0 |
| 2 | 3.253 | 0.007 | 0.036 | 1.3% | 41,240 | 40 |
| 4 | 1.603 | 0.007 | 0.031 | 2.3% | 123,720 | 120 |
| 6 | 1.159 | 0.007 | 0.070 | 6.2% | 206,200 | 200 |
| 8 | 0.998 | 0.008 | 0.173 | 15.4% | 288,680 | 280 |
| 12 | 0.927 | 0.009 | 0.144 | 14.1% | 453,640 | 440 |
| 16 | 0.829 | 0.017 | 0.060 | 8.5% | 618,600 | 600 |

### E2 — tamanho da matriz (n = 8)

| Lado da matriz (N x N) | Versão | Sequencial (s) | Versão (s) | Speedup | Eficiência |
|---:|---|---:|---:|---:|---:|
| 256 | Distribuído (sockets TCP) | 0.206 | 0.053 | 3.88 | 48% |
| 256 | Paralelo (processos, estático) | 0.206 | 0.039 | 5.22 | 65% |
| 512 | Distribuído (sockets TCP) | 0.788 | 0.175 | 4.49 | 56% |
| 512 | Paralelo (processos, estático) | 0.788 | 0.155 | 5.10 | 64% |
| 1024 | Distribuído (sockets TCP) | 3.112 | 0.655 | 4.75 | 59% |
| 1024 | Paralelo (processos, estático) | 3.112 | 0.520 | 5.98 | 75% |
| 2048 | Distribuído (sockets TCP) | 12.269 | 2.287 | 5.36 | 67% |
| 2048 | Paralelo (processos, estático) | 12.269 | 2.307 | 5.32 | 66% |

### E3 — número de gerações (n = 8)

| Gerações | Versão | Sequencial (s) | Versão (s) | Speedup | Eficiência |
|---:|---|---:|---:|---:|---:|
| 10 | Distribuído (sockets TCP) | 1.813 | 0.370 | 4.90 | 61% |
| 10 | Paralelo (processos, estático) | 1.813 | 0.357 | 5.07 | 63% |
| 20 | Distribuído (sockets TCP) | 3.127 | 0.646 | 4.84 | 61% |
| 20 | Paralelo (processos, estático) | 3.127 | 0.618 | 5.06 | 63% |
| 40 | Distribuído (sockets TCP) | 5.492 | 1.146 | 4.79 | 60% |
| 40 | Paralelo (processos, estático) | 5.492 | 1.125 | 4.88 | 61% |
| 80 | Distribuído (sockets TCP) | 10.176 | 2.120 | 4.80 | 60% |
| 80 | Paralelo (processos, estático) | 10.176 | 2.047 | 4.97 | 62% |

### E4 — % inicial de espalhadores (otimização de frente) (n = 8)

| Espalhadores iniciais | Versão | Sequencial (s) | Versão (s) | Speedup | Eficiência |
|---:|---|---:|---:|---:|---:|
| 0.1% | Distribuído (sockets TCP) | 0.511 | 0.208 | 2.45 | 31% |
| 0.1% | Paralelo (processos, dinâmico) | 0.511 | 0.155 | 3.30 | 41% |
| 0.1% | Paralelo (processos, estático) | 0.511 | 0.191 | 2.68 | 34% |
| 1% | Distribuído (sockets TCP) | 6.610 | 1.245 | 5.31 | 66% |
| 1% | Paralelo (processos, dinâmico) | 6.610 | 1.122 | 5.89 | 74% |
| 1% | Paralelo (processos, estático) | 6.610 | 1.240 | 5.33 | 67% |
| 5% | Distribuído (sockets TCP) | 4.463 | 0.866 | 5.15 | 64% |
| 5% | Paralelo (processos, dinâmico) | 4.463 | 0.702 | 6.36 | 79% |
| 5% | Paralelo (processos, estático) | 4.463 | 0.832 | 5.36 | 67% |
| 20% | Distribuído (sockets TCP) | 0.745 | 0.169 | 4.40 | 55% |
| 20% | Paralelo (processos, dinâmico) | 0.745 | 0.125 | 5.94 | 74% |
| 20% | Paralelo (processos, estático) | 0.745 | 0.139 | 5.38 | 67% |
| 50% | Distribuído (sockets TCP) | 0.407 | 0.097 | 4.22 | 53% |
| 50% | Paralelo (processos, dinâmico) | 0.407 | 0.067 | 6.08 | 76% |
| 50% | Paralelo (processos, estático) | 0.407 | 0.074 | 5.51 | 69% |

### E5 — Profundidade do halo (custo de comunicação)

| Matriz | Halo H | Tempo sim. (s) | Speedup | Bordas (s) | Sinc. (s) | Mensagens de borda | Bytes de borda |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 256 | 1 | 0.097 | 3.06 | 0.0114 | 0.0299 | 448 | 117,824 |
| 256 | 2 | 0.082 | 3.64 | 0.0060 | 0.0209 | 224 | 116,704 |
| 256 | 4 | 0.074 | 3.98 | 0.0034 | 0.0175 | 112 | 116,144 |
| 256 | 8 | 0.082 | 3.64 | 0.0022 | 0.0177 | 56 | 115,864 |
| 256 | 16 | 0.082 | 3.60 | 0.0016 | 0.0143 | 28 | 115,724 |
| 1024 | 1 | 0.932 | 4.94 | 0.0121 | 0.1777 | 448 | 461,888 |
| 1024 | 2 | 0.881 | 5.23 | 0.0070 | 0.1321 | 224 | 460,768 |
| 1024 | 4 | 0.849 | 5.43 | 0.0042 | 0.0942 | 112 | 460,208 |
| 1024 | 8 | 0.847 | 5.43 | 0.0025 | 0.0717 | 56 | 459,928 |
| 1024 | 16 | 0.854 | 5.39 | 0.0018 | 0.0418 | 28 | 459,788 |

### E6 — Balanceamento de carga (espalhadores só no 1/4 superior + otimização de frente)

| Estratégia | Tempo sim. (s) | Speedup | Desbalanceamento |
|---|---:|---:|---:|
| Sequencial | 0.403 | 1.00 | - |
| Estático | 0.173 | 2.33 | 98% |
| Dinâmico bloco=4 | 0.075 | 5.38 | 1% |
| Dinâmico bloco=16 | 0.111 | 3.63 | 6% |
| Dinâmico bloco=64 | 0.131 | 3.07 | 27% |
| Distribuído (estático) | 0.202 | 1.99 | 94% |

### E7 — Código original x sequencial refatorado

Matriz 512x512, 10 gerações: original **1.512 s**, refatorado **0.491 s** → **3.08x** mais rápido, com resultado idêntico.

