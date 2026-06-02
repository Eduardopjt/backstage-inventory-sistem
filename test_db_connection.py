#!/usr/bin/env python3
"""
Script para testar conexão com Supabase PostgreSQL
Execute com: python test_db_connection.py
"""

import os
import sys
from dotenv import load_dotenv

# Carregar variáveis de .env
load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

print("=" * 60)
print("🔍 TESTE DE CONEXÃO COM SUPABASE")
print("=" * 60)

# Verificar se DATABASE_URL está definido
if not DATABASE_URL:
    print("❌ ERRO: DATABASE_URL não está definido!")
    print("   Configure em: .env ou variáveis de ambiente")
    sys.exit(1)

print(f"\n✓ DATABASE_URL encontrado")
print(f"  Formato: {DATABASE_URL[:50]}...")

# Tentar conectar
try:
    import psycopg2
    print("\n✓ psycopg2 instalado")
    
    print("\n⏳ Tentando conectar ao banco...")
    conn = psycopg2.connect(DATABASE_URL, sslmode="require")
    cursor = conn.cursor()
    
    # Testar query simples
    cursor.execute("SELECT 1")
    result = cursor.fetchone()
    
    if result:
        print("✅ CONECTADO COM SUCESSO!")
        print(f"   Resposta do servidor: {result}")
        
        # Tentar criar tabela de teste
        print("\n⏳ Testando criação de tabela...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_connection (
                id SERIAL PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        print("✅ Tabela de teste criada/verificada")
        
        # Inserir teste
        cursor.execute("INSERT INTO test_connection DEFAULT VALUES RETURNING id")
        test_id = cursor.fetchone()[0]
        conn.commit()
        print(f"✅ Inserção de teste bem-sucedida (ID: {test_id})")
        
        # Limpar
        cursor.execute("DROP TABLE test_connection")
        conn.commit()
        print("✅ Limpeza concluída")
        
        cursor.close()
        conn.close()
        
    else:
        print("❌ Query retornou vazio")
        sys.exit(1)
        
except psycopg2.OperationalError as e:
    print(f"❌ ERRO DE CONEXÃO: {e}")
    print("\nProblemas comuns:")
    print("  1. Senha incorreta no DATABASE_URL")
    print("  2. Supabase projeto não criado")
    print("  3. IP não autorizado (whitelist)")
    print("  4. String de conexão malformada")
    sys.exit(1)
    
except psycopg2.ProgrammingError as e:
    print(f"❌ ERRO SQL: {e}")
    sys.exit(1)
    
except ImportError:
    print("❌ psycopg2 não está instalado!")
    print("   Execute: pip install psycopg2-binary")
    sys.exit(1)
    
except Exception as e:
    print(f"❌ ERRO DESCONHECIDO: {type(e).__name__}: {e}")
    sys.exit(1)

print("\n" + "=" * 60)
print("✅ TODOS OS TESTES PASSARAM!")
print("=" * 60)
print("\nSeu banco de dados está pronto para produção.")
