# Propagação de Fake News em Sistemas Paralelos e Distribuídos
### Relatório técnico

> Documento-base para a apresentação (PDF) e o vídeo. Cada seção corresponde a um item
> exigido na proposta. Os números da seção 8 vêm de `resultados/tabelas.md` e
> são gerados automaticamente por `benchmark.py` + `graficos.py`.

---

## 1. Descrição do problema

A população é uma matriz L × C, e cada célula é um indivíduo. A cada **geração discreta**
cada indivíduo olha seus **8 vizinhos (vizinhança de Moore)** e muda de estado:

| Estado | Significado |
|---|---|
| 0 — Ignorante | ainda não recebeu ou não acredita na notícia |
| 1 — Espalhador | acredita e compartilha |
| 2 — Inativo | já recebeu, mas não compartilha mais |

É um **autômato celular** (Wolfram, 1983) com dinâmica do tipo *rumor spreading*
(Daley & Kendall, 1964; Maki & Thompson, 1973), em que ignorante, espalhador e inativo
correspondem a *ignorant*, *spreader* e *stifler*.

O objetivo do trabalho é transformar o código sequencial fornecido em versões **paralela**
e **distribuída**, mantendo exatamente o mesmo comportamento lógico, e analisar
desempenho, gargalos e custo de comunicação.

## 2. Modelo computacional

### 2.1 Regra clássica (idêntica ao `FakeNews.py`)
```
Ignorante  -> Espalhador  se (nº de vizinhos espalhadores) >= limiar
Espalhador -> Inativo
Inativo    -> Inativo
```
A próxima geração é calculada **somente a partir da geração atual** (atualização síncrona).
Por isso o problema é naturalmente paralelo *dentro* de uma geração: cada célula pode ser
calculada de forma independente. *Entre* gerações há dependência, e é preciso sincronizar.

### 2.2 Regra estendida (melhorias de modelagem, `--modo estendido`)
| Elemento | Regra | Justificativa |
|---|---|---|
| **Contágio probabilístico** | ignorante vira espalhador com P = 1 − (1 − p)^k | Modelo de cascata independente (Kempe, Kleinberg & Tardos, 2003): cada vizinho espalhador tem chance independente *p* de convencer. Um limiar fixo é determinístico demais. |
| **Resistência individual** | P é multiplicada por (1 − r), com r ∈ [0, r_max] sorteado por pessoa (16 níveis) | Populações são heterogêneas: alguns checam fatos e outros não. Isso gera regiões que não são atingidas. |
| **Influenciadores** | um espalhador influenciador conta como *w* vizinhos (padrão 4) | Nós de alto grau aceleram rumores (Moreno, Nekovee & Pacheco, 2004). |
| **Bots** | começam espalhando e nunca ficam inativos | Bots sociais amplificam conteúdo de baixa credibilidade (Shao et al., 2018). |
| **Esquecimento** | espalhador vira inativo com probabilidade q por geração | Perda de interesse (*stifling*) do modelo Daley-Kendall. Em vez de durar 1 geração, o espalhador fica ativo em média 1/q gerações. |

### 2.3 Representação dos dados
Cada indivíduo ocupa **1 byte** num único `bytearray` contíguo, com uma **moldura** de
células vazias ao redor da matriz:

```
bit:  7 6 5 4 | 3 2  | 1 0
      resist. | tipo | estado          largura W = colunas + 2
```

- **Moldura (padding):** os vizinhos fora da matriz existem e são "ignorantes", então o laço
  não testa limites. O original faz 8 comparações `0 <= ni < linhas` por célula.
- **Dupla bufferização:** dois buffers, um de leitura e um de escrita, trocados por
  referência. O original faz `deepcopy` da matriz inteira a cada geração.
- **`bytes.translate`** (tabela de 256 entradas, executada em C de forma *sequencial*)
  extrai de uma vez o "peso de vizinho" de todas as células e aplica as transições que não
  dependem de vizinhos. Não há paralelismo implícito aqui: isso é igual nas três versões.
- Tipo e resistência ficam **dentro do byte**, então as linhas de borda enviadas pela rede
  já carregam toda a informação necessária.

### 2.4 Aleatoriedade reprodutível em paralelo
Para que o modo estendido dê **o mesmo resultado com 1, 4 ou 16 workers**, o sorteio de uma
célula não pode depender de qual processo a calcula nem da ordem de cálculo. Usamos um
**gerador baseado em contador** (Salmon et al., 2011): o número aleatório é uma função *pura*
`hash(semente, geração, linha, coluna, canal)`, com o finalizador do SplitMix64
(Steele, Lea & Flood, 2014). Qualquer processo, em qualquer máquina, obtém o mesmo valor.

## 3. Solução sequencial
[fakenews/sequencial.py](../fakenews/sequencial.py)

```
criar grade (mesma sequência de random.seed/randint do original)
para g em 0..G-1:
    passo(atual -> nova, linhas 1..L)       # kernel compartilhado
    trocar atual <-> nova                   # O(1)
    contar estados; registrar histórico
    se não há espalhadores: parar
```
Ela é verificada contra o `FakeNews.py` original: o histórico de contagens e a grade final
são idênticos. Também é **≈3× mais rápida** que o original (experimento E7), e é ela a
linha de base do speedup. Assim o ganho medido vem só da paralelização, e não de
otimizações misturadas.

## 4. Versão paralela
[fakenews/paralelo.py](../fakenews/paralelo.py)

### 4.1 Por que processos, e não threads?
No CPython com GIL, só uma thread executa bytecode Python por vez. Este kernel é 100% Python,
então threads **não dão speedup**: isso foi medido (experimento E1, curva "threads + GIL").
A proposta permite `multiprocessing` explicitamente. Cada processo tem seu próprio
interpretador e GIL, e o paralelismo é real. O backend de threads foi mantido com o mesmo
algoritmo para demonstrar o problema. Num Python *free-threaded* (PEP 703) ele escalaria.

### 4.2 Divisão da matriz
- **Estático:** faixas contíguas de ≈ L/n linhas, uma por worker (as primeiras L mod n
  faixas ganham +1 linha).
- **Dinâmico (self-scheduling):** a matriz é cortada em blocos de *b* linhas, e cada worker
  pega o próximo bloco livre num contador compartilhado protegido por `Lock`.

```
 linha 0   ┌───────────────┐            ┌───────────────┐ bloco 0 -> w2
           │   worker 0    │            ├───────────────┤ bloco 1 -> w0
           ├───────────────┤            ├───────────────┤ bloco 2 -> w1
           │   worker 1    │            ├───────────────┤ bloco 3 -> w2
           ├───────────────┤            ├───────────────┤ ...
           │   worker 2    │            ├───────────────┤ (quem termina
 linha L-1 └───────────────┘            └───────────────┘  pega o próximo)
              ESTÁTICO                      DINÂMICO
```

### 4.3 Sincronização e ausência de condições de corrida
- Dois buffers em **memória compartilhada** (`multiprocessing.shared_memory`): na geração *g*
  todos **leem** `buf[g%2]` e **escrevem** em `buf[(g+1)%2]`.
- Cada linha do buffer de escrita pertence a exatamente um bloco, e cada bloco a um worker.
  Não há duas escritas na mesma posição.
- Ninguém escreve no buffer que está sendo lido.
- **Duas barreiras** por geração (`inicio` e `fim`) garantem que a geração g+1 só começa
  depois que toda a geração g terminou. Isso mantém a consistência entre gerações.
- O processo principal soma as contagens de cada worker, que ficam num vetor compartilhado
  com uma posição por worker (sem disputa), e decide a parada. O único ponto de exclusão
  mútua é o contador de blocos do escalonamento dinâmico.
- Os workers são criados **uma única vez** e reaproveitados em todas as gerações.

## 5. Versão distribuída
[fakenews/distribuido/](../fakenews/distribuido/)

### 5.1 Arquitetura
```
                       ┌─────────────────────┐
           OLA / INIT  │    COORDENADOR      │  ESTAT ─► soma ─► DECISAO
         ┌────────────►│  (redução global)   │◄──────────────┐
         │             └─────────────────────┘               │
   ┌───────────┐  BORDA  ┌───────────┐  BORDA  ┌───────────┐
   │ worker 0  │◄───────►│ worker 1  │◄───────►│ worker 2  │
   │ linhas    │ TCP     │ linhas    │ TCP     │ linhas    │
   │ 0..k-1    │ direto  │ k..2k-1   │ direto  │ 2k..L-1   │
   └───────────┘         └───────────┘         └───────────┘
```
1. Cada worker conecta ao coordenador, abre uma porta de escuta e envia `OLA`.
2. O coordenador cria a grade, divide em **faixas de linhas** e envia `INIT`: id, faixa,
   endereço do vizinho de baixo e as linhas iniciais.
3. Cada worker **conecta ao vizinho de baixo e aceita o de cima**. Como todos já estão
   escutando antes do `INIT`, o `connect` completa pela fila do `listen` e não há deadlock.
   As conexões são **persistentes**.
4. A cada ciclo: troca de bordas → cálculo → envio das contagens (`ESTAT`) → espera
   `DECISAO`. É uma redução global equivalente a um `MPI_Allreduce`.
5. No final cada worker envia sua faixa (`FINAL`), e o coordenador remonta a matriz.

### 5.2 Sincronização das fronteiras (ghost rows)
Para calcular sua primeira linha, o worker *i* precisa da última linha do worker *i−1*.
Cada worker guarda **linhas fantasmas** (cópias das linhas vizinhas) acima e abaixo da sua
faixa. Elas são atualizadas por troca de mensagens antes de cada cálculo. O envio roda numa
thread auxiliar enquanto a thread principal recebe: se os dois lados fizessem `sendall`
grande antes de `recv`, ocorreria deadlock com os buffers do socket cheios.

### 5.3 Protocolo
Mensagens binárias com cabeçalho fixo `[tipo: 1 byte][tamanho: 4 bytes]` seguido do
conteúdo. TCP é um fluxo de bytes, por isso o tamanho é necessário. Uma linha de 1024
pessoas vai como 1026 bytes crus, sem JSON e sem parsing. `TCP_NODELAY` desliga o
algoritmo de Nagle, o que reduz a latência das mensagens pequenas.

### 5.4 Redução de comunicação: halo profundo (*ghost cell expansion*)
Com halo de profundidade H (Ding & He, 2001), os workers trocam **H linhas a cada H
gerações** em vez de 1 linha por geração. Depois da troca, o worker calcula H gerações
seguidas e recalcula de forma redundante parte das linhas fantasmas, que "estragam" 1 linha
por geração a partir da ponta:

```
passo s = 0      calcula linhas [1 , H+n+H-1)     (só não dá p/ calcular a ponta)
passo s = 1      calcula linhas [2 , H+n+H-2)
...
passo s = H-1    calcula linhas [H , H+n)         = exatamente as linhas próprias
```
É uma troca de **latência** (H vezes menos mensagens e menos barreiras globais) por
**cálculo redundante** (≈ H² linhas extras por ciclo). Os resultados continuam idênticos,
o que é conferido pelo `verificar.py`.

### 5.5 Vários computadores
O coordenador pode lançar parte dos workers localmente (`--locais`) e esperar o restante
de outras máquinas (`worker_remoto.py --coordenador IP:PORTA`). O worker anuncia o IP pelo
qual alcançou o coordenador, que repassa esse endereço ao vizinho.

## 6. Garantia de consistência
`verificar.py` executa:
1. sequencial × `FakeNews.py` original (3 cenários): histórico e grade final idênticos;
2. 5 cenários (clássico, estendido, otimização de frente, foco inicial, dimensões que não
   dividem igualmente) × 11 configurações paralelas e distribuídas (1–5 workers, estático e
   dinâmico, threads, halo 1–4): **histórico de contagens e hash SHA-256 da grade final
   iguais aos do sequencial**.

O benchmark também confere *cada* execução contra o sequencial (coluna `correto` do CSV).

## 7. Configuração experimental
<!-- AMBIENTE -->

## 8. Resultados
<!-- RESULTADOS -->

## 9. Melhorias implementadas (resumo)
<!-- MELHORIAS -->

## 10. Dificuldades encontradas
- **GIL:** a primeira abordagem natural (threads) não acelera código Python puro. A solução
  foi usar processos com memória compartilhada, e o backend de threads ficou como evidência.
- **Custo de criar processos no Windows:** o método `spawn` reimporta o interpretador em
  cada processo (≈0,1–0,3 s). Por isso os workers são criados uma única vez, e o tempo de
  inicialização é medido separadamente (`tempo_total` × `tempo_simulacao`).
- **Reprodutibilidade com aleatoriedade:** um `random` por processo daria resultados
  diferentes conforme o nº de workers. A solução foi o RNG baseado em contador (seção 2.4).
- **Deadlock na troca de bordas:** se dois workers vizinhos fazem `sendall` grande ao mesmo
  tempo antes de `recv`, ambos travam com o buffer do socket cheio. A solução foi o envio em
  thread auxiliar e a ordem fixa de conexão (conecta embaixo, aceita em cima).
- **TCP sem fronteiras de mensagem:** `recv` pode devolver mensagens partidas ou
  concatenadas. A solução foi o cabeçalho com tamanho + `receber_exato`.
- **Halo profundo:** acertar os intervalos de linhas recalculadas a cada passo e o
  tratamento dos workers da borda (sem vizinho) exigiu testes de equivalência sistemáticos.
- **Medição:** como o tempo varia entre execuções, cada ponto foi repetido 3 vezes e usamos
  a mediana. Tempo de inicialização e tempo de simulação são reportados separadamente.

## 11. Referências

**Modelo**
1. DALEY, D. J.; KENDALL, D. G. Epidemics and rumours. *Nature*, v. 204, p. 1118, 1964.
2. MAKI, D. P.; THOMPSON, M. *Mathematical Models and Applications*. Prentice-Hall, 1973.
3. WOLFRAM, S. Statistical mechanics of cellular automata. *Reviews of Modern Physics*, v. 55, n. 3, p. 601–644, 1983.
4. KEMPE, D.; KLEINBERG, J.; TARDOS, É. Maximizing the spread of influence through a social network. In: *ACM SIGKDD*, p. 137–146, 2003.
5. MORENO, Y.; NEKOVEE, M.; PACHECO, A. F. Dynamics of rumor spreading in complex networks. *Physical Review E*, v. 69, 066130, 2004.
6. VOSOUGHI, S.; ROY, D.; ARAL, S. The spread of true and false news online. *Science*, v. 359, n. 6380, p. 1146–1151, 2018.
7. SHAO, C. et al. The spread of low-credibility content by social bots. *Nature Communications*, v. 9, 4787, 2018.

**Paralelismo, distribuição e otimizações**

8. AMDAHL, G. M. Validity of the single processor approach to achieving large scale computing capabilities. In: *AFIPS Spring Joint Computer Conference*, p. 483–485, 1967.
9. GUSTAFSON, J. L. Reevaluating Amdahl's law. *Communications of the ACM*, v. 31, n. 5, p. 532–533, 1988.
10. GRAMA, A.; GUPTA, A.; KARYPIS, G.; KUMAR, V. *Introduction to Parallel Computing*. 2. ed. Addison-Wesley, 2003.
11. PACHECO, P. *An Introduction to Parallel Programming*. Morgan Kaufmann, 2011.
12. TANENBAUM, A. S.; VAN STEEN, M. *Distributed Systems: Principles and Paradigms*. 2. ed. Pearson, 2007.
13. COULOURIS, G.; DOLLIMORE, J.; KINDBERG, T.; BLAIR, G. *Distributed Systems: Concepts and Design*. 5. ed. Addison-Wesley, 2011.
14. DING, C.; HE, Y. A ghost cell expansion method for reducing communications in solving PDE problems. In: *ACM/IEEE Supercomputing (SC'01)*, 2001.
15. SALMON, J. K.; MORAES, M. A.; DROR, R. O.; SHAW, D. E. Parallel random numbers: as easy as 1, 2, 3. In: *SC'11*, ACM, 2011.
16. STEELE, G. L.; LEA, D.; FLOOD, C. H. Fast splittable pseudorandom number generators. In: *OOPSLA*, ACM, p. 453–472, 2014.
17. POLYCHRONOPOULOS, C. D.; KUCK, D. J. Guided self-scheduling: a practical scheduling scheme for parallel supercomputers. *IEEE Transactions on Computers*, v. C-36, n. 12, p. 1425–1439, 1987.

**Documentação técnica**

18. Python Software Foundation. `multiprocessing`, `multiprocessing.shared_memory`, `threading`, `socket`, `struct`. Disponível em: https://docs.python.org/3/library/
19. GROSS, S. PEP 703 – Making the Global Interpreter Lock Optional in CPython, 2023. https://peps.python.org/pep-0703/
20. Código sequencial fornecido pelo professor (`FakeNews.py`).

**Uso de IA generativa:** o código e este relatório foram desenvolvidos com apoio do
assistente Claude (Anthropic, modelo Claude Opus 5.5, novembro de 2026), usado para
estruturar o código, sugerir otimizações e redigir a documentação. O grupo é responsável
por revisar, entender e validar todo o material.
