"""STAM — simulação do controle de acesso a um compartimento por entrega.

Neste exemplo, represento a leitura do crachá RFID por uma entrada no teclado
e o estado das travas por variáveis. Utilizo identificadores fictícios.
Execução: python3 controle_acesso_stam.py
"""

import json
from datetime import datetime, timezone
from uuid import uuid4


# Associo cada crachá a uma identificação funcional e a um perfil.
# Os perfis são exemplos para demonstrar as decisões do fluxograma.
CADASTRO = {
    "F01": ("prof-01", "farmácia"),
    "E01": ("prof-02", "enfermeiro"),
    "T01": ("prof-03", "técnico de enfermagem"),
}


def registrar(entrega, evento, **dados):
    """Acrescenta um evento ao histórico e preserva as entregas anteriores."""
    registro = {
        "instante_utc": datetime.now(timezone.utc).isoformat(),
        "entrega": entrega,
        "evento": evento,
        **dados,
    }
    with open("historico_stam.jsonl", "a", encoding="utf-8") as arquivo:
        arquivo.write(json.dumps(registro, ensure_ascii=False) + "\n")


def identificar(entrega, etapa, perfil_exigido, **contexto):
    """Repete a identificação até encontrar o perfil exigido para esta etapa."""
    while True:
        cracha = input(f"Crachá para {etapa}: ").strip().upper()
        pessoa, perfil = CADASTRO.get(cracha, ("desconhecido", None))
        if perfil == perfil_exigido:
            registrar(entrega, "acesso autorizado", etapa=etapa,
                      profissional=pessoa, perfil_exigido=perfil_exigido, **contexto)
            return pessoa

        # Registro a recusa antes de solicitar outro crachá. A trava continua
        # fechada porque a função só devolve o controle após a autorização.
        registrar(entrega, "acesso negado", etapa=etapa, profissional=pessoa,
                  perfil_exigido=perfil_exigido, **contexto)
        print("Acesso negado. Apresente outro crachá.")


def escolher(mensagem, opcoes):
    """Aceita somente uma das opções apresentadas no terminal."""
    while True:
        valor = input(f"{mensagem} ({' / '.join(opcoes)}): ").strip()
        if valor in opcoes:
            return valor
        print("Selecione uma das opções indicadas.")


def executar_entrega():
    # 1. Inicio o ciclo na base, com os dois nichos travados. O identificador
    # permite reunir todos os registros de uma mesma entrega no histórico.
    entrega = uuid4().hex
    travado = {"1": True, "2": True}
    registrar(entrega, "início na base", travado=travado)
    print("STAM na base. Os dois compartimentos estão travados.")

    # 2. Verifico o vínculo com a farmácia antes de liberar o nicho escolhido.
    responsavel = identificar(entrega, "carregamento", "farmácia")
    nicho = escolher("Compartimento para o carregamento", travado)
    travado[nicho] = False
    input(f"Nicho {nicho} liberado. Pressione Enter após inserir a carga. ")
    destino = escolher("Destino", ("Posto A", "Posto B"))
    perfil = escolher("Perfil exigido para esta carga",
                      ("enfermeiro", "técnico de enfermagem"))
    contexto = {"nicho": nicho, "destino": destino}

    # 3. Ao confirmar o fechamento, associo carga, destino, perfil e
    # responsável. O segundo nicho mantém seu estado durante toda a operação.
    input("Feche o compartimento e pressione Enter para confirmar. ")
    travado[nicho] = True
    registrar(entrega, "carregamento concluído", profissional=responsavel,
              perfil_exigido=perfil, travado=travado, **contexto)

    # 4. Represento o percurso por eventos de bancada. As mensagens abaixo
    # simulam a sinalização prevista. A opção de emergência representa a
    # interrupção da missão, sem acionar motores ou um botão físico.
    print(f"Aviso sonoro simulado. Transporte para {destino}.")
    evento = escolher("Evento durante o transporte", ("chegada", "emergência"))
    if evento == "emergência":
        registrar(entrega, "transporte interrompido", travado=travado, **contexto)
        print("Missão interrompida com a carga travada.")
        return

    print(f"Chegada a {destino}. Recebimento autorizado para: {perfil}.")
    registrar(entrega, "chegada ao destino", **contexto)

    # 5. Recupero o perfil definido na origem. Um crachá cadastrado com outro
    # perfil também gera recusa, mesmo que pertença a um profissional conhecido.
    recebedor = identificar(entrega, "recebimento", perfil, **contexto)
    travado[nicho] = False
    input(f"Nicho {nicho} liberado. Retire a carga, feche o nicho e pressione Enter. ")

    # 6. Registro o recebimento após a confirmação de retirada e fechamento.
    # Só então represento o retorno do robô à base.
    travado[nicho] = True
    registrar(entrega, "recebimento concluído", profissional=recebedor,
              travado=travado, **contexto)
    registrar(entrega, "retorno simulado à base", **contexto)
    print("Recebimento registrado. STAM de volta à base.")


if __name__ == "__main__":
    executar_entrega()
