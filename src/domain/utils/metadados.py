from pathlib import Path
import pandas as pd
import os


def ajustando_metadados_ligacoes_existentes(metadados_ligacoes_existentes_df: dict[list, list], df_arquivo_metadados: pd.DataFrame) -> pd.DataFrame:

    index_df_com_audios_existentes = metadados_ligacoes_existentes_df['index_df_com_audios_existentes']

    nome_audios_existentes = metadados_ligacoes_existentes_df['nome_audio_existente']

    # MATENDO NO DATAFRAME APENAS AS LIGACOES EXISTENTES
    df_hvoice_metadados = df_arquivo_metadados[df_arquivo_metadados.index.isin(index_df_com_audios_existentes)]

    # ADICIONANDO NA PRIMEIRA POSIÇÃO A COLUNA NOME AUDIO
    if 'nome_audio' not in df_hvoice_metadados.columns:
        df_hvoice_metadados.insert(0, 'nome_audio', "")

    df_hvoice_metadados.loc[index_df_com_audios_existentes, 'nome_audio'] = nome_audios_existentes


    # APAGANDO COLUNAS call_id e call_id_telecon
    colunas_para_remover = [
        '[Call ID (Controle Interno)]',
        'Call ID (Controle Interno)',
        '[CALL ID (CONTROLE INTERNO)]',
        'CALL ID (CONTROLE INTERNO)',
        '[CALL ID TAB(CONTROLE INTERNO)]',
        'CALL ID TAB(CONTROLE INTERNO)'
    ]

    colunas_existentes = [c for c in colunas_para_remover if c in df_hvoice_metadados.columns]

    df_hvoice_metadados = df_hvoice_metadados.drop(columns=colunas_existentes, errors='ignore')

    return df_hvoice_metadados


def ajustando_metadados_ligacoes_existentes_geral(metadados_ligacoes_existentes_df: dict[list, list], df_arquivo_metadados: pd.DataFrame) -> pd.DataFrame:

    index_df_com_audios_existentes = metadados_ligacoes_existentes_df['index_df_com_audios_existentes']

    nome_audios_existentes = metadados_ligacoes_existentes_df['nome_audio_existente']

    # MATENDO NO DATAFRAME APENAS AS LIGACOES EXISTENTES
    df_hvoice_metadados = df_arquivo_metadados[df_arquivo_metadados.index.isin(index_df_com_audios_existentes)]

    # ADICIONANDO NA PRIMEIRA POSIÇÃO A COLUNA NOME AUDIO
    if 'nome_audio' not in df_hvoice_metadados.columns:
        df_hvoice_metadados.insert(0, 'nome_audio', "")

    df_hvoice_metadados.loc[index_df_com_audios_existentes, 'nome_audio'] = nome_audios_existentes


    # APAGANDO COLUNAS call_id e call_id_telecon
    df_hvoice_metadados = df_hvoice_metadados.drop('[CALL ID TAB(CONTROLE INTERNO)]', axis=1)

    return df_hvoice_metadados


def salvando_arquivo_metadado(
    df_arquivo_metadados: pd.DataFrame,
    diretorio_raiz_hvoice: str,
    carteira: str,
    tipo_envio: str,
    data_hvoice: str,
    nome_pasta: str
):
    tipo_envio_str = tipo_envio[0] if isinstance(tipo_envio, (list, tuple)) else str(tipo_envio)
    nome_pasta = f"{nome_pasta}_{data_hvoice}"

    diretorio = os.path.join(diretorio_raiz_hvoice, nome_pasta)
    os.makedirs(diretorio, exist_ok=True)

    df_arquivo_metadados.to_csv(
        f"{diretorio}/atendimentos_{data_hvoice}.csv",
        index=False
    )
