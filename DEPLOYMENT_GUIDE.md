# 🚀 Guia de Deployment - Render + Supabase

## Erro 500: Verificação de Checklist

Se você está recebendo erro 500, siga este checklist:

### ✅ 1. Supabase - Pegar String de Conexão Correta

1. Vá para **supabase.com** → Seu projeto
2. Menu lateral: **Settings** → **Database** (ou **Configuration**)
3. Procure por **"Connection string"** ou **"Connection pooling"**
4. Copie a string em formato **PostgreSQL**:
   ```
   postgresql://postgres:[YOUR-PASSWORD]@db.[PROJECT-ID].supabase.co:5432/postgres
   ```
5. **IMPORTANTE**: Substitua `[YOUR-PASSWORD]` pela senha que você criou no Supabase (geralmente uma string aleatória que o Supabase gerou)

### ✅ 2. Render - Configurar Variáveis de Ambiente

1. Vá para [dashboard.render.com](https://dashboard.render.com)
2. Selecione seu serviço `controle-de-estoque-web-app`
3. Vá para **Environment**
4. Adicione/atualize:

```
SECRET_KEY=gerat-uma-chave-aleatoria-longa
DATABASE_URL=postgresql://postgres:SUASENHA@db.pdbbynyshpcuzdsudrvq.supabase.co:5432/postgres
```

⚠️ **Importante**: 
- Não use `postgresql://` se a string começar com `postgres://`
- Certifique-se de que a **senha está correta** (é o que mais causa erro 500)
- Não há espaços em branco extra

### ✅ 3. Render - Verificar Comandos

**Build Command:**
```bash
pip install -r requirements.txt
```

**Start Command:**
```bash
gunicorn app:app --bind 0.0.0.0:$PORT
```

### ✅ 4. Fazer Redeploy

1. No dashboard do Render
2. Selecione o serviço
3. Clique em **"Manual Deploy"** ou **"Redeploy"**
4. Aguarde o deployment terminar (5-10 minutos)

### ✅ 5. Verificar Logs

Se ainda houver erro, veja os logs:

1. Dashboard Render → Seu serviço
2. Aba **"Logs"**
3. Procure por mensagens de erro (geralmente "connection refused" ou "auth failed")

## Exemplo de Senha Supabase

Quando você cria um projeto no Supabase, recebe algo como:
```
Connection string: postgresql://postgres:AbCdEf1234567890@db.abc123.supabase.co:5432/postgres
```

A senha neste exemplo é: `AbCdEf1234567890`

---

## Se o Erro Persistir

Tire um print/screenshot dos seguintes locais:
1. **Supabase**: Settings → Database → Connection string (oculte a senha)
2. **Render**: Environment variables (oculte valores sensíveis)
3. **Render**: Logs da aplicação

E compartilhe para diagnóstico.

## Resumo Rápido

| Onde | O que fazer |
|------|-------------|
| Supabase | Pegar a connection string completa com senha |
| Render Env | Colar a connection string em `DATABASE_URL` |
| Render Env | Adicionar `SECRET_KEY` com valor aleatório |
| Render | Manual Deploy |
| Render Logs | Verificar se conectou ao banco |

---

**Testando Localmente (antes de deploy):**

```bash
# Ativar ambiente virtual
.\.venv\Scripts\Activate.ps1

# Setar variáveis de ambiente
$env:DATABASE_URL="postgresql://postgres:SENHA@db.abc.supabase.co:5432/postgres"
$env:SECRET_KEY="sua-chave-secreta"

# Rodar app
python app.py
```

Depois acesse: `http://localhost:5000`
