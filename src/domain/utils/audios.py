from typing import Literal, List
from mutagen.mp3 import MP3
from pathlib import Path
import pandas as pd
import shutil
import os
import math


def _retorno_audios(nome_audio_existente, caminho_completo_audios_existentes, index_df_com_audios_existentes, total_segundos):
    return {
        'nome_audio_existente': nome_audio_existente,
        'caminho_completo_audios_existentes': caminho_completo_audios_existentes,
        'index_df_com_audios_existentes': index_df_com_audios_existentes,
        'total_segundos_audios': total_segundos,
        'total_minutos_audios': total_segundos / 60
    }


def _nome_audio_com_data_hora(nome_arquivo: str, data_hora: str) -> str:
    data_hora_nome = (
        data_hora
        .replace('/', '-')
        .replace(':', '-')
        .replace(' ', '_')
    )
    caminho = Path(nome_arquivo)
    return f"{caminho.stem}_{data_hora_nome}.wav"


def selecionado_audios_existentes(df_arquivo_metadados: pd.DataFrame, valor_tempo: int) -> dict:
     # Limite de segundos a acumular
    limite_segundos = valor_tempo * 60

    total_segundos = 0
    nome_audio_existente = []
    caminho_completo_audios_existentes = []
    index_df_com_audios_existentes = []

    diretorio_raiz_audios_olos = r'\\10.0.0.30\Audio\Olos_P3\RBM'

    def _find_col(df, candidatos):
        cols_norm = {c.lower().replace("[","").replace("]","").strip(): c for c in df.columns}

        for cand in candidatos:
            cand_norm = cand.lower().replace("[","").replace("]","").strip()
            if cand_norm in cols_norm:
                return cols_norm[cand_norm]

        return None

    col_data = _find_col(df_arquivo_metadados, ['Data Hora do Acionamento', '[Data Hora do Acionamento]'])
    col_call = _find_col(df_arquivo_metadados, ['Call ID (Controle Interno)', '[Call ID (Controle Interno)]'])

    if not col_data or not col_call:
        print(" Colunas não encontradas.")
        print("Colunas disponíveis:", df_arquivo_metadados.columns.tolist())
        return _retorno_audios([], [], [], total_segundos)

    for index in df_arquivo_metadados.index:
        valor_data = str(df_arquivo_metadados.loc[index, col_data]).strip()
        call_id = str(df_arquivo_metadados.loc[index, col_call]).strip()

        if not valor_data or valor_data.lower() in ['nan', 'nat', 'none']:
            print(f"Linha ignorada: data inválida -> {valor_data}")
            continue

        partes = valor_data.split(' ')
        if len(partes) < 2:
            print(f"Linha ignorada: formato incorreto de data/hora -> {valor_data}")
            continue

        data, hora = partes[0], partes[1]
        ano, mes, dia = data[:4], data[5:7], data[8:10]
        hora_inicial = hora[:2] if len(hora) >= 2 else "00"

        diretorio_audios_olos_completo = os.path.join(
            diretorio_raiz_audios_olos,
            ano,
            f"{ano}{mes}",
            f"{ano}{mes}{dia}",
            f"{ano}{mes}{dia}{hora_inicial}"
        )

        if not os.path.exists(diretorio_audios_olos_completo):
            continue

        for arquivos_olos in os.listdir(diretorio_audios_olos_completo):
            if f'{call_id}_' not in arquivos_olos:
                continue

            caminho_audio = os.path.join(diretorio_audios_olos_completo, arquivos_olos)

            try:
                audio = MP3(caminho_audio)
                duracao_segundos = int(round(audio.info.length))
            except Exception as e:
                print(f"Erro ao ler {caminho_audio}: {e}")
                continue

            total_segundos += duracao_segundos

            nome_wav = _nome_audio_com_data_hora(arquivos_olos, valor_data)

            if nome_wav not in nome_audio_existente:
                nome_audio_existente.append(nome_wav)
                caminho_completo_audios_existentes.append(caminho_audio)
                index_df_com_audios_existentes.append(index)

            minutos_atuais = math.ceil(total_segundos / 60)
            print(f"Acumulado: {total_segundos}s (~{minutos_atuais} min)")

            if total_segundos >= limite_segundos:
                print(f"Passou do limite de {valor_tempo} minutos")
                return _retorno_audios(
                    nome_audio_existente,
                    caminho_completo_audios_existentes,
                    index_df_com_audios_existentes,
                    total_segundos
                )

    return _retorno_audios(
        nome_audio_existente,
        caminho_completo_audios_existentes,
        index_df_com_audios_existentes,
        total_segundos
    )


def selecionado_audios_existentes_geral(
    df_arquivo_metadados: pd.DataFrame,
    max_minuto_total: float,
    qtd_por_operador: int = 1
) -> dict:

    limite_segundos = max_minuto_total * 60
    total_segundos = 0
    nome_audio_existente = []
    caminho_completo_audios_existentes = []
    index_df_com_audios_existentes = []

    diretorio_raiz_audios_olos = r"\\10.0.0.30\Audio\Olos_P2\RBM"

    def _find_col(df, candidatos):
        for c in candidatos:
            if c in df.columns:
                return c
        for c in df.columns:
            c_normal = c.replace('[','').replace(']','').strip().lower()
            for cand in candidatos:
                if cand.replace('[','').replace(']','').strip().lower() == c_normal:
                    return c
        return None

    col_data = _find_col(df_arquivo_metadados, ['Data Hora do Acionamento', '[Data Hora do Acionamento]'])
    col_call = _find_col(df_arquivo_metadados, [
        'CALL ID TAB(CONTROLE INTERNO)', '[CALL ID TAB(CONTROLE INTERNO)]',
        'CALL ID (CONTROLE INTERNO)', '[CALL ID (CONTROLE INTERNO)]'
    ])
    col_operador = _find_col(
        df_arquivo_metadados,
        ['ID do Operador', '[ID do Operador]']
    )

    if not col_data or not col_call or not col_operador:
        print(" Colunas obrigatórias não encontradas.")
        print("Colunas disponíveis:", df_arquivo_metadados.columns.tolist())
        return _retorno_audios([], [], [], total_segundos)

    selecionados_por_operador = {}

    for index in df_arquivo_metadados.index:
        operador = str(df_arquivo_metadados.loc[index, col_operador]).strip()
        if selecionados_por_operador.get(operador, 0) >= qtd_por_operador:
            continue

        valor_data = str(df_arquivo_metadados.loc[index, col_data]).strip()
        call_id = str(df_arquivo_metadados.loc[index, col_call]).strip()

        if not valor_data or valor_data.lower() in ['nan', 'nat', 'none']:
            print(f"Linha ignorada: data inválida -> {valor_data}")
            continue

        partes = valor_data.split(' ')
        if len(partes) < 2:
            print(f"Linha ignorada: formato incorreto de data/hora -> {valor_data}")
            continue

        data, hora = partes[0], partes[1]
        ano, mes, dia = data[:4], data[5:7], data[8:10]
        hora_inicial = hora[:2] if len(hora) >= 2 else "00"

        diretorio_audios_olos_completo = os.path.join(
            diretorio_raiz_audios_olos,
            ano,
            f"{ano}{mes}",
            f"{ano}{mes}{dia}",
            f"{ano}{mes}{dia}{hora_inicial}"
        )

        if not os.path.exists(diretorio_audios_olos_completo):
            continue

        for arquivo in sorted(os.listdir(diretorio_audios_olos_completo)):
            if f"{call_id}_" not in arquivo or not arquivo.endswith(".mp3"):
                continue

            caminho_audio = os.path.join(diretorio_audios_olos_completo, arquivo)
            try:
                audio = MP3(caminho_audio)
                duracao_segundos = int(round(audio.info.length))
            except Exception as e:
                print(f"Erro ao ler {caminho_audio}: {e}")
                continue

            total_segundos += duracao_segundos
            nome_wav = _nome_audio_com_data_hora(arquivo, valor_data)

            if nome_wav not in nome_audio_existente:
                nome_audio_existente.append(nome_wav)
                caminho_completo_audios_existentes.append(caminho_audio)
                index_df_com_audios_existentes.append(index)
                selecionados_por_operador[operador] = (
                    selecionados_por_operador.get(operador, 0) + 1
                )

            minutos_atuais = math.ceil(total_segundos / 60)
            print(f"Acumulado: {total_segundos}s (~{minutos_atuais} min)")

            if total_segundos >= limite_segundos:
                print(f"Limite de {max_minuto_total} minutos atingido.")
                return _retorno_audios(
                    nome_audio_existente,
                    caminho_completo_audios_existentes,
                    index_df_com_audios_existentes,
                    total_segundos
                )

            # Um caso deve gerar somente um audio. A ordenacao acima torna a
            # escolha repetivel caso existam arquivos com o mesmo prefixo.
            break

    return _retorno_audios(
        nome_audio_existente,
        caminho_completo_audios_existentes,
        index_df_com_audios_existentes,
        total_segundos
    )


def salvando_arquivo_audio(
    caminho_completo_audios_existentes: list,
    diretorio_raiz_hvoice: str,
    carteira: str,
    tipo_envio: str,
    data_hvoice: str,
    nome_pasta: str,
    nome_audio_existente: list = None
):

    tipo_envio_str = tipo_envio[0] if isinstance(tipo_envio, (list, tuple)) else str(tipo_envio)
    nome_pasta = f"{nome_pasta}_{data_hvoice}"

    diretorio_temp = Path(diretorio_raiz_hvoice) / nome_pasta
    os.makedirs(diretorio_temp, exist_ok=True)

    # ======================================================
    # LIMPAR PASTA TEMP
    # ======================================================

    for arquivo in diretorio_temp.iterdir():
        try:
            if arquivo.is_file():
                arquivo.unlink()
        except Exception as e:
            print(f"Erro ao limpar arquivo {arquivo.name}: {e}")

    # ======================================================
    # VERIFICA SE HÁ ÁUDIOS
    # ======================================================

    if not caminho_completo_audios_existentes:
        return

    # ======================================================
    # PROCESSA CADA ÁUDIO
    # ======================================================

    for index, caminho_audio in enumerate(caminho_completo_audios_existentes):
        try:
            origem = Path(caminho_audio)

            if not origem.exists():
                continue

            nome_destino = origem.name
            if nome_audio_existente and index < len(nome_audio_existente):
                nome_destino = Path(nome_audio_existente[index]).with_suffix(origem.suffix).name

            destino = Path(fr"\\?\{diretorio_temp}") / nome_destino
            try:
                shutil.copy2(str(origem), str(destino))
            except Exception as e:
                print(f"FALHA AO COPIAR {origem} → {e}")

        except Exception as e:
            print(f"ERRO GERAL no processamento do arquivo {caminho_audio}: {e}")

    # ======================================================
    # CONVERTE PARA WAV E REMOVE
    # ======================================================

    for arquivo in diretorio_temp.iterdir():
        if arquivo.suffix.lower() == ".mp3":
            try:
                wav_file = arquivo.with_suffix(".wav")
                shutil.copy2(str(arquivo), str(wav_file))
            except Exception as e:
                print(f"ERRO ao criar WAV {arquivo.name}: {e}")

    for arquivo in diretorio_temp.iterdir():
        if arquivo.suffix.lower() == ".mp3":
            try:
                arquivo.unlink()
            except Exception as e:
                print(f"ERRO ao remover MP3 {arquivo.name}: {e}")
