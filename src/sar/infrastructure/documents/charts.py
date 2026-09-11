import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from io import BytesIO


def gerar_grafico_matplotlib(df_final, nome_inst, capacidade_str, periodo, dt_inicio, dt_fim):
    """Gera o gráfico de tráfego e retorna em BytesIO (isolado do Streamlit)"""
    fig, ax = plt.subplots(figsize=(12, 3.8))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#1e1e3a")

    ax.plot(
        df_final["clock"],
        df_final["recv_mbps"],
        color="#2ECC71",
        linewidth=1.2,
        label="Download (Entrada)",
        alpha=0.95,
    )
    ax.plot(
        df_final["clock"],
        df_final["sent_mbps"],
        color="#3498DB",
        linewidth=1.2,
        label="Upload (Saída)",
        alpha=0.95,
    )
    ax.fill_between(df_final["clock"], df_final["recv_mbps"], alpha=0.12, color="#2ECC71")
    ax.fill_between(df_final["clock"], df_final["sent_mbps"], alpha=0.12, color="#3498DB")

    inicio_ts = pd.to_datetime(int(pd.Timestamp(dt_inicio).timestamp()), unit="s")
    fim_ts = pd.to_datetime(int(pd.Timestamp(dt_fim).timestamp()) + 86400 - 1, unit="s")
    ax.set_xlim(inicio_ts, fim_ts)

    dias_total = (fim_ts - inicio_ts).days
    freq_dias = "1D" if dias_total <= 60 else f"{max(1, dias_total // 30)}D"
    ticks_datas = pd.date_range(start=inicio_ts.normalize(), end=fim_ts.normalize(), freq=freq_dias).tolist()

    ultimo_dia = fim_ts.normalize()
    if ultimo_dia not in ticks_datas:
        ticks_datas.append(ultimo_dia)

    ax.set_xticks(ticks_datas)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
    plt.xticks(rotation=90)

    for i, label in enumerate(ax.xaxis.get_ticklabels()):
        if i % 5 == 0 or i == len(ticks_datas) - 1:
            label.set_fontsize(9)
            label.set_color("#ffffff")
            label.set_fontweight("bold")
        else:
            label.set_fontsize(6)
            label.set_color("#777777")

    max_trafego = max(df_final["recv_mbps"].max(), df_final["sent_mbps"].max()) if not df_final.empty else 0
    y_max = ((max_trafego // 100) + 1) * 100 if max_trafego <= 1000 else max_trafego * 1.05
    if y_max == 0:
        y_max = 100

    ax.set_ylim(0, y_max)
    plt.yticks(color="#cccccc", fontsize=8)
    ax.set_xlabel("Data", color="#aaaaaa", fontsize=9)
    ax.set_ylabel("Tráfego (Mbps)", color="#aaaaaa", fontsize=9)

    ax.set_title(
        f"Tráfego de Rede — {nome_inst}\n{periodo}  |  Capacidade: {capacidade_str}",
        color="white",
        fontsize=10,
        fontweight="bold",
        pad=10,
    )
    ax.legend(loc="upper right", fontsize=8, facecolor="#2c2c54", edgecolor="#555", labelcolor="white")
    ax.tick_params(colors="#cccccc", which="both")

    for spine in ax.spines.values():
        spine.set_edgecolor("#444")
    ax.grid(axis="y", color="#333", linewidth=0.6, linestyle="--", alpha=0.7)
    ax.grid(axis="x", color="#333", linewidth=0.3, linestyle=":", alpha=0.5)

    plt.tight_layout(pad=1.5)
    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf
