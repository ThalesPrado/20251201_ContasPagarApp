import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os

# Configurações gerais
ARQUIVO_CONTAS = "contas_a_pagar.csv"
HISTORICO_CONTAS = os.path.expanduser("~/Downloads/historico_contas.xlsx")

# Funções auxiliares
def carregar_dados():
    if os.path.exists(ARQUIVO_CONTAS):
        return pd.read_csv(ARQUIVO_CONTAS)
    else:
        return pd.DataFrame(columns=["Nome", "Descrição", "Valor", "Vencimento", "Situação", "Método de Pagamento", "Chave PIX", "Juros", "Data de Pagamento"])

def salvar_dados(df):
    df.to_csv(ARQUIVO_CONTAS, index=False)
    salvar_historico(df)

def salvar_historico(df):
    if not os.path.exists(HISTORICO_CONTAS):
        with pd.ExcelWriter(HISTORICO_CONTAS, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="Lançamentos", index=False)
            df.to_excel(writer, sheet_name="Histórico", index=False)
    else:
        historico = pd.read_excel(HISTORICO_CONTAS, sheet_name="Histórico")
        historico = pd.concat([historico, df], ignore_index=True)
        historico.drop_duplicates(inplace=True)
        with pd.ExcelWriter(HISTORICO_CONTAS, engine="openpyxl", mode="w") as writer:
            df.to_excel(writer, sheet_name="Lançamentos", index=False)
            historico.to_excel(writer, sheet_name="Histórico", index=False)

def calcular_juros_e_totais(df):
    hoje = datetime.now().date()
    df["Dias Restantes"] = df["Vencimento"].apply(lambda x: max((pd.to_datetime(x).date() - hoje).days, 0))
    df["Dias em Atraso"] = df["Vencimento"].apply(lambda x: max((hoje - pd.to_datetime(x).date()).days, 0))
    df["Juros Calculados"] = df.apply(lambda x: round(x["Valor"] * ((1 + x["Juros"]) ** x["Dias em Atraso"] - 1), 2) if x["Dias em Atraso"] > 0 else 0.0, axis=1)
    df["Valor Total"] = df["Valor"] + df["Juros Calculados"]
    return df

# Interface Streamlit
st.title("Gerenciador de Contas a Pagar")
st.sidebar.title("Menu")
st.sidebar.markdown("**Escolha uma opção:**")
opcao = st.sidebar.selectbox("Opções", ["1. Adicionar Conta", "2. Mostrar Sumário", "3. Notificações", "4. Dar Baixa", "5. Editar Conta", "6. Excluir Conta", "7. Limpar Contas", "8. Sair"])

if "1." in opcao:
    st.subheader("Adicionar Conta")
    if "form_submitted" not in st.session_state:
        st.session_state["form_submitted"] = False

    if st.session_state["form_submitted"]:
        st.experimental_rerun()

    with st.form("form_add_conta"):
        nome = st.text_input("Nome da Conta")
        descricao = st.text_area("Descrição")
        valor = st.number_input("Valor", min_value=0.0, step=0.01)
        vencimento = st.date_input("Vencimento")
        metodo_pagamento = st.selectbox("Método de Pagamento", ["PIX", "Dinheiro", "TED", "Cheque", "Transferência", "Outros"])
        pix = st.text_input("Chave PIX (se aplicável)") if metodo_pagamento == "PIX" else ""
        juros = st.number_input("Juros Diário (%)", min_value=0.0, step=0.1)
        submitted = st.form_submit_button("Adicionar Conta")

        if submitted:
            df = carregar_dados()
            nova_conta = {
                "Nome": nome,
                "Descrição": descricao,
                "Valor": valor,
                "Vencimento": vencimento,
                "Situação": "Não Pago",
                "Método de Pagamento": metodo_pagamento,
                "Chave PIX": pix,
                "Juros": juros / 100,
                "Data de Pagamento": None
            }
            df = pd.concat([df, pd.DataFrame([nova_conta])], ignore_index=True)
            df = calcular_juros_e_totais(df)
            salvar_dados(df)
            st.success(f"Conta '{nome}' adicionada com sucesso!")
            st.session_state["form_submitted"] = True

elif "2." in opcao:
    st.subheader("Mostrar Sumário")
    df = carregar_dados()
    if df.empty():
        st.warning("Nenhuma conta cadastrada.")
    else:
        df = calcular_juros_e_totais(df)
        contas_a_pagar = df[df["Situação"] == "Não Pago"]
        contas_pagas = df[df["Situação"] == "Pago"]
        contas_vencidas = contas_a_pagar[contas_a_pagar["Dias em Atraso"] > 0]

        st.subheader("Contas a Pagar")
        st.dataframe(contas_a_pagar)
        st.subheader("Contas Pagas")
        st.dataframe(contas_pagas)
        st.subheader("Contas Vencidas")
        st.dataframe(contas_vencidas)

        st.subheader("Totais por Mês")
        df["Mês"] = pd.to_datetime(df["Vencimento"]).dt.to_period("M")
        totais_por_mes = df.groupby(["Mês", "Situação"])["Valor"].sum().unstack(fill_value=0)
        st.dataframe(totais_por_mes)

elif "3." in opcao:
    st.subheader("Notificações")
    df = carregar_dados()
    if df.empty():
        st.warning("Nenhuma conta cadastrada.")
    else:
        df = calcular_juros_e_totais(df)
        contas_para_vencer = df[(df["Situação"] == "Não Pago") & (df["Dias Restantes"] <= 3)]
        contas_atrasadas = df[(df["Situação"] == "Não Pago") & (df["Dias em Atraso"] > 0)]

        st.subheader("Contas Próximas do Vencimento (3 dias)")
        st.dataframe(contas_para_vencer)
        st.subheader("Contas Atrasadas")
        st.dataframe(contas_atrasadas)

elif "4." in opcao:
    st.subheader("Dar Baixa")
    df = carregar_dados()
    if df.empty():
        st.warning("Nenhuma conta cadastrada para dar baixa.")
    else:
        conta = st.selectbox("Selecione a conta", df[df["Situação"] == "Não Pago"]["Nome"])
        if st.button("Dar Baixa"):
            df.loc[df["Nome"] == conta, "Situação"] = "Pago"
            df.loc[df["Nome"] == conta, "Data de Pagamento"] = datetime.now().date()
            df = calcular_juros_e_totais(df)
            salvar_dados(df)
            st.success(f"Conta '{conta}' marcada como paga.")

elif "5." in opcao:
    st.subheader("Editar Conta")
    df = carregar_dados()
    if df.empty():
        st.warning("Nenhuma conta cadastrada para editar.")
    else:
        conta = st.selectbox("Selecione a conta", df["Nome"])
        if conta:
            indice = df[df["Nome"] == conta].index[0]
            with st.form("form_edit_conta"):
                descricao = st.text_area("Descrição", value=df.loc[indice, "Descrição"])
                valor = st.number_input("Valor", value=df.loc[indice, "Valor"], step=0.01)
                vencimento = st.date_input("Vencimento", value=pd.to_datetime(df.loc[indice, "Vencimento"], format="%Y-%m-%d"))
                metodo_pagamento = st.selectbox("Método de Pagamento", ["PIX", "Dinheiro", "TED", "Cheque", "Transferência", "Outros"], index=["PIX", "Dinheiro", "TED", "Cheque", "Transferência", "Outros"].index(df.loc[indice, "Método de Pagamento"]))
                pix = st.text_input("Chave PIX", value=df.loc[indice, "Chave PIX"])
                juros = st.number_input("Juros Diário (%)", value=df.loc[indice, "Juros"] * 100, step=0.1)
                submitted = st.form_submit_button("Salvar Alterações")

                if submitted:
                    df.loc[indice, "Descrição"] = descricao
                    df.loc[indice, "Valor"] = valor
                    df.loc[indice, "Vencimento"] = vencimento
                    df.loc[indice, "Método de Pagamento"] = metodo_pagamento
                    df.loc[indice, "Chave PIX"] = pix
                    df.loc[indice, "Juros"] = juros / 100
                    df = calcular_juros_e_totais(df)
                    salvar_dados(df)
                    st.success("Alterações salvas com sucesso!")

elif "6." in opcao:
    st.subheader("Excluir Conta")
    df = carregar_dados()
    if df.empty():
        st.warning("Nenhuma conta cadastrada para excluir.")
    else:
        conta = st.selectbox("Selecione a conta para excluir", df["Nome"])
        if st.button("Excluir Conta"):
            df = df[df["Nome"] != conta]
            salvar_dados(df)
            st.success(f"Conta '{conta}' excluída com sucesso!")

elif "7." in opcao:
    st.subheader("Limpar Contas")
    if st.button("Limpar Todas as Contas"):
        if os.path.exists(ARQUIVO_CONTAS):
            os.remove(ARQUIVO_CONTAS)
            st.success("Todas as contas foram removidas com sucesso!")
        else:
            st.warning("Nenhuma conta encontrada para limpar.")

elif "8." in opcao:
    st.info("Obrigado por usar o sistema! O histórico foi salvo na pasta Downloads.")
    st.success("Por favor, envie o arquivo Excel para o Kleber.")
