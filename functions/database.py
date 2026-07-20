import json
import os
import time
import threading
import copy
from typing import Optional, Any
from connections.mongo_db import collection as bot_collection, get_storage_info

class database:
    # Cache em memória para documentos frequentemente acessados
    _cache: dict[str, tuple[Any, float]] = {}
    _cache_lock = threading.Lock()
    _default_ttl = 60  # 60 segundos por padrão
    
    # Documentos que devem ser cacheados por mais tempo (configurações raramente alteradas)
    _long_cache_docs = {
        "custom_mode",
        "custom_colors",
        "canais",
    }
    _long_cache_ttl = 300  # 5 minutos para documentos de configuração
    @staticmethod
    def obter(filename: str):
        try:
            with open(f"{filename}", "r", encoding="utf-8") as file:
                return json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}
    
    @staticmethod
    def salvar(filename: str, data: dict):
        with open(f"{filename}", "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4, ensure_ascii=False)

    @staticmethod
    def get_document(config_type: str):
        """
        Obtém um documento de configuração específico do bot.
        Usa cache em memória para melhorar performance.
        config_type é usado como _id do documento.
        Retorna um dicionário vazio ou lista vazia se nenhum documento for encontrado.
        
        Se o documento contém apenas a chave 'items' (além de _id), retorna a lista diretamente.
        """
        current_time = time.time()
        
        # Verificar cache primeiro
        with database._cache_lock:
            if config_type in database._cache:
                cached_data, expiry_time = database._cache[config_type]
                if current_time < expiry_time:
                    # Cache válido, retornar cópia profunda para evitar mutação
                    return copy.deepcopy(cached_data)
        
        # Cache não encontrado ou expirado, buscar do MongoDB
        try:
            document = bot_collection.find_one({"_id": config_type})
            if document:
                # Remove o _id para manter compatibilidade
                doc_copy = document.copy()
                doc_copy.pop("_id", None)
                
                # Se o documento tem apenas 'items', retornar a lista diretamente
                if len(doc_copy) == 1 and "items" in doc_copy:
                    result = doc_copy["items"]
                else:
                    result = doc_copy
                
                # Armazenar no cache (fazer cópia profunda para evitar mutação)
                cached_result = copy.deepcopy(result)
                ttl = database._long_cache_ttl if config_type in database._long_cache_docs else database._default_ttl
                with database._cache_lock:
                    database._cache[config_type] = (cached_result, current_time + ttl)
                
                # Retornar cópia profunda para evitar mutação
                return copy.deepcopy(result)
            
            # Documento não encontrado, cachear resultado vazio por menos tempo
            empty_result = {}
            with database._cache_lock:
                database._cache[config_type] = (empty_result, current_time + 10)  # 10 segundos para "não encontrado"
            return empty_result
            
        except Exception:
            # Em caso de erro, retornar vazio
            return {}

    @staticmethod
    def get_documents(query: dict = None):
        """
        Obtém múltiplos documentos de configuração do bot.
        Retorna uma lista de dicionários.
        """
        if query is None:
            query = {}
        documents = list(bot_collection.find(query))
        # Remove o _id de cada documento
        for doc in documents:
            doc.pop("_id", None)
        return documents

    @staticmethod
    def delete_document(config_type: str):
        """
        Deleta um documento de configuração específico do bot.
        """
        bot_collection.delete_one({"_id": config_type})
        # Invalidar cache
        with database._cache_lock:
            database._cache.pop(config_type, None)

    @staticmethod
    def delete_documents(query: dict):
        """
        Deleta múltiplos documentos de configuração do bot.
        """
        # Buscar IDs dos documentos que serão deletados para invalidar cache
        documents_to_delete = list(bot_collection.find(query, {"_id": 1}))
        deleted_ids = [doc["_id"] for doc in documents_to_delete]
        
        bot_collection.delete_many(query)
        
        # Invalidar cache dos documentos deletados
        with database._cache_lock:
            for doc_id in deleted_ids:
                database._cache.pop(doc_id, None)
        
    @staticmethod
    def save_document(config_type: str, query_or_data=None, data=None):
        """
        Salva um documento de configuração do bot (atualiza se existir, insere se não).
        config_type é usado como _id do documento.
        
        Aceita duas assinaturas para retrocompatibilidade:
        - save_document(config_type, data) - Nova assinatura
        - save_document(config_type, {}, data) - Assinatura antiga (query ignorado)
        
        Suporta tanto dicionários quanto listas.
        """
        # Se data é None, então query_or_data é o data (nova assinatura)
        if data is None:
            data = query_or_data
        # Caso contrário, query_or_data é o query (ignorado) e data é o terceiro argumento
        
        # Se data é uma lista, encapsular em um dicionário
        if isinstance(data, list):
            document = {
                "_id": config_type,
                "items": data
            }
            cache_data = data
        else:
            # Se é um dicionário, copiar e adicionar _id
            data_copy = data.copy()
            data_copy["_id"] = config_type
            document = data_copy
            # Para cache, remover _id novamente
            cache_data = {k: v for k, v in data_copy.items() if k != "_id"}
            # Se o documento tem apenas 'items', retornar a lista diretamente
            if len(cache_data) == 1 and "items" in cache_data:
                cache_data = cache_data["items"]
        
        bot_collection.replace_one(
            {"_id": config_type},
            document,
            upsert=True
        )
        
        # Atualizar cache imediatamente (fazer cópia profunda)
        current_time = time.time()
        ttl = database._long_cache_ttl if config_type in database._long_cache_docs else database._default_ttl
        cached_data = copy.deepcopy(cache_data)
        with database._cache_lock:
            database._cache[config_type] = (cached_data, current_time + ttl)

    @staticmethod
    def initialize_database_if_needed():
        """
        Verifica se o bot já foi inicializado. Se não, popula a coleção do bot
        com o arquivo consolidado 'database_template.json'.
        Cada chave do JSON vira um documento com _id = nome da chave.
        """
        initialization_doc = bot_collection.find_one({"_id": "_meta_initialization"})

        if initialization_doc:
            # O bot já foi inicializado, não faz nada.
            return

        print("Primeira inicialização detectada. Populando a coleção do bot com valores padrão...")

        template_file = "database_template.json"
        
        try:
            with open(template_file, "r", encoding="utf-8") as f:
                all_configs = json.load(f)
            
            for config_type, default_data in all_configs.items():
                try:
                    if isinstance(default_data, list):
                        # Se for lista, salva como um documento com a lista dentro
                        database.save_document(config_type, {"items": default_data})
                        print(f" - Config '{config_type}' inicializada com {len(default_data)} itens.")
                    else:
                        # Se for dict, salva diretamente
                        database.save_document(config_type, default_data)
                        print(f" - Config '{config_type}' inicializada com sucesso.")
                
                except Exception as e:
                    print(f"Erro ao inicializar a config '{config_type}': {e}")
            
            # Marca que a inicialização foi concluída para não rodar novamente.
            bot_collection.insert_one({
                "_id": "_meta_initialization",
                "initialized_at": os.path.getmtime(template_file)
            })
            print("Inicialização da coleção do bot concluída.")
        
        except FileNotFoundError:
            print(f"ERRO: Arquivo '{template_file}' não encontrado!")
        except json.JSONDecodeError as e:
            print(f"ERRO: Arquivo '{template_file}' contém JSON inválido: {e}")

    @staticmethod
    def verify_and_create_missing_documents():
        """
        Verifica se todos os documentos do template existem na database.
        Se algum estiver faltando, cria com os valores padrão do template.
        Executa toda vez que o bot inicia.
        """
        template_file = "database_template.json"
        
        try:
            with open(template_file, "r", encoding="utf-8") as f:
                all_configs = json.load(f)
            
            missing_count = 0
            for config_type, default_data in all_configs.items():
                # Verifica se o documento existe
                existing_doc = bot_collection.find_one({"_id": config_type})
                
                if not existing_doc:
                    # Documento não existe, criar com valores padrão
                    try:
                        if isinstance(default_data, list):
                            database.save_document(config_type, {"items": default_data})
                            print(f"[Storage] Documento faltante '{config_type}' criado com {len(default_data)} itens.")
                        else:
                            database.save_document(config_type, default_data)
                            print(f"[Storage] Documento faltante '{config_type}' criado com sucesso.")
                        missing_count += 1
                    except Exception as e:
                        print(f"[Storage] Erro ao criar documento '{config_type}': {e}")
            
            if missing_count > 0:
                print(f"[Storage] {missing_count} documento(s) faltante(s) foi(ram) criado(s).")
            else:
                print("[Storage] Todos os documentos do template estão presentes na database.")
        
        except FileNotFoundError:
            print(f"[Storage] ERRO: Arquivo '{template_file}' não encontrado!")
        except json.JSONDecodeError as e:
            print(f"[Storage] ERRO: Arquivo '{template_file}' contém JSON inválido: {e}")
        except Exception as e:
            print(f"[Storage] ERRO ao verificar documentos: {e}")
    
    @staticmethod
    def health_check() -> dict:
        """Valida o backend de persistência e retorna informações seguras."""
        info = get_storage_info()
        probe_id = "_meta_health_check"
        try:
            bot_collection.replace_one(
                {"_id": probe_id},
                {"_id": probe_id, "ok": True, "checked_at": time.time()},
                upsert=True,
            )
            probe = bot_collection.find_one({"_id": probe_id})
            bot_collection.delete_one({"_id": probe_id})
            return {**info, "ok": bool(probe and probe.get("ok"))}
        except Exception as exc:
            return {**info, "ok": False, "error": str(exc)}

    @staticmethod
    def clear_cache(config_type: Optional[str] = None):
        """
        Limpa o cache de documentos.
        
        Args:
            config_type: Se fornecido, limpa apenas o cache deste documento.
                        Se None, limpa todo o cache.
        """
        with database._cache_lock:
            if config_type:
                database._cache.pop(config_type, None)
            else:
                database._cache.clear()
    
    @staticmethod
    def get_cache_stats() -> dict:
        """
        Retorna estatísticas do cache.
        """
        with database._cache_lock:
            current_time = time.time()
            valid_entries = sum(1 for _, (_, expiry) in database._cache.items() if current_time < expiry)
            expired_entries = len(database._cache) - valid_entries
            return {
                "total_entries": len(database._cache),
                "valid_entries": valid_entries,
                "expired_entries": expired_entries,
                "cached_documents": list(database._cache.keys())
            }