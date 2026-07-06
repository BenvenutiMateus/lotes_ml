import streamlit as st
import pandas as pd
import numpy as np
import altair as alt

# ======================================================
# ⚙️ CONFIG
# ======================================================
st.set_page_config(
    page_title="Análise Profissional de Lote",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ======================================================
# 🧹 CACHE, LIMPEZA & PADRONIZAÇÃO
# ======================================================
@st.cache_data
def carregar_dados(file):
    df = pd.read_excel(file, header=1)

    # Prevenção de variações de nomenclatura de colunas
    df = df.rename(columns={"Condição\n(Grade)": "Grade", "Condição (Grade)": "Grade"})
    df.columns = df.columns.str.strip()

    if "Categoria" in df.columns:
        df["Categoria"] = df["Categoria"].astype(str)

    df["Qtd"] = pd.to_numeric(df.get("Qtd"), errors="coerce")
    df["Valor Unit"] = pd.to_numeric(df.get("Valor Unit"), errors="coerce")
    df["Valor Total"] = pd.to_numeric(df.get("Valor Total"), errors="coerce")

    # Remove linhas que não têm os dados financeiros essenciais
    df = df.dropna(subset=["Qtd", "Valor Unit", "Valor Total"])

    return df

# ======================================================
# 📂 UPLOAD
# ======================================================
st.sidebar.title("📂 Upload do Lote")

uploaded_file = st.sidebar.file_uploader(
    "Carregue o arquivo Excel",
    type=["xlsx", "xls"]
)

if uploaded_file is None:
    st.info("⬅️ Envie um arquivo Excel na barra lateral para iniciar a análise.")
    st.stop()

try:
    df = carregar_dados(uploaded_file)
except Exception as e:
    st.error(f"Erro ao ler a planilha. Verifique se o formato está correto. Detalhe: {e}")
    st.stop()

if df.empty:
    st.warning("O arquivo foi carregado, mas não contém dados válidos de quantidade e valor.")
    st.stop()

# ======================================================
# ⚙️ PARÂMETROS CALIBRÁVEIS (AJUSTE 4)
# ======================================================
# Antes esses números estavam "chumbados" no código sem nenhuma validação.
# Agora ficam expostos aqui para o usuário poder calibrar contra a realidade
# do próprio negócio (e futuramente, contra resultado real de lotes já vendidos).
with st.sidebar.expander("⚙️ Calibração de Parâmetros (Avançado)", expanded=False):
    st.caption("Valores padrão são heurísticos — ajuste conforme sua experiência real de mercado.")

    st.markdown("**Peso por Grade (score de Qualidade)**")
    cg1, cg2 = st.columns(2)
    peso_grade_a = cg1.number_input("A", 0.0, 1.0, 1.00, 0.05, key="pg_a")
    peso_grade_b = cg2.number_input("B", 0.0, 1.0, 0.80, 0.05, key="pg_b")
    peso_grade_c = cg1.number_input("C", 0.0, 1.0, 0.60, 0.05, key="pg_c")
    peso_grade_d = cg2.number_input("D", 0.0, 1.0, 0.50, 0.05, key="pg_d")
    peso_grade_e = cg1.number_input("E", 0.0, 1.0, 0.40, 0.05, key="pg_e")
    peso_grade_u = cg2.number_input("U", 0.0, 1.0, 0.30, 0.05, key="pg_u")

    ticket_min = st.number_input("Ticket médio mínimo saudável (R$)", min_value=0.0, value=200.0, step=10.0)

    st.markdown("**Concentração (margens acima do mínimo teórico)**")
    conc_bom_margem = st.slider("Margem 'bom' acima do mínimo teórico", 0.0, 0.5, 0.10, 0.01,
                                 help="Ex: se o mínimo teórico de concentração Top3 é 60% (poucas categorias), 'bom' será 60%+margem")
    conc_ruim_margem = st.slider("Margem 'ruim' acima do mínimo teórico", conc_bom_margem, 0.8, 0.30, 0.01)

    st.markdown("**Pesos do Score Final**")
    pw1, pw2 = st.columns(2)
    peso_qualidade = pw1.number_input("Qualidade", 0.0, 1.0, 0.25, 0.05)
    peso_diversificacao = pw2.number_input("Diversificação", 0.0, 1.0, 0.20, 0.05)
    peso_ticket = pw1.number_input("Ticket Médio", 0.0, 1.0, 0.15, 0.05)
    peso_concentracao = pw2.number_input("Concentração", 0.0, 1.0, 0.20, 0.05)
    peso_risco = pw1.number_input("Risco", 0.0, 1.0, 0.20, 0.05)

    _soma_pesos = peso_qualidade + peso_diversificacao + peso_ticket + peso_concentracao + peso_risco
    if abs(_soma_pesos - 1.0) > 1e-6:
        st.caption(f"⚠️ Soma dos pesos = {_soma_pesos:.2f}. Serão normalizados automaticamente para somar 1.0.")

pesos_grade = {
    "A": peso_grade_a, "B": peso_grade_b, "C": peso_grade_c,
    "D": peso_grade_d, "E": peso_grade_e, "U": peso_grade_u
}
df["peso_grade"] = df["Grade"].map(pesos_grade).fillna(0)

qtd_total = df["Qtd"].sum()
qtd_max = df["Qtd"].max()
valor_total_lote = df["Valor Total"].sum()

# Prevenção de divisão por zero
if qtd_total == 0 or qtd_max == 0 or valor_total_lote == 0:
    st.error("A quantidade total, a quantidade máxima ou o valor total do lote é zero. Impossível calcular scores.")
    st.stop()

# ======================================================
# 1️⃣ QUALIDADE (0–1)  [AJUSTE 2: agora ponderado por VALOR, não por Qtd]
# ======================================================
# Antes: ponderava por Qtd, enquanto diversificação/concentração ponderam por Valor Total.
# Isso fazia um lote parecer "boa qualidade" mesmo com muito capital concentrado em itens ruins,
# só porque havia MUITAS peças de grade alta (mas baratas). Agora todas as métricas falam a
# mesma língua: quanto do CAPITAL do lote está em itens de boa grade.
score_qualidade = (df["peso_grade"] * df["Valor Total"]).sum() / valor_total_lote

# ======================================================
# 2️⃣ DIVERSIFICAÇÃO – HHI NORMALIZADO (0–1)  [AJUSTE 3]
# ======================================================
valor_cat = df.groupby("Categoria")["Valor Total"].sum()
participacao = valor_cat / valor_total_lote
n_categorias = valor_cat.shape[0]

hhi = np.sum(participacao ** 2)

# O HHI bruto nunca é menor que 1/n_categorias (mesmo com distribuição perfeitamente igual).
# Sem normalizar, um lote com poucas categorias é estruturalmente condenado a um score baixo,
# mesmo estando perfeitamente distribuído entre as categorias que tem.
# Normalizamos pelo mínimo teórico possível para o número de categorias existente.
if n_categorias > 1:
    hhi_min_teorico = 1 / n_categorias
    hhi_normalizado = (hhi - hhi_min_teorico) / (1 - hhi_min_teorico)
else:
    hhi_normalizado = 1.0  # uma única categoria = concentração máxima, sem ambiguidade

score_diversificacao = 1 - np.clip(hhi_normalizado, 0, 1)

# ======================================================
# 3️⃣ TICKET MÉDIO SAUDÁVEL (0–1)
# ======================================================
ticket_medio = valor_total_lote / qtd_total

if ticket_medio >= ticket_min and ticket_min > 0:
    score_ticket = 1
elif ticket_min == 0:
    score_ticket = 1
else:
    score_ticket = ticket_medio / ticket_min

score_ticket = np.clip(score_ticket, 0, 1)

# ======================================================
# 4️⃣ CONCENTRAÇÃO DE CAPITAL (0–1)  [AJUSTE 3: thresholds relativos ao nº de categorias]
# ======================================================
top_n = min(3, n_categorias)
top3_share = valor_cat.sort_values(ascending=False).head(top_n).sum() / valor_total_lote

# Se o lote só tem 1, 2 ou 3 categorias, o Top3 é matematicamente ~100% mesmo que a distribuição
# seja saudável — isso penalizava injustamente lotes pequenos/nichados. Agora os limiares "bom"
# e "ruim" são ancorados no mínimo teórico possível para aquele número de categorias.
min_teorico_top3 = min(1.0, top_n / n_categorias) if n_categorias > 0 else 1.0

def score_concentracao(share, min_teorico, bom_margem, ruim_margem):
    bom = min(1.0, min_teorico + bom_margem)
    ruim = min(1.0, min_teorico + ruim_margem)
    if ruim <= bom:  # guarda contra configurações inválidas de sidebar
        ruim = bom + 0.01
    if share <= bom:
        return 1.0
    elif share >= ruim:
        return 0.0
    else:
        return 1 - (share - bom) / (ruim - bom)

score_conc = score_concentracao(top3_share, min_teorico_top3, conc_bom_margem, conc_ruim_margem)

# ======================================================
# 5️⃣ RISCO OPERACIONAL (0–1)  [AJUSTE 3/4: percentil em vez de /qtd_max + média ponderada por valor]
# ======================================================
df["fora_ticket"] = (df["Valor Unit"] < ticket_min).astype(int)

# Antes: Qtd / qtd_max. Um único item com quantidade muito grande (outlier) distorcia a escala
# inteira, fazendo os demais itens parecerem artificialmente "seguros" em comparação.
# Agora usamos o percentil (rank) da quantidade dentro do próprio lote — mais robusto a outliers.
df["qtd_percentil"] = df["Qtd"].rank(pct=True)

df["risco_item"] = (
    (1 - df["peso_grade"]) * 0.5 +
    df["fora_ticket"] * 0.3 +
    df["qtd_percentil"] * 0.2
)

# Antes: média simples por linha. Isso diluía o risco de poucos itens de alto valor problemáticos
# em meio a muitas linhas de baixo valor. Agora a média é ponderada pelo capital de cada item,
# então itens que realmente "pesam no bolso" pesam também no score de risco.
score_risco = np.clip(1 - np.average(df["risco_item"], weights=df["Valor Total"]), 0, 1)

# ======================================================
# 🧮 SCORE FINAL (0–1)  [AJUSTE 4: pesos calibráveis, normalizados para somar 1]
# ======================================================
_pesos_brutos = {
    "qualidade": peso_qualidade,
    "diversificacao": peso_diversificacao,
    "ticket": peso_ticket,
    "concentracao": peso_concentracao,
    "risco": peso_risco
}
_soma = sum(_pesos_brutos.values())
pesos = {k: (v / _soma if _soma > 0 else 0.2) for k, v in _pesos_brutos.items()}

score_final = (
    pesos["qualidade"] * score_qualidade +
    pesos["diversificacao"] * score_diversificacao +
    pesos["ticket"] * score_ticket +
    pesos["concentracao"] * score_conc +
    pesos["risco"] * score_risco
)

# ======================================================
# 🧠 DECISÃO EXECUTIVA (Movido para o topo)
# ======================================================
st.title("📦 Análise Profissional de Lote")

if score_final >= 0.80 and score_risco >= 0.70:
    st.success(f"🟢 **DECISÃO: COMPRAR O LOTE** (Score: {score_final*100:.1f}%)")
elif score_final >= 0.65:
    st.warning(f"🟡 **DECISÃO: NEGOCIAR PREÇO / MIX** (Score: {score_final*100:.1f}%)")
else:
    st.error(f"🔴 **DECISÃO: EVITAR ESTE LOTE** (Score: {score_final*100:.1f}%)")

st.caption("⚠️ Este score é uma heurística de triagem, não uma verdade validada estatisticamente. "
           "Use como apoio à decisão, não como veredito único — especialmente para lotes com poucas categorias.")

st.divider()

# ======================================================
# 📊 KPIs
# ======================================================
k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Score Geral", f"{score_final*100:.1f} / 100")
k2.metric("Ticket Médio", f"R$ {ticket_medio:.2f}")
k3.metric("Diversificação (HHI norm.)", f"{hhi_normalizado:.3f}")
k4.metric("Dependência Top 3", f"{top3_share:.1%}", help=f"Mínimo teórico para {n_categorias} categoria(s): {min_teorico_top3:.1%}")
k5.metric("Score de Risco", f"{score_risco*100:.1f} / 100")

st.write("")

# ======================================================
# 📊 DECOMPOSIÇÃO E HEATMAP LADO A LADO
# ======================================================
col_chart1, col_chart2 = st.columns(2)

with col_chart1:
    st.markdown("##### Decomposição do Score")
    df_score = pd.DataFrame({
        "Componente": ["Qualidade", "Diversificação", "Ticket Médio", "Concentração", "Segurança (Risco)"],
        "Peso": [pesos["qualidade"], pesos["diversificacao"], pesos["ticket"], pesos["concentracao"], pesos["risco"]],
        "Score Obtido": [score_qualidade, score_diversificacao, score_ticket, score_conc, score_risco]
    })
    df_score["Contribuição Final"] = df_score["Peso"] * df_score["Score Obtido"]

    chart_score = alt.Chart(df_score).mark_bar(cornerRadiusBottomRight=4, cornerRadiusTopRight=4).encode(
        x=alt.X("Contribuição Final:Q", title="Pontos Adicionados"),
        y=alt.Y("Componente:N", sort="-x", title=None),
        color=alt.Color("Componente:N", legend=None),
        tooltip=["Componente", alt.Tooltip("Score Obtido:Q", format=".2f"), alt.Tooltip("Contribuição Final:Q", format=".3f")]
    ).properties(height=300)
    st.altair_chart(chart_score, width='stretch')

with col_chart2:
    st.markdown("##### Concentração Financeira (Categoria x Grade)")
    heat_df = df.groupby(["Categoria", "Grade"])["Valor Total"].sum().reset_index()
    heatmap = alt.Chart(heat_df).mark_rect().encode(
        x=alt.X("Categoria:N", title=None, axis=alt.Axis(labelAngle=-45)),
        y=alt.Y("Grade:N", title="Grade"),
        color=alt.Color("Valor Total:Q", scale=alt.Scale(scheme="reds"), title="Capital (R$)"),
        tooltip=["Categoria", "Grade", alt.Tooltip("Valor Total:Q", format=",.2f")]
    ).properties(height=300)
    st.altair_chart(heatmap, width='stretch')

# ======================================================
# 🎯 SCATTER – MATRIZ DE RISCO vs CAPITAL (INTERATIVO)
# ======================================================
st.markdown("##### Matriz de Risco x Capital Pressionado")
st.markdown("💡 **Como ler:** Arraste e use o scroll do mouse para dar zoom. Itens no quadrante **superior direito** (Muito Risco + Muito Dinheiro Investido) são os verdadeiros perigos do lote.")

colunas_tooltip = ["Categoria", "Grade", alt.Tooltip("Valor Unit:Q", format=".2f"), "Qtd", alt.Tooltip("risco_item:Q", format=".2f")]
if "Descrição do Item" in df.columns:
    colunas_tooltip.insert(0, "Descrição do Item")

cores_grade_chart = alt.Scale(
    domain=["A", "B", "C", "D", "E", "U"],
    range=["#2ecc71", "#f1c40f", "#e67e22", "#e74c3c", "#8e44ad", "#7f8c8d"]
)

scatter = alt.Chart(df).mark_circle(opacity=0.6).encode(
    x=alt.X("risco_item:Q", title="Grau de Risco (0 = Seguro | 1 = Perigoso)", scale=alt.Scale(domain=[-0.05, 1.05])),
    y=alt.Y("Valor Total:Q", title="Capital Total no Item (R$)"),
    size=alt.Size("Qtd:Q", scale=alt.Scale(range=[20, 800]), title="Quantidade"),
    color=alt.Color("Grade:N", scale=cores_grade_chart, title="Grade"),
    tooltip=colunas_tooltip
).properties(
    height=500
).interactive()

linha_risco = alt.Chart(pd.DataFrame({'x': [0.6]})).mark_rule(color='red', strokeDash=[5, 5]).encode(x='x')
linha_capital = alt.Chart(pd.DataFrame({'y': [df['Valor Total'].mean() * 2]})).mark_rule(color='orange', strokeDash=[5, 5]).encode(y='y')

st.altair_chart(scatter + linha_risco + linha_capital, width='stretch')

# ======================================================
# 📈 ANÁLISES DETALHADAS
# ======================================================
st.divider()
st.title("📈 Análises Detalhadas do Lote")

col_det1, col_det2 = st.columns(2)

with col_det1:
    st.markdown("##### 📊 Distribuição por Grade")
    grade_df = df.groupby("Grade").agg({"Valor Total": "sum", "Qtd": "sum"}).reset_index()
    chart_grade = alt.Chart(grade_df).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
        x=alt.X("Grade:N", sort=["A", "B", "C", "D", "E", "U"]),
        y=alt.Y("Valor Total:Q", title="Valor Total (R$)"),
        color=alt.Color("Grade:N", scale=cores_grade_chart, legend=None),
        tooltip=["Grade", "Qtd", alt.Tooltip("Valor Total:Q", format=",.2f")]
    ).properties(height=350)
    st.altair_chart(chart_grade, width='stretch')

with col_det2:
    if "Subcategoria" in df.columns:
        st.markdown("##### 📑 Top 10 Subcategorias por Valor")
        sub_df = df.groupby("Subcategoria")["Valor Total"].sum().reset_index().sort_values("Valor Total", ascending=False).head(10)
        chart_sub = alt.Chart(sub_df).mark_bar(cornerRadiusBottomRight=4, cornerRadiusTopRight=4).encode(
            x=alt.X("Valor Total:Q", title="Valor Total (R$)"),
            y=alt.Y("Subcategoria:N", sort="-x", title="Subcategoria"),
            color=alt.value("#3498db"),
            tooltip=["Subcategoria", alt.Tooltip("Valor Total:Q", format=",.2f")]
        ).properties(height=350)
        st.altair_chart(chart_sub, width='stretch')
    elif "Categoria" in df.columns:
        st.markdown("##### 📑 Categorias por Valor")
        cat_df = df.groupby("Categoria")["Valor Total"].sum().reset_index().sort_values("Valor Total", ascending=False).head(10)
        chart_cat = alt.Chart(cat_df).mark_bar(cornerRadiusBottomRight=4, cornerRadiusTopRight=4).encode(
            x=alt.X("Valor Total:Q", title="Valor Total (R$)"),
            y=alt.Y("Categoria:N", sort="-x", title="Categoria"),
            color=alt.value("#3498db"),
            tooltip=["Categoria", alt.Tooltip("Valor Total:Q", format=",.2f")]
        ).properties(height=350)
        st.altair_chart(chart_cat, width='stretch')

st.markdown("##### 🏆 Top 10 Itens Mais Valiosos do Lote")
colunas_top = ["Descrição do Item", "Categoria", "Subcategoria", "Grade", "Qtd", "Valor Unit", "Valor Total"]
colunas_existentes = [col for col in colunas_top if col in df.columns]
top10_df = df.sort_values("Valor Total", ascending=False).head(10)[colunas_existentes]
st.dataframe(top10_df, width='stretch', hide_index=True)


# ======================================================
# 💰 SIMULADOR FINANCEIRO (PREÇO TETO & PROJEÇÃO REAL)
# ======================================================
st.divider()
st.title("💰 Simulador Financeiro Integrado")

st.markdown("""
Calcule o **Lucro esperado** a partir de custos adicionais, aproveitamento
""")

st.markdown("#### 1. Parâmetros da Operação")
col_sim1, col_sim2, col_sim3 = st.columns(3)

custos_operacionais = col_sim1.number_input("⚙️ Custos Adicionais (%)", min_value=0, max_value=100, value=30, help="Custos operacionais, taxas de marketplace, impostos") / 100
desconto_venda = col_sim2.number_input("📉 Promoção / Desconto (%)", min_value=0, max_value=100, value=10, help="Desconto aplicado ao valor recuperável para vender mais rápido") / 100
preco_lote = col_sim3.number_input("💵 Custo Real do Lote (R$)", min_value=0.0, value=0.0, step=100.0, help="Preço pelo qual você pretende comprar ou comprou o lote")

st.markdown("#### 2. Aproveitamento Esperado por Grade (%)")
col_g1, col_g2, col_g3, col_g4, col_g5, col_g6 = st.columns(6)

peso_a = col_g1.number_input("Grade A", min_value=0, max_value=100, value=100) / 100
peso_b = col_g2.number_input("Grade B", min_value=0, max_value=100, value=100) / 100
peso_c = col_g3.number_input("Grade C", min_value=0, max_value=100, value=80) / 100
peso_d = col_g4.number_input("Grade D", min_value=0, max_value=100, value=60) / 100
peso_e = col_g5.number_input("Grade E", min_value=0, max_value=100, value=60) / 100
peso_u = col_g6.number_input("Grade U", min_value=0, max_value=100, value=50) / 100

pesos_grade_financeiro = {
    "A": peso_a,
    "B": peso_b,
    "C": peso_c,
    "D": peso_d,
    "E": peso_e,
    "U": peso_u
}
df["peso_venda"] = df["Grade"].map(pesos_grade_financeiro).fillna(0)

# ==================== A MATEMÁTICA ====================

valor_tabela_total = df["Valor Total"].sum()
valor_recuperavel = (df["Valor Total"] * df["peso_venda"]).sum()
faturamento_estimado = valor_recuperavel * (1 - desconto_venda)
despesas_totais = faturamento_estimado * custos_operacionais
lucro_projetado = faturamento_estimado - despesas_totais - preco_lote

# ==================== VISUALIZAÇÃO ====================
st.markdown("### Resumo Financeiro da Operação")

metric1, metric2, metric3, metric4 = st.columns(4)
metric1.metric("1. Valor de Tabela (Bruto)", f"R$ {valor_tabela_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
metric2.metric("2. Valor c/ Avarias (Recuperável)", f"R$ {valor_recuperavel:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
metric3.metric("3. Faturamento Esperado", f"R$ {faturamento_estimado:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
metric4.metric("4. Custos Adicionais", f"R$ {despesas_totais:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

st.markdown("---")

if preco_lote > 0:
    if lucro_projetado >= 0:
        st.success(f"✅ **LUCRO PROJETADO:** R$ {lucro_projetado:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        st.caption(f"Comprando por R$ {preco_lote:,.2f}, este será o seu lucro estimado.")
    else:
        st.error(f"❌ **PREJUÍZO PROJETADO:** R$ {abs(lucro_projetado):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
        st.caption(f"Comprando por R$ {preco_lote:,.2f}, a operação resulta em prejuízo.")
else:
    st.warning("⚠️ Insira o 'Custo Real do Lote' para ver a projeção de lucro.")

# Gráfico de Cascata (Waterfall) simulado em barras para demonstrar a "mordida" no valor
df_waterfall = pd.DataFrame({
    "Etapa": [
        "1. Valor Original",
        "2. Perda por Avarias",
        "3. Desconto de Venda",
        "4. Custos Operacionais",
        "5. Custo pago ao ML",
        "6. SEU LUCRO (Preço Teto)",
    ],
    "Valor (R$)": [
        valor_tabela_total,
        -(valor_tabela_total - valor_recuperavel),
        -(valor_recuperavel - faturamento_estimado),
        -despesas_totais,
        -preco_lote,
        lucro_projetado
    ]
})

chart_financeiro = alt.Chart(df_waterfall).mark_bar().encode(
    x=alt.X("Etapa:N", sort=None, title=None, axis=alt.Axis(labelAngle=-15)),
    y=alt.Y("Valor (R$):Q", title="Reais (R$)"),
    color=alt.condition(
        alt.datum['Valor (R$)'] > 0,
        alt.value("#2ecc71"),
        alt.value("#e74c3c")
    ),
    tooltip=["Etapa", alt.Tooltip("Valor (R$):Q", format=",.2f")]
).properties(height=350, title="Decomposição de Valor para Preço Teto")

st.altair_chart(chart_financeiro, width='stretch')