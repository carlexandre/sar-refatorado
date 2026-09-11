import os
import requests
import urllib3
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from io import BytesIO
from pyzabbix import ZabbixAPI
from dotenv import load_dotenv
import database as db

def conectar_zabbix():
    """Cria a conexão com o Zabbix para uso em scripts de backend."""
    load_dotenv()
    ZABBIX_URL = os.getenv("ZABBIX_URL")
    ZABBIX_USER = os.getenv("ZABBIX_USER")
    ZABBIX_PASSWORD = os.getenv("ZABBIX_PASSWORD")
    CERT_PATH = "zabbix-certificado.crt" 
    
    if not all([ZABBIX_URL, ZABBIX_USER, ZABBIX_PASSWORD]):
        raise ValueError("Credenciais do Zabbix ausentes no .env")

    session = requests.Session()
    if os.path.exists(CERT_PATH):
        session.verify = CERT_PATH
    else:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        session.verify = False
    
    zapi = ZabbixAPI(ZABBIX_URL, session=session)
    zapi.login(ZABBIX_USER, ZABBIX_PASSWORD)
    return zapi

def gerar_grafico_matplotlib(df_final, nome_inst, capacidade_str, periodo, dt_inicio, dt_fim):
    """Gera o gráfico de tráfego e retorna em BytesIO (isolado do Streamlit)"""
    fig, ax = plt.subplots(figsize=(12, 3.8))
    fig.patch.set_facecolor('#1a1a2e')
    ax.set_facecolor('#1e1e3a')

    ax.plot(df_final['clock'], df_final['recv_mbps'], color='#2ECC71', linewidth=1.2, label='Download (Entrada)', alpha=0.95)
    ax.plot(df_final['clock'], df_final['sent_mbps'], color='#3498DB', linewidth=1.2, label='Upload (Saída)', alpha=0.95)
    ax.fill_between(df_final['clock'], df_final['recv_mbps'], alpha=0.12, color='#2ECC71')
    ax.fill_between(df_final['clock'], df_final['sent_mbps'], alpha=0.12, color='#3498DB')

    inicio_ts = pd.to_datetime(int(pd.Timestamp(dt_inicio).timestamp()), unit='s')
    fim_ts = pd.to_datetime(int(pd.Timestamp(dt_fim).timestamp()) + 86400 - 1, unit='s')
    ax.set_xlim(inicio_ts, fim_ts)

    dias_total = (fim_ts - inicio_ts).days
    freq_dias = '1D' if dias_total <= 60 else f'{max(1, dias_total // 30)}D'
    ticks_datas = pd.date_range(start=inicio_ts.normalize(), end=fim_ts.normalize(), freq=freq_dias).tolist()
    
    ultimo_dia = fim_ts.normalize()
    if ultimo_dia not in ticks_datas:
        ticks_datas.append(ultimo_dia)
            
    ax.set_xticks(ticks_datas)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d/%m'))
    plt.xticks(rotation=90)

    for i, label in enumerate(ax.xaxis.get_ticklabels()):
        if i % 5 == 0 or i == len(ticks_datas) - 1:
            label.set_fontsize(9)
            label.set_color('#ffffff')
            label.set_fontweight('bold')
        else:
            label.set_fontsize(6)
            label.set_color('#777777')

    max_trafego = max(df_final['recv_mbps'].max(), df_final['sent_mbps'].max()) if not df_final.empty else 0
    y_max = ((max_trafego // 100) + 1) * 100 if max_trafego <= 1000 else max_trafego * 1.05
    if y_max == 0: y_max = 100
        
    ax.set_ylim(0, y_max)
    plt.yticks(color='#cccccc', fontsize=8)
    ax.set_xlabel('Data', color='#aaaaaa', fontsize=9)
    ax.set_ylabel('Tráfego (Mbps)', color='#aaaaaa', fontsize=9)
    
    ax.set_title(f'Tráfego de Rede — {nome_inst}\n{periodo}  |  Capacidade: {capacidade_str}', color='white', fontsize=10, fontweight='bold', pad=10)
    ax.legend(loc='upper right', fontsize=8, facecolor='#2c2c54', edgecolor='#555', labelcolor='white')
    ax.tick_params(colors='#cccccc', which='both')
    
    for spine in ax.spines.values(): spine.set_edgecolor('#444')
    ax.grid(axis='y', color='#333', linewidth=0.6, linestyle='--', alpha=0.7)
    ax.grid(axis='x', color='#333', linewidth=0.3, linestyle=':', alpha=0.5)

    plt.tight_layout(pad=1.5)
    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf

def processar_dados_instituicao(zapi, inst_id, dt_inicio, dt_fim):
    """
    Busca os dados no BD e Zabbix para UMA instituição e retorna 
    o dicionário estruturado que o gerador de PDF exige.
    """
    ts_from = int(pd.Timestamp(dt_inicio).timestamp())
    ts_till = int(pd.Timestamp(dt_fim).timestamp()) + 86400
    periodo_str = f"{dt_inicio.strftime('%d/%m/%Y')} a {dt_fim.strftime('%d/%m/%Y')}"

    with db.conectar() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT nome_instituicao, host_id, item_down_id, item_up_id, capacidade_str FROM links WHERE id = ?", (inst_id,))
        dados_link = cursor.fetchone()
    
    if not dados_link:
        raise ValueError(f"Instituição ID {inst_id} não encontrada no banco.")
        
    nome_inst, host_id, item_down, item_up, cap_str = dados_link

    def buscar_dados(item_id):
        dados = zapi.history.get(itemids=[item_id], time_from=ts_from, time_till=ts_till, output='extend', history=3)
        eh_tendencia = False
        precisa_trend = False
        
        if not dados:
            precisa_trend = True
        else:
            primeiro_registro = min(int(d['clock']) for d in dados)
            if (primeiro_registro - ts_from) > 86400:
                precisa_trend = True

        if precisa_trend:
            dados = zapi.trend.get(itemids=[item_id], time_from=ts_from, time_till=ts_till, output=['clock', 'value_avg', 'value_max'])
            eh_tendencia = True
        return dados, eh_tendencia

    raw_in, is_trend_in = buscar_dados(item_down)
    raw_out, is_trend_out = buscar_dados(item_up)

    if not raw_in or not raw_out:
        return None # Sem dados no período

    def calc_stats(dados_raw, is_trend):
        df = pd.DataFrame(dados_raw)
        if is_trend:
            return pd.to_numeric(df['value_max']).max(), pd.to_numeric(df['value_avg']).mean()
        df['value'] = pd.to_numeric(df['value'])
        return df['value'].max(), df['value'].mean()

    pico_in, media_in = calc_stats(raw_in, is_trend_in)
    pico_out, media_out = calc_stats(raw_out, is_trend_out)

    estatisticas_reais = {
        'media_in': media_in / 1_000_000, 'max_in': pico_in / 1_000_000,
        'media_out': media_out / 1_000_000, 'max_out': pico_out / 1_000_000
    }

    def prep_df(dados, is_trend):
        df = pd.DataFrame(dados)
        df['clock'] = pd.to_datetime(pd.to_numeric(df['clock']), unit='s')
        df['value'] = pd.to_numeric(df['value_max']) if is_trend else pd.to_numeric(df['value'])
        return df[['clock', 'value']]

    df_final = pd.merge(
        prep_df(raw_in, is_trend_in), prep_df(raw_out, is_trend_out),
        on='clock', how='outer', suffixes=('_in', '_out')
    ).sort_values('clock')
    
    df_final['value_in'] = df_final['value_in'].ffill().fillna(0)
    df_final['value_out'] = df_final['value_out'].ffill().fillna(0)
    df_final['recv_mbps'] = df_final['value_in'] / 1_000_000
    df_final['sent_mbps'] = df_final['value_out'] / 1_000_000

    infos = {
        'instituicao': nome_inst,
        'interface': "Interface de Borda",
        'periodo': periodo_str,
        'capacidade': cap_str 
    }

    grafico_bytes = gerar_grafico_matplotlib(df_final, nome_inst, cap_str, periodo_str, dt_inicio, dt_fim)

    alertas_reais = []
    eventos_problema = zapi.event.get(hostids=[host_id], time_from=ts_from, time_till=ts_till, output=['eventid', 'name', 'clock', 'r_eventid'], value=1, sortfield='clock')
    r_event_ids = [e['r_eventid'] for e in eventos_problema if e.get('r_eventid') and e.get('r_eventid') != '0']
    
    mapa_recuperacao = {}
    if r_event_ids:
        eventos_recuperacao = zapi.event.get(eventids=r_event_ids, output=['eventid', 'clock'])
        mapa_recuperacao = {r['eventid']: int(r['clock']) for r in eventos_recuperacao}

    for e in eventos_problema:
        trigger_name = e['name'].lower()
        if not any(termo in trigger_name for termo in ['bandwidth', 'uptime', 'restart']):
            continue

        inicio = int(e['clock'])
        r_id = e.get('r_eventid')
        dur_str = "Ativo/S.Rec."
        if r_id and r_id in mapa_recuperacao:
            duracao_segundos = mapa_recuperacao[r_id] - inicio
            dias, resto = divmod(duracao_segundos, 86400)
            horas, resto = divmod(resto, 3600)
            minutos, segundos = divmod(resto, 60)
            partes = [f"{v}{l}" for v, l in zip([dias, horas, minutos], ['d', 'h', 'm']) if v > 0]
            if not partes: partes.append(f"{segundos}s")
            dur_str = " ".join(partes)
        
        alertas_reais.append({
            'data': pd.to_datetime(inicio, unit='s').tz_localize('UTC').tz_convert('America/Fortaleza').strftime('%d/%m %H:%M'),
            'trigger': e['name'], 'duracao': dur_str, 'host': nome_inst
        })

    return {
        'grafico_bytes': grafico_bytes,
        'infos': infos,
        'alertas': alertas_reais,
        'stats': estatisticas_reais
    }