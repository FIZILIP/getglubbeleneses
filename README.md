# US 1919 Genève-Ville — Sistema de Gestão Desportiva

## Como instalar e usar

### Pré-requisitos (Windows)
- Python 3.11 ou superior: https://www.python.org/downloads/
- Inno Setup: https://jrsoftware.org/isinfo.php

---

## Executar em desenvolvimento (sem instalador)

```bash
pip install -r requirements.txt
python launcher.py
```
Abre automaticamente em: http://127.0.0.1:5002

**Credenciais padrão:**
- Utilizador: `admin`
- Senha: `getclub123`

---

## Publicar online com GitHub + Render

Este projeto já está preparado para Render com:

- `Procfile` usando `gunicorn app:app`
- `render.yaml` criando o serviço web, banco PostgreSQL e disco persistente
- suporte a `DATABASE_URL` para usar PostgreSQL em produção
- criação automática das tabelas e do utilizador `admin` no arranque

### 1. Criar o repositório no GitHub

Use um repositório **privado**, porque o projeto tem lógica de licença e ficheiros administrativos.

No terminal, dentro da pasta do projeto:

```bash
git init
git add .
git commit -m "Preparar GETCLUB para deploy"
git branch -M main
git remote add origin https://github.com/SEU-USUARIO/getclub.git
git push -u origin main
```

Antes do `git add .`, confirme que o `.gitignore` está ativo. Ele evita enviar ficheiros como:

- `dist/`
- `installer_output/`
- `getclub.db`
- `uploads/`
- `static/uploads/`
- `__pycache__/`
- `key_generator.py`

### 2. Criar o deploy no Render

No Render:

1. Clique em **New +**
2. Escolha **Blueprint**
3. Conecte sua conta GitHub
4. Selecione o repositório `getclub`
5. Confirme o deploy usando o ficheiro `render.yaml`

O Render deve criar automaticamente:

- serviço web `getclub`
- banco PostgreSQL `getclub-db`
- disco persistente montado em `/var/data`

### 3. Entrar no sistema

Depois do deploy terminar, abra a URL gerada pelo Render e entre com:

- Utilizador: `admin`
- Senha: `getclub123`

Troque a senha do administrador assim que entrar.

### 4. Notas importantes para produção

- Os uploads e ficheiros de licença ficam no disco persistente `/var/data`.
- A base de dados online usa PostgreSQL, não o ficheiro local `getclub.db`.
- Se o repositório for público, remova ou proteja antes qualquer código privado de licença.
- O primeiro arranque pode demorar um pouco porque o Render instala as dependências.

---

## Criar o instalador .exe para Windows

1. Abrir o terminal nesta pasta
2. Executar `build_windows.bat` (duplo clique)
3. Aguardar a compilação com PyInstaller
4. Abrir `setup_getclub.iss` com o Inno Setup Compiler
5. Clicar em **Build → Compile**
6. O instalador é gerado em `installer_output\GETCLUB_Setup_v1.0.exe`

---

## Criar instalador para macOS (sem precisar de Python na máquina final)

1. No Mac, abra o Terminal na pasta do projeto
2. Dê permissão ao script:

```bash
chmod +x build_macos.sh
```

3. Execute:

```bash
./build_macos.sh
```

4. Ao final, serão gerados:
- `dist/GETCLUB.app`
- `dist/GETCLUB_macOS.dmg`
- `dist/GETCLUB_Installer_macOS.pkg`

Distribuição:
- Envie `GETCLUB_macOS.dmg` (instalação por arrastar) ou `GETCLUB_Installer_macOS.pkg` (instalação guiada)
- A máquina final não precisa ter Python instalado
- Ao abrir pela primeira vez, o macOS pode mostrar aviso de segurança:
  use botão direito no app → **Abrir**
- O build também gera automaticamente uma versão transparente da logo para o ícone do app no Dock.

---

## Sistema de Licença (Trial 3 Dias + Anual/Vitalícia)

A aplicação funciona em modo de avaliação por **3 dias** após a primeira execução.

Após os 3 dias, o utilizador é redirecionado para a página de ativação onde deve introduzir uma chave.

### Gerar chaves de ativação

Execute o gerador **SEPARADAMENTE** (não distribua este ficheiro):

```bash
# Gerar 1 chave anual (1 ano)
python key_generator.py --tipo anual --anos 1 --qtd 1

# Gerar 10 chaves anuais (2 anos)
python key_generator.py --tipo anual --anos 2 --qtd 10

# Gerar 5 chaves vitalícias
python key_generator.py --tipo vitalicia --qtd 5
```

Formatos:
- Anual: `GETCLUB2-A-YYYYMMDD-XXXXXXXX-XXXXXXXXXX`
- Vitalícia: `GETCLUB2-V-PERP-XXXXXXXX-XXXXXXXXXX`

---

## Estrutura do projeto

```
getclub-sistema/
├── app.py              — Servidor Flask principal
├── models.py           — Modelos da base de dados
├── license.py          — Sistema de trial + ativação anual/vitalícia
├── key_generator.py    — Gerador de licenças (uso privado)
├── launcher.py         — Lançador Windows
├── build_windows.bat   — Script de compilação
├── setup_getclub.iss   — Script Inno Setup
├── templates/          — Páginas HTML
│   └── ativar_licenca.html  — Página de ativação
└── static/
    └── img/
        └── getclub-logo.png — Logo da aplicação
```

---

## Notas importantes

- O `key_generator.py` **não deve ser incluído** no instalador final.
- A licença é guardada em `~/.getclub_license.json` no computador do utilizador.
- O segredo de geração de keys está em `license.py` — mantenha-o privado.
- O `key_generator.py` pode ser executado apenas por quem administra as licenças.
