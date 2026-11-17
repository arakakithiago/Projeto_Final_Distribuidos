"""
Parâmetros da simulação.

Todas as versões (sequencial, paralela e distribuída) recebem o MESMO objeto
Config. Como a grade inicial e todos os sorteios aleatórios são derivados
apenas destes parâmetros (em especial da `semente`), as três versões produzem
exatamente o mesmo resultado — o que é verificado por `verificar.py`.
"""

from dataclasses import dataclass, asdict, fields


@dataclass
class Config:
    # ---------------- Parâmetros do modelo original ----------------
    linhas: int = 100
    colunas: int = 100
    geracoes: int = 50
    percentual_espalhadores: float = 0.05
    limiar: int = 3                    # (modo clássico) nº mínimo de vizinhos espalhadores
    semente: int = 42

    # "classico"  -> regra idêntica ao FakeNews.py fornecido (determinística)
    # "estendido" -> modelo probabilístico com resistência, influenciadores e bots
    modo: str = "classico"

    # Encerra a simulação quando não houver mais espalhadores (igual ao original).
    parar_sem_espalhadores: bool = True

    # ---------------- Melhorias computacionais ----------------
    # Pula as linhas onde nada pode mudar (nenhum espalhador na linha nem nas vizinhas).
    otimizar_frente: bool = False
    # Coloca os espalhadores iniciais apenas no 1/4 superior da grade
    # (cenário usado para demonstrar desbalanceamento de carga).
    foco_inicial: bool = False

    # ---------------- Parâmetros do modo estendido ----------------
    prob_contagio: float = 0.30        # chance de UM vizinho comum convencer por geração
    prob_esquecer: float = 0.50        # chance de um espalhador parar de compartilhar
    resistencia_max: float = 0.90      # resistência individual sorteada em [0, resistencia_max]
    perc_influenciadores: float = 0.01 # fração da população que é influenciadora
    peso_influenciador: int = 4        # um influenciador "vale" por N vizinhos comuns
    perc_bots: float = 0.002           # fração da população que é bot (nunca para de espalhar)

    def para_dict(self):
        """Converte para dicionário (usado para enviar a config pela rede em JSON)."""
        return asdict(self)

    @classmethod
    def de_dict(cls, d):
        """Reconstrói a Config a partir de um dicionário, ignorando chaves desconhecidas."""
        nomes = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in nomes})

    def validar(self):
        if self.linhas < 1 or self.colunas < 1:
            raise ValueError("A grade precisa ter pelo menos 1x1.")
        if self.modo not in ("classico", "estendido"):
            raise ValueError("modo deve ser 'classico' ou 'estendido'.")
        if self.linhas >= 2 ** 24 or self.colunas >= 2 ** 24 or self.geracoes >= 2 ** 14:
            # limites do gerador aleatório baseado em contador (ver modelo.aleatorio_u32)
            raise ValueError("Limites: linhas/colunas < 16.777.216 e gerações < 16.384.")
        if not 1 <= self.peso_influenciador <= 31:
            raise ValueError("peso_influenciador deve estar entre 1 e 31.")
