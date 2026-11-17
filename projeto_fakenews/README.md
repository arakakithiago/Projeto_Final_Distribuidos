# Propagação de Fake News — versões Sequencial, Paralela e Distribuída

Simulação da propagação de uma fake news numa população representada por uma
matriz 2D (autômato celular, vizinhança de Moore). Partindo do `FakeNews.py`
fornecido, o projeto implementa:

| Versão | Tecnologia | Arquivo |
|---|---|---|
| Sequencial (linha de base) | Python puro | [fakenews/sequencial.py](fakenews/sequencial.py) |
| Paralela | `multiprocessing` + `shared_memory` + barreiras (e `threading` para comparação) | [fakenews/paralelo.py](fakenews/paralelo.py) |
| Distribuída | Sockets TCP, coordenador + workers, troca de bordas peer-to-peer | [fakenews/distribuido/](fakenews/distribuido/) |

As três versões usam **o mesmo kernel** ([fakenews/modelo.py](fakenews/modelo.py)) e produzem
**resultados idênticos bit a bit**, o que é verificado automaticamente por `verificar.py`.

A explicação completa (modelo, decisões, melhorias, resultados, referências) está em
**[docs/RELATORIO.md](docs/RELATORIO.md)**.

---

## Requisitos

- Python 3.10 ou mais novo (testado no 3.15)
- Simulação: **só a biblioteca padrão**. Nada de NumPy/Numba etc. (a proposta proíbe).
- Gráficos e visualização: `matplotlib` (que já traz o Pillow)

```bash
pip install -r requirements.txt
```

## Como executar

Todos os comandos são rodados **dentro da pasta `projeto_fakenews/`**.

### 1. Verificar a correção (recomendado primeiro)
```bash
python verificar.py
```
Compara o sequencial com o `FakeNews.py` original e depois compara paralelo e
distribuído com o sequencial (vários cenários e nº de workers). Ao final deve aparecer
`TODAS AS VERSÕES SÃO EQUIVALENTES`.

### 2. Rodar uma simulação
```bash
# mesmos parâmetros do FakeNews.py original
python executar.py sequencial  --tamanho 100 --geracoes 50 --mostrar-geracoes

# paralela com 8 processos
python executar.py paralelo    --tamanho 1024 --geracoes 20 --workers 8

# paralela com escalonamento dinâmico + otimização de frente
python executar.py paralelo    --tamanho 1024 --workers 8 --escalonamento dinamico --otimizar-frente

# paralela com threads (para ver o efeito do GIL)
python executar.py paralelo    --tamanho 512 --workers 4 --backend threads

# distribuída com 4 processos locais, halo de profundidade 4
python executar.py distribuido --tamanho 1024 --workers 4 --halo 4

# modelo estendido (probabilidades, resistência, influenciadores, bots)
python executar.py sequencial  --tamanho 300 --modo estendido --mostrar-geracoes
```
Use `python executar.py -h` para ver todos os parâmetros.

### 3. Distribuído em várias máquinas
Copie a pasta do projeto para todas as máquinas (mesma rede, porta liberada no firewall).

```bash
# Máquina A (coordenador, IP 192.168.0.10): 4 workers no total, 2 locais
python executar.py distribuido --tamanho 2048 --workers 4 \
       --host 0.0.0.0 --porta 5000 --locais 2 --ip-local 192.168.0.10

# Máquina B: inicia os 2 workers restantes
python worker_remoto.py --coordenador 192.168.0.10:5000
python worker_remoto.py --coordenador 192.168.0.10:5000
```
O coordenador espera os `--workers` se conectarem, informa a cada worker o endereço
do vizinho e a simulação começa. As bordas trafegam direto entre os workers.

### 4. Experimentos de desempenho, gráficos e visualização
```bash
python benchmark.py            # completo (~30 min); --rapido para um teste de ~1 min
python graficos.py             # gera resultados/graficos/*.png e resultados/tabelas.md
python visualizar.py           # GIF da propagação + curvas (resultados/visualizacao/)
python ambiente.py             # configuração da máquina (resultados/ambiente.json)
```

## Estrutura

```
projeto_fakenews/
├── fakenews/
│   ├── config.py             parâmetros (dataclass Config)
│   ├── modelo.py             estados, codificação em bytes, regras, kernel `passo`, RNG por contador
│   ├── resultado.py          resultado comum + estatísticas adicionais
│   ├── sequencial.py         versão sequencial
│   ├── paralelo.py           versão paralela (processos | threads; escalonamento estático | dinâmico)
│   └── distribuido/
│       ├── protocolo.py      mensagens binárias com cabeçalho (tipo, tamanho)
│       ├── coordenador.py    distribui a grade, faz a redução global, decide a parada, coleta
│       └── worker.py         calcula a faixa, troca ghost rows com os vizinhos (halo profundo)
├── referencia/FakeNews_original.py   código fornecido (sem alterações), usado na verificação
├── executar.py               linha de comando para as 3 versões
├── worker_remoto.py          worker para outra máquina
├── verificar.py              testes de equivalência
├── benchmark.py              experimentos E1–E7
├── graficos.py               gráficos + tabelas
├── visualizar.py             GIF + curvas de estados
├── ambiente.py               configuração experimental
├── docs/RELATORIO.md         documentação técnica completa
└── resultados/               CSVs, gráficos, tabelas, visualizações
```

## Uso de IA generativa
Conforme exigido pela proposta: este código e a documentação foram desenvolvidos com
apoio do assistente Claude (Anthropic). Todo o material deve ser revisado,
compreendido e validado pelos integrantes do grupo. Ver a seção de referências do relatório.
