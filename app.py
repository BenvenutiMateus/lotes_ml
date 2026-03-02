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
    df = pd.read_excel(file, header=6)
    
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
# 🎨 GRADES E CÁLCULOS BASE
# ======================================================
pesos_grade = {"A": 1.00, "B": 0.75, "C": 0.50, "D": 0.30, "E": 0.15, "U": 0.10}
df["peso_grade"] = df["Grade"].map(pesos_grade).fillna(0)

qtd_total = df["Qtd"].sum()
qtd_max = df["Qtd"].max()
valor_total_lote = df["Valor Total"].sum()

# Prevenção de divisão por zero
if qtd_total == 0 or qtd_max == 0:
    st.error("A quantidade total ou máxima de itens é zero. Impossível calcular scores.")
    st.stop()

# ======================================================
# 1️⃣ QUALIDADE (0–1)
# ======================================================
score_qualidade = (df["peso_grade"] * df["Qtd"]).sum() / qtd_total

# ======================================================
# 2️⃣ DIVERSIFICAÇÃO – HHI (0–1)
# ======================================================
valor_cat = df.groupby("Categoria")["Valor Total"].sum()
participacao = valor_cat / valor_total_lote

hhi = np.sum(participacao ** 2)
score_diversificacao = 1 - hhi

# ======================================================
# 3️⃣ TICKET MÉDIO SAUDÁVEL (0–1)
# ======================================================
ticket_medio = valor_total_lote / qtd_total
ticket_min, ticket_max = 80, 200

if ticket_min <= ticket_medio <= ticket_max:
    score_ticket = 1
elif ticket_medio < ticket_min:
    score_ticket = ticket_medio / ticket_min
else:
    score_ticket = ticket_max / ticket_medio

score_ticket = np.clip(score_ticket, 0, 1)

# ======================================================
# 4️⃣ CONCENTRAÇÃO DE CAPITAL (0–1)
# ======================================================
top3_share = valor_cat.sort_values(ascending=False).head(3).sum() / valor_total_lote

def score_concentracao(share, bom=0.40, ruim=0.60):
    if share <= bom:
        return 1
    elif share >= ruim:
        return 0
    else:
        return 1 - (share - bom) / (ruim - bom)

score_conc = score_concentracao(top3_share)

# ======================================================
# 5️⃣ RISCO OPERACIONAL (0–1)
# ======================================================
df["fora_ticket"] = ((df["Valor Unit"] < ticket_min) | (df["Valor Unit"] > ticket_max)).astype(int)

# Penaliza itens de grade baixa, fora do ticket padrão e que tem muito volume (difíceis de escoar)
df["risco_item"] = (
    (1 - df["peso_grade"]) * 0.5 +
    df["fora_ticket"] * 0.3 +
    (df["Qtd"] / qtd_max) * 0.2
)

score_risco = np.clip(1 - df["risco_item"].mean(), 0, 1)

# ======================================================
# 🧮 SCORE FINAL (0–1)
# ======================================================
pesos = {
    "qualidade": 0.25,
    "diversificacao": 0.20,
    "ticket": 0.15,
    "concentracao": 0.20,
    "risco": 0.20
}

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

# Trazer a decisão para o topo é uma ótima prática executiva (Bottom Line Up Front)
if score_final >= 0.80 and score_risco >= 0.70:
    st.success(f"🟢 **DECISÃO: COMPRAR O LOTE** (Score: {score_final*100:.1f}%)")
elif score_final >= 0.65:
    st.warning(f"🟡 **DECISÃO: NEGOCIAR PREÇO / MIX** (Score: {score_final*100:.1f}%)")
else:
    st.error(f"🔴 **DECISÃO: EVITAR ESTE LOTE** (Score: {score_final*100:.1f}%)")

st.divider()

# ======================================================
# 📊 KPIs
# ======================================================
k1, k2, k3, k4, k5 = st.columns(5)
# Removido o delta do k1 para não gerar setinha vermelha/verde confusa. Foco no número seco.
k1.metric("Score Geral", f"{score_final*100:.1f} / 100") 
k2.metric("Ticket Médio", f"R$ {ticket_medio:.2f}")
k3.metric("Diversificação (HHI)", f"{hhi:.3f}")
k4.metric("Dependência Top 3", f"{top3_share:.1%}")
k5.metric("Score de Risco", f"{score_risco*100:.1f} / 100")

st.write("") # Espaçamento

# ======================================================
# 📊 DECOMPOSIÇÃO E HEATMAP LADO A LADO
# ======================================================
col_chart1, col_chart2 = st.columns(2)

with col_chart1:
    st.markdown("##### Decomposição do Score")
    df_score = pd.DataFrame({
        "Componente": ["Qualidade", "Diversificação", "Ticket Médio", "Concentração", "Segurança (Risco)"],
        "Peso": [0.25, 0.20, 0.15, 0.20, 0.20],
        "Score Obtido": [score_qualidade, score_diversificacao, score_ticket, score_conc, score_risco]
    })
    df_score["Contribuição Final"] = df_score["Peso"] * df_score["Score Obtido"]

    chart_score = alt.Chart(df_score).mark_bar(cornerRadiusEnd=4).encode(
        x=alt.X("Contribuição Final:Q", title="Pontos Adicionados"),
        y=alt.Y("Componente:N", sort="-x", title=None),
        color=alt.Color("Componente:N", legend=None),
        tooltip=["Componente", alt.Tooltip("Score Obtido:Q", format=".2f"), alt.Tooltip("Contribuição Final:Q", format=".3f")]
    ).properties(height=300)
    st.altair_chart(chart_score, use_container_width=True)

with col_chart2:
    st.markdown("##### Concentração Financeira (Categoria x Grade)")
    heat_df = df.groupby(["Categoria", "Grade"])["Valor Total"].sum().reset_index()
    heatmap = alt.Chart(heat_df).mark_rect().encode(
        x=alt.X("Categoria:N", title=None, axis=alt.Axis(labelAngle=-45)),
        y=alt.Y("Grade:N", title="Grade"),
        color=alt.Color("Valor Total:Q", scale=alt.Scale(scheme="reds"), title="Capital (R$)"),
        tooltip=["Categoria", "Grade", alt.Tooltip("Valor Total:Q", format=",.2f")]
    ).properties(height=300)
    st.altair_chart(heatmap, use_container_width=True)

# ======================================================
# 🎯 SCATTER – MATRIZ DE RISCO vs CAPITAL (INTERATIVO)
# ======================================================
st.markdown("##### Matriz de Risco x Capital Pressionado")
st.markdown("💡 **Como ler:** Arraste e use o scroll do mouse para dar zoom. Itens no quadrante **superior direito** (Muito Risco + Muito Dinheiro Investido) são os verdadeiros perigos do lote.")

colunas_tooltip = ["Categoria", "Grade", alt.Tooltip("Valor Unit:Q", format=".2f"), "Qtd", alt.Tooltip("risco_item:Q", format=".2f")]
if "Descrição do Item" in df.columns:
    colunas_tooltip.insert(0, "Descrição do Item")

# Definindo cores fixas para as grades para ficar visualmente padronizado
cores_grade_chart = alt.Scale(
    domain=["A", "B", "C", "D", "E", "U"],
    range=["#2ecc71", "#f1c40f", "#e67e22", "#e74c3c", "#8e44ad", "#7f8c8d"]
)

scatter = alt.Chart(df).mark_circle(opacity=0.6).encode(
    # O Eixo X agora é o Risco! Fica muito mais fácil de ver o que é perigoso.
    x=alt.X("risco_item:Q", title="Grau de Risco (0 = Seguro | 1 = Perigoso)", scale=alt.Scale(domain=[-0.05, 1.05])),
    
    # O Eixo Y agora é o Valor Total. Mostra onde seu dinheiro está preso.
    y=alt.Y("Valor Total:Q", title="Capital Total no Item (R$)"),
    
    # O tamanho da bolha mostra o volume físico (quantidade)
    size=alt.Size("Qtd:Q", scale=alt.Scale(range=[20, 800]), title="Quantidade"),
    
    # A cor mostra a Grade
    color=alt.Color("Grade:N", scale=cores_grade_chart, title="Grade"),
    
    tooltip=colunas_tooltip
).properties(
    height=500
).interactive() # <-- ISSO AQUI MUDA TUDO! Permite dar zoom e navegar.

# Adicionando linhas de "Atenção" no meio do gráfico para dividir em quadrantes
linha_risco = alt.Chart(pd.DataFrame({'x': [0.6]})).mark_rule(color='red', strokeDash=[5, 5]).encode(x='x')
linha_capital = alt.Chart(pd.DataFrame({'y': [df['Valor Total'].mean() * 2]})).mark_rule(color='orange', strokeDash=[5, 5]).encode(y='y')

st.altair_chart(scatter + linha_risco + linha_capital, use_container_width=True)

# ======================================================
# 💰 SIMULADOR DE LANCE MÁXIMO (PRECIFICAÇÃO REVERSA)
# ======================================================
st.divider()
st.title("💰 Simulador de Preço Teto (Lance Máximo)")

st.markdown("""
Esta calculadora usa engenharia reversa para descobrir o **lance máximo** seguro a se pagar pelo lote, 
garantindo sua margem de lucro e cobrindo os custos de venda, considerando que você venderá abaixo do preço de mercado.
""")

# Parâmetros Interativos
col_sim1, col_sim2, col_sim3, col_sim4 = st.columns(4)

# O usuário informou que quer lucrar 15%
margem_lucro = col_sim1.number_input("🎯 Lucro Desejado (%)", min_value=1, max_value=100, value=15) / 100
desconto_mercado = col_sim2.number_input("📉 Desconto de Venda (%)", min_value=0, max_value=100, value=20, help="Desconto para vender mais rápido/barato que o mercado") / 100
custo_operacional = col_sim3.number_input("⚙️ Custos Operacionais (%)", min_value=0, max_value=100, value=25, help="Taxas de marketplace (ex: 16%), impostos, embalagem") / 100
peso_grade_u = col_sim4.number_input("📦 Aproveitamento Grade 'U' (%)", min_value=0, max_value=100, value=25, help="Como 'U' é sem triagem, qual % você acha que vai salvar?") / 100

# Recalculando o peso de cada item com o novo peso interativo da Grade U
pesos_grade_financeiro = {
    "A": 1.00, 
    "B": 0.9, 
    "C": 0.60, 
    "D": 0.35, 
    "E": 0.10, 
    "U": peso_grade_u # Peso dinâmico definido por você
}
df["peso_venda"] = df["Grade"].map(pesos_grade_financeiro).fillna(0)

# ==================== A MATEMÁTICA ====================

# 1. Valor Total de prateleira (se tudo fosse Grade A)
valor_tabela_total = df["Valor Total"].sum()

# 2. Valor Recuperável (Descontando as avarias baseadas na Grade)
valor_recuperavel = (df["Valor Total"] * df["peso_venda"]).sum()

# 3. Faturamento Bruto Estimado (Descontando o percentual para vender mais barato)
faturamento_estimado = valor_recuperavel * (1 - desconto_mercado)

# 4. Deduções
despesas_totais = faturamento_estimado * custo_operacional
lucro_em_reais = faturamento_estimado * margem_lucro

# 5. PREÇO TETO DE COMPRA (O que sobra é o máximo que você pode pagar)
# Obs: O lote cobra tributos sobre o valor do lance. Se o imposto do leilão for ex: 5%, precisaria dividir o teto por 1.05
preco_teto = faturamento_estimado - despesas_totais - lucro_em_reais

# ==================== VISUALIZAÇÃO ====================
st.markdown("### Resumo Financeiro da Operação")

metric1, metric2, metric3, metric4 = st.columns(4)
metric1.metric("1. Valor de Tabela (Bruto)", f"R$ {valor_tabela_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
metric2.metric("2. Valor c/ Avarias (Recuperável)", f"R$ {valor_recuperavel:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
metric3.metric("3. Faturamento Esperado (Com Desconto)", f"R$ {faturamento_estimado:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
metric4.metric(f"💰 SEU LUCRO ({margem_lucro*100:.0f}%)", f"R$ {lucro_em_reais:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

st.success(f"🛑 **PREÇO TETO DO LANCE:** O valor máximo a pagar no lote é **R$ {preco_teto:,.2f}**".replace(",", "X").replace(".", ",").replace("X", "."))

# Gráfico de Cascata (Waterfall) simulado em barras para demonstrar a "mordida" no valor
df_waterfall = pd.DataFrame({
    "Etapa": [
        "1. Valor Original", 
        "2. Perda por Avarias", 
        "3. Desconto p/ Mercado", 
        "4. Custos Operacionais", 
        "5. SEU LUCRO", 
        "👉 LANCE MÁXIMO"
    ],
    "Valor (R$)": [
        valor_tabela_total,
        -(valor_tabela_total - valor_recuperavel),
        -(valor_recuperavel - faturamento_estimado),
        -despesas_totais,
        -lucro_em_reais,
        preco_teto
    ]
})

chart_financeiro = alt.Chart(df_waterfall).mark_bar().encode(
    x=alt.X("Etapa:N", sort=None, title=None, axis=alt.Axis(labelAngle=-15)),
    y=alt.Y("Valor (R$):Q", title="Reais (R$)"),
    color=alt.condition(
        alt.datum['Valor (R$)'] > 0,
        alt.value("#2ecc71"),  # Verde para Valores Positivos
        alt.value("#e74c3c")   # Vermelho para Descontos
    ),
    tooltip=["Etapa", alt.Tooltip("Valor (R$):Q", format=",.2f")]
).properties(height=350, title="Decomposição de Valor (De onde o dinheiro sai)")

st.altair_chart(chart_financeiro, use_container_width=True)