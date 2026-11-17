"""
Versão DISTRIBUÍDA (sockets TCP), arquitetura coordenador + workers.

    coordenador.py : cria a grade, distribui faixas de linhas, agrega as
                     contagens (redução global), decide a parada e coleta o
                     resultado final.
    worker.py      : calcula sua faixa e troca linhas de fronteira
                     DIRETAMENTE com os workers vizinhos (peer-to-peer).
    protocolo.py   : formato binário das mensagens.
"""
