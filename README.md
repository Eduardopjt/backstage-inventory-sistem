# BACKSTAGE 📦

Sistema robusto e moderno para gerenciamento de inventário com interface intuitiva e funcionalidades avançadas.

## Tecnologias

- **Backend**: Python + Flask
- **Frontend**: HTML5, CSS3, JavaScript puro
- **Banco de dados**: SQLite
- **Gráficos**: Chart.js

## Recursos Principais

✅ Autenticação de usuários com hash de senha
✅ Suporte SaaS multi-tenant com contas de empresas/equipes
✅ Cadastro e edição de itens com SKU, categoria e localização
✅ Sistema de movimentação com Entrada, Saída e Ajuste
✅ Histórico completo de movimentações com filtros avançados
✅ Dashboard com KPIs e gráficos em tempo real
✅ Relatórios por fornecedor e localização
✅ Exportação de dados em CSV e PDF
✅ Gerenciamento de categorias customizadas
✅ Alertas de estoque baixo
✅ Responsividade mobile
✅ Notificações inline (sem alert())
✅ Alteração de senha do usuário

## Como Instalar e Executar

### 1. Clone ou baixe o projeto

### 2. Crie um ambiente virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Instale as dependências:

```powershell
pip install -r requirements.txt
```

### 4. Execute o aplicativo:

```powershell
python app.py
```

### 5. Abra no navegador:

```
http://127.0.0.1:5000
```

## Primeiros Passos

1. **Registre uma nova conta** com empresa/equipe, usuário e senha (mín. 3 chars usuário, 6 chars senha)
2. **Faça login** com suas credenciais
3. **Crie categorias** na aba Configurações
4. **Adicione itens** no Inventário com nome, SKU, categoria e localização
5. **Registre movimentações**:
   - **Entrada**: Adiciona itens ao estoque (com fornecedor e preço unitário)
   - **Saída**: Remove itens (com destino obrigatório)
   - **Ajuste**: Corrige a quantidade diretamente
6. **Visualize relatórios** e exporte dados em CSV/PDF

## Funcionalidades Detalhadas

### Dashboard
- KPIs com total de SKUs, quantidade total, itens com estoque baixo
- Gráficos de quantidade por localização e tipos de movimentação
- Lista de itens críticos (abaixo do estoque mínimo)

### Inventário
- Tabela interativa com busca por nome/SKU
- Filtro por categoria
- Ações rápidas: Entrada, Saída, Ajuste, Editar, Deletar
- Destaque automático para itens com estoque baixo
- Dropdown de localizações com sugestões

### Histórico
- Visualização completa de todas as movimentações
- Filtros por data, tipo (Entrada/Saída/Ajuste) e termo de busca
- Informações de fornecedor/destino e observações

### Relatórios
- **Por Fornecedor**: Totalizações de entrada, quantidade e ticket médio
- **Por Localização**: Quantidade total e número de itens por local
- **Exportar**: CSV com todos os itens ou PDF formatado

### Configurações
- Gerenciamento de categorias com cores
- Alteração de senha segura (valida senha atual)
- Informações da conta

## Validações e Segurança

✓ Senhas com hash usando werkzeug.security
✓ Proteção CSRF implícita (sessão)
✓ Validação de quantidade (não negativa)
✓ Isolamento de dados por usuário
✓ Proteção contra saídas negativas
✓ Notificações de erros inline
✓ Confirmação antes de deletar

## Estrutura de Pastas

```
.
├── app.py                    # Aplicação Flask principal
├── inventory.db             # Banco de dados SQLite
├── requirements.txt         # Dependências Python
├── README.md               # Este arquivo
├── static/
│   ├── css/
│   │   └── style.css       # Estilos responsivos
│   └── js/
│       └── app.js          # Lógica do frontend
└── templates/
    ├── index.html          # Interface principal
    ├── login.html          # Tela de login
    └── register.html       # Tela de registro
```

## Endpoints da API

### Autenticação
- `POST /login` - Login de usuário
- `POST /register` - Registro de novo usuário
- `GET /logout` - Sair
- `POST /api/user/change-password` - Alterar senha

### Itens
- `GET /api/items` - Listar itens
- `POST /api/items` - Criar item
- `PUT /api/items/<id>` - Editar item
- `DELETE /api/items/<id>` - Deletar item

### Movimentações
- `POST /api/items/<id>/entrada` - Registrar entrada
- `POST /api/items/<id>/saida` - Registrar saída
- `POST /api/items/<id>/ajuste` - Registrar ajuste
- `GET /api/items/<id>/historico` - Ver histórico do item

### Relatórios
- `GET /api/balanco` - Resumo geral
- `GET /api/balanco/movements` - Movimentações com filtro
- `GET /api/balanco/suppliers` - Análise por fornecedor

### Categorias e Localizações
- `GET /api/categories` - Listar categorias
- `POST /api/categories` - Criar categoria
- `DELETE /api/categories/<id>` - Deletar categoria
- `GET /api/locations` - Listar localizações usadas

## Troubleshooting

**Erro ao abrir o app:**
- Verifique se o arquivo `inventory.db` tem permissão de escrita
- Limpe o cache do navegador (Ctrl+Shift+Del)

**Problema ao registrar movimentação:**
- Valide que a quantidade é > 0
- Para saída, confirme que há estoque suficiente
- Para saída, certifique-se de preencher o destino

**Dados sumiram:**
- O banco SQLite persiste no arquivo `inventory.db`
- Faça backup do arquivo se for importante

**Convites por email:**
- Configure as variáveis `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` e `MAIL_FROM`
- Os convites são enviados apenas quando o SMTP estiver configurado

## Melhorias Futuras

- [ ] Autenticação multi-fator
- [ ] Integração com QR codes
- [ ] Sincronização em nuvem
- [ ] App mobile nativo
- [ ] Relatórios avançados com gráficos customizados
- [ ] Integração com NF-e
- [ ] Sistema de alertas por email

## Licença

Software livre para uso pessoal e comercial.

---

**Desenvolvido com ❤️ para melhorar sua gestão de estoque.**
