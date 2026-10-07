import sys

from rotina_de_acessos import criar_rotina_de_acessos

class AdmitidosRotina():
    def main(simular: bool = False) -> None:
        resultado = criar_rotina_de_acessos(simular=simular).executar()

        if simular:
            print("SIMULAÇÃO — nada foi aberto nem gravado\n")
            if not resultado.linhas:
                print(
                    f"Nenhum chamado a abrir: {resultado.admitidos} admitido(s) novo(s), "
                    f"{resultado.ja_tinham_acesso_pedido} já tinham acesso pedido"
                )
            else:
                print(resultado.titulo)
                for celulas in resultado.linhas:
                    print("   " + " | ".join(celulas))
                print(f"\nSeguidores: {resultado.seguidores}")
                if resultado.gestores_sem_acesso_ao_acelerato:
                    print("Sem conta no Acelerato: " + ", ".join(resultado.gestores_sem_acesso_ao_acelerato))
            print(f"Em acompanhamento: {resultado.chamados_acompanhados}")
            return

        if resultado.abriu_chamado:
            print(
                f"Chamado {resultado.chamado_aberto} aberto para "
                f"{resultado.admitidos} admitido(s), {resultado.seguidores} gestor(es) em cópia"
            )
        elif resultado.ja_tinham_acesso_pedido:
            print(
                f"Nenhum admitido novo: {resultado.ja_tinham_acesso_pedido} já tinham acesso pedido"
            )
        else:
            print("Nenhum admitido novo")

        if resultado.gestores_sem_acesso_ao_acelerato:
            print(
                "Sem conta no Acelerato (não entram em cópia): "
                + ", ".join(resultado.gestores_sem_acesso_ao_acelerato)
            )

        print(
            f"Acompanhados: {resultado.chamados_acompanhados} | "
            f"Encerrados agora: {resultado.chamados_concluidos or 'nenhum'}"
        )

        for falha in resultado.falhas:
            print(f"FALHA: {falha}")


if __name__ == "__main__":
    rotina = AdmitidosRotina()
    rotina.main(simular="--simular" in sys.argv)
