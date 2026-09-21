from fpdf import FPDF
from sar.infrastructure.documents.templates import load_template, asset
from sar.domain.traffic import utilization
import os
import textwrap
import tempfile
from datetime import date
from io import BytesIO

# =============================================================================
# TEXTOS PADRÃO DO RELATÓRIO
# =============================================================================

# =============================================================================
# HELPERS
# =============================================================================


def _enc(texto: str) -> str:
    """Converte texto para latin-1, substituindo caracteres inválidos."""
    try:
        return str(texto).encode("latin-1", "replace").decode("latin-1")
    except Exception:
        return str(texto)


def _salvar_grafico_temp(grafico_bytes: BytesIO) -> str | None:
    """
    Salva o BytesIO do gráfico em um arquivo temporário e retorna o caminho.
    """
    if not grafico_bytes:
        return None
    try:
        grafico_bytes.seek(0)
        conteudo = grafico_bytes.read()
        if not conteudo:
            return None
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
            tmp.write(conteudo)
            tmp.flush()
            return tmp.name
    except Exception:
        return None


# =============================================================================
# CLASSE DO PDF
# =============================================================================


class RelatorioPDF(FPDF):
    LOGO_POPCE = asset("pop-ce-logo-preto.png")
    LOGO_RNP = asset("rnp-logo-preto.png")

    COR_TITULO_FUNDO = (230, 230, 230)
    COR_TITULO_TEXTO = (30, 30, 30)
    COR_CORPO = (50, 50, 50)
    COR_HEADER_TAB = (200, 200, 200)
    COR_LINHA_PAR = (248, 248, 248)
    COR_ALERTA = (220, 50, 50)

    def header(self):
        if self.page_no() == 1:
            return

        if os.path.exists(self.LOGO_POPCE):
            self.image(self.LOGO_POPCE, x=85, y=8, w=40)
            self.set_y(26)
        else:
            self.set_font("Arial", "B", 13)
            self.set_text_color(50, 50, 50)
            self.cell(0, 10, "PoP-CE", border=0, new_x="LMARGIN", new_y="NEXT", align="C")

        self.set_font("Arial", "B", 7)
        self.set_text_color(80, 80, 80)
        self.cell(0, 4, "PONTO DE PRESENÇA DA RNP CEARÁ", border=0, new_x="LMARGIN", new_y="NEXT", align="C")
        self.set_draw_color(180, 180, 180)
        self.line(10, self.get_y() + 2, 200, self.get_y() + 2)
        self.ln(6)

    def footer(self):
        if self.page_no() == 1:
            return

        self.set_y(-25)
        self.set_draw_color(180, 180, 180)
        self.line(10, self.get_y(), 200, self.get_y())

        if os.path.exists(self.LOGO_RNP):
            self.image(self.LOGO_RNP, x=80, y=276, w=50)

        self.set_y(-13)
        self.set_font("Arial", "", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 8, f"Página {self.page_no()}", border=0, align="R")

    # ------------------------------------------------------------------
    # CAPA
    # ------------------------------------------------------------------

    def gerar_capa(self, nome_instituicao: str, periodo: str):
        self.add_page()
        if os.path.exists(self.LOGO_POPCE):
            self.image(self.LOGO_POPCE, x=70, y=40, w=70)

        self.set_y(105)
        self.set_font("Arial", "B", 13)
        self.set_text_color(80, 80, 80)
        self.cell(
            0, 7, _enc("PONTO DE PRESENÇA DA RNP CEARÁ"), border=0, new_x="LMARGIN", new_y="NEXT", align="C"
        )

        self.set_draw_color(180, 180, 180)
        self.line(40, self.get_y() + 3, 170, self.get_y() + 3)
        self.ln(14)

        self.set_font("Arial", "B", 20)
        self.set_text_color(20, 20, 20)
        self.cell(0, 9, _enc("RELATÓRIO TÉCNICO DE"), border=0, new_x="LMARGIN", new_y="NEXT", align="C")
        self.cell(0, 9, _enc("MONITORAMENTO DE TRÁFEGO"), border=0, new_x="LMARGIN", new_y="NEXT", align="C")

        self.ln(6)
        self.set_font("Arial", "", 13)
        self.set_text_color(80, 80, 80)
        self.cell(0, 7, _enc("Rede GigaFOR / PoP-CE"), border=0, new_x="LMARGIN", new_y="NEXT", align="C")

        self.ln(18)
        self.set_font("Arial", "", 11)
        self.set_text_color(100, 100, 100)
        self.cell(0, 6, "Período de Referência:", border=0, new_x="LMARGIN", new_y="NEXT", align="C")
        self.set_font("Arial", "B", 12)
        self.set_text_color(30, 30, 30)
        self.cell(0, 7, _enc(periodo), border=0, new_x="LMARGIN", new_y="NEXT", align="C")

        self.ln(10)
        self.set_font("Arial", "B", 15)
        self.set_text_color(20, 20, 20)
        self.multi_cell(0, 7, _enc(nome_instituicao), border=0, align="C")

        self.set_y(-35)
        self.set_font("Arial", "", 9)
        self.set_text_color(130, 130, 130)
        self.cell(
            0,
            5,
            _enc(f"Fortaleza - CE   |   Gerado em {date.today().strftime('%d/%m/%Y')}"),
            border=0,
            align="C",
        )

    # ------------------------------------------------------------------
    # HELPERS DE CONTEÚDO
    # ------------------------------------------------------------------

    def checar_espaco(self, espaco_necessario: float):
        """Evita títulos órfãos ou blocos cortados pulando página se faltar espaço."""
        if self.get_y() + espaco_necessario > 267:  # 297(A4) - 30(Margin) = 267
            self.add_page()

    def secao_titulo(self, numero: str, titulo: str):
        self.checar_espaco(15)  # Título pede ao menos 15mm para não ficar sozinho
        self.set_font("Arial", "B", 11)
        self.set_text_color(*self.COR_TITULO_TEXTO)
        self.set_fill_color(*self.COR_TITULO_FUNDO)
        self.cell(
            0, 8, _enc(f"{numero}  {titulo}"), border=0, new_x="LMARGIN", new_y="NEXT", align="L", fill=True
        )
        self.ln(2)

    def subsecao_titulo(self, texto: str):
        self.checar_espaco(12)  # Subtítulo pede ao menos 12mm
        self.set_font("Arial", "B", 10)
        self.set_text_color(60, 60, 60)
        self.cell(0, 6, _enc(texto), border=0, new_x="LMARGIN", new_y="NEXT", align="L")
        self.ln(1)

    def corpo_texto(self, texto: str):
        self.set_font("Arial", "", 10)
        self.set_text_color(*self.COR_CORPO)
        self.multi_cell(0, 5.5, _enc(texto))
        self.ln(4)

    def linha_dado(self, rotulo: str, valor: str, fill: bool = False):
        self.checar_espaco(7)
        self.set_fill_color(*self.COR_LINHA_PAR)
        self.set_font("Arial", "B", 9)
        self.set_text_color(60, 60, 60)
        self.cell(65, 7, _enc(rotulo), border="B", fill=fill)
        self.set_font("Arial", "", 9)
        self.set_text_color(30, 30, 30)
        self.cell(0, 7, _enc(valor), border="B", new_x="LMARGIN", new_y="NEXT", fill=fill)

    def tabela_stats(self, stats: dict):
        self.checar_espaco(25)
        media_in = stats.get("media_in", 0)
        media_out = stats.get("media_out", 0)
        max_in = stats.get("max_in", 0)
        max_out = stats.get("max_out", 0)

        dados = [
            (
                "Tráfego Médio - Entrada (Download)",
                f"{media_in:.2f} Mbps",
                "Tráfego Médio - Saída (Upload)",
                f"{media_out:.2f} Mbps",
            ),
            (
                "Pico Máximo - Entrada (Download)",
                f"{max_in:.2f} Mbps",
                "Pico Máximo - Saída (Upload)",
                f"{max_out:.2f} Mbps",
            ),
        ]

        col_w = 95
        for rotulo1, val1, rotulo2, val2 in dados:
            self.set_fill_color(*self.COR_HEADER_TAB)
            self.set_font("Arial", "B", 8)
            self.set_text_color(40, 40, 40)
            self.cell(col_w, 6, _enc(rotulo1), border=1, fill=True)
            self.cell(col_w, 6, _enc(rotulo2), border=1, new_x="LMARGIN", new_y="NEXT", fill=True)
            self.set_fill_color(255, 255, 255)
            self.set_font("Arial", "B", 11)
            self.set_text_color(20, 20, 20)
            self.cell(col_w, 8, _enc(val1), border=1, align="C", fill=True)
            self.cell(col_w, 8, _enc(val2), border=1, align="C", new_x="LMARGIN", new_y="NEXT", fill=True)
            self.ln(2)

    def tabela_alertas(self, lista_alertas: list):
        self.checar_espaco(20)
        self.set_fill_color(*self.COR_HEADER_TAB)
        self.set_font("Arial", "B", 9)
        self.set_text_color(30, 30, 30)
        self.cell(32, 7, "Data/Hora", border=1, align="C", fill=True)
        self.cell(90, 7, "Descrição do Alerta", border=1, align="C", fill=True)
        self.cell(28, 7, "Duração", border=1, align="C", fill=True)
        self.cell(40, 7, "Equipamento", border=1, align="C", new_x="LMARGIN", new_y="NEXT", fill=True)

        if not lista_alertas:
            self.set_font("Arial", "I", 9)
            self.set_text_color(100, 100, 100)
            self.cell(
                190,
                7,
                "Nenhuma ocorrência crítica registrada no período.",
                border=1,
                new_x="LMARGIN",
                new_y="NEXT",
                align="C",
            )
            self.ln(6)
            return

        self.set_font("Arial", "", 9)
        for idx, alerta in enumerate(lista_alertas):
            if isinstance(alerta, dict):
                trig = _enc(alerta.get("trigger", "-"))
                host = _enc(alerta.get("host", "-"))
                dt_alerta = _enc(alerta.get("data", "-"))
                duracao = _enc(alerta.get("duracao", "-"))
            else:
                trig, host, dt_alerta, duracao = _enc(str(alerta)), "-", "-", "-"

            if len(host) > 24:
                host = host[:21] + "..."

            linhas_trig = textwrap.wrap(trig, width=52)
            num_linhas = max(1, len(linhas_trig))
            altura = 6 * num_linhas

            if self.get_y() + altura > 267:
                self.add_page()
                self.set_fill_color(*self.COR_HEADER_TAB)
                self.set_font("Arial", "B", 9)
                self.set_text_color(30, 30, 30)
                self.cell(32, 7, "Data/Hora", border=1, align="C", fill=True)
                self.cell(90, 7, "Descrição do Alerta", border=1, align="C", fill=True)
                self.cell(28, 7, "Duração", border=1, align="C", fill=True)
                self.cell(40, 7, "Equipamento", border=1, align="C", new_x="LMARGIN", new_y="NEXT", fill=True)
                self.set_font("Arial", "", 9)

            fill = idx % 2 == 0
            self.set_fill_color(*self.COR_LINHA_PAR)

            if duracao in ("Ativo/S.Rec.", "Ativo"):
                self.set_fill_color(255, 235, 235)
                fill = True

            y0 = self.get_y()

            self.set_text_color(40, 40, 40)
            self.cell(32, altura, dt_alerta, border=1, align="C", fill=fill)

            x_trig = self.get_x()
            if num_linhas == 1:
                self.cell(90, altura, trig, border=1, align="L", fill=fill)
            else:
                self.cell(90, altura, "", border=1, align="L", fill=fill)
                self.set_xy(x_trig + 1, y0 + 1)
                self.multi_cell(88, 6, trig, border=0, align="L")
                self.set_xy(x_trig + 90, y0)

            if duracao in ("Ativo/S.Rec.", "Ativo"):
                self.set_text_color(*self.COR_ALERTA)
            self.cell(28, altura, duracao, border=1, align="C", fill=fill)
            self.set_text_color(40, 40, 40)

            self.cell(40, altura, host, border=1, align="C", new_x="LMARGIN", new_y="NEXT", fill=fill)

        self.ln(8)

    def bloco_observacao(self, stats: dict, capacidade_str: str):
        self.checar_espaco(25)
        max_in = stats.get("max_in", 0)
        max_out = stats.get("max_out", 0)

        percentual, _ = utilization(stats, capacidade_str)

        # Compare o pico medido com a capacidade declarada, nunca com o teto do gráfico.
        if percentual is None:
            icone = "[?]"
            obs = (
                f"O pico medido foi de {max_in:.1f} Mbps na entrada e {max_out:.1f} Mbps na saída. "
                f"Não foi possível calcular a utilização porque a capacidade cadastrada "
                f"({capacidade_str}) não tem uma unidade reconhecida. Confira o cadastro do link."
            )
            self.set_fill_color(245, 245, 245)
        elif percentual >= 90:
            icone = "[!]"
            obs = f"O tráfego atingiu picos críticos no período analisado (Entrada: {max_in:.1f} Mbps / Saída: {max_out:.1f} Mbps), representando {percentual:.1f}% da capacidade contratada de {capacidade_str}. Recomenda-se avaliação da capacidade do link."
            self.set_fill_color(255, 235, 220)
        elif percentual >= 75:
            icone = "[~]"
            obs = f"O link apresentou utilização elevada no período (Entrada: {max_in:.1f} Mbps / Saída: {max_out:.1f} Mbps), alcançando {percentual:.1f}% da capacidade contratada de {capacidade_str}. Monitoramento contínuo é recomendado."
            self.set_fill_color(255, 248, 220)
        else:
            icone = "[OK]"
            obs = f"O link operou dentro da normalidade no período analisado (Entrada: {max_in:.1f} Mbps / Saída: {max_out:.1f} Mbps), utilizando até {percentual:.1f}% da capacidade contratada de {capacidade_str}."
            self.set_fill_color(230, 248, 235)

        self.set_font("Arial", "B", 9)
        self.set_text_color(40, 40, 40)
        self.cell(
            0, 6, _enc(f"Observação Automática  {icone}"), border=0, new_x="LMARGIN", new_y="NEXT", fill=True
        )
        self.set_font("Arial", "", 9)
        self.set_text_color(50, 50, 50)
        self.multi_cell(0, 5, _enc(obs), fill=True)
        self.ln(6)


# =============================================================================
# FUNÇÃO PRINCIPAL
# =============================================================================


def criar_pdf_completo(lista_dados: list, dt_inicio: date, dt_fim: date) -> bytes:
    """
    Gera o PDF agrupando os relatórios de múltiplas instituições em um único documento.
    """

    template = load_template()
    TEXTOS = template["texts"]
    nomes_instituicoes = [d["infos"]["instituicao"] for d in lista_dados]
    if len(nomes_instituicoes) > 1:
        str_nomes = ", ".join(nomes_instituicoes[:-1]) + " e " + nomes_instituicoes[-1]
    else:
        str_nomes = nomes_instituicoes[0]

    periodo = f"{dt_inicio.strftime('%d/%m/%Y')} a {dt_fim.strftime('%d/%m/%Y')}"

    # ---- Monta o objeto PDF (Margem inferior elevada para 30 para fugir do footer) ----
    pdf = RelatorioPDF(orientation="P", unit="mm", format="A4")
    pdf.COR_TITULO_FUNDO = tuple(template["colors"]["title_background"])
    pdf.COR_TITULO_TEXTO = tuple(template["colors"]["title_text"])
    pdf.set_auto_page_break(auto=True, margin=30)
    pdf.set_margins(left=10, top=10, right=10)

    # ---- PÁGINA 1: CAPA ----
    pdf.gerar_capa(nome_instituicao=str_nomes, periodo=periodo)

    # ---- PÁGINA 2: INTRODUÇÃO (Global) ----
    pdf.add_page()
    pdf.secao_titulo("1.", "Introdução")

    texto_intro_adaptado = TEXTOS["introducao"].replace("{alvo}", str_nomes)
    pdf.corpo_texto(texto_intro_adaptado)

    pdf.secao_titulo("1.1.", "Sobre a RNP - Rede Nacional de Ensino e Pesquisa")
    pdf.corpo_texto(TEXTOS["sobre_rnp"])

    pdf.secao_titulo("1.2.", "Sobre a GigaFOR - Rede Metropolitana de Fortaleza")
    pdf.corpo_texto(TEXTOS["sobre_gigafor"])

    # ---- SEÇÕES DINÂMICAS: UMA PARA CADA INSTITUIÇÃO ----
    num_secao = 2
    for dados in lista_dados:
        inst = dados["infos"].get("instituicao", "Instituição")
        cap = dados["infos"].get("capacidade", "N/D")
        grafico_bytes = dados.get("grafico_bytes")
        alertas = dados.get("alertas", [])
        stats = dados.get("stats", {})

        pdf.add_page()
        pdf.secao_titulo(f"{num_secao}.", f"Análise de Tráfego - {inst}")

        pdf.subsecao_titulo(f"{num_secao}.1. Dados Cadastrais")
        pdf.ln(1)
        pdf.linha_dado("Instituição:", inst, fill=True)
        pdf.linha_dado("Período de Referência:", periodo, fill=False)
        pdf.linha_dado("Capacidade do Link:", cap, fill=True)
        pdf.ln(6)

        pdf.subsecao_titulo(f"{num_secao}.2. Gráfico de Tráfego")
        pdf.ln(2)

        caminho_tmp = _salvar_grafico_temp(grafico_bytes)
        if caminho_tmp:
            try:
                # Checa espaco pro grafico
                pdf.checar_espaco(85)
                pdf.image(caminho_tmp, x=10, w=190)
            except Exception:
                pdf.corpo_texto("[Gráfico indisponível]")
            finally:
                try:
                    os.remove(caminho_tmp)
                except OSError:
                    pass
        else:
            pdf.set_fill_color(245, 245, 245)
            pdf.set_font("Arial", "I", 9)
            pdf.set_text_color(130, 130, 130)
            pdf.cell(
                0,
                18,
                "Gráfico indisponível para este período.",
                border=1,
                new_x="LMARGIN",
                new_y="NEXT",
                align="C",
                fill=True,
            )
        pdf.ln(6)

        pdf.subsecao_titulo(f"{num_secao}.3. Métricas de Tráfego")
        pdf.ln(2)
        pdf.tabela_stats(stats)
        pdf.ln(2)
        pdf.bloco_observacao(stats, cap)
        pdf.ln(4)

        pdf.subsecao_titulo(f"{num_secao}.4. Resumo de Ocorrências e Alertas")
        pdf.ln(2)
        pdf.tabela_alertas(alertas)
        pdf.ln(2)

        pdf.subsecao_titulo(f"{num_secao}.5. Conclusão ({inst})")
        texto_conclusao = TEXTOS["conclusao"].replace("{periodo}", periodo).replace("{instituicao}", inst)
        pdf.corpo_texto(texto_conclusao)

        num_secao += 1

    saida = pdf.output(dest="S")

    if isinstance(saida, str):
        return saida.encode("latin-1")
    return bytes(saida)
