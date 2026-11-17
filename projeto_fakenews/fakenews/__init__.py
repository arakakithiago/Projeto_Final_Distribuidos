"""
Pacote da simulação de propagação de Fake News.

Módulos:
    config       -> parâmetros da simulação (dataclass Config)
    modelo       -> representação da grade, regras de transição e o "kernel"
                    que calcula uma geração (compartilhado por TODAS as versões)
    sequencial   -> versão sequencial (linha de base para o speedup)
    paralelo     -> versão paralela (multiprocessing ou threading)
    distribuido  -> versão distribuída (coordenador + workers via sockets TCP)
"""
