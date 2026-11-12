# CareManager

MVP desktop para organizar a disponibilidade de funcionários de atendimento domiciliar. O aplicativo Qt conversa com uma API central; os computadores não compartilham um arquivo de banco de dados.

## Arquitetura

- `desktop/`: interface PySide6 para Windows e Linux.
- `server/`: API FastAPI e persistência SQLAlchemy.
- PostgreSQL: banco central executado pelo Docker Compose.
- Análises no desktop: gráficos com Matplotlib, processamento com NumPy/pandas e estimativa exploratória com scikit-learn.

Cada registro representa a disponibilidade de um funcionário em uma data e horário e pode incluir o nome do paciente. A identidade do registro é funcionário + data + horário. Reimportar a mesma combinação atualiza os dados em vez de duplicá-los. O código opcional do funcionário identifica a mesma pessoa em diferentes plantões e deve ser mantido consistente entre importações.

## Iniciar o servidor

Requisitos: Docker Desktop com Docker Compose.

1. Copie `.env.example` para `.env` e defina senhas/chave próprias e fortes.
2. Na pasta do projeto, execute:

   ```sh
   docker compose up --build -d
   ```

3. A API ficará disponível na porta `8000`. Em outro computador, use o IP do servidor, por exemplo `http://192.168.1.100:8000`.

O serviço é HTTP e usa uma chave compartilhada para a API. Restrinja a porta à rede da empresa e use VPN ou HTTPS antes de permitir acesso fora da rede confiável. Não use dados reais de funcionários ou clientes até implementar contas individuais, auditoria, backups testados e os controles de privacidade necessários.

### Executar localmente sem Docker

Para desenvolvimento local, o servidor também aceita SQLite:

```powershell
$env:CAREMANAGER_DATABASE_URL = "sqlite:///./caremanager.sqlite3"
$env:CAREMANAGER_API_KEY = "uma-chave-local-com-pelo-menos-24-caracteres"
cd server
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

O arquivo do banco será criado na pasta `server`. No desktop, conecte a `http://127.0.0.1:8000` e informe a mesma chave configurada em `CAREMANAGER_API_KEY`. Esta opção é para desenvolvimento em uma máquina; para uso compartilhado, siga a configuração PostgreSQL com Docker acima.

## Iniciar o desktop

Requer Python 3.12 ou superior. Em cada computador:

```sh
python -m venv .venv
```

No Windows, execute os comandos a partir da pasta raiz do projeto e use `.venv\Scripts\python.exe`. No Linux, use `.venv/bin/python`. Assim, o mesmo ambiente também pode ser usado pelo script de compilação do executável.

Instale as dependências do desktop e do servidor:

```sh
python -m pip install -r desktop/requirements.txt -r server/requirements.txt
```

Para conectar a uma API já iniciada, execute `desktop/main.py`. Na conexão inicial, informe o endereço da API e o mesmo valor definido como `CAREMANAGER_API_KEY` no servidor. Para iniciar o desktop junto com uma API local e um banco SQLite, use `desktop/offline_main.py`, conforme o guia completo do Windows abaixo.

## Guia completo para Windows

Há duas formas de usar o aplicativo:

- **Offline, em um computador:** o desktop inicia a própria API e grava os dados localmente em SQLite. Não precisa de Docker nem de configurar uma chave.
- **Compartilhado, em vários computadores:** uma API e um banco PostgreSQL ficam em um computador servidor; cada desktop se conecta a eles pela rede. Esse modo requer Docker Desktop no servidor.

### 1. Instalar o Python

1. Abra [python.org/downloads/windows](https://www.python.org/downloads/windows/) e baixe o instalador do Python para Windows, versão 3.12 ou superior (64 bits).
2. Execute o instalador. Na primeira tela, marque **Add python.exe to PATH** e escolha **Install Now**.
3. Quando a instalação terminar, feche e abra novamente o PowerShell.
4. Verifique a instalação:

   ```powershell
   py --version
   ```

   A versão exibida precisa ser 3.12 ou superior. Se `py` não for reconhecido, tente `python --version`. Se nenhum comando funcionar, instale o Python novamente e confirme que marcou **Add python.exe to PATH**.

### 2. Preparar o projeto

1. No PowerShell, entre na pasta do projeto. Se ela estiver em Documentos, use:

   ```powershell
   cd "$HOME\Documents\Cuidare-Morumbi"
   ```

   Se extraiu o projeto em outro local, substitua o caminho pelo local correto.
2. Confirme que está na pasta certa:

   ```powershell
   Test-Path .\desktop\offline_main.py
   ```

   O resultado deve ser `True`. Se for `False`, navegue até a pasta que contém as pastas `desktop` e `server`.
3. Crie o ambiente Python do projeto:

   ```powershell
   py -3 -m venv .venv
   ```

4. Atualize o instalador de pacotes e instale as dependências necessárias:

   ```powershell
   .\.venv\Scripts\python.exe -m pip install --upgrade pip
   .\.venv\Scripts\python.exe -m pip install -r .\desktop\requirements.txt -r .\server\requirements.txt
   ```

   É necessário ter internet durante a instalação. Não é preciso ativar o ambiente virtual: os comandos usam diretamente o Python que foi criado dentro do projeto.

### 3. Iniciar em modo offline (um computador)

No mesmo PowerShell, ainda na pasta do projeto, execute:

```powershell
$env:PYTHONPATH = "$PWD\desktop;$PWD\server"
.\.venv\Scripts\python.exe .\desktop\offline_main.py
```

O PowerShell ficará ocupado enquanto o aplicativo estiver aberto. Feche a janela do aplicativo para encerrá-lo. Os dados ficam em `%LOCALAPPDATA%\Cuidare-Morumbi\caremanager.sqlite3`; o log fica em `%LOCALAPPDATA%\Cuidare-Morumbi\caremanager.log`. Para abrir novamente, repita os dois comandos acima. Nesse modo, não é preciso digitar uma chave: o aplicativo cria uma automaticamente e preenche o campo **Chave de acesso** na tela inicial; basta clicar em **Conectar**. Não execute `desktop/main.py` e não precisa abrir `dist\CareManager.exe`.

### 4. Iniciar o servidor compartilhado com Docker (opcional)

Faça esta configuração apenas no computador que será o servidor:

1. Instale o Docker Desktop para Windows em [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop/), abra-o e espere até indicar que está em execução.
2. No PowerShell, navegue até a pasta raiz do projeto e crie o arquivo de configuração:

   ```powershell
   cd "$HOME\Documents\Cuidare-Morumbi"
   Copy-Item .\.env.example .\.env
   ```

3. Gere uma chave para a API:

   ```powershell
   py -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

4. Abra `.env` no Bloco de Notas:

   ```powershell
   notepad .env
   ```

   Substitua todos os valores de exemplo, incluindo `POSTGRES_PASSWORD` por uma senha forte e `CAREMANAGER_API_KEY` pelo valor gerado no passo anterior. A chave da API precisa ter pelo menos 24 caracteres. Salve o arquivo e mantenha-o privado; não compartilhe nem publique esse arquivo.
5. Inicie o servidor e o banco:

   ```powershell
   docker compose up --build -d
   ```

6. Confira se os serviços estão ativos:

   ```powershell
   docker compose ps
   ```

   Para consultar os registros do servidor se houver erro:

   ```powershell
   docker compose logs server
   ```

Em cada computador cliente, instale o Python e prepare o projeto seguindo as etapas 1 e 2. Inicie o desktop conectado ao servidor:

```powershell
$env:PYTHONPATH = "$PWD\desktop;$PWD\server"
.\.venv\Scripts\python.exe .\desktop\main.py
```

Na janela de conexão, informe o endereço do servidor (por exemplo, `http://192.168.1.100:8000`) e a mesma chave `CAREMANAGER_API_KEY` configurada no `.env` do servidor. O endereço `127.0.0.1` só aponta para o próprio computador e não deve ser usado nos outros clientes. Restrinja a porta 8000 à rede confiável; não exponha o serviço diretamente à internet. Não use dados reais de funcionários ou pacientes até implementar os controles de privacidade necessários.

Para parar os serviços no computador servidor:

```powershell
docker compose down
```

Isso mantém os dados do volume do PostgreSQL. **Não** use `docker compose down -v`, pois essa opção também remove o volume com os dados do banco.

## Executável Windows para uso offline

O executável inicia a API FastAPI somente em `127.0.0.1`, escolhe uma porta local disponível e usa um banco SQLite persistido em `%LOCALAPPDATA%\Cuidare-Morumbi`. Depois de compilado, o uso não requer internet, Docker, Python nem configuração de chave.

Para compilar no Windows, instale os requisitos do desktop no ambiente `.venv` e execute na pasta do projeto:

```powershell
.\.venv\Scripts\python.exe -m pip install -r desktop\requirements.txt
.\desktop\build_exe.ps1
```

O resultado ficará em `dist\CareManager.exe`. Para usar os mesmos dados em outro computador, copie também o arquivo `caremanager.sqlite3` da pasta `%LOCALAPPDATA%\Cuidare-Morumbi`; faça uma cópia de segurança antes de substituir um banco existente.

O executável produzido por este projeto não tem assinatura digital e pode ser bloqueado pelo Smart App Control do Windows. Para usar o aplicativo sem esse executável, siga as etapas de execução com Python acima; não é necessário desativar os recursos de segurança do Windows.

## Fluxo disponível

1. **Gerenciar funcionários** abre o menu de ações.
2. **Importar funcionários CSV** permite escolher um arquivo próprio ou a planilha de escala com as colunas `Data`, `Turno`, `Pessoa da escala`, `Paciente` e `Horário`; código do funcionário e disponibilidade são opcionais. Para importar resultados anteriores dos plantões, inclua também o resultado do plantão e a data de confirmação. Reconhece datas `DD/MM/AAAA`, horários como `07h-19h` ou `19h-08h` e disponibilidade vazia ou ausente como não informada. Uma linha `(sem escalado)` sem horário é salva como furo de plantão, sem associá-la a um funcionário.
3. **Controle de funcionários** permite filtrar por nome do funcionário, paciente, turno, disponibilidade, data inicial e intervalo de horários. Datas devem seguir `AAAA-MM-DD` e horários `HH:MM`. Também permite adicionar, editar, excluir com confirmação, exportar os resultados filtrados para CSV ou baixar todos os cadastros em CSV. **Limpar funcionários** apaga permanentemente todos os registros associados a funcionários no banco conectado, mesmo os ocultos pelos filtros, e mantém os furos sem funcionário; a ação pede confirmação.
4. **Análises da equipe** resume os registros, profissionais cadastrados e disponibilidade informada, além de exibir gráficos por disponibilidade, data e turno. Também treina um modelo de machine learning para estimar risco de falta em plantões futuros usando funcionário, turno, dia da semana, mês e hora de início. O modelo exige pelo menos 50 resultados confirmados, incluindo cinco faltas e cinco plantões realizados; sem esse histórico, o painel informa que faltam dados. Quando há amostras suficientes, apresenta os dez maiores riscos e a acurácia balanceada em validação temporal. A estimativa é experimental, não garante faltas e não substitui a escala.
5. **Plantões** permite registrar cada plantão como realizado, falta, cancelado ou substituído, com a data e hora da confirmação. Os dados ficam no próprio registro da escala, sem criar outra tabela. Também podem ser preenchidos em lote por CSV usando as colunas de resultado e confirmação juntas; resultados confirmados devem incluir a data de confirmação. Em escalas futuras, exibe a taxa histórica individual somente quando houver pelo menos 10 resultados anteriores confirmados; abaixo disso, informa que faltam dados. A estimativa é exploratória, não garante faltas e não substitui a escala.

Datas aceitam `AAAA-MM-DD` ou `DD/MM/AAAA`; horários aceitam `HH:MM` ou `HH:MM:SS`; disponibilidade aceita verdadeiro/verdadeira, falso/falsa, sim/não, yes/no e 1/0, além de vazio, `null` ou `nulo` para indicar que não foi informada.

O campo de paciente é apenas um nome opcional associado ao registro; ainda não há cadastro separado de pacientes, escalas de atendimento por paciente, detecção automática de furos ou contas individuais.
#   C u i d a r e  
 