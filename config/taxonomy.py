"""
DocIntel — Taxonomia de Classificação Hierárquica
"""

# === Classe 1: Documentação Crítica ===
CLASSE_DOC_CRITICA = "DOCUMENTACAO_CRITICA"
SUBCLASSES_DOC = {
    "PESSOAL": "Documentos de identidade, certidões, registros civis",
    "FAMILIAR": "Certidões de nascimento, casamento, dependentes",
    "PROFISSIONAL": "CTPS, contratos de trabalho, cartas de referência, currículos",
    "IMIGRACAO": "Vistos, formulários D160, EB2-NIW, USCIS, petições, comprovantes",
    "JURIDICA": "Contratos, procurações, termos legais",
    "FINANCEIRA": "Extratos, comprovantes de renda, IPVA, impostos, investimentos",
    "MEDICA": "Laudos, receitas, exames, prontuários",
    "ESCOLAR": "Diplomas, históricos, certificados, matrículas",
    "PATRIMONIAL": "Escrituras, financiamentos, seguros, IPTU",
    "CONTRATUAL": "Contratos de serviço, aluguéis, assinaturas",
    "FISCAL": "Declarações de IR, informes de rendimentos",
    "IDENTIDADE_CERTIDOES": "RG, CPF, CNH, passaporte, título de eleitor",
}

# === Classe 2: Projetos ===
CLASSE_PROJETOS = "PROJETOS"
SUBCLASSES_PROJ = {
    "SOFTWARE_ATIVO": "Projeto de software em desenvolvimento ativo",
    "SOFTWARE_LEGADO": "Projeto de software abandonado ou congelado",
    "DOCUMENTACAO_TECNICA": "Documentação de API, README, wikis técnicas",
    "PROTOTIPO": "Prova de conceito, spike, MVP",
    "BACKUP_PROJETO": "Cópia de segurança de projeto (sufixo _backup, old, etc.)",
    "ARTEFATOS_BUILD": "Binários compilados, builds, releases",
    "ARQUIVOS_SUPORTE": "Assets, recursos, mídia usada em projetos",
    "WORKSPACE_PRINCIPAL": "Ambiente de trabalho raiz do projeto",
    "AMBIENTE_DESENVOLVIMENTO": "SDKs desenvolvidos, engines customizados",
}

# === Classe 3: Programas e Ferramentas ===
CLASSE_PROGRAMAS = "PROGRAMAS_FERRAMENTAS"
SUBCLASSES_PROG = {
    "SDK": "Kit de desenvolvimento: SGDK, GENDK, .NET SDK",
    "INSTALADOR": "Executável de instalação de software",
    "ENGINE": "Engine de jogo ou ferramenta de autoria",
    "UTILITARIO": "Ferramentas de apoio: 7-Zip, Notepad++, etc.",
    "PACOTE_SUPORTE": "Drivers, runtimes, redistributáveis",
    "DEPENDENCIA_LOCAL": "node_modules, vendor, venv, .gradle",
    "EMULADOR": "RetroArch, Dolphin, PCSX2, etc.",
    "FIRMWARE": "BIOS, firmwares, kernels de emulação",
    "AMBIENTE_TECNICO": "Configurações, profiles, workspaces de IDE",
}

# === Classe 4: Acervo Pesado ===
CLASSE_ACERVO = "ACERVO_PESADO"
SUBCLASSES_ACERVO = {
    "JOGOS": "Jogos completos, instaladores de jogos",
    "ROMS": "ROMs de consoles, ISOs de jogos retro",
    "VIDEOS_BRUTOS": "Gravações de tela, tutoriais, vídeos pessoais",
    "BIBLIOTECAS_MIDIA": "Música, imagens organizadas, sprites",
    "ARQUIVOS_COMPACTADOS_GRANDES": "7z, ZIP, RAR acima de 1GB",
    "DUMPS": "Dumps de disco, imagens de partição",
    "ESPELHOS_BACKUP": "Backups completos de disco ou sistema",
}

# === Classe 5: Ambíguo ===
CLASSE_AMBIGUO = "AMBIGUO_REVISAO"
SUBCLASSES_AMBIGUO = {
    "CATEGORIA_INCERTA": "Sistema não conseguiu classificar com confiança",
    "CONFLITO_CONTEXTO": "Múltiplos contextos detectados sem dominante claro",
    "MULTIPLOS_DONOS": "Mais de uma pessoa detectada sem titular claro",
    "DUPLICIDADE_SEMANTICA": "Conteúdo similar a outro arquivo já classificado",
    "CRITICO_SEM_CONFIANCA": "Documento potencialmente crítico mas score baixo",
}

# === Entidades Conhecidas ===
KNOWN_PERSONS = {
    "Misael": {"variantes": ["Misael", "MISAEL", "Misael Junio", "Misael Oliveira", "MBG"], "tipo": "TITULAR"},
    "Cleidi": {"variantes": ["Cleidi", "Cleudimar", "CLEUDIMAR", "Cleidi Diniz"], "tipo": "CONJUGE"},
    "Olavo": {"variantes": ["Olavo"], "tipo": "DEPENDENTE"},
    "Ana Luiza": {"variantes": ["Ana Luiza", "Ana", "ANA LUIZA"], "tipo": "DEPENDENTE"},
    "Mateus": {"variantes": ["Mateus"], "tipo": "DEPENDENTE"},
}

KNOWN_ORGS = {
    "D4U": {"variantes": ["D4U", "DforYou", "D for You", "D4U Immigration"], "tipo": "ASSESSORIA_IMIGRACAO"},
    "AeC": {"variantes": ["AeC", "A&C", "AeC Contact Center"], "tipo": "EMPREGADOR"},
    "ProfitPro": {"variantes": ["ProfitPro", "Profit Pro", "Profit"], "tipo": "PLATAFORMA_TRADING"},
    "NuBank": {"variantes": ["NuBank", "Nubank", "Nu", "NU_"], "tipo": "BANCO"},
    "ABEMD": {"variantes": ["ABEMD"], "tipo": "PREMIACAO"},
}

IMMIGRATION_KEYWORDS = {
    "EB2", "NIW", "EB2-NIW", "EB2NIW", "D160", "D-160",
    "USCIS", "I-140", "I-485", "green card", "visto",
    "visa", "petition", "immigration", "imigracao", "imigração",
}

FINANCIAL_KEYWORDS = {
    "extrato", "IPVA", "financiamento", "seguro", "fatura",
    "imposto", "IR", "rendimento", "investimento", "carteira",
    "dividendo", "NTSL", "trading", "operacional", "renko",
}

# === Mapeamento Fase por Pasta Raiz (heurística inicial) ===
FASE_MAP_I = {
    "Bussines": "FASE_1",
    "Importante": "FASE_1",
    "finanças": "FASE_1",
    "_format_22-2-2025": "FASE_1",
    "Profit": "FASE_1",
    "ProfitPro": "FASE_1",
    "GENDK": "FASE_2",
    "SGDK": "FASE_2",
    "SMSDK": "FASE_2",
    "Mega_Emu": "FASE_2",
    "desktop": "FASE_2",  # Contém projetos misturados
    "projetoMidias": "FASE_2",
    "Steam conf": "FASE_3",
    "OneDrive_backup": "FASE_3",
    "Lenovo": "FASE_3",
    "LaunchBox": "FASE_4",
    "LaunchBox (3)": "FASE_4",
    "LaunchBox (old)": "FASE_4",
    "LaunchBox (old 2)": "FASE_4",
    "RetroFE": "FASE_4",
    "Roms": "FASE_4",
    "SteamLibrary": "FASE_4",
    "Assets": "FASE_4",
    "Rogue Samurai": "FASE_4",
}

FASE_MAP_F = {
    "Steam": "FASE_1",  # Contém Informações pessoais
    "Projects": "FASE_2",
    "Emulators": "FASE_4",
    "ROMs": "FASE_4",
    "backups": "FASE_5",
}
