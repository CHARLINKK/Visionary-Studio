import os
import sys
import json
import zipfile
from datetime import datetime

# Adiciona a raiz do projeto ao sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils.page_store import PageStore

def migrate_raw_directory(raw_dir: str):
    """
    Localiza todos os arquivos _map.json legados em raw_dir,
    cria um backup de segurança .zip de todos os JSONs,
    e consolida os balões e painéis no Envelope Canônico v2 via PageStore.
    """
    if not os.path.isdir(raw_dir):
        print(f"[ERRO] Diretório não encontrado: {raw_dir}")
        return

    # 1. Localizar todos os arquivos JSON de mapas
    map_files = []
    for root, dirs, files in os.walk(raw_dir):
        for f in files:
            if f.endswith("_map.json"):
                map_files.append(os.path.join(root, f))

    if not map_files:
        print("[INFO] Nenhum arquivo _map.json encontrado.")
        return

    print(f"[*] Encontrados {len(map_files)} arquivos de mapa em {raw_dir}.")

    # 2. Criar BACKUP de segurança COMPLETO em .zip antes de qualquer alteração
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_zip_path = os.path.join(raw_dir, f"_backup_v1_legacy_{timestamp}.zip")
    print(f"[*] Criando backup de segurança de todos os JSONs em: {backup_zip_path}...")
    
    with zipfile.ZipFile(backup_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(raw_dir):
            for f in files:
                if f.endswith(".json") and not f.startswith("_backup"):
                    full_path = os.path.join(root, f)
                    arcname = os.path.relpath(full_path, raw_dir)
                    zipf.write(full_path, arcname)

    print(f"[OK] Backup concluído com sucesso ({os.path.getsize(backup_zip_path)} bytes).")

    # 3. Executar a migração via PageStore com verificação estrita de dados
    migrated_count = 0
    already_v2_count = 0
    error_count = 0

    for map_path in map_files:
        try:
            with open(map_path, "r", encoding="utf-8") as f:
                raw_data = json.load(f)

            if isinstance(raw_data, dict) and raw_data.get("version") == 2:
                panels = raw_data.get("panels", [])
                has_corrupted_panels = any(
                    isinstance(p, dict) and (p.get("label") == "text_bubble" or p.get("is_bubble"))
                    for p in panels
                )
                if has_corrupted_panels:
                    record = PageStore.load_page_record(map_path)
                    PageStore.save_page_record(
                        map_path,
                        boxes=record["boxes"],
                        panels=record["panels"],
                        backup=record["backup"]
                    )
                    migrated_count += 1
                    print(f"  [+] Purificado panels v2: {os.path.relpath(map_path, raw_dir)}")
                else:
                    already_v2_count += 1
                continue

            orig_boxes_count = len(raw_data) if isinstance(raw_data, list) else len(raw_data.get("boxes", []))

            # Carrega via PageStore (absorve transparentemente _panels.json e _map_backup.json se existirem)
            record = PageStore.load_page_record(map_path)
            
            # Validação de integridade: número de caixas deve ser exatamente igual
            if len(record["boxes"]) != orig_boxes_count:
                raise ValueError(f"Inconsistência na contagem de caixas: esperado {orig_boxes_count}, obteve {len(record['boxes'])}")

            # Salva o Envelope Canônico v2 e limpa os arquivos satélites obsoletos
            PageStore.save_page_record(map_path)
            migrated_count += 1
            print(f"  [+] Migrado v2: {os.path.relpath(map_path, raw_dir)} ({len(record['boxes'])} caixas, {len(record['panels'])} painéis)")

        except Exception as e:
            error_count += 1
            print(f"  [-] ERRO ao migrar {map_path}: {e}")

    print("\n" + "="*60)
    print(" [RELATORIO DE MIGRACAO V1 -> V2]")
    print("="*60)
    print(f"   • Total de mapas encontrados:   {len(map_files)}")
    print(f"   • Migrados com sucesso para v2: {migrated_count}")
    print(f"   • Já estavam no formato v2:     {already_v2_count}")
    print(f"   • Erros encontrados:            {error_count}")
    print(f"   • Backup de segurança salvo em: {backup_zip_path}")
    print("="*60)

if __name__ == "__main__":
    target = r"V:\Genikasuri\RAW"
    if len(sys.argv) > 1:
        target = sys.argv[1]
    migrate_raw_directory(target)
