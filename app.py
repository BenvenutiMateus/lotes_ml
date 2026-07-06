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
# 🎨 GRADES E CÁLCULOS BASE
# ======================================================
pesos_grade = {"A": 1.00, "B": 0.8, "C": 0.60, "D": 0.50, "E": 0.4, "U": 0.3}
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
ticket_min = 200

if ticket_medio >= ticket_min:
    score_ticket = 1
else:
    score_ticket = ticket_medio / ticket_min

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
df["fora_ticket"] = (df["Valor Unit"] < ticket_min).astype(int)

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
Calcule o ** Lucro esperado ** a partir de custos adicionais, aproveitamento
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

# 1. Valor Total de prateleira
valor_tabela_total = df["Valor Total"].sum()

# 2. Valor Recuperável (Descontando as avarias baseadas na Grade)
valor_recuperavel = (df["Valor Total"] * df["peso_venda"]).sum()

# 3. Faturamento Bruto Estimado
faturamento_estimado = valor_recuperavel * (1 - desconto_venda)

# 4. Deduções
despesas_totais = faturamento_estimado * custos_operacionais


# 6. LUCRO PROJETADO (REAL)
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
        l
        lucro_projetado
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
).properties(height=350, title="Decomposição de Valor para Preço Teto")

st.altair_chart(chart_financeiro, width='stretch')
