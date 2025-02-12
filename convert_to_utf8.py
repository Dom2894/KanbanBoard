# Script per convertire un file in UTF-8
import shutil

input_file = 'app.py'  # Nome del file originale
output_file = 'app_utf8.py'  # Nome del file convertito

try:
    # Leggi il file con la codifica originale (ad esempio, CP1252)
    with open(input_file, 'r', encoding='cp1252') as file:
        content = file.read()

    # Scrivi il file con codifica UTF-8
    with open(output_file, 'w', encoding='utf-8') as file:
        file.write(content)

    print(f"File convertito da {input_file} a {output_file}.")
except Exception as e:
    print(f"Errore durante la conversione: {e}")