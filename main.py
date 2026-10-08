from .rotina_de_acessos import criar_rotina_de_acessos
from .rotina_de_rescisoes import criar_rotina_de_rescisoes

class AdmitidosRotina:
    def main(self, simular: bool = False) -> None:
        print('início rotina de Admitidos')
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
            print(f"FALHA  na rotina admitidos: {falha}")

        print("fim da rotina de admitidos")


class RescindidosRotina:
    def main(self, simular: bool = False) -> None:
        print("início rotina de Rescisões")
        resultado = criar_rotina_de_rescisoes(simular=simular).executar()

        if simular:
            print("SIMULAÇÃO — nada foi aberto nem gravado\n")
            if not resultado.linhas:
                print(
                    f"Nenhum chamado a abrir: {resultado.rescindidos} rescisão(ões) nova(s), "
                    f"{resultado.ja_tinham_rescisao_pedida} já tinham inativação pedida"
                )
            else:
                print(resultado.titulo)
                for celulas in resultado.linhas:
                    print("   " + " | ".join(celulas))
                print(f"\nSeguidores: {resultado.seguidores}")
        elif resultado.abriu_chamado:
            print(
                f"Chamado {resultado.chamado_aberto} aberto para "
                f"{resultado.rescindidos} rescisão(ões), {resultado.seguidores} em cópia"
            )
        elif resultado.ja_tinham_rescisao_pedida:
            print(
                f"Nenhuma rescisão nova: {resultado.ja_tinham_rescisao_pedida} "
                f"já tinham inativação pedida"
            )
        else:
            print("Nenhuma rescisão nova")

        for falha in resultado.falhas:
            print(f"FALHA: {falha}")
        print("fim da rotina de rescisões")
