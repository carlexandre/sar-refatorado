from fpdf import FPDF
from sar.infrastructure.documents.templates import load_template, asset
from sar.domain.models import ResolvedInvoiceTemplate
import os


def _enc(texto: str) -> str:
    """Converte texto para latin-1, evitando erros de encoding no FPDF."""
    try:
        return str(texto).encode("latin-1", "replace").decode("latin-1")
    except Exception:
        return str(texto)


class FaturaPDF(FPDF):
    pass  # As faturas geralmente ocupam apenas uma folha rígida, não requer Header repetitivo


def _rgb(value):
    value = value.lstrip("#")
    return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))


def criar_fatura_pdf(dados: dict, template=None) -> bytes:
    """Gera a fatura em PDF idêntica ao modelo fornecido, mas com Itens Dinâmicos."""
    resource = load_template()
    template = template or ResolvedInvoiceTemplate(
        title_text=resource["issuer"]["title"],
        payment_terms=resource["issuer"]["payment_terms"],
    )
    font = template.font_family
    pdf = FaturaPDF(orientation="P", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_auto_page_break(auto=False)

    # ==========================================
    # LOGO E TÍTULO PRINCIPAL
    # ==========================================
    logo_path = asset(template.logo_asset)
    if os.path.exists(logo_path):
        pdf.image(logo_path, x=10, y=10, w=45, h=20)
    else:
        pdf.set_xy(10, 10)
        pdf.set_fill_color(30, 100, 180)
        pdf.rect(10, 10, 45, 20, "F")
        pdf.set_font(font, "B", 12)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(45, 20, "GIGAFOR", border=1, align="C", fill=True)

    pdf.set_xy(55, 10)
    pdf.set_font(font, "B", template.title_font_size)
    pdf.set_text_color(*_rgb(template.primary_color))
    pdf.set_draw_color(*_rgb(template.border_color))
    pdf.cell(145, 20, _enc(template.title_text), border=1, align="C")
    pdf.set_text_color(*_rgb(template.text_color))

    # ==========================================
    # BLOCO 1: DE / FATURA PARA
    # ==========================================
    pdf.set_xy(10, 35)
    pdf.set_font(font, "", template.body_font_size)

    pdf.cell(12, 5, _enc("DE:"), border="LT")
    pdf.cell(73, 5, _enc(load_template()["issuer"]["name"]), border="RT")
    pdf.cell(28, 5, _enc("FATURA PARA:"), border="LT")

    nome_cliente = dados.get("cliente_nome", "")
    # Reduz a fonte automaticamente até o texto caber na célula (largura 77mm)
    font_size_nome = 9
    pdf.set_font(font, "", font_size_nome)
    while pdf.get_string_width(_enc(nome_cliente)) > 74 and font_size_nome > 5:
        font_size_nome -= 0.5
        pdf.set_font(font, "", font_size_nome)
    pdf.cell(77, 5, _enc(nome_cliente), border="RT", ln=1)
    pdf.set_font(font, "", template.body_font_size)

    pdf.cell(12, 5, _enc("CNPJ:"), border="L")
    pdf.cell(73, 5, _enc(load_template()["issuer"]["cnpj"]), border="R")
    pdf.cell(12, 5, _enc("CNPJ:"), border="L")
    pdf.cell(93, 5, _enc(f"{dados.get('cliente_cnpj', '')}"), border="R", ln=1)

    pdf.cell(18, 5, _enc("Endereço:"), border="L")
    pdf.cell(42, 5, _enc(load_template()["issuer"]["address"]), border=0)
    pdf.cell(8, 5, _enc("Nº:"), border=0)
    pdf.cell(17, 5, _enc(load_template()["issuer"]["number"]), border="R")

    pdf.cell(18, 5, _enc("Endereço:"), border="L")
    pdf.cell(50, 5, _enc(f"{dados.get('cliente_end', '')}"), border=0)
    pdf.cell(8, 5, _enc("Nº:"), border=0)
    pdf.cell(29, 5, _enc(f"{dados.get('cliente_num', '')}"), border="R", ln=1)

    pdf.cell(15, 5, _enc("Cidade:"), border="L")
    pdf.cell(45, 5, _enc(load_template()["issuer"]["city"]), border=0)
    pdf.cell(12, 5, _enc("Estado:"), border=0)
    pdf.cell(13, 5, _enc(load_template()["issuer"]["state"]), border="R")

    pdf.cell(15, 5, _enc("Cidade:"), border="L")
    pdf.cell(50, 5, _enc(f"{dados.get('cliente_cidade', '')}"), border=0)
    pdf.cell(15, 5, _enc("Estado:"), border=0)
    pdf.cell(25, 5, _enc(f"{dados.get('cliente_uf', '')}"), border="R", ln=1)

    pdf.cell(12, 5, _enc("CEP:"), border="LB")
    pdf.cell(73, 5, _enc(load_template()["issuer"]["postal_code"]), border="RB")
    pdf.cell(12, 5, _enc("CEP:"), border="LB")
    pdf.cell(93, 5, _enc(f"{dados.get('cliente_cep', '')}"), border="RB", ln=1)

    pdf.ln(4)

    # ==========================================
    # BLOCO 2: INFORMAÇÕES DA FATURA
    # ==========================================
    pdf.cell(25, 6, _enc("Nº da fatura:"), border="LTB")
    pdf.cell(165, 6, _enc(f"{dados.get('fatura_num', '')}"), border="RTB", ln=1)

    pdf.cell(30, 6, _enc("Data da fatura:"), border="LTB")
    pdf.cell(65, 6, _enc(f"{dados.get('fatura_data', '')}"), border="RTB")
    pdf.cell(25, 6, _enc("Vencimento:"), border="LTB")
    pdf.cell(70, 6, _enc(f"{dados.get('fatura_venc', '')}"), border="RTB", ln=1)

    # [Melhoria 2] Demonstrar o período da fatura
    if template.show_period and dados.get("periodo_str"):
        pdf.cell(30, 6, _enc("Período Ref.:"), border="LTB")
        pdf.cell(160, 6, _enc(dados.get("periodo_str", "")), border="RTB", ln=1)

    pdf.ln(4)

    # ==========================================
    # BLOCO 3: TABELA DE PRODUTOS
    # ==========================================
    pdf.set_font(font, "B", 10)
    pdf.cell(115, 8, _enc("Descrição do produto/serviço:"), border=1, align="C")
    pdf.cell(20, 8, _enc("QTD:"), border=1, align="C")
    pdf.cell(30, 8, _enc("Preço unitário:"), border=1, align="C")
    pdf.cell(25, 8, _enc("Total:"), border=1, align="C", ln=1)

    pdf.set_font(font, "", template.body_font_size)

    # [Melhoria 1] Iteração Dinâmica de Itens
    itens = dados.get("itens", [])
    if not itens:
        itens = [{"descricao": "Conectividade à Rede GigaFOR", "quantidade": 1, "valor_unitario": 0.0}]

    total_fatura = 0.0
    h_usado = 0

    for item in itens:
        desc = item.get("descricao", "")
        qtd = item.get("quantidade", 1)
        val_un = float(item.get("valor_unitario", 0.0))
        tot = qtd * val_un
        total_fatura += tot

        x_start = pdf.get_x()
        y_start = pdf.get_y()

        pdf.multi_cell(115, 5, _enc(f"\n{desc}\n "), border="LBR", align="C")
        h = pdf.get_y() - y_start
        h_usado += h

        pdf.set_xy(x_start + 115, y_start)
        pdf.cell(20, h, _enc(str(qtd)), border=1, align="C")
        pdf.cell(
            30,
            h,
            _enc(f"R$ {val_un:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")),
            border=1,
            align="C",
        )
        pdf.cell(
            25,
            h,
            _enc(f"R$ {tot:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")),
            border=1,
            align="C",
            ln=1,
        )

    # Preenchimento em branco para empurrar o total dinamicamente
    h_blank = max(0, 50 - h_usado)
    if h_blank > 0:
        pdf.cell(115, h_blank, "", border=1)
        pdf.cell(20, h_blank, "", border=1)
        pdf.cell(30, h_blank, "", border=1)
        pdf.cell(25, h_blank, "", border=1, ln=1)

    # ==========================================
    # BLOCO 4: RODAPÉ E TOTAIS
    # ==========================================
    w_termos = 115
    w_totais = 75
    x_termos = 10
    x_totais = 125

    pdf.set_font(font, "B", 10)

    pdf.set_x(x_termos)
    pdf.cell(w_termos, 6, _enc("Termos de Pagamento:"), border="LTR", align="C")
    pdf.set_x(x_totais)
    pdf.cell(w_totais, 6, _enc("Subtotal:"), border="LTR", align="C", ln=1)

    y_start_totals = pdf.get_y()
    termos = template.payment_terms

    pdf.set_font(font, "", template.body_font_size)
    pdf.set_x(x_termos)
    pdf.multi_cell(w_termos, 5, _enc(termos), border="LBR", align="L")

    str_total = f"R$ {total_fatura:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    pdf.set_xy(x_totais, y_start_totals)
    pdf.cell(w_totais, 5, _enc(str_total), border="LR", align="C", ln=1)

    pdf.set_x(x_totais)
    pdf.set_font(font, "B", 10)
    pdf.cell(w_totais, 5, _enc("Total:"), border="LR", align="C", ln=1)

    pdf.set_x(x_totais)
    pdf.set_font(font, "B", 12)
    pdf.cell(w_totais, 10, _enc(str_total), border="LBR", align="C", ln=1)

    if template.show_observation and template.observation_text:
        pdf.ln(3)
        pdf.set_x(10)
        pdf.set_font(font, "", template.body_font_size)
        pdf.multi_cell(190, 5, _enc(template.observation_text), border=1, align="L")

    if dados.get("preview"):
        pdf.set_text_color(180, 180, 180)
        pdf.set_font(font, "B", 34)
        pdf.set_xy(45, 270)
        pdf.cell(120, 12, _enc("PRÉVIA"), align="C")

    saida = pdf.output(dest="S")
    if isinstance(saida, str):
        return saida.encode("latin-1")
    return bytes(saida)
