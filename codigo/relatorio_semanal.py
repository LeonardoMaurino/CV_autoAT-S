# Código do nó "Relatório (Python)" do workflow do relatório semanal (cópia pra facilitar a leitura;
# o que roda no n8n é o que está dentro do JSON em workflows/).
# Relatório semanal do mercado de vagas (roda no runner de Python do n8n).
# Entrada: as linhas da planilha "job tracker" (nó do Google Sheets antes deste).
# Saída: 1 item com a legenda do Telegram (HTML) e a imagem do relatório em PNG (base64).
import base64
import html
import io
import re
import unicodedata
from datetime import datetime, timedelta, timezone

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import FancyBboxPatch, Rectangle

# ---------------- dados ----------------
COLUNAS = ["Job Post Link", "Job Title", "Seniority Level", "Posted At", "Company Name", "No Aplicants", "Description"]
df = pd.DataFrame([item["json"] for item in _items])
df.columns = [str(c).strip() for c in df.columns]  # a planilha tem colunas com espaço no fim ("Job Title ")
for c in COLUNAS:
    if c not in df.columns:
        df[c] = ""
df = df[COLUNAS].fillna("").astype(str)
for c in ("Job Title", "Company Name"):
    df[c] = df[c].map(html.unescape).str.strip()  # alguns títulos vêm com código HTML ("QA&#32")

# a mesma vaga pode ter sido salva mais de uma vez: cada link conta uma vez só
df["chave"] = df["Job Post Link"].str.split("?").str[0].str.strip()
df.loc[df["chave"] == "", "chave"] = df["Job Title"] + "|" + df["Company Name"]
df = df.drop_duplicates("chave")
df["data"] = pd.to_datetime(df["Posted At"].str.slice(0, 10), errors="coerce")

BRT = timezone(timedelta(hours=-3))  # Brasília (sem horário de verão)
hoje = datetime.now(BRT).date()
fim = hoje - timedelta(days=1)  # semana fechada: os 7 dias até ontem
inicio = fim - timedelta(days=6)
semana = df[df["data"].between(pd.Timestamp(inicio), pd.Timestamp(fim))].copy()
anterior = df[df["data"].between(pd.Timestamp(inicio - timedelta(days=7)), pd.Timestamp(fim - timedelta(days=7)))]
n, n_ant = len(semana), len(anterior)


def normaliza(texto):
    s = unicodedata.normalize("NFD", str(texto)).lower()
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return " " + re.sub(r"[^a-z0-9#+]+", " ", s).strip() + " "


def termos(lista):
    return [normaliza(t) for t in lista]


def cita(texto_normalizado, lista_normalizada):
    return any(t in texto_normalizado for t in lista_normalizada)


AREAS = {
    "RPA e automação": termos(["rpa", "automação", "automation", "uipath", "blue prism", "power automate",
                               "hiperautomação"]),
    "Dev, IA e dados": termos(["desenvolvedor", "desenvolvedora", "developer", "dev", "programador", "programadora",
                               "software engineer", "engenheiro de software", "engenheira de software", "backend",
                               "back-end", "frontend", "front-end", "fullstack", "full stack", "ia", "ai",
                               "machine learning", "ml", "llm", "llms", "genai", "cientista de dados",
                               "cientista dados", "data scientist", "ciência de dados", "data science",
                               "desenvolvimento de software", "desenvolvimento de sistemas", "analista de sistemas",
                               "dados", "data engineer", "data analyst", "data analytics", "bi",
                               "business intelligence", "qa"]),
    "Infra": termos(["infraestrutura", "infra", "infrastructure", "devops", "sre", "cloud", "sysadmin",
                     "analista de redes", "suporte técnico", "help desk", "helpdesk", "service desk",
                     "sistemas operacionais"]),
}
OUTRAS = "Outras áreas"  # o que sobra é ruído da busca do LinkedIn (financeiro, vendas, SAP...)
HABILIDADES = {
    "Python": termos(["python"]),
    "SQL": termos(["sql"]),
    "Excel": termos(["excel"]),
    "Power BI": termos(["power bi", "powerbi"]),
    "UiPath": termos(["uipath"]),
    "Power Automate": termos(["power automate"]),
    "Automation Anywhere": termos(["automation anywhere"]),
    "Blue Prism": termos(["blue prism"]),
    "Java": termos(["java"]),
    "C#/.NET": termos(["c#", ".net", "dotnet"]),
    "JavaScript/TS": termos(["javascript", "typescript", "node.js", "nodejs"]),
    "React": termos(["react"]),
    "AWS": termos(["aws"]),
    "Azure": termos(["azure"]),
    "Google Cloud": termos(["gcp", "google cloud"]),
    "Docker/K8s": termos(["docker", "kubernetes", "k8s"]),
    "Git": termos(["git", "github", "gitlab"]),
    "APIs": termos(["api", "apis", "restful"]),
    "Machine Learning": termos(["machine learning", "scikit-learn", "sklearn"]),
    "IA generativa/LLM": termos(["llm", "llms", "genai", "ia generativa", "generative ai", "openai", "langchain"]),
    "Pandas": termos(["pandas"]),
    "Spark": termos(["spark", "pyspark"]),
    "Scrum/ágil": termos(["scrum", "ágil", "agile", "kanban"]),
    "Inglês": termos(["inglês", "english"]),
}


def area(titulo_normalizado):
    return next((a for a, lista in AREAS.items() if cita(titulo_normalizado, lista)), OUTRAS)


def candidatos(valor):
    m = re.search(r"\d[\d.,]*", str(valor))
    return int(re.sub(r"\D", "", m.group())) if m else None


semana["titulo_n"] = semana["Job Title"].map(normaliza)
semana["texto_n"] = (semana["Job Title"] + " " + semana["Description"]).map(normaliza)
semana["area"] = semana["titulo_n"].map(area)
semana["cand"] = pd.to_numeric(semana["No Aplicants"].map(candidatos), errors="coerce")

contagem = {h: int(semana["texto_n"].map(lambda t, lista=lista: cita(t, lista)).sum()) for h, lista in HABILIDADES.items()}
top_habilidades = sorted(((h, c) for h, c in contagem.items() if c > 0), key=lambda hc: -hc[1])[:8]
ordem_areas = [*AREAS, OUTRAS]
por_area = [int((semana["area"] == a).sum()) for a in ordem_areas]
dias = [inicio + timedelta(days=i) for i in range(7)]
por_dia_serie = semana["data"].dt.date.value_counts()
por_dia = [int(por_dia_serie.get(d, 0)) for d in dias]
empresas = semana["Company Name"].str.strip()
empresas = empresas[empresas != ""]
n_empresas = int(empresas.nunique())
# o LinkedIn mostra "seja um dos 25 primeiros" (vem como 25) e para de contar em 200, então a média engana:
# o que dá pra medir bem é quantas vagas ainda estavam com até 25 candidatos quando o bot achou
ate25 = round((semana["cand"].dropna() <= 25).mean() * 100) if semana["cand"].notna().any() else None
disputada = semana.loc[semana["cand"].idxmax()] if semana["cand"].notna().any() else None

# ---------------- imagem (1080x1350, cabe bem no Telegram e no LinkedIn) ----------------
W, H, DPI = 1080, 1350, 100
PT = 72 / DPI  # converte px em pt
PLANO, SUPERFICIE, BORDA = "#f9f9f7", "#fcfcfb", (11 / 255, 11 / 255, 11 / 255, 0.10)
TINTA, TINTA2, APAGADO, BASE = "#0b0b0b", "#52514e", "#898781", "#c3c2b7"
AZUL, SUBIU, CAIU = "#2a78d6", "#006300", "#d03b3b"
DIAS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]

plt.rcParams.update({"font.family": "DejaVu Sans", "text.color": TINTA})
fig = plt.figure(figsize=(W / DPI, H / DPI), dpi=DPI, facecolor=PLANO)


def fy(topo_px):
    return 1 - topo_px / H


def texto(x, topo, s, px, cor=TINTA, peso="normal", ha="left"):
    fig.text(x / W, fy(topo), s, fontsize=px * PT, color=cor, fontweight=peso, ha=ha, va="baseline")


def cartao(x, topo, w, h):
    fig.add_artist(FancyBboxPatch((x / W, fy(topo + h)), w / W, h / H, boxstyle=f"round,pad=0,rounding_size={16 / W}",
                                  mutation_aspect=W / H, transform=fig.transFigure, zorder=-1,  # atrás dos gráficos
                                  facecolor=SUPERFICIE, edgecolor=BORDA, linewidth=1))


def eixo(x, topo, w, h):
    ax = fig.add_axes([x / W, fy(topo + h), w / W, h / H])
    ax.set_facecolor("none")
    for lado in ax.spines.values():
        lado.set_visible(False)
    ax.tick_params(length=0)
    return ax


def barra(ax, x, y, largura, altura, ux, uy, horizontal):
    """Barra com a ponta arredondada (raio 4px) e a base reta."""
    r = 4 * ux
    comprimento_px = largura / ux if horizontal else altura / uy
    if comprimento_px > 10:
        ax.add_patch(FancyBboxPatch((x, y), largura, altura, boxstyle=f"round,pad=0,rounding_size={r}",
                                    mutation_aspect=uy / ux, facecolor=AZUL, edgecolor="none"))
    base = (x, y, min(largura, 8 * ux), altura) if horizontal else (x, y, largura, min(altura, 8 * uy))
    ax.add_patch(Rectangle(base[:2], base[2], base[3], facecolor=AZUL, edgecolor="none"))


def painel_barras(x, topo, w, h, titulo, subtitulo, rotulos, valores, fmt, largura_rotulo, sem_dados):
    cartao(x, topo, w, h)
    texto(x + 28, topo + 52, titulo, 32, TINTA, "bold")
    if subtitulo:
        texto(x + 28, topo + 88, subtitulo, 22, TINTA2)
    topo_eixo = topo + (116 if subtitulo else 84)
    if not valores or max(valores) == 0:
        texto(x + 28, topo_eixo + 44, sem_dados, 26, APAGADO)
        return
    ax_w, ax_h = w - 28 - largura_rotulo - 84, topo + h - 28 - topo_eixo
    ax = eixo(x + 28 + largura_rotulo, topo_eixo, ax_w, ax_h)
    k, vmax = len(valores), max(valores)
    ax.set_xlim(0, vmax)
    ax.set_ylim(k - 0.5, -0.5)
    ux, uy = vmax / ax_w, k / ax_h
    espessura = min(24 * uy, 0.7)
    for i, v in enumerate(valores):
        if v > 0:
            barra(ax, 0, i - espessura / 2, v, espessura, ux, uy, horizontal=True)
        ax.text(v + 10 * ux, i, fmt(v), va="center", ha="left", fontsize=24 * PT, color=TINTA2)
    ax.set_xticks([])
    ax.set_yticks(range(k))
    ax.set_yticklabels(rotulos, fontsize=26 * PT, color=TINTA)
    ax.tick_params(axis="y", pad=14)
    ax.axvline(0, color=BASE, linewidth=1)


def painel_colunas(x, topo, w, h, titulo, rotulos, valores, sem_dados, nota=None):
    cartao(x, topo, w, h)
    texto(x + 28, topo + 52, titulo, 32, TINTA, "bold")
    if nota:
        texto(x + 28, topo + 86, nota, 20, APAGADO)
    if max(valores) == 0:
        texto(x + 28, topo + 128, sem_dados, 26, APAGADO)
        return
    topo_eixo = topo + (144 if nota else 120)
    ax_w, ax_h = w - 56, topo + h - 78 - topo_eixo
    ax = eixo(x + 28, topo_eixo, ax_w, ax_h)
    k, vmax = len(valores), max(valores)
    ax.set_xlim(-0.5, k - 0.5)
    ax.set_ylim(0, vmax)
    ux, uy = k / ax_w, vmax / ax_h
    espessura = min(24 * ux, 0.7)
    for i, v in enumerate(valores):
        if v > 0:
            barra(ax, i - espessura / 2, 0, espessura, v, ux, uy, horizontal=False)
        ax.text(i, v + 8 * uy, str(v), ha="center", va="bottom", fontsize=24 * PT, color=TINTA2)
    ax.set_yticks([])
    ax.set_xticks(range(k))
    ax.set_xticklabels(rotulos, fontsize=21 * PT, color=TINTA2, linespacing=1.3)
    ax.tick_params(axis="x", pad=10)
    ax.axhline(0, color=BASE, linewidth=1)


def bloco(x, topo, w, h, rotulo, valor, detalhe, heroi=False, cor_detalhe=TINTA2):
    cartao(x, topo, w, h)
    texto(x + 24, topo + 46, rotulo, 23, TINTA2)
    texto(x + 24, topo + (134 if heroi else 120), valor, 76 if heroi else 50, TINTA, "bold")
    texto(x + 24, topo + h - 28, detalhe, 21, cor_detalhe)


periodo = f"{inicio:%d/%m} a {fim:%d/%m}"
texto(56, 76, f"Mercado de vagas · {periodo}", 44, TINTA, "bold")
texto(56, 120, "RPA, dev, IA e ciência de dados · São Paulo", 26, TINTA2)

if n_ant:
    variacao = round((n - n_ant) / n_ant * 100)
    if variacao > 0:
        detalhe_n, cor_n = f"▲ {variacao}% vs anterior", SUBIU
    elif variacao < 0:
        detalhe_n, cor_n = f"▼ {abs(variacao)}% vs anterior", CAIU
    else:
        detalhe_n, cor_n = "igual à anterior", TINTA2
else:
    variacao, detalhe_n, cor_n = None, "sem semana p/ comparar", APAGADO

# dia com 0 vagas quase sempre é dia sem coleta (PC ou n8n desligado), não falta de vaga
dias_sem_coleta = [d for d, v in zip(dias, por_dia) if v == 0] if n else []

largura_bloco = (W - 112 - 40) / 3
bloco(56, 152, largura_bloco, 210, "Vagas novas", str(n), detalhe_n, heroi=True, cor_detalhe=cor_n)
bloco(56 + largura_bloco + 20, 152, largura_bloco, 210, "Até 25 candidatos",
      "—" if ate25 is None else f"{ate25}%", "quando o bot achou")
bloco(56 + 2 * (largura_bloco + 20), 152, largura_bloco, 210, "Empresas", str(n_empresas), "abrindo vagas")

painel_barras(56, 386, W - 112, 520, "Habilidades mais pedidas", "% das vagas da semana que citam cada uma",
              [h for h, _ in top_habilidades], [round(c / n * 100) for _, c in top_habilidades] if n else [],
              lambda v: f"{v}%", 300, "sem vagas nesta semana")
meia = (W - 112 - 20) / 2
painel_barras(56, 930, meia, 360, "Vagas por área", None, ordem_areas, por_area, str, 246, "sem vagas")
painel_colunas(56 + meia + 20, 930, meia, 360, "Vagas por dia", [f"{DIAS[d.weekday()]}\n{d:%d}" for d in dias],
               por_dia, "sem vagas", "dia com 0 = provavelmente sem coleta" if dias_sem_coleta else None)
texto(56, 1326, "Fonte: vagas do LinkedIn coletadas pelo CV_autoAT-S. Cada vaga conta uma vez.", 20, APAGADO)

buf = io.BytesIO()
fig.savefig(buf, format="png", dpi=DPI, facecolor=PLANO)
plt.close(fig)

# ---------------- legenda do Telegram (HTML) ----------------
def corta(s, limite):
    s = " ".join(str(s).split())
    return s if len(s) <= limite else s[: limite - 1].rstrip() + "…"


esc = html.escape
linhas = [f"📊 <b>Mercado de vagas · {periodo}</b>", ""]
if n == 0:
    linhas.append("Nenhuma vaga nova nesta semana. O n8n ficou ligado?")
else:
    comparacao = "" if variacao is None else (f" ({'+' if variacao > 0 else ''}{variacao}% vs semana anterior)")
    linhas.append(f"<b>{n} vagas novas</b>{comparacao}")
    tecnicas = [(h, c) for h, c in top_habilidades if h not in ("Inglês", "Scrum/ágil")]
    if tecnicas:
        h, c = tecnicas[0]
        linhas.append(f"Habilidade técnica mais pedida: <b>{esc(h)}</b>, em {round(c / n * 100)}% das vagas")
    if contagem["Inglês"]:
        linhas.append(f"Inglês aparece em {round(contagem['Inglês'] / n * 100)}% das vagas")
    if ate25 is not None:
        linhas.append(f"{ate25}% das vagas ainda tinham até 25 candidatos quando o bot achou")
    if dias_sem_coleta:
        linhas.append("⚠️ Sem coleta em " + ", ".join(f"{d:%d/%m}" for d in dias_sem_coleta)
                      + " (PC ou n8n desligado?): os números da semana ficam menores")
    top_empresas = empresas.value_counts().head(3)
    if len(top_empresas):
        linhas.append("")
        linhas.append("🏢 Quem mais abriu vagas: " + ", ".join(f"{esc(corta(e, 30))} ({q})" for e, q in top_empresas.items()))
    if disputada is not None:
        # o LinkedIn para de contar em 200: "200" na prática quer dizer "200 ou mais"
        mais = "+" if disputada["cand"] >= 200 or re.search(r"over|mais de", disputada["No Aplicants"], re.I) else ""
        linhas.append(f"🔥 Mais disputada: {esc(corta(disputada['Job Title'], 60))} · "
                      f"{esc(corta(disputada['Company Name'], 30))} ({int(disputada['cand'])}{mais} candidatos)")

return [{"json": {
    "legenda": "\n".join(linhas),
    "png_base64": base64.b64encode(buf.getvalue()).decode(),
    "periodo": periodo,
    "vagas": n,
}}]
