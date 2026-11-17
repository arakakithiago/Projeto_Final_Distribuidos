"""
Estrutura comum de resultado + estatísticas adicionais (melhoria).

Todas as versões devolvem um `Resultado`, o que permite ao benchmark e ao
verificador tratá-las de forma uniforme.
"""

from dataclasses import dataclass, field

from .modelo import assinatura


@dataclass
class Resultado:
    versao: str                       # "sequencial", "paralelo-processos", ...
    cfg: object                       # Config usada
    historico: list                   # [(ignorantes, espalhadores, inativos)] por geração (0 = inicial)
    tempo_simulacao: float            # só o laço de gerações (s)
    tempo_total: float                # inclui criação de processos/conexões, distribuição e coleta (s)
    grade: bytearray = None           # grade final (com moldura)
    workers: int = 1
    detalhes: dict = field(default_factory=dict)   # métricas específicas (comunicação, etc.)

    @property
    def geracoes_executadas(self):
        return len(self.historico) - 1

    @property
    def assinatura(self):
        return assinatura(self.grade, self.cfg.linhas, self.cfg.colunas)

    # ------------- estatísticas adicionais -------------
    def estatisticas(self):
        total = self.cfg.linhas * self.cfg.colunas
        esp = [h[1] for h in self.historico]
        pico = max(esp)
        g_pico = esp.index(pico)
        ign_final, esp_final, inat_final = self.historico[-1]
        alcance = (total - ign_final) / total   # quem chegou a receber a notícia
        # novos convencidos por geração = queda no nº de ignorantes
        novos = [self.historico[g - 1][0] - self.historico[g][0]
                 for g in range(1, len(self.historico))]
        return {
            "populacao": total,
            "pico_espalhadores": pico,
            "geracao_do_pico": g_pico,
            "alcance_final_%": 100 * alcance,
            "ignorantes_finais_%": 100 * ign_final / total,
            "inativos_finais_%": 100 * inat_final / total,
            "max_novos_por_geracao": max(novos) if novos else 0,
            "geracoes_executadas": self.geracoes_executadas,
        }

    def imprimir(self, mostrar_geracoes=False):
        cfg = self.cfg
        total = cfg.linhas * cfg.colunas
        print(f"=== {self.versao.upper()} | {cfg.linhas}x{cfg.colunas} ({total:,} pessoas) | "
              f"modo {cfg.modo} | workers {self.workers} ===")
        if mostrar_geracoes:
            for g, (ign, esp, inat) in enumerate(self.historico):
                print(f"Geração {g:03d} | Ignorantes: {ign:>10,} | "
                      f"Espalhadores: {esp:>10,} | Inativos: {inat:>10,}")
        st = self.estatisticas()
        ign, esp, inat = self.historico[-1]
        print(f"Gerações executadas : {self.geracoes_executadas}")
        print(f"Ignorantes finais   : {ign:,} ({100 * ign / total:.2f}%)")
        print(f"Espalhadores finais : {esp:,} ({100 * esp / total:.2f}%)")
        print(f"Inativos finais     : {inat:,} ({100 * inat / total:.2f}%)")
        print(f"Pico de espalhadores: {st['pico_espalhadores']:,} na geração {st['geracao_do_pico']}")
        print(f"Alcance final       : {st['alcance_final_%']:.2f}% da população")
        print(f"Tempo de simulação  : {self.tempo_simulacao:.4f} s")
        print(f"Tempo total         : {self.tempo_total:.4f} s")
        for k, v in self.detalhes.items():
            if isinstance(v, float):
                print(f"{k:<20}: {v:.4f}")
            elif not isinstance(v, (list, dict)):
                print(f"{k:<20}: {v}")
        print(f"Assinatura da grade : {self.assinatura}")
