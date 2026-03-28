# DocIntel

DocIntel e um pipeline local de inventario, extracao, governanca e curadoria operacional de arquivos para Windows. O projeto foi desenhado para mapear grandes volumes de dados em `F:\` e `I:\`, registrar tudo em SQLite, executar extracao controlada de hash/texto e, so depois disso, propor uma organizacao segura em multiplos destinos sem mover nem apagar os arquivos originais.

## Baseline de endurecimento de producao

O repositorio agora comeca a migrar para uma base explicita de producao em `docintel/`, preservando compatibilidade com os scripts legados:

- migracoes SQLite explicitas e idempotentes em `docintel/db/migrations.py`;
- contratos centrais e guardrails backend-first em `docintel/core/` e `docintel/guardrails.py`;
- logging estruturado em JSONL em `docintel/observability.py`;
- bloqueio de execucao automatica arriscada nos supervisores;
- documentacao viva em `docs/architecture.md`, `docs/data-model.md` e `docs/security-policy.md`.

Hoje o projeto cobre quatro blocos principais:

1. descoberta do ambiente e dos volumes acessiveis;
2. inventario recursivo dos arquivos e classificacao inicial por fase;
3. extracao de hash e texto para o recorte critico do acervo;
4. planejamento operacional de organizacao com manifests e relatórios.

O foco do projeto nao e apenas "catalogar arquivos". Ele tenta responder perguntas operacionais reais:

- o que existe nos discos de origem;
- o que ja foi processado e o que ainda esta pendente;
- o que e documento critico, projeto ativo, ferramenta essencial, acervo pesado ou backup;
- o que pode ir para Google Drive, `I:\`, `F:\` ou fila de revisao;
- o que deve permanecer fora do `Drive_Pessoal`, especialmente jogos, ROMs, emuladores e acervo pesado.

## Objetivo operacional

O projeto assume que os discos de origem sao fontes canonicas de leitura. A organizacao sugerida pelo DocIntel segue o modelo:

- `GOOGLE_DRIVE`: apenas material pequeno e critico, com alta disponibilidade.
- `I:\DocIntel_Organizado`: trabalho vivo, projetos e ferramentas essenciais.
- `F:\DocIntel_Organizado`: acervo pesado, backups, espelhos e material frio.
- `REVIEW_QUEUE`: tudo que precisa de avaliacao humana antes de qualquer acao.

O sistema trabalha em modo `copy-first`. Mesmo quando a execucao de copia e autorizada, a politica e:

- nunca mover a origem;
- nunca apagar a origem;
- copiar com verificacao basica;
- bloquear operacoes quando houver falta de capacidade ou configuracao incompleta.

## Como o projeto atua

### 1. Fase 0: descoberta do ambiente

Implementada em [`scanner/environment.py`](/F:/DocIntel/scanner/environment.py), esta etapa detecta volumes Windows via PowerShell/WMI, testa acesso, estima prioridade e gera um mapa do ambiente em `output/reports/mapa_ambiente_armazenamento.md`.

Ela tambem procura junctions e symlinks nos niveis superiores dos discos para reduzir pontos cegos antes do inventario.

### 2. Etapa 2: varredura completa

Implementada em [`scanner/discovery.py`](/F:/DocIntel/scanner/discovery.py), a varredura recursiva percorre os discos configurados em [`config/settings.py`](/F:/DocIntel/config/settings.py):

- `F:\`
- `I:\`

Cada arquivo encontrado vira um registro na tabela `files` do SQLite em `output/inventario_global.db`, com metadados como:

- caminho completo;
- nome e extensao;
- tamanho;
- timestamps;
- disco de origem;
- pasta raiz;
- profundidade;
- fase correspondente.

O inventario e feito com insercoes em lote e `WAL` para escalar melhor em acervos grandes.

### 3. Etapa 3: extracao

Implementada em [`run_extraction.py`](/F:/DocIntel/run_extraction.py), esta etapa processa apenas `FASE_1` e `FASE_2`.

Regras principais:

- `FASE_1` tem prioridade sobre `FASE_2`;
- extensoes textuais elegiveis recebem hash + extracao de texto;
- binarios ou extensoes fora do escopo recebem apenas hash;
- diretorios como `node_modules`, `.git`, `.venv`, `dist`, `build`, `target` e afins sao marcados como `EXCLUIDO` da deep extraction, mas continuam no inventario;
- a execucao e idempotente e pode ser retomada, porque ignora registros ja processados.

Status usados na coluna `status_indexacao`:

- `PENDENTE`
- `HASH_CALCULADO`
- `EXTRAIDO`
- `EXCLUIDO`
- `AUSENTE`

### 4. Gate pos-extracao

Quando a Etapa 3 termina para `FASE_1` e `FASE_2`, [`post_extraction_gate.py`](/F:/DocIntel/post_extraction_gate.py) gera os relatórios de fechamento:

- `output/reports/relatorio_final_extracao.md`
- `output/reports/amostragem_pos_extracao.md`
- `output/reports/status_distribuicao_final.md`
- `F:\DocIntel\GATE_ETAPA4_BLOQUEADO.md`

Esse gate existe para impedir que uma futura Etapa 4 semantica rode sem revisao humana.

### 5. Supervisao pos-indexacao

[`supervise_post_extraction.py`](/F:/DocIntel/supervise_post_extraction.py) e o supervisor seguro dessa fase. Ele:

- valida se a Etapa 3 terminou;
- roda o gate pos-extracao;
- dispara o planejador de organizacao;
- so executa copias se o operador passar `--execute-copy`.

Sem `--execute-copy`, o comportamento padrao e seguro: gerar plano e relatórios sem alterar a origem.

### 6. Planejamento de organizacao

[`organization_planner.py`](/F:/DocIntel/organization_planner.py) e o modulo que transforma inventario + heuristicas em decisoes operacionais.

Ele:

- le o banco em modo leitura;
- detecta duplicatas por hash;
- audita pastas de usuario do `C:\` como `Desktop`, `Downloads` e `Documents`;
- calcula capacidade disponivel em `I:\` e `F:\`;
- classifica cada registro em categorias operacionais;
- gera manifests menores por destino;
- persiste decisoes na tabela `organization_decisions`;
- opcionalmente executa copias de forma controlada.

## Arquitetura do projeto

### Diretorios principais

- [`config`](/F:/DocIntel/config): configuracoes globais, taxonomia e politica de organizacao.
- [`scanner`](/F:/DocIntel/scanner): descoberta de ambiente e varredura recursiva.
- [`db`](/F:/DocIntel/db): conexao SQLite, schema e operacoes de persistencia.
- [`extractors`](/F:/DocIntel/extractors): espaco para extratores reutilizaveis.
- [`output`](/F:/DocIntel/output): banco e artefatos gerados.
- [`tests`](/F:/DocIntel/tests): testes automatizados atuais do planejador.

### Scripts de entrada

- [`main.py`](/F:/DocIntel/main.py): orquestra Fase 0 + Etapa 2.
- [`run_extraction.py`](/F:/DocIntel/run_extraction.py): executa a Etapa 3.
- [`monitor_extraction.py`](/F:/DocIntel/monitor_extraction.py): monitora a Etapa 3 em modo leitura.
- [`post_extraction_gate.py`](/F:/DocIntel/post_extraction_gate.py): gera relatórios de fechamento e bloqueia a Etapa 4.
- [`supervise_post_extraction.py`](/F:/DocIntel/supervise_post_extraction.py): supervisor seguro do pos-extracao.
- [`organization_planner.py`](/F:/DocIntel/organization_planner.py): gera ou executa manifests de organizacao.
- [`continuity_supervisor.py`](/F:/DocIntel/continuity_supervisor.py): monitora continuidade da Etapa 3 e relanca a extracao quando necessario.
- [`storage_audit.py`](/F:/DocIntel/storage_audit.py): auditoria utilitaria de armazenamento e pastas de usuario do `C:\`.

## Modelo de dados

O schema vive em [`db/connection.py`](/F:/DocIntel/db/connection.py). As tabelas mais importantes sao:

- `files`: inventario central de arquivos.
- `documents`: espaco para enriquecimento semantico de documentos.
- `projects`: metadados agregados por projeto/pasta raiz.
- `duplicates`: relacoes de duplicidade.
- `classifications`: classificacoes com justificativa textual.
- `actions_proposed`: acoes sugeridas com risco e aprovacao.
- `organization_decisions`: decisoes de curadoria operacional.
- `audit_log`: trilha de auditoria.

Na pratica, o coracao do pipeline atual esta em `files`, `organization_decisions` e `audit_log`.

## Taxonomia e heuristicas

### Fases

O mapeamento inicial por pasta raiz fica em [`config/taxonomy.py`](/F:/DocIntel/config/taxonomy.py).

Exemplos:

- em `F:\`, `Steam` entra em `FASE_1`, `Projects` em `FASE_2`, `Emulators` e `ROMs` em `FASE_4`, `backups` em `FASE_5`;
- em `I:\`, pastas como `Importante`, `Profit` e `Bussines` entram em `FASE_1`;
- colecoes como `LaunchBox`, `Roms` e `SteamLibrary` entram em `FASE_4`.

Esse mapeamento e heuristico. Ele organiza prioridade operacional, nao verdade semantica absoluta.

### Politica de curadoria

A politica operacional esta em [`config/organization_policy.py`](/F:/DocIntel/config/organization_policy.py).

Algumas regras importantes:

- documentos pessoais/criticos pequenos podem ir para `GOOGLE_DRIVE`;
- projetos e documentacao tecnica tendem para `I_DRIVE`;
- programas essenciais tendem para `I_DRIVE`;
- backups, espelhos e material frio tendem para `F_DRIVE`;
- jogos, ROMs, emuladores, ISOs, dumps e acervo pesado tendem para `F_DRIVE`;
- registros ambiguos vao para `REVIEW_QUEUE`.

O projeto usa pistas por:

- extensao;
- caminho;
- fase;
- tamanho;
- idade do arquivo;
- duplicidade por hash;
- disponibilidade de espaco nos destinos.

## Guardrails de seguranca

Os guardrails mais importantes do projeto hoje sao:

- inventario e leitura primeiro, acao depois;
- `run_extraction.py` nao organiza nada, apenas enriquece o inventario;
- `post_extraction_gate.py` nunca inicia a Etapa 4;
- `supervise_post_extraction.py` nao copia nada sem `--execute-copy`;
- `organization_planner.py` em modo padrao so gera plano e manifests;
- modo de execucao do planner usa copia, nunca move;
- colisao de nome no destino gera variante com sufixo;
- destino sem espaco ou sem configuracao vira bloqueio de politica;
- jogos, ROMs, emuladores e acervo pesado devem ficar fora do `Drive_Pessoal`.

## Relatorios e artefatos gerados

### Relatorios de inventario e extracao

Gerados em [`output/reports`](/F:/DocIntel/output/reports):

- `mapa_ambiente_armazenamento.md`
- `cobertura_varredura.md`
- `status_execucao.md`
- `extracao_parcial_resumo.md`
- `relatorio_final_extracao.md`
- `amostragem_pos_extracao.md`
- `status_distribuicao_final.md`
- `validacao_qualidade.md`

### Relatorios de organizacao

Gerados em [`output/reports/organizacao_drive_pessoal`](/F:/DocIntel/output/reports/organizacao_drive_pessoal):

- `organization_summary.md`
- `top_riscos_operacionais.md`
- `supervisao_pos_indexacao.md`
- `organization_manifest.csv` (indice leve de compatibilidade)
- `google_drive_manifest.csv`
- `drain_c_manifest.csv`
- `i_drive_curated_manifest.csv`
- `f_drive_cold_storage_manifest.csv`
- `review_queue_manifest.csv`

Os manifests por destino sao os artefatos operacionais reais. O manifesto consolidado existe mais como ponte de compatibilidade.

## Fluxo recomendado de execucao

## Launcher desktop sem comando

Para iniciar o projeto sem digitar comandos, use:

```powershell
.\Iniciar_DocIntel_GUI.bat
```

Para validar o launcher sem abrir a janela definitivamente:

```powershell
python .\launch_docintel_gui.py --health-check
```

Esse launcher:

- encontra o Python automaticamente;
- prioriza `.venv\Scripts\python.exe` quando existir;
- valida/migra o SQLite antes de abrir a interface;
- instala `PySide6` mediante confirmacao se a dependencia estiver ausente;
- abre uma GUI operacional segura com botoes para:
  - atualizar status;
  - rodar supervisao segura;
  - gerar planejamento seguro;
  - abrir dashboard, relatorios e README.

A GUI atual e um **control center operacional real** para o estado atual do projeto. Ela nao substitui a futura interface explorer-like completa, mas ja permite usar o pipeline com seguranca sem depender de linha de comando.

### 1. Inicializar banco e inventariar

```powershell
python .\main.py
```

Isso:

- inicializa o banco;
- descobre o ambiente;
- varre `F:\` e `I:\`;
- gera relatórios de cobertura e resumo.

### 2. Rodar a extracao

```powershell
python .\run_extraction.py
```

### 3. Acompanhar o progresso sem interferir na escrita

```powershell
python .\monitor_extraction.py
```

### 4. Quando a extracao terminar, supervisionar o pos-processamento em modo seguro

```powershell
python .\supervise_post_extraction.py
```

### 5. Gerar apenas o plano de organizacao

```powershell
python .\organization_planner.py
```

### 6. Executar um manifest por copia, se e somente se isso tiver sido aprovado

```powershell
python .\organization_planner.py --execute --manifest .\output\reports\organizacao_drive_pessoal\i_drive_curated_manifest.csv
```

## Continuidade automatizada

[`continuity_supervisor.py`](/F:/DocIntel/continuity_supervisor.py) existe para cenarios longos de extracao. Ele verifica:

- se `status_execucao.md` existe e pode ser lido;
- se `run_extraction.py` ainda esta em execucao;
- se ha pendencias em `FASE_1` e `FASE_2`;
- se o pos-processamento seguro ja foi concluido.

Exemplo:

```powershell
python .\continuity_supervisor.py --once
```

ou

```powershell
python .\continuity_supervisor.py --poll-seconds 60
```

## Dependencias

Pelo codigo atual, o projeto depende pelo menos de:

- Python 3.11+;
- SQLite (embutido no Python);
- `pypdf` para PDFs;
- `python-docx` para `.docx`;
- `openpyxl` para `.xlsx` e `.xls`;
- PowerShell no Windows para descoberta de volumes e monitoramento de processos.

O projeto foi escrito com caminho e comportamento claramente voltados para Windows.

## Configuracao importante

As configuracoes centrais ficam em [`config/settings.py`](/F:/DocIntel/config/settings.py).

Pontos relevantes:

- `SOURCE_DRIVES = ["F:\\", "I:\\"]`
- `DB_PATH = output/inventario_global.db`
- `REPORTS_DIR = output/reports`
- `GOOGLE_DRIVE_ROOT` e detectado automaticamente, com override por `DOCINTEL_GOOGLE_DRIVE_ROOT`
- `DOCINTEL_I_CURATED_ROOT` e `DOCINTEL_F_CURATED_ROOT` podem sobrescrever os destinos padrao
- ha limites de espaco minimo para `C:\`, `I:\` e `F:\`

## Estado atual observado no projeto

Pelo comportamento atual do repositorio e dos artefatos presentes, o projeto ja passou por:

- inventario em larga escala;
- fechamento da Etapa 3 para `FASE_1` e `FASE_2`;
- geracao de relatórios pos-extracao;
- geracao previa de manifests de organizacao.

Tambem ha limitacoes operacionais importantes:

- `organization_planner.py` pode levar bastante tempo em execucoes completas;
- em algumas rodadas de supervisao ele nao promove novos manifests canônicos antes do timeout;
- `GOOGLE_DRIVE` pode permanecer bloqueado se a raiz nao estiver configurada;
- `I:\DocIntel_Organizado` pode ficar bloqueado por falta de folga operacional;
- o gate da Etapa 4 continua deliberadamente bloqueando o proximo estagio ate aprovacao humana.

## Testes

Hoje existe cobertura automatizada inicial para regras do planejador em [`tests/test_organization_planner.py`](/F:/DocIntel/tests/test_organization_planner.py).

Para rodar:

```powershell
python -m unittest .\tests\test_organization_planner.py
```

Os testes atuais verificam, entre outras coisas:

- documento critico pequeno indo para `GOOGLE_DRIVE`;
- projeto em `F:\Projects` indo para `I_DRIVE`;
- ROM pesada permanecendo em `F_DRIVE`;
- drenagem por copia de projeto detectado em `C:\`;
- normalizacao de nomes de arquivo.

## O que o projeto ainda nao faz sozinho

Mesmo com bastante automacao, o projeto ainda depende de decisao humana para pontos importantes:

- aprovar ou nao a Etapa 4;
- revisar arquivos ambiguos;
- revisar manifests sensiveis;
- decidir quando executar copias reais;
- confirmar excecoes de politica, especialmente quando um arquivo parece pessoal e ao mesmo tempo pertence a contexto de jogo/emulacao/projeto.

## Resumo executivo

Se voce quiser entender o projeto em uma frase:

DocIntel e uma esteira local de governanca de arquivos que inventaria discos, enriquece metadados, bloqueia avancos arriscados por padrao e gera um plano seguro para reorganizar acervos grandes sem destruir a origem.
