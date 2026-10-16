"""Base de exemplo da demo e conjunto de perguntas das evals de recuperação (ADR-0012).

Os documentos são fictícios. Cada pergunta aponta o documento que precisa voltar
entre os primeiros resultados: `literal` repete palavras do texto (passa até com o
embedder por hash do replay); `semantica` usa outras palavras e só mede embedder real.
"""

from dataclasses import dataclass

BASE_NAME = "Políticas de atendimento"
BASE_SLUG = "politicas_atendimento"
BASE_DESCRIPTION = "Troca e devolução, prazos de entrega, garantia e formas de pagamento"

DOCUMENTS: dict[str, str] = {
    "Troca e devolução": (
        "O cliente pode pedir a troca ou a devolução de um produto em até 30 dias corridos "
        "a partir do recebimento, desde que o item esteja sem uso e na embalagem original. "
        "A devolução por arrependimento de compra online vale por 7 dias, com reembolso "
        "integral, inclusive do frete. O reembolso no cartão aparece em até duas faturas; "
        "no Pix, cai em até 5 dias úteis depois que o item chega ao centro de distribuição."
    ),
    "Prazos de entrega": (
        "Pedidos aprovados até as 14h saem no mesmo dia útil. Capitais do Sudeste recebem "
        "em 1 a 3 dias úteis; demais capitais em 3 a 6 dias úteis; interior em até 10 dias "
        "úteis. Entrega expressa custa R$ 29,90 e chega no dia seguinte nas capitais do "
        "Sudeste. O código de rastreio é enviado por e-mail quando o pedido é despachado."
    ),
    "Garantia": (
        "Todos os produtos têm garantia legal de 90 dias contra defeito de fabricação. "
        "Eletrônicos têm garantia estendida de 12 meses oferecida pelo fabricante. Para "
        "acionar, o cliente envia a nota fiscal e fotos do defeito pelo portal; a análise "
        "técnica leva até 15 dias e, aprovada, o produto é consertado ou substituído. "
        "Dano por queda, umidade ou mau uso não é coberto."
    ),
    "Formas de pagamento": (
        "Aceitamos cartão de crédito em até 10 vezes sem juros para compras acima de "
        "R$ 300, Pix com 5% de desconto e boleto com vencimento em 3 dias úteis. Pedido "
        "pago com boleto só é separado depois da compensação, que leva até 2 dias úteis. "
        "Não aceitamos cheque nem pagamento na entrega."
    ),
}


@dataclass(frozen=True)
class EvalQuestion:
    question: str
    expected: str
    kind: str  # literal | semantica


QUESTIONS: list[EvalQuestion] = [
    EvalQuestion("Qual o prazo para devolução por arrependimento?", "Troca e devolução", "literal"),
    EvalQuestion("Em quantos dias úteis o reembolso no Pix cai?", "Troca e devolução", "literal"),
    EvalQuestion("Quanto custa a entrega expressa?", "Prazos de entrega", "literal"),
    EvalQuestion("Quando o código de rastreio é enviado?", "Prazos de entrega", "literal"),
    EvalQuestion("Quanto tempo de garantia legal os produtos têm?", "Garantia", "literal"),
    EvalQuestion("Dano por queda é coberto pela garantia?", "Garantia", "literal"),
    EvalQuestion("Qual o desconto no Pix?", "Formas de pagamento", "literal"),
    EvalQuestion("Vocês aceitam cheque?", "Formas de pagamento", "literal"),
    EvalQuestion(
        "Comprei pelo site e me arrependi, consigo meu dinheiro de volta?",
        "Troca e devolução",
        "semantica",
    ),
    EvalQuestion("Moro em Manaus, quando meu pedido chega?", "Prazos de entrega", "semantica"),
    EvalQuestion(
        "Meu notebook parou de ligar com dois meses de uso, o que faço?", "Garantia", "semantica"
    ),
    EvalQuestion("Dá para parcelar uma compra de 500 reais?", "Formas de pagamento", "semantica"),
]
