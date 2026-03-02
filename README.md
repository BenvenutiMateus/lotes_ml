
# Dashboard de Análise de Lotes

Aplicação Streamlit para análise profissional e precificação de lotes com suporte a múltiplas métricas de risco e simulação de preço teto.

## 🚀 Funcionalidades

- **Upload de arquivos Excel** com dados de lotes
- **5 indicadores de qualidade**: Qualidade, Diversificação, Ticket Médio, Concentração, Risco
- **Score final 0-100** com recomendação executiva (Comprar/Negociar/Evitar)
- **Visualizações interativas**: gráficos de decomposição, heatmap de concentração, matriz risco×capital
- **Simulador de preço teto**: cálculo reverso de lance máximo com margem de lucro configurável

## 📋 Requisitos

- Python 3.8+
- pandas, numpy, altair, streamlit

## 🔧 Instalação

```bash
pip install -r requirements.txt
```

## ▶️ Execução

```bash
streamlit run app.py
```

## 📊 Como Usar

1. Carregue um arquivo Excel (com dados a partir da linha 7)
2. Visualize o score geral e diagnóstico da qualidade
3. Analise a distribuição de risco nos gráficos interativos
4. Configure o simulador para encontrar o lance máximo seguro

## 📁 Estrutura de Dados

O Excel deve conter colunas: Categoria, Grade, Qtd, Valor Unit, Valor Total, Descrição do Item
