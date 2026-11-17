"""
Modelo computacional da propagação de Fake News (autômato celular).

======================================================================
1. ESTADOS (iguais ao código sequencial fornecido)
======================================================================
    0 = IGNORANTE  : ainda não recebeu / não acredita na notícia
    1 = ESPALHADOR : acredita e compartilha
    2 = INATIVO    : já recebeu, mas não compartilha mais

======================================================================
2. REPRESENTAÇÃO DA GRADE  (melhoria computacional)
======================================================================
O código original usa lista de listas de inteiros (cada inteiro Python ocupa
~28 bytes + 8 do ponteiro) e faz `deepcopy` a cada geração. Aqui a grade é um
único `bytearray` contíguo, 1 byte por indivíduo, em ordem de linhas
(row-major). Vantagens:

  * 36x menos memória e cópia/fatiamento em velocidade de memcpy;
  * uma faixa de linhas é um bloco contíguo de bytes -> pode ser colocada
    diretamente em memória compartilhada (versão paralela) ou enviada por
    socket sem serialização (versão distribuída);
  * permite usar `bytes.translate` (tabela de 256 entradas, executada em C
    sequencialmente — NÃO é paralelismo implícito) para extrair informações
    de todas as células de uma vez.

Moldura (padding): a grade tem 1 linha e 1 coluna extras de cada lado,
sempre IGNORANTE. Assim o laço não precisa testar se o vizinho está fora da
matriz (o código original testa `0 <= ni < linhas` 8 vezes por célula).

    largura W = colunas + 2
    célula (i, j) da matriz  ->  índice (i + 1) * W + (j + 1)

Cada byte guarda o indivíduo inteiro:

    bit  7 6 5 4 | 3 2 | 1 0
         resist. | tipo| estado

    estado      : IGNORANTE / ESPALHADOR / INATIVO
    tipo        : NORMAL / INFLUENCIADOR / BOT        (modo estendido)
    resistência : nível 0..15                         (modo estendido)

Como tipo e resistência viajam junto com o estado, a versão distribuída não
precisa de nenhuma mensagem extra para conhecer os vizinhos das bordas.

======================================================================
3. REGRAS DE TRANSIÇÃO
======================================================================
Modo "classico" (idêntico ao FakeNews.py fornecido):
    IGNORANTE  -> ESPALHADOR se nº de vizinhos espalhadores >= limiar
    ESPALHADOR -> INATIVO
    INATIVO    -> INATIVO

Modo "estendido" (melhorias de modelagem, ver docs/RELATORIO.md):
    IGNORANTE  -> ESPALHADOR com probabilidade
                  P = [1 - (1 - p)^k] * (1 - resistência)
                  onde k = soma dos "pesos" dos vizinhos espalhadores
                  (vizinho comum = 1, influenciador = peso_influenciador).
                  É a regra de "cascata independente" (Kempe et al., 2003):
                  cada vizinho tem uma chance independente p de convencer.
    ESPALHADOR -> INATIVO com probabilidade prob_esquecer
                  (perda de interesse, como no modelo Daley-Kendall)
    BOT        -> permanece ESPALHADOR para sempre
    INATIVO    -> INATIVO

======================================================================
4. ALEATORIEDADE REPRODUTÍVEL EM PARALELO  (melhoria)
======================================================================
Se cada thread/processo usasse seu próprio `random`, o resultado dependeria
da quantidade de workers e da ordem de execução. Em vez disso usamos um
gerador baseado em CONTADOR (Salmon et al., 2011): o número aleatório de uma
célula é uma função hash pura de (semente, geração, linha, coluna, canal).
Qualquer processo, em qualquer máquina, calcula o MESMO valor para a mesma
célula -> as versões sequencial, paralela e distribuída são idênticas bit a bit.

======================================================================
5. O "KERNEL" `passo`
======================================================================
`passo(atual, nova, W, r0, r1, desloc, geracao, regras)` calcula a próxima
geração para as linhas [r0, r1) de um buffer local. É a MESMA função usada
pelas três versões; o que muda é apenas quem chama e sobre qual pedaço:

    sequencial  -> grade inteira
    paralelo    -> um bloco de linhas copiado da memória compartilhada
    distribuído -> a faixa do worker + linhas fantasmas (ghost rows)

`desloc` converte linha local em linha global (necessário para o gerador
aleatório baseado em contador).
"""

import hashlib
import random

# ----------------------------------------------------------------------
# Constantes
# ----------------------------------------------------------------------
IGNORANTE = 0
ESPALHADOR = 1
INATIVO = 2

NORMAL = 0
INFLUENCIADOR = 1
BOT = 2

NIVEIS_RESISTENCIA = 16

MASCARA_ESTADO = 0b0000_0011
MASCARA_TIPO = 0b0000_1100
MASCARA_RESIST = 0b1111_0000

_M64 = 0xFFFFFFFFFFFFFFFF
_U32 = 1 << 32

# "canais" separam sorteios diferentes da mesma célula na mesma geração
CANAL_CONTAGIO = 0
CANAL_ESQUECER = 1


def codificar(estado, tipo=NORMAL, resistencia=0):
    """Empacota (estado, tipo, resistência) em um único byte."""
    return estado | (tipo << 2) | (resistencia << 4)


def decodificar(byte):
    """Desempacota um byte em (estado, tipo, resistência)."""
    return byte & 3, (byte >> 2) & 3, byte >> 4


# ----------------------------------------------------------------------
# Gerador aleatório baseado em contador
# ----------------------------------------------------------------------
def aleatorio_u32(semente, geracao, i, j, canal):
    """
    Retorna um inteiro pseudoaleatório em [0, 2^32) que depende SOMENTE dos
    argumentos (função pura, sem estado).

    1) monta uma chave única: geração (14 bits) | linha (24) | coluna (24) | canal (2)
    2) aplica o finalizador do SplitMix64 (Steele, Lea e Flood, 2014), que
       espalha qualquer mudança de 1 bit da entrada por toda a saída.
    """
    x = ((geracao << 50) | (i << 26) | (j << 2) | canal) ^ semente
    x = (x + 0x9E3779B97F4A7C15) & _M64
    x = ((x ^ (x >> 30)) * 0xBF58476D1CE4E5B9) & _M64
    x = ((x ^ (x >> 27)) * 0x94D049BB133111EB) & _M64
    x ^= x >> 31
    return x >> 32


# ----------------------------------------------------------------------
# Regras pré-calculadas
# ----------------------------------------------------------------------
class Regras:
    """
    Pré-calcula tudo o que depende só da Config, para o laço principal fazer
    o mínimo de trabalho por célula. Cada processo/worker constrói a sua.

    Tabelas de 256 posições (uma para cada valor possível de byte):
        tab_contrib : quanto a célula "pesa" como vizinha (0 se não espalha)
        tab_estado  : só o estado (0, 1 ou 2) -> usada para contar
        tab_fixa    : transições que não dependem de vizinhos nem de sorteio
                      (clássico: ESPALHADOR -> INATIVO; o resto fica igual)
    """

    def __init__(self, cfg):
        cfg.validar()
        self.estendido = cfg.modo == "estendido"
        self.limiar = cfg.limiar
        self.otimizar = cfg.otimizar_frente
        # mistura a semente para que sementes próximas (42, 43) gerem fluxos bem diferentes
        self.semente = int.from_bytes(
            hashlib.sha256(str(cfg.semente).encode()).digest()[:8], "little")

        peso_inf = cfg.peso_influenciador if self.estendido else 1
        contrib = bytearray(256)
        estado = bytearray(256)
        fixa = bytearray(256)
        for b in range(256):
            s = b & MASCARA_ESTADO
            t = (b & MASCARA_TIPO) >> 2
            estado[b] = s
            if s == ESPALHADOR:
                contrib[b] = peso_inf if t == INFLUENCIADOR else 1
            if s == ESPALHADOR and not self.estendido:
                fixa[b] = (b & ~MASCARA_ESTADO & 0xFF) | INATIVO
            else:
                fixa[b] = b
        self.tab_contrib = bytes(contrib)
        self.tab_estado = bytes(estado)
        self.tab_fixa = bytes(fixa)

        if self.estendido:
            # lim_conv[(k << 4) | nivel] = P(convencer) * 2^32
            # Compara-se um inteiro aleatório u32 < lim  (evita float no laço).
            k_max = 8 * peso_inf
            p = cfg.prob_contagio
            self.lim_conv = [0] * ((k_max + 1) << 4)
            for k in range(k_max + 1):
                p_vizinhos = 1.0 - (1.0 - p) ** k
                for nivel in range(NIVEIS_RESISTENCIA):
                    resist = nivel / (NIVEIS_RESISTENCIA - 1) * cfg.resistencia_max
                    self.lim_conv[(k << 4) | nivel] = int(p_vizinhos * (1.0 - resist) * _U32)
            self.lim_esquecer = int(cfg.prob_esquecer * _U32)


# ----------------------------------------------------------------------
# Criação da grade inicial
# ----------------------------------------------------------------------
def criar_grade(cfg):
    """
    Cria a grade inicial (com moldura) como bytearray.

    No modo clássico a sequência de sorteios é EXATAMENTE a do FakeNews.py
    original (random.seed(semente) + randint(i), randint(j) por espalhador),
    portanto a grade inicial é idêntica à do código fornecido.
    Obs.: como no original, um mesmo ponto pode ser sorteado duas vezes, então
    o nº real de espalhadores pode ser um pouco menor que o percentual.
    """
    L, C = cfg.linhas, cfg.colunas
    W = C + 2
    rng = random.Random(cfg.semente)
    grade = bytearray((L + 2) * W)

    total = L * C
    linha_max = L - 1
    if cfg.foco_inicial:
        linha_max = max(0, L // 4 - 1)
    posicoes = []
    for _ in range(int(total * cfg.percentual_espalhadores)):
        i = rng.randint(0, linha_max)
        j = rng.randint(0, C - 1)
        posicoes.append((i + 1) * W + j + 1)

    if cfg.modo == "estendido":
        # resistência: 1 byte aleatório por célula, aproveitando só os 4 bits altos
        sorteio = rng.randbytes(total)
        nibble_alto = bytes(b & MASCARA_RESIST for b in range(256))
        for i in range(L):
            a = (i + 1) * W + 1
            grade[a:a + C] = sorteio[i * C:(i + 1) * C].translate(nibble_alto)

    for k in posicoes:
        grade[k] = (grade[k] & ~MASCARA_ESTADO & 0xFF) | ESPALHADOR

    if cfg.modo == "estendido":
        def sortear_celula():
            return (rng.randint(0, L - 1) + 1) * W + rng.randint(0, C - 1) + 1

        for _ in range(int(total * cfg.perc_influenciadores)):
            k = sortear_celula()
            grade[k] = (grade[k] & ~MASCARA_TIPO & 0xFF) | (INFLUENCIADOR << 2)
        for _ in range(int(total * cfg.perc_bots)):
            k = sortear_celula()
            grade[k] = (BOT << 2) | ESPALHADOR   # bots já começam espalhando
    return grade


# ----------------------------------------------------------------------
# Kernel: cálculo de uma geração
# ----------------------------------------------------------------------
def passo(atual, nova, W, r0, r1, desloc, geracao, regras):
    """
    Calcula a geração seguinte das linhas locais [r0, r1) de `atual`,
    escrevendo o resultado nas MESMAS linhas de `nova`.

    Requisitos: as linhas r0-1 e r1 de `atual` precisam existir (vizinhos),
    e `atual` nunca é modificado -> dupla bufferização, sem condição de corrida
    entre células da mesma geração.

    atual, nova : bytearrays com o mesmo layout (W bytes por linha)
    desloc      : linha_global = linha_local + desloc
    geracao     : índice da geração sendo calculada (para o sorteio)
    """
    # (1) Pesos de vizinhança de todas as células de uma vez (C, sequencial).
    e = atual.translate(regras.tab_contrib)
    # (2) Transições "fixas" já aplicadas; o laço só corrige o que depende de vizinhos.
    fixa = atual.translate(regras.tab_fixa)
    nova[r0 * W:r1 * W] = fixa[r0 * W:r1 * W]

    # (3) Otimização da frente de propagação: linha r só pode mudar se houver
    #     espalhador em r-1, r ou r+1. bytes.count(0, ini, fim) não copia dados.
    if regras.otimizar:
        tem_esp = [e.count(0, r * W, (r + 1) * W) != W for r in range(r0 - 1, r1 + 1)]

    estendido = regras.estendido
    limiar = regras.limiar
    if estendido:
        semente = regras.semente
        lim_conv = regras.lim_conv
        lim_esq = regras.lim_esquecer

    for r in range(r0, r1):
        if regras.otimizar:
            t = r - r0  # tem_esp[t] = linha r-1, [t+1] = r, [t+2] = r+1
            if not (tem_esp[t] or tem_esp[t + 1] or tem_esp[t + 2]):
                continue  # nada muda nesta linha (já copiada em (2))

        a = r * W
        if not estendido:
            # -------- Regra clássica (determinística) --------
            for k in range(a + 1, a + W - 1):
                if not atual[k] & 3:  # IGNORANTE
                    if (e[k - W - 1] + e[k - W] + e[k - W + 1] +
                            e[k - 1] + e[k + 1] +
                            e[k + W - 1] + e[k + W] + e[k + W + 1]) >= limiar:
                        nova[k] = atual[k] | ESPALHADOR
        else:
            # -------- Regra estendida (probabilística) --------
            gi = r + desloc  # linha global
            for k in range(a + 1, a + W - 1):
                c = atual[k]
                s = c & 3
                if s == IGNORANTE:
                    v = (e[k - W - 1] + e[k - W] + e[k - W + 1] +
                         e[k - 1] + e[k + 1] +
                         e[k + W - 1] + e[k + W] + e[k + W + 1])
                    if v:
                        lim = lim_conv[(v << 4) | (c >> 4)]
                        if lim and aleatorio_u32(semente, geracao, gi, k - a - 1,
                                                 CANAL_CONTAGIO) < lim:
                            nova[k] = c | ESPALHADOR
                elif s == ESPALHADOR and (c & MASCARA_TIPO) != (BOT << 2):
                    if aleatorio_u32(semente, geracao, gi, k - a - 1,
                                     CANAL_ESQUECER) < lim_esq:
                        nova[k] = (c & ~MASCARA_ESTADO & 0xFF) | INATIVO


# ----------------------------------------------------------------------
# Utilitários
# ----------------------------------------------------------------------
def contar(buf, W, r0, r1, regras):
    """
    Conta (ignorantes, espalhadores, inativos) nas linhas [r0, r1) de `buf`.
    As colunas da moldura valem 0 e por isso são descontadas dos ignorantes.
    """
    estados = bytes(buf[r0 * W:r1 * W]).translate(regras.tab_estado)
    esp = estados.count(ESPALHADOR)
    inat = estados.count(INATIVO)
    return (r1 - r0) * (W - 2) - esp - inat, esp, inat


def interior(grade, L, C):
    """Extrai a matriz L x C sem a moldura (bytes contíguos)."""
    W = C + 2
    return b"".join(bytes(grade[(i + 1) * W + 1:(i + 1) * W + 1 + C]) for i in range(L))


def assinatura(grade, L, C):
    """Hash SHA-256 do estado final -> usado para provar que as versões são idênticas."""
    return hashlib.sha256(interior(grade, L, C)).hexdigest()[:16]


def dividir_linhas(L, n):
    """
    Divide L linhas em n faixas contíguas [ini, fim) o mais iguais possível
    (as primeiras L % n faixas recebem uma linha a mais).
    """
    base, resto = divmod(L, n)
    faixas, ini = [], 0
    for p in range(n):
        fim = ini + base + (1 if p < resto else 0)
        faixas.append((ini, fim))
        ini = fim
    return faixas
