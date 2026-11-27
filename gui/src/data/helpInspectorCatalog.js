/**
 * Visionary Studio - Hyper-Granular Interactive Help Inspector Catalog ("What's This?" Mode)
 *
 * Catálogo técnico e operacional de alta profundidade cobrindo todos os módulos,
 * painéis, micro-elementos, botões e controles contextuais do Visionary Studio.
 * Escopo do Software: Tradução assistida de mangás japoneses já em inglês (EN -> PT-BR).
 */

export const HELP_CATALOG = [
  // =========================================================================
  // 00. CONTROLE DO MODO DE INSPEÇÃO
  // =========================================================================
  {
    id: 'help-inspector-toggle',
    selector: '[data-help-id="help-inspector-toggle"]',
    priority: 100,
    category: 'Sistema de Ajuda & Diagnóstico',
    title: 'Botão do Inspetor Interativo (?)',
    shortcut: 'F1 ou Esc',
    summary: 'Ativa o modo de inspeção cirúrgica da interface. Transforma o cursor em mira explicativa e intercepta qualquer clique para exibir a documentação operacional daquele elemento exato.',
    details: [
      'Proteção contra Execução Acidental: Cliques em botões destrutivos (apagar balão, resetar página, limpar lote) apenas abrem o pop-up explicativo sem executar a ação real.',
      'Inspeção em Camadas (Raio-X): Ao clicar em um sub-elemento contido dentro de um card ou painel, o topo do pop-up oferece abas numéricas para navegar entre o micro-controle, o card e o painel-pai.',
      'Navegação entre Telas: Clicar em abas principais (Estúdio, Biblioteca, Lightbox, Módulos) permite alternar de tela mantendo o Inspetor ligado para continuar explorando.'
    ],
    tip: 'Pressione Esc para fechar o pop-up aberto ou encerrar o Modo Inspetor instantaneamente.'
  },

  // =========================================================================
  // 01. BARRA DE TÍTULO (TITLEBAR)
  // =========================================================================
  {
    id: 'titlebar-brand-logo',
    selector: '.titlebar-info',
    priority: 92,
    category: 'Barra de Título • Sistema',
    title: 'Visionary Studio PRO (Edição Offline Local)',
    summary: 'Suíte profissional de delimitação geométrica e tradução assistida desenvolvida exclusivamente para mangás e quadrinhos já em inglês (EN → PT-BR).',
    details: [
      'Execução 100% Offline: Todo o processamento visual (YOLO, Florence-2) e os modelos de linguagem (Ollama) operam localmente no seu computador.',
      'Aceleração Neural: Ativa tensores FP16 e aceleração por GPU NVIDIA (CUDA) para máxima velocidade em lotes de páginas.',
      'Gatilho Secreto de Diagnóstico: 5 cliques rápidos sobre a logo abrem o console interno de testes de desenvolvedor.'
    ],
    tip: 'Suas páginas e traduções ficam salvas estritamente no seu disco local sem nenhum envio para a nuvem.'
  },
  {
    id: 'titlebar-active-chapter-pill',
    selector: '.titlebar-active-file',
    priority: 92,
    category: 'Barra de Título • Contexto',
    title: 'Crachá do Capítulo em Memória',
    summary: 'Informa qual capítulo de mangá está carregado no buffer de trabalho no momento.',
    details: [
      'Visível globalmente em qualquer aba (Estúdio, Lightbox, Biblioteca).',
      'Tanto o Canvas de edição quanto as operações de lote atuam exclusivamente sobre os arquivos deste capítulo.',
      'Atualiza instantaneamente ao selecionar outra pasta no Explorador Lateral.'
    ],
    tip: 'Se este campo estiver vazio, selecione uma pasta de capítulo no Explorador Lateral para iniciar.'
  },
  {
    id: 'titlebar-bg-download',
    selector: '.titlebar-bg-download-pill',
    priority: 95,
    category: 'Barra de Título • Tarefas em Background',
    title: 'Monitor de Download de Motores Neurais',
    summary: 'Exibe a porcentagem em tempo real quando modelos de IA (Florence-2 OCR, YOLO ou LLMs de tradução) estão sendo baixados em segundo plano.',
    details: [
      'Permite continuar revisando ou navegando no software enquanto os pesos dos modelos são transferidos.',
      'Clique diretamente nesta pílula para abrir o painel detalhado com taxa de transferência (MB/s), total baixado e tempo estimado (ETA).'
    ],
    tip: 'Os downloads são resumíveis: se a conexão cair, o progresso continuará de onde parou.'
  },
  {
    id: 'titlebar-win-minimize',
    selector: '.win-btn[title="Minimizar"]',
    priority: 95,
    category: 'Controles de Janela',
    title: 'Minimizar Janela (_)',
    summary: 'Recolhe a janela para a barra de tarefas do Windows.',
    details: [
      'Não interrompe lotes de OCR ou tradução que estejam em processamento no momento.',
      'Se as notificações estiverem ativas, você receberá um alerta nativo do Windows quando o lote for concluído.'
    ]
  },
  {
    id: 'titlebar-win-maximize',
    selector: '.win-btn[title="Maximizar"], .win-btn[title="Restaurar"]',
    priority: 95,
    category: 'Controles de Janela',
    title: 'Maximizar / Restaurar Dimensões',
    summary: 'Expande a janela para preencher 100% do monitor ou restaura para o tamanho em janela flutuante.',
    details: [
      'Duplo clique na área vazia central da barra de título produz o mesmo efeito.',
      'Recomendado trabalhar maximizado para melhor aproveitamento do Canvas e da visualização Lado a Lado.'
    ]
  },
  {
    id: 'titlebar-win-close',
    selector: '.win-btn-close',
    priority: 95,
    category: 'Controles de Janela',
    title: 'Fechar Janela (Gerenciamento de Ciclo de Vida)',
    summary: 'Aciona o fechamento da janela com proteção de trabalho em segundo plano.',
    details: [
      'Modo Inteligente (Padrão): Se houver um lote de tradução rodando, o app não fecha; ele minimiza silenciosamente para a Bandeja do Sistema (System Tray) para terminar a tarefa.',
      'Se não houver lote ativo, encerra todos os processos Python/Ollama e descarrega a VRAM da GPU.',
      'O comportamento pode ser configurado em Configurações -> Áudio & Sistema -> "Ao Fechar a Janela".'
    ],
    tip: 'Para reabrir o app quando ele estiver minimizado na bandeja, clique duas vezes no ícone do Visionary perto do relógio do Windows.'
  },
  {
    id: 'titlebar-region',
    selector: '.custom-titlebar',
    priority: 30,
    category: 'Barra de Título',
    title: 'Barra de Título do Sistema',
    summary: 'Área superior de controle, arrasto e ancoragem da janela do programa no Windows.',
    details: [
      'Clique e arraste pela região central vazia para movimentar a janela livremente entre monitores.',
      'Duplo clique na barra alterna entre o modo maximizado e o modo em janela flutuante.'
    ]
  },

  // =========================================================================
  // 02. BARRA DE ABAS PRINCIPAIS (TOP TABS)
  // =========================================================================
  {
    id: 'nav-btn-expand-sidebar',
    selector: '.btn-expand-sidebar',
    priority: 92,
    category: 'Navegação Principal • Alternador',
    title: 'Botão Expandir Painel Lateral',
    summary: 'Reabre a gaveta lateral recolhida para recuperar o acesso às pastas ou capítulos.',
    details: [
      'No Estúdio e na Lightbox, reabre o Explorador de Pastas RAW do disco.',
      'Na Biblioteca, reabre a lista de arquivos de roteiro (.txt) consolidados.',
      'Permite recolher a lateral para focar 100% na tela de edição gráfica e reabrir com 1 clique.'
    ]
  },
  {
    id: 'nav-tab-estudio',
    selector: '.tab-btn[data-tab="processamento"]',
    priority: 92,
    category: 'Navegação Principal • Workspace',
    title: 'Aba Estúdio (Núcleo de Tradução & Delimitação)',
    shortcut: 'Aba 1',
    actionType: 'switch-tab',
    actionPayload: 'processamento',
    actionLabel: 'Abrir Aba Estúdio',
    summary: 'Estação de trabalho principal onde você inspeciona e calibra os balões em cada página de mangá, revisa o OCR em inglês e gera/edita as falas traduzidas em Português.',
    details: [
      'Coluna Central: Canvas gráfico de alta resolução com zoom e pan para inspecionar traços e caixas de fala.',
      'Coluna Direita (Inspetor): Alterna entre ferramentas geométricas (Layout 1), caixas de OCR (2) e edição de tradução PT-BR (3).',
      'Dock de Lote (Extrema Direita): Seleciona páginas do capítulo e dispara a pipeline completa em segundo plano.'
    ],
    tip: 'Todas as modificações feitas no Estúdio gravam dados no arquivo local _map.json sem alterar a imagem original.'
  },
  {
    id: 'nav-tab-biblioteca',
    selector: '.tab-btn[data-tab="biblioteca"]',
    priority: 92,
    category: 'Navegação Principal • Workspace',
    title: 'Aba Biblioteca (Roteiros & Cópia para Letristas)',
    shortcut: 'Aba 2',
    actionType: 'switch-tab',
    actionPayload: 'biblioteca',
    actionLabel: 'Abrir Aba Biblioteca',
    summary: 'Ambiente final de revisão e produtividade editorial. Transforma o capítulo processado em um roteiro limpo pronto para colar no Photoshop, Clip Studio Paint ou InDesign.',
    details: [
      'Cópia em 1 Clique: Clicar sobre qualquer fala copia o texto formatado para o clipboard e marca o item em verde ("✓ Colado").',
      'Formatador Tipográfico: Aplica travessão editorial (—), reticências (…) e caixa alta no instante da cópia.',
      'Visualização Lado a Lado: Exibe a imagem da página com balões numerados interativos sincronizados com o roteiro.'
    ],
    tip: 'Ative o botão "Auto-Retomar" para que a Biblioteca sempre abra diretamente na primeira fala que você ainda não colou.'
  },
  {
    id: 'nav-tab-lightbox',
    selector: '.tab-btn[data-tab="lightbox"]',
    priority: 92,
    category: 'Navegação Principal • Workspace',
    title: 'Aba Lightbox (Mesa de Montagem & Spreads)',
    shortcut: 'Aba 3',
    actionType: 'switch-tab',
    actionPayload: 'lightbox',
    actionLabel: 'Abrir Aba Lightbox',
    summary: 'Mesa de luz para preparação e organização física dos arquivos de imagem antes de rodar o detector de balões.',
    details: [
      'Costura de Páginas Duplas: Junta duas páginas divididas em uma imagem panorâmica única (evita balões cortados no meio da lombada).',
      'Divisão Vertical: Corta páginas duplas ao meio quando o capítulo vem com páginas unidas por engano.',
      'Reordenação Física: Arraste miniaturas para corrigir páginas fora de ordem e clique em "Salvar Ordem" para renomear os arquivos no disco.'
    ],
    tip: 'Trate páginas duplas na Lightbox SEMPRE antes de rodar o Layout no Estúdio para garantir leitura contínua dos balões centrais.'
  },
  {
    id: 'nav-tab-modulos',
    selector: '.tab-btn[data-tab="modulos"]',
    priority: 92,
    category: 'Navegação Principal • Workspace',
    title: 'Aba Módulos (Central de IA & Hardware)',
    shortcut: 'Aba 4',
    actionType: 'switch-tab',
    actionPayload: 'modulos',
    actionLabel: 'Abrir Aba Módulos',
    summary: 'Centro de gerenciamento de motores neurais locais e catálogo de modelos LLM para tradução EN -> PT-BR.',
    details: [
      'Telemetria de Hardware: Monitora consumo de VRAM da placa de vídeo, CUDA e uso de memória RAM.',
      'Motores de Visão: Instalação e calibração do detector YOLO e do leitor óptico Florence-2 (Large/Base).',
      'Serviço Ollama Local: Catálogo de modelos de linguagem (7B, 14B, 32B) com teste de compatibilidade com sua GPU.'
    ],
    tip: 'Se o PC ficar lento após várias horas de trabalho, clique em "Liberar VRAM" dentro desta aba.'
  },
  {
    id: 'nav-tab-configuracoes',
    selector: '.tab-btn[data-tab="configuracoes"]',
    priority: 92,
    category: 'Navegação Principal • Workspace',
    title: 'Aba Configurações (Preferências & Sistema)',
    shortcut: 'Aba 5',
    actionType: 'switch-tab',
    actionPayload: 'configuracoes',
    actionLabel: 'Abrir Aba Configurações',
    summary: 'Painel de customização visual, ergonomia, diretórios padrão, automações de workflow e mapa de atalhos de teclado.',
    details: [
      'Interface: Alterna temas (Pro Studio, Paperwhite, Cyber CAD, E-Ink) e escala de zoom (90% a 120%).',
      'Workflow & Pastas: Fixa a pasta raiz padrão onde ficam seus mangás no PC.',
      'Áudio & Sistema: Configura avisos sonoros de fim de lote e comportamento do botão fechar.'
    ]
  },
  {
    id: 'nav-global-breadcrumb',
    selector: '.global-breadcrumb',
    priority: 88,
    category: 'Navegação Principal • Contexto',
    title: 'Indicador de Caminho do Capítulo (Breadcrumb)',
    summary: 'Exibe a estrutura de pastas do capítulo em processamento (Série / Capítulo).',
    details: [
      'Ajuda a confirmar instantaneamente se você está operando sobre o capítulo correto.',
      'Passe o mouse sobre o texto para revelar o caminho físico absoluto no Windows Explorer.'
    ]
  },

  // =========================================================================
  // 03. EXPLORADOR LATERAL ESQUERDO
  // =========================================================================
  {
    id: 'sidebar-region',
    selector: '.app-sidebar',
    priority: 30,
    category: 'Explorador Lateral • Painel Principal',
    title: 'Painel do Explorador de Capítulos & Arquivos',
    summary: 'Centro de controle de entrada de arquivos e árvore de capítulos do seu computador.',
    details: [
      'Modo Estúdio / Lightbox: Opera como navegador de arquivos do Windows, listando discos rígidos (C:, D:) e pastas contendo páginas de mangá em formato de imagem (.jpg, .png, .webp).',
      'Modo Biblioteca: Transforma-se automaticamente no gerenciador de roteiros (.txt) compilados, exibindo quais capítulos já foram traduzidos e o progresso de falas pendentes.',
      'Detecção Automática: Ao clicar em uma pasta com imagens, o Visionary reconhece o capítulo, conta as páginas e carrega a mesa de trabalho instantaneamente.',
      'Redimensionamento Flexível: Posicione o mouse sobre a borda divisória direita e arraste para alargar ou encolher a coluna conforme seu monitor.'
    ],
    tip: 'Fixe a pasta principal de seus mangás em Configurações -> Workflow & Pastas para que o Explorador abra diretamente nela sempre que você iniciar o programa.'
  },
  {
    id: 'sidebar-collapse-btn',
    selector: '.btn-toggle-sidebar',
    priority: 94,
    category: 'Explorador Lateral • Controle',
    title: 'Botão Recolher Painel Lateral (-)',
    summary: 'Oculta a barra lateral esquerda para liberar área útil na tela.',
    details: [
      'Dá máxima largura para o Canvas de edição gráfica no Estúdio e para o modo Lado a Lado da Biblioteca.',
      'Para reabrir o painel a qualquer momento, basta clicar no botão "Explorador" ou "Capítulos" no topo esquerdo.'
    ]
  },
  {
    id: 'explorer-btn-up',
    selector: '.btn-explorer-up',
    priority: 94,
    category: 'Explorador Lateral • Navegação',
    title: 'Botão Subir Nível de Pasta (↑)',
    summary: 'Navega para a pasta pai do diretório atual na árvore de arquivos do Windows.',
    details: [
      'Permite subir de um capítulo para a pasta do volume, da série ou até a raiz de discos rígidos.',
      'Quando você já está no nível máximo, o botão fica desabilitado indicando a listagem de discos (C:, D:).'
    ],
    tip: 'Na aba Biblioteca, este botão abre diretamente a pasta física dos arquivos .txt no Windows Explorer.'
  },
  {
    id: 'explorer-btn-refresh',
    selector: '.btn-explorer-refresh',
    priority: 94,
    category: 'Explorador Lateral • Sincronização',
    title: 'Botão Atualizar Árvore de Pastas (↻)',
    summary: 'Reescaneia imediatamente o sistema de arquivos para refletir adições ou renomeações feitas externamente.',
    details: [
      'Use quando você acabar de descompactar novas pastas de mangá no Windows e quiser que elas apareçam na lista.',
      'Recalcula na hora as bolinhas de status e as contagens de páginas de cada capítulo.'
    ]
  },
  {
    id: 'explorer-search-input',
    selector: '.explorer-search-box, .explorer-search-input',
    priority: 90,
    category: 'Explorador Lateral • Filtro',
    title: 'Campo de Busca Rápida de Capítulos',
    summary: 'Filtra dinamicamente as pastas da listagem em tempo real conforme você digita.',
    details: [
      'Permite encontrar rapidamente volumes específicos em coleções com centenas de capítulos digitando números (ex: "024") ou palavras-chave.',
      'A busca é instantânea e não diferencia maiúsculas de minúsculas.'
    ]
  },
  {
    id: 'explorer-search-clear',
    selector: '.explorer-search-clear',
    priority: 96,
    category: 'Explorador Lateral • Filtro',
    title: 'Limpar Termo de Busca (X)',
    summary: 'Remove o filtro digitado e restaura a listagem de todos os capítulos da pasta.'
  },
  {
    id: 'explorer-status-dot-green',
    selector: '.explorer-status-dot.green',
    priority: 98,
    category: 'Explorador Lateral • Telemetria de Pasta',
    title: 'Bolinha Verde: Capítulo 100% Processado',
    summary: 'Indica que este capítulo já passou por todas as etapas (Layout, OCR e Tradução) e está pronto para exportação.',
    details: [
      'Todas as falas possuem tradução PT-BR gerada e compilada.',
      'Você pode abri-lo direto na Biblioteca para iniciar a diagramação no editor de imagem.'
    ]
  },
  {
    id: 'explorer-status-dot-progress',
    selector: '.explorer-status-dot.progress',
    priority: 98,
    category: 'Explorador Lateral • Telemetria de Pasta',
    title: 'Bolinha Laranja: Processamento Parcial',
    summary: 'Indica que o capítulo possui dados em andamento, mas ainda não foi finalizado.',
    details: [
      'Significa que apenas parte das páginas foi processada ou que o OCR foi extraído mas falta rodar a Tradução.',
      'Abra o capítulo no Estúdio para continuar de onde parou sem refazer o que já está pronto.'
    ]
  },
  {
    id: 'explorer-status-dot-blue',
    selector: '.explorer-status-dot.blue',
    priority: 98,
    category: 'Explorador Lateral • Telemetria de Pasta',
    title: 'Bolinha Azul: Pasta Organizadora / Série',
    summary: 'Identifica uma pasta contêiner que não possui imagens soltas, mas sim subpastas de capítulos dentro dela.',
    details: [
      'Clique na pasta para entrar nela e listar os capítulos individuais.'
    ]
  },
  {
    id: 'explorer-page-pill',
    selector: '.explorer-page-pill',
    priority: 97,
    category: 'Explorador Lateral • Telemetria de Pasta',
    title: 'Pílula de Quantidade de Páginas (ex: "76 págs")',
    summary: 'Informa o total exato de arquivos de imagem encontrados dentro do diretório.',
    details: [
      'Permite conferir se o capítulo veio completo antes mesmo de abri-lo.',
      'Ignora arquivos que não sejam imagens (.txt, .json, capas temporárias).'
    ]
  },
  {
    id: 'explorer-item',
    selector: '.explorer-item',
    priority: 80,
    category: 'Explorador Lateral • Entrada de Dados',
    title: 'Capítulo de Mangá (Pasta de Imagens RAW)',
    summary: 'Pasta contendo as páginas do mangá no seu computador que você deseja traduzir, delimitar balões ou diagramar.',
    details: [
      'Clique no Capítulo: Carrega imediatamente o lote de páginas na memória do programa e exibe a primeira página no Canvas do Estúdio.',
      'Indicador de Status: A bolinha colorida mostra de relance se o capítulo está 100% traduzido (verde), em andamento (laranja) ou se é uma pasta de série (azul).',
      'Contagem de Imagens: O crachá à direita indica quantas páginas válidas existem no capítulo.',
      'Capítulo Ativo: O capítulo aberto no momento fica marcado com destaque roxo.'
    ]
  },
  {
    id: 'library-status-complete',
    selector: '.file-status-pill.complete',
    priority: 98,
    category: 'Biblioteca • Status de Roteiro',
    title: 'Selo "✓ Pronto" no Roteiro',
    summary: 'Certifica que 100% dos balões deste capítulo já foram traduzidos e nenhum diálogo ficou pendente.'
  },
  {
    id: 'library-status-pending',
    selector: '.file-status-pill.pending',
    priority: 98,
    category: 'Biblioteca • Status de Roteiro',
    title: 'Selo de Falas Pendentes (⏳ X)',
    summary: 'Mostra a quantidade exata de balões deste capítulo que ainda estão marcados como [PENDENTE].',
    details: [
      'Ajuda o letrista a saber quais capítulos precisam de tradução antes de iniciar a colagem na arte.'
    ]
  },
  {
    id: 'library-btn-delete-file',
    selector: '.btn-delete-file',
    priority: 98,
    category: 'Biblioteca • Gerenciamento',
    title: 'Botão Excluir Roteiro da Biblioteca (Lixeira)',
    summary: 'Remove o arquivo consolidado .txt da lista de capítulos da Biblioteca.',
    details: [
      'Não apaga suas imagens originais nem o arquivo de coordenadas _map.json.',
      'Útil para limpar capítulos antigos que você já terminou de diagramar.'
    ]
  },
  {
    id: 'library-file-item',
    selector: '.library-file-item',
    priority: 80,
    category: 'Biblioteca • Lista de Capítulos',
    title: 'Roteiro Compilado do Capítulo (.txt)',
    summary: 'Roteiro editorial estruturado com todos os diálogos traduzidos para Português, pronto para cópia rápida no Photoshop ou Clip Studio.',
    details: [
      'Clique Simples: Abre o roteiro completo no visualizador central com ferramentas de cópia em 1 clique e visualização Lado a Lado.',
      'Metadados Visíveis: Exibe o nome do capítulo, data da última alteração, tamanho do arquivo e quantidade de falas pendentes.',
      'Sincronização Direta: Sempre que você altera um diálogo no Estúdio, o arquivo .txt correspondente é atualizado automaticamente.'
    ]
  },

  // =========================================================================
  // 04. ESTÚDIO — BARRA SUPERIOR DO EDITOR (SEAMLESS TOPBAR)
  // =========================================================================
  {
    id: 'studio-prev-page-btn',
    selector: '.editor-topbar .page-nav .btn-icon:first-child',
    priority: 96,
    category: 'Estúdio • Navegação Sequencial',
    title: 'Página Anterior (<)',
    shortcut: 'Seta Cima, PageUp ou [',
    summary: 'Retorna para a página anterior do capítulo salvando automaticamente as edições atuais.',
    details: [
      'Fica desabilitado quando a página 1 está aberta.',
      'Você também pode usar as teclas direcionais (Seta Cima / Seta Baixo) ou PageUp / PageDown.'
    ]
  },
  {
    id: 'studio-page-counter',
    selector: '.editor-topbar .page-count',
    priority: 96,
    category: 'Estúdio • Navegação Sequencial',
    title: 'Indicador Numérico de Página (Atual / Total)',
    summary: 'Mostra sua posição exata dentro do capítulo (ex: 14 / 76).',
    details: [
      'Garante que você acompanhe o andamento sequencial da leitura durante a revisão.'
    ]
  },
  {
    id: 'studio-next-page-btn',
    selector: '.editor-topbar .page-nav .btn-icon:last-child',
    priority: 96,
    category: 'Estúdio • Navegação Sequencial',
    title: 'Próxima Página (>)',
    shortcut: 'Seta Baixo, PageDown ou ]',
    summary: 'Avança para a próxima página do capítulo gravando todos os dados no disco antes de transicionar.'
  },
  {
    id: 'studio-editor-title',
    selector: '.editor-topbar .editor-title',
    priority: 92,
    category: 'Estúdio • Identificação de Imagem',
    title: 'Nome da Imagem Ativa & Ponto de Restauração',
    summary: 'Exibe o nome do arquivo da página aberta no Canvas (ex: 014.png).',
    details: [
      'Se o arquivo possuir um backup automático de histórico, um ícone de restauração azul aparecerá ao lado do nome.'
    ]
  },
  {
    id: 'studio-mode-view',
    selector: '.editor-topbar .mode-btn:nth-child(1)',
    priority: 95,
    category: 'Estúdio • Modos de Trabalho',
    title: 'Modo Visualizar (Inspeção Limpa & Métricas)',
    summary: 'Desativa contornos e caixas de edição para permitir leitura pura da arte sem sobreposições gráficas.',
    details: [
      'A coluna direita exibe o diagnóstico da página: resolução em pixels, proporção de diálogos vs onomatopeias (SFX) e total de caracteres.',
      'Contém o botão de recomendação automática que orienta qual é a próxima ação recomendada para a página.'
    ],
    tip: 'Use o modo Visualizar para apreciar a fluidez dramática da cena sem poluição visual na página.'
  },
  {
    id: 'studio-mode-layout',
    selector: '.editor-topbar .mode-btn[title*="Modo Layout"]',
    priority: 95,
    category: 'Estúdio • Modos de Trabalho',
    title: 'Modo 1: Layout (Delimitação Geométrica dos Balões)',
    shortcut: 'Tecla 1',
    summary: 'Ambiente para inspecionar e calibrar os polígonos que delimitam onde o OCR deve ler o texto em inglês.',
    details: [
      'Habilita ferramentas de desenho: Caixa Retangular (B), Caneta Poligonal (P), Vínculo de Falas (L) e SFX (S).',
      'Ordem de Leitura: Define a ordem em que a IA lerá os diálogos (Direita -> Esquerda, Topo -> Base).',
      'Margem de Segurança: Permite inflar polígonos (+6px) para evitar que pontuações ("...", "?!") ou letras nas bordas fiquem de fora do OCR.'
    ],
    tip: 'Se o OCR cortar letras no início ou fim de uma palavra, aumente a margem do balão neste modo.'
  },
  {
    id: 'studio-mode-ocr',
    selector: '.editor-topbar .mode-btn[title*="Modo OCR"]',
    priority: 95,
    category: 'Estúdio • Modos de Trabalho',
    title: 'Modo 2: OCR (Revisão da Extração em Inglês)',
    shortcut: 'Tecla 2',
    summary: 'Abre os cards de texto extraídos pelo Florence-2 para conferência visual do texto original.',
    details: [
      'Cada balão na imagem possui uma caixa de texto numerada correspondente na coluna direita.',
      'Filtro de Descarte: Sinaliza balões com provável ruído ou arte desenhada para que você possa descartá-los com 1 clique.',
      'Correção Rápida: Se uma palavra em inglês veio com erro de leitura (ex: "l" lido como "1"), corrija-a aqui antes de traduzir.'
    ],
    tip: 'Corrigir o inglês antes da tradução garante que o modelo LLM produza um português muito mais natural e preciso.'
  },
  {
    id: 'studio-mode-translation',
    selector: '.editor-topbar .mode-btn[title*="Modo Tradução"]',
    priority: 95,
    category: 'Estúdio • Modos de Trabalho',
    title: 'Modo 3: Tradução (Revisão e Adaptação PT-BR)',
    shortcut: 'Tecla 3',
    summary: 'Ambiente de polimento dos diálogos traduzidos para Português do Brasil.',
    details: [
      'Visão Comparativa: O card exibe o texto original em inglês logo acima da caixa em português para consulta imediata.',
      'Restauração Inteligente: Se você editar uma fala manualmente e quiser desfazer, o botão "↺ Restaurar IA" resgata a versão original.',
      'Sincronização em Tempo Real: Toda alteração feita aqui atualiza o arquivo de roteiro consolidado da Biblioteca.'
    ]
  },
  {
    id: 'studio-autosave-badge',
    selector: '.autosave-status-badge',
    priority: 94,
    category: 'Estúdio • Integridade de Dados',
    title: 'Monitor de Salvamento Automático (Auto-Save)',
    summary: 'Sinaliza o status de persistência das alterações no arquivo _map.json do capítulo.',
    details: [
      'Salvo (Verde): Todas as coordenadas, caixas e textos estão 100% gravados em disco.',
      'Salvando... (Azul): Transação assíncrona de escrita em andamento.',
      'Erro ao Salvar (Vermelho): Falha de permissão ou bloqueio de arquivo; clique no botão para tentar gravar novamente.'
    ]
  },
  {
    id: 'studio-btn-fit-screen',
    selector: '.editor-topbar .btn-topbar-tool[title*="Ajustar Imagem"]',
    priority: 94,
    category: 'Estúdio • Câmera do Canvas',
    title: 'Botão Ajustar à Tela (Reset de Zoom)',
    summary: 'Reenquadra a página inteira no espaço visível da tela e exibe a porcentagem atual de escala.',
    details: [
      'Útil após navegar com muito zoom em detalhes pequenos para recuperar a visão panorâmica da página.',
      'Calcula a proporção ideal mantendo a proporção geométrica da arte sem distorções.'
    ]
  },
  {
    id: 'studio-btn-auto-zoom',
    selector: '.editor-topbar .btn-topbar-tool[title*="Auto-Zoom"]',
    priority: 95,
    category: 'Estúdio • Câmera do Canvas',
    title: 'Alternador de Auto-Zoom Contextual',
    shortcut: 'Tecla Z',
    summary: 'Quando ativado (ponto luminoso aceso), clicar em qualquer balão na lista lateral aproxima e centraliza a câmera automaticamente naquele balão.',
    details: [
      'Economiza milhares de movimentos manuais de pan e zoom durante a revisão de capítulos com 50+ falas.',
      'Pressione a tecla Z no teclado para ligar ou desligar rapidamente.'
    ]
  },

  // =========================================================================
  // 05. ESTÚDIO — INSPETOR NO MODO "LAYOUT" (GEOMETRIA & BALÕES)
  // =========================================================================
  {
    id: 'layout-tool-select',
    selector: '.btn-layout-dock[title*="Selecionar e mover"], .canvas-tool-btn[title*="Selecionar e mover"]',
    priority: 96,
    category: 'Modo Layout • Ferramentas de Desenho',
    title: 'Ferramenta Seleção (Mover & Ajustar)',
    shortcut: 'Tecla V',
    summary: 'Cursor padrão de edição para selecionar, mover ou redimensionar balões existentes no Canvas.',
    details: [
      'Clique sobre um balão para abrir suas 8 alças elásticas e painel de propriedades.',
      'Arraste o balão para corrigir seu posicionamento em relação ao desenho.',
      'Pressione Esc ou clique no fundo vazio da página para desmarcar.'
    ]
  },
  {
    id: 'layout-tool-rect',
    selector: '.btn-layout-dock[title*="Desenhar caixa retangular"], .canvas-tool-btn[title*="Desenhar caixa retangular"]',
    priority: 96,
    category: 'Modo Layout • Ferramentas de Desenho',
    title: 'Ferramenta Retângulo (Criar Novo Balão BBox)',
    shortcut: 'Tecla B',
    summary: 'Cria uma nova caixa de diálogo retangular desenhando diretamente sobre a imagem.',
    details: [
      'Use para capturar placas narrativas, recordatórios de narração ou falas que o detector automático não tenha identificado.',
      'Ao soltar o clique, o novo balão é inserido na ordem de leitura e recebe seu número sequencial automaticamente.'
    ]
  },
  {
    id: 'layout-tool-pen',
    selector: '.btn-layout-dock[title*="Desenhar balão livre"], .canvas-tool-btn[title*="Desenhar balão livre"]',
    priority: 96,
    category: 'Modo Layout • Ferramentas de Desenho',
    title: 'Ferramenta Caneta (Polígono Ponto a Ponto)',
    shortcut: 'Tecla P',
    summary: 'Permite criar contornos curvos ou polígonos inclinados contornando o balão vértice por vértice.',
    details: [
      'Clique em sequência ao redor da área de texto para criar os 4 vértices do polígono (concluído no 4º clique).',
      'Ideal para balões em perspectiva ou quando uma caixa retangular capturaria traços da arte vizinha.'
    ]
  },
  {
    id: 'layout-tool-link',
    selector: '.btn-layout-dock[title*="Vincular grupo"], .canvas-tool-btn[title*="Vincular Balões"]',
    priority: 96,
    category: 'Modo Layout • Ferramentas de Desenho',
    title: 'Ferramenta Vínculo de Falas (Link)',
    shortcut: 'Tecla L',
    summary: 'Agrupa dois ou mais balões que pertencem à mesma frase dividida em múltiplos quadros.',
    details: [
      'Com a ferramenta ativa, clique no primeiro balão e depois no segundo para traçar a linha de união.',
      'O tradutor LLM processará os dois balões como um único período gramatical, gerando uma tradução contínua e coerente.'
    ],
    tip: 'Use em falas quebradas (ex: balão 1 com "Eu não..." e balão 2 com "...acredito nisso!") para evitar traduções sem sentido.'
  },
  {
    id: 'layout-tool-sfx',
    selector: '.btn-layout-dock[title*="Alternar SFX"], .canvas-tool-btn[title*="Alternar Balão"]',
    priority: 96,
    category: 'Modo Layout • Ferramentas de Desenho',
    title: 'Ferramenta Alternar SFX (Onomatopeia)',
    shortcut: 'Tecla S',
    summary: 'Pincel rápido para alternar balões entre Diálogo Normal (Roxo) e Efeito Sonoro / Onomatopeia (Amarelo).',
    details: [
      'Ao clicar em um balão com esta ferramenta ativa, sua categoria se inverte imediatamente.',
      'Itens marcados como SFX recebem tratamento diferenciado na exportação para não poluir o roteiro principal de falas.'
    ]
  },
  {
    id: 'layout-contour-polygon-btn',
    selector: '.btn-contour-toggle[title*="Contorno Orgânico"]',
    priority: 96,
    category: 'Modo Layout • Tipo de Contorno',
    title: 'Contorno Orgânico (Segmentação Curva OpenCV)',
    summary: 'Renderiza o recorte dos balões acompanhando a curvatura real da elipse do desenho.',
    details: [
      'Permite que o OCR enxergue o interior do balão sem capturar traços escuros da arte que fiquem fora da elipse.',
      'Recomendado para a esmagadora maioria das páginas de mangá.'
    ]
  },
  {
    id: 'layout-contour-rect-btn',
    selector: '.btn-contour-toggle[title*="Caixa Retangular"]',
    priority: 96,
    category: 'Modo Layout • Tipo de Contorno',
    title: 'Caixa Retangular (Bounding Box Reta)',
    summary: 'Simplifica a geometria dos balões para retângulos tradicionais de 4 cantos.',
    details: [
      'Mais rápido para caixas de narração quadradas, recordatórios e letreiros retos.'
    ]
  },
  {
    id: 'layout-subtab-list',
    selector: '.btn-layout-tab:first-child',
    priority: 95,
    category: 'Modo Layout • Inspetor',
    title: 'Aba: Ordem de Leitura (Lista Sequencial)',
    summary: 'Exibe a lista de todos os balões da página com seus números de ranking (#1, #2...), tags espaciais e mini-mapas.',
    details: [
      'Permite arrastar cards para cima ou para baixo para reordenar a sequência de fala.',
      'Oferece ferramentas de ordenação automática de mangá.'
    ]
  },
  {
    id: 'layout-subtab-props',
    selector: '.btn-layout-tab:last-child',
    priority: 95,
    category: 'Modo Layout • Inspetor',
    title: 'Aba: Propriedades do Balão Selecionado',
    summary: 'Painel com os controles de ajuste fino do balão ativo no momento.',
    details: [
      'Modo de Edição de Nós: Bordas elásticas (8), Vértices mestres ou Todos os pontos OpenCV.',
      'Margem OCR (+6px / -6px): Infla ou encolhe o contorno para salvar pontuações cortadas.',
      'Botões de exclusão (Del) e restauração de posição original.'
    ]
  },
  {
    id: 'layout-auto-sort-btn',
    selector: '.btn-flow.auto, .canvas-tool-btn.auto-sort',
    priority: 96,
    category: 'Modo Layout • Ordenação',
    title: 'Auto-Ordenar Mangá (Direita ➔ Esquerda)',
    summary: 'Recalcula instantaneamente a numeração de todos os balões da página seguindo a geometria tradicional de mangá.',
    details: [
      'Analisa as coordenadas (X, Y) e organiza o fluxo da direita para a esquerda e de cima para baixo.',
      'Use após desenhar balões novos manualmente para integrá-los na ordem certa da cena.'
    ]
  },
  {
    id: 'layout-sequence-btn',
    selector: '.btn-flow[title*="Modo Sequência"], .canvas-tool-btn[title*="Modo Sequência"]',
    priority: 96,
    category: 'Modo Layout • Ordenação',
    title: 'Marcar Ordem 1-a-1 no Canvas',
    summary: 'Ativa o modo de ordenação interativo por clique direto sobre a página.',
    details: [
      'Clique nos balões na imagem na ordem exata em que você quer que sejam lidos (1º, 2º, 3º...).',
      'Ao terminar de clicar em todos os balões da página, a nova numeração é salva e aplicada automaticamente.',
      'Ideal para cenas complexas com quadros sobrepostos ou balões diagonais.'
    ],
    tip: 'Pressione Esc ou clique no botão novamente para cancelar a ordenação a qualquer momento sem alterar nada.'
  },
  {
    id: 'canvas-bottom-filmstrip-bar',
    selector: '.canvas-bottom-filmstrip',
    priority: 95,
    category: 'Estúdio • Fita de Balões',
    title: 'Fita de Leitura dos Balões (Filmstrip)',
    summary: 'Barra horizontal na base do Canvas que organiza todos os balões da página em ordem sequencial de leitura.',
    details: [
      'Navegação Contínua: Permite selecionar e inspecionar qualquer balão da página sem tirar os olhos da arte.',
      'Diferenciação Visual: Balões roxos representam falas de personagens; chips amarelos representam efeitos sonoros (SFX).',
      'Atalhos de Teclado: Use as teclas A (anterior) e D (próximo) para percorrer a fita rapidamente.',
      'Recolhimento: Clique na seta para baixo para minimizar a barra e desobstruir o rodapé do Canvas.'
    ],
    tip: 'O balão ativo no Canvas é automaticamente centralizado na fita conforme você navega.'
  },
  {
    id: 'canvas-filmstrip-chip',
    selector: '.filmstrip-chip',
    priority: 98,
    category: 'Estúdio • Fita de Balões',
    title: 'Chip de Balão na Fita (#)',
    summary: 'Representação individual deste balão na sequência cronológica da página com número e prévia do texto.',
    details: [
      'Clique no chip para selecionar este balão no Canvas e abrir seus parâmetros no Inspetor.',
      'O botão de raio no canto do chip permite converter entre Fala de Diálogo e SFX com um único clique.'
    ]
  },
  {
    id: 'canvas-filmstrip-nav-arrows',
    selector: '.filmstrip-arrow-btn',
    priority: 99,
    category: 'Estúdio • Fita de Balões',
    title: 'Navegar Balão Anterior / Próximo (A / D)',
    summary: 'Avança ou retrocede para o balão vizinho na sequência de leitura (aproxima e centraliza a câmera apenas com o Auto-Zoom [Z] ativo).'
  },
  {
    id: 'canvas-filmstrip-toggle-collapse',
    selector: '.filmstrip-collapse-btn, .filmstrip-collapsed-pill',
    priority: 99,
    category: 'Estúdio • Fita de Balões',
    title: 'Minimizar / Expandir Fita de Balões',
    summary: 'Alterna entre a fita horizontal expandida e uma pílula discreta no rodapé para maximizar o campo de visão da arte.'
  },
  {
    id: 'props-margin-expand',
    selector: '.btn-stepper-pill.expand',
    priority: 98,
    category: 'Propriedades do Balão • Margem OCR',
    title: 'Botão +6px Margem (Expandir Contorno)',
    summary: 'Expande o polígono do balão selecionado em 6 pixels para fora em todas as direções.',
    details: [
      'Ferramenta essencial quando o detector automático deixa as pontuações ("...", "?!") ou as letras das extremidades coladas na linha de corte.',
      'Garante que 100% dos pixels do texto fiquem dentro do recorte que será enviado para o Florence-2 OCR.'
    ],
    tip: 'Se o texto extraído no Modo OCR faltou uma vírgula ou pontuação, volte aqui e dê um ou dois cliques em "+6px Margem".'
  },
  {
    id: 'props-margin-shrink',
    selector: '.btn-stepper-pill.shrink',
    priority: 98,
    category: 'Propriedades do Balão • Margem OCR',
    title: 'Botão -6px Margem (Encolher Contorno)',
    summary: 'Reduz o polígono do balão selecionado em 6 pixels para dentro.',
    details: [
      'Use quando o contorno estiver muito largo e encostando em linhas escuras de desenhos ou hachuras ao redor do balão.'
    ]
  },
  {
    id: 'balloon-nav-card',
    selector: '.balloon-nav-card',
    priority: 95,
    category: 'Estúdio • Ordem de Leitura',
    title: 'Card de Balão (Lista de Leitura)',
    summary: 'Representação deste balão na fila sequencial de extração e tradução da página de mangá.',
    details: [
      'Clique para selecionar o balão no Canvas (aproxima e centraliza somente se o Auto-Zoom [Z] estiver ativado).',
      'Duplo clique abre a aba de Propriedades para ajuste de nós e margem (+6px).',
      'Segure e arraste o card para alterar manualmente a ordem de fala na página.',
      'O mini-mapa à esquerda exibe a localização geométrica real do balão na página inteira.'
    ],
    tip: 'A numeração (#01, #02...) define a ordem de saída no roteiro final e no lote de tradução.'
  },
  {
    id: 'balloon-card-minimap',
    selector: '.mini-page-map',
    priority: 99,
    category: 'Card de Balão • Mini-Mapa SVG',
    title: 'Mini-Mapa Vetorial de Localização Real',
    summary: 'Projeção geométrica da página inteira desenhando o balão exatamente na sua posição (X, Y) e proporção real.',
    details: [
      'Cor Roxa: Balão de fala comum.',
      'Cor Amarela: Efeito sonoro / SFX.',
      'Permite identificar visualmente a qual parte da página aquele card se refere sem precisar caçar o balão na imagem grande.'
    ]
  },
  {
    id: 'balloon-card-rank',
    selector: '.card-v1-rank',
    priority: 99,
    category: 'Card de Balão • Ranking',
    title: 'Número Sequencial do Balão (#01, #02...)',
    summary: 'Posição cronológica desta fala na ordem em que será enviada para o tradutor de IA e gravada no roteiro final.'
  },
  {
    id: 'balloon-card-loc-tag',
    selector: '.card-v1-loc',
    priority: 99,
    category: 'Card de Balão • Localização',
    title: 'Tag Espacial (ex: Topo Dir, Centro, Base Esq)',
    summary: 'Cálculo de quadrante para localização rápida do balão na página.'
  },
  {
    id: 'balloon-card-dimensions',
    selector: '.card-v1-dim',
    priority: 99,
    category: 'Card de Balão • Geometria',
    title: 'Dimensões em Pixels (Largura × Altura)',
    summary: 'Tamanho exato da caixa do balão no arquivo de imagem original.'
  },
  {
    id: 'balloon-card-btn-sfx',
    selector: '.balloon-sfx-badge, .balloon-hover-action-btn.toggle-sfx',
    priority: 99,
    category: 'Card de Balão • Ação Rápida',
    title: 'Alternar SFX / Fala (Ícone Raio)',
    summary: 'Converte este item individual entre Balão de Diálogo e Efeito Sonoro direto na lista.'
  },
  {
    id: 'balloon-card-btn-reset',
    selector: '.balloon-hover-action-btn.reset-pos',
    priority: 99,
    category: 'Card de Balão • Ação Rápida',
    title: 'Restaurar Posição Original (↺)',
    summary: 'Aparece se o balão tiver sido movido ou redimensionado. Devolve o contorno às coordenadas originais da IA.'
  },
  {
    id: 'balloon-card-btn-props',
    selector: '.balloon-hover-action-btn.edit-props',
    priority: 99,
    category: 'Card de Balão • Ação Rápida',
    title: 'Abrir Propriedades do Balão (Sliders)',
    summary: 'Foca este balão no Canvas e abre a aba Propriedades para ajuste de margem ou nós.'
  },

  // =========================================================================
  // 06. ESTÚDIO — BLOCOS DE TEXTO (OCR & TRADUÇÃO)
  // =========================================================================
  {
    id: 'block-drag-grip',
    selector: '.inspector-block-grip',
    priority: 99,
    category: 'Bloco de Texto • Ordenação',
    title: 'Alça de Reordenação de Diálogo (⠿)',
    summary: 'Segure e arraste por este ícone pontilhado para mover o balão para cima ou para baixo na ordem da página.'
  },
  {
    id: 'block-order-input',
    selector: '.inspector-block-input',
    priority: 99,
    category: 'Bloco de Texto • Ordenação',
    title: 'Campo Numérico de Posição (#)',
    summary: 'Permite digitar o novo número do bloco diretamente no teclado para reposicioná-lo na hora sem arrastar.'
  },
  {
    id: 'block-remove-btn',
    selector: '.inspector-block-remove-btn',
    priority: 99,
    category: 'Bloco de Texto • Exclusão',
    title: 'Excluir Balão da Página (X)',
    summary: 'Remove este diálogo da página e do roteiro, reindexando automaticamente a numeração dos demais.'
  },
  {
    id: 'block-decision-keep',
    selector: '.btn-decision-keep',
    priority: 99,
    category: 'Filtro de Ruído • Decisão',
    title: 'Botão "Manter Balão"',
    summary: 'Rejeita a sugestão de descarte e preserva este balão como fala legítima de personagem.'
  },
  {
    id: 'block-decision-discard',
    selector: '.btn-decision-discard',
    priority: 99,
    category: 'Filtro de Ruído • Decisão',
    title: 'Botão "Descartar" (Remover Ruído)',
    summary: 'Confirma que o recorte é apenas uma onomatopeia desenhada ou sujeira gráfica e remove-o da página.'
  },
  {
    id: 'inspector-decision-card',
    selector: '.inspector-decision-card',
    priority: 95,
    category: 'Modos OCR/Tradução • Filtro',
    title: 'Painel "Sugerido para Descarte (Ruído / SFX)"',
    summary: 'Alerta inteligente emitido quando a IA detecta que o texto no interior do balão não é um diálogo narrativo.',
    details: [
      'Evita que ruídos gráficos ("WIPE", "THUD", "GRIT") entrem na fila de tradução como falas de personagens.'
    ]
  },
  {
    id: 'block-ocr-reference',
    selector: '.inspector-ref-box',
    priority: 97,
    category: 'Modo Tradução • Referência',
    title: 'Caixa de Referência: OCR Original (Inglês)',
    summary: 'Mostra o texto em inglês lido pelo Florence-2 para que você possa comparar com a tradução em português sem sair do card.'
  },
  {
    id: 'inspector-restore-ai-btn',
    selector: '.inspector-btn-restore-ai',
    priority: 99,
    category: 'Modo Tradução • Histórico',
    title: 'Botão "↺ Restaurar IA"',
    summary: 'Aparece se você alterou a tradução manualmente. Clique para voltar à frase exata que o LLM gerou originalmente.'
  },
  {
    id: 'block-textarea',
    selector: '.inspector-block-textarea',
    priority: 96,
    category: 'Estúdio • Edição Textual',
    title: 'Campo de Edição de Texto do Balão',
    summary: 'Editor de texto com salvamento automático para revisão da frase selecionada.',
    details: [
      'No Modo OCR (2): Permite corrigir falhas de leitura óptica no texto em inglês (letras coladas, pontuações) antes de traduzir.',
      'No Modo Tradução (3): Permite adaptar e reescrever a fala em Português com linguagem natural, gírias e pontuações do diálogo.',
      'Persistência Imediata: As alterações são gravadas no arquivo local _map.json conforme você digita, sem necessidade de clicar em salvar.'
    ],
    tip: 'Use a barra inferior de símbolos rápidos para inserir reticências (…) ou exclamações duplas (!?) com um único clique.'
  },

  // =========================================================================
  // 07. ESTÚDIO — PROCESSAMENTO EM LOTE (BATCH SIDEBAR)
  // =========================================================================
  {
    id: 'batch-select-all-btn',
    selector: '.btn-select-all',
    priority: 95,
    category: 'Processamento em Lote • Seleção',
    title: 'Botão Selecionar Todas / Desmarcar',
    summary: 'Alterna a seleção de todas as páginas do capítulo com um único clique.',
    details: [
      'Apenas páginas marcadas com checkbox serão enviadas para o pipeline ao clicar em Executar.'
    ]
  },
  {
    id: 'batch-counter-badge',
    selector: '.batch-counter-badge, .batch-sub-bar',
    priority: 92,
    category: 'Processamento em Lote • Contagem',
    title: 'Contador de Seleção de Lote (ex: 76 / 76)',
    summary: 'Indica a proporção de páginas marcadas em relação ao total do capítulo.'
  },
  {
    id: 'batch-page-item-row',
    selector: '.batch-page-item',
    priority: 95,
    category: 'Processamento em Lote • Lista de Páginas',
    title: 'Item de Página do Capítulo',
    summary: 'Linha de controle da página na lista de execução em lote do Estúdio.',
    details: [
      'Clique na linha para abrir instantaneamente esta página no Canvas de visualização e edição.',
      'Marque a caixa de seleção à esquerda para incluir esta página no próximo lote de execução.',
      'O micro-trilho de 3 pontos à direita indica o status de conclusão: 1º Layout (balões), 2º OCR (inglês) e 3º Tradução (português).'
    ],
    tip: 'Páginas ativas no Canvas ficam destacadas com borda mais iluminada na lista.'
  },
  {
    id: 'batch-page-checkbox-item',
    selector: '.batch-page-item .checkbox-wrapper',
    priority: 98,
    category: 'Processamento em Lote • Seleção',
    title: 'Caixa de Seleção da Página',
    summary: 'Marca ou desmarca esta página específica para inclusão no processamento em lote da pipeline.',
    tip: 'Páginas desmarcadas são completamente ignoradas durante a execução do lote.'
  },
  {
    id: 'batch-track-dot-lay',
    selector: '.vs-track-dot:nth-child(1)',
    priority: 99,
    category: 'Micro-Trilho • Etapa 1',
    title: '1º Ponto: Status de Layout (Delimitação)',
    summary: 'Aceso quando a página já possui balões e caixas geométricas detectadas.'
  },
  {
    id: 'batch-track-dot-ocr',
    selector: '.vs-track-dot:nth-child(2)',
    priority: 99,
    category: 'Micro-Trilho • Etapa 2',
    title: '2º Ponto: Status de OCR (Texto em Inglês)',
    summary: 'Aceso quando o texto em inglês já foi extraído das caixas de balão.'
  },
  {
    id: 'batch-track-dot-trn',
    selector: '.vs-track-dot:nth-child(3)',
    priority: 99,
    category: 'Micro-Trilho • Etapa 3',
    title: '3º Ponto: Status de Tradução (PT-BR)',
    summary: 'Aceso quando todos os diálogos já foram traduzidos para Português.'
  },
  {
    id: 'batch-micro-track',
    selector: '.vs-micro-track',
    priority: 96,
    category: 'Processamento em Lote • Indicador',
    title: 'Micro-Trilho de 3 Etapas (Layout • OCR • Tradução)',
    summary: 'Semáforo de 3 pontos foscos que mostra de relance quais fases da pipeline já estão gravadas em cada página.'
  },
  {
    id: 'batch-clear-translate',
    selector: '.btn-clear-ghost[title*="apenas traduções"]',
    priority: 98,
    category: 'Processamento em Lote • Limpeza Seletiva',
    title: 'Apagar Apenas Traduções',
    summary: 'Exclui as frases em português das páginas selecionadas mantendo os balões de layout e o texto em inglês extraído intocados.',
    tip: 'Ideal quando você quer reprocessar o capítulo com outro modelo de linguagem sem perder suas correções manuais de layout.'
  },
  {
    id: 'batch-clear-ocr',
    selector: '.btn-clear-ghost[title*="Apagar OCR"]',
    priority: 98,
    category: 'Processamento em Lote • Limpeza Seletiva',
    title: 'Apagar OCR e Traduções',
    summary: 'Limpa os textos extraídos e traduzidos mantendo todos os polígonos e margens que você desenhou ou expandiu no Modo Layout.'
  },
  {
    id: 'batch-clear-all',
    selector: '.btn-clear-ghost[title*="Apagar balões"]',
    priority: 98,
    category: 'Processamento em Lote • Limpeza Seletiva',
    title: 'Apagar Tudo (Layout + OCR + Tradução)',
    summary: 'Reseta todos os dados gerados nas páginas marcadas (as imagens originais nunca são modificadas).'
  },
  {
    id: 'batch-sfx-filter-pill',
    selector: '.val-sfx-pill',
    priority: 98,
    category: 'Processamento em Lote • Pipeline',
    title: 'Filtro SFX Profundo (Florence-2)',
    summary: 'Quando ligado, roda visão computacional avançada durante o Layout para classificar e descartar onomatopeias desenhadas.',
    details: [
      'Deixe ligado em mangás com muitas onomatopeias gráficas.',
      'Deixe desligado se quiser que a detecção de balões termine mais rapidamente.'
    ]
  },
  {
    id: 'batch-stage-row-layout',
    selector: '.batch-stages-vertical .batch-stage-row:nth-child(1)',
    priority: 94,
    category: 'Processamento em Lote • Pipeline',
    title: 'Etapa 1: Delimitação de Balões (Layout YOLO)',
    summary: 'Detecta a posição, caixas delimitadoras e polígonos orgânicos de todos os balões e textos desta página.',
    details: [
      'Executa o modelo neural YOLO treinado na geometria de mangás para encontrar cada balão.',
      'Gera os contornos que serão enviados para recorte e reconhecimento de texto.',
      'Clique no botão Play à direita para rodar apenas esta etapa nas páginas selecionadas.'
    ]
  },
  {
    id: 'batch-stage-row-ocr',
    selector: '.batch-stages-vertical .batch-stage-row:nth-child(2)',
    priority: 94,
    category: 'Processamento em Lote • Pipeline',
    title: 'Etapa 2: Leitura Óptica de Caracteres (OCR Florence-2)',
    summary: 'Extrai o texto em inglês e todas as pontuações (... e ?!) de dentro dos balões delimitados.',
    details: [
      'Requer que a Etapa 1 (Layout) já tenha detectado os balões na página.',
      'Utiliza inteligência visual profunda para ler fontes estilizadas e onomatopeias.',
      'Clique no botão Play à direita para rodar apenas o OCR nas páginas selecionadas.'
    ]
  },
  {
    id: 'batch-stage-row-translate',
    selector: '.batch-stages-vertical .batch-stage-row:nth-child(3)',
    priority: 94,
    category: 'Processamento em Lote • Pipeline',
    title: 'Etapa 3: Tradução Assistida (LLM Local)',
    summary: 'Traduz os diálogos capturados do inglês para Português Brasileiro (PT-BR) com adaptação coloquial e ritmo dramático.',
    details: [
      'Executa localmente via Ollama sem custos de API e com privacidade absoluta.',
      'Mantém a ordem correta de leitura de mangá (da direita para a esquerda).',
      'Clique no botão Play à direita para rodar apenas a tradução nas páginas selecionadas.'
    ]
  },
  {
    id: 'batch-run-only-layout',
    selector: '.batch-stages-vertical .batch-stage-row:nth-child(1) .btn-step-run',
    priority: 98,
    category: 'Processamento em Lote • Disparo Individual',
    title: 'Executar Apenas 1. Layout (Play)',
    summary: 'Dispara apenas o detector de balões para as páginas marcadas sem rodar OCR nem Tradução ainda.',
    tip: 'Fluxo profissional: rode apenas o Layout no capítulo inteiro -> passe rapidamente pelas páginas conferindo se algum balão cortou texto -> depois rode OCR e Tradução.'
  },
  {
    id: 'batch-run-only-ocr',
    selector: '.batch-stages-vertical .batch-stage-row:nth-child(2) .btn-step-run',
    priority: 98,
    category: 'Processamento em Lote • Disparo Individual',
    title: 'Executar Apenas 2. OCR (Play)',
    summary: 'Extrai o texto em inglês dos balões já delimitados nas páginas marcadas.'
  },
  {
    id: 'batch-run-only-translate',
    selector: '.batch-stages-vertical .batch-stage-row:nth-child(3) .btn-step-run',
    priority: 98,
    category: 'Processamento em Lote • Disparo Individual',
    title: 'Executar Apenas 3. Tradução (Play)',
    summary: 'Envia os textos extraídos para o modelo LLM traduzir para Português em lote mantendo coerência contextual.'
  },
  {
    id: 'batch-overwrite-toggle',
    selector: '.batch-option-row',
    priority: 95,
    category: 'Processamento em Lote • Opção',
    title: 'Checkbox "Sobrescrever dados existentes"',
    summary: 'Controla se páginas que já têm aquela etapa pronta devem ser puladas (desmarcado) ou reprocessadas por cima (marcado).'
  },
  {
    id: 'batch-run-full-btn',
    selector: '.btn-primary-batch',
    priority: 96,
    category: 'Processamento em Lote • Disparo Mestre',
    title: 'Botão Mestre: Executar Pipeline Completa',
    summary: 'Enfileira e executa automaticamente as 3 etapas em sequência (Layout ➔ OCR ➔ Tradução) e compila o roteiro .txt na Biblioteca.',
    details: [
      'Executa em background sem travar a interface.',
      'Acompanhe o progresso em tempo real pela barra na base do painel.'
    ]
  },

  // =========================================================================
  // 08. LIGHTBOX (MESA DE LUZ)
  // =========================================================================
  {
    id: 'lightbox-stitch-direction',
    selector: '.stitch-select-wrapper',
    priority: 96,
    category: 'Lightbox • Costura de Spreads',
    title: 'Seletor de Sentido de Costura (Mangá vs Ocidental)',
    summary: 'Define a ordem espacial ao unir duas páginas lado a lado.',
    details: [
      'Mangá (Dir ➔ Esq): Coloca a 1ª página selecionada na DIREITA e a 2ª na ESQUERDA (ordem correta de cenas duplas japonesas).',
      'Ocidental (Esq ➔ Dir): Coloca a 1ª página na esquerda e a 2ª na direita.'
    ],
    tip: 'Em mangás japoneses, mantenha sempre Mangá (Dir ➔ Esq) para que a ação da cena dupla não fique invertida.'
  },
  {
    id: 'lightbox-merge-btn',
    selector: '.lightbox-unified-toolbar .toolbar-btn[title*="Unir páginas"]',
    priority: 96,
    category: 'Lightbox • Costura de Spreads',
    title: 'Botão Unir Páginas (Costura sem Perda)',
    summary: 'Junta 2 imagens selecionadas em um único arquivo horizontal mantendo a resolução total dos dois arquivos.',
    details: [
      'Requer exatamente 2 páginas selecionadas na grade.',
      'Gera um novo arquivo (ex: 002_003.png) e remove as metades soltas do capítulo.'
    ]
  },
  {
    id: 'lightbox-split-btn',
    selector: '.lightbox-unified-toolbar .toolbar-btn[title*="Dividir página"]',
    priority: 96,
    category: 'Lightbox • Costura de Spreads',
    title: 'Botão Dividir Página Dupla (Tesoura)',
    summary: 'Corta uma página dupla ao meio verticalmente, gerando duas páginas individuais na ordem correta de leitura.'
  },
  {
    id: 'lightbox-save-order-btn',
    selector: '.lightbox-unified-toolbar .toolbar-btn.primary-save',
    priority: 98,
    category: 'Lightbox • Persistência de Arquivos',
    title: 'Botão Salvar Nova Ordem no Disco',
    summary: 'Renomeia fisicamente os arquivos na pasta do Windows para gravar a nova ordem que você montou arrastando cards.',
    details: [
      'Aparece automaticamente após você reordenar páginas.',
      'Garante que o Estúdio e o roteiro final sigam exatamente a sequência física consolidada.'
    ]
  },
  {
    id: 'lightbox-card',
    selector: '.lightbox-card',
    priority: 82,
    category: 'Lightbox • Mesa de Montagem',
    title: 'Página do Mangá na Mesa de Luz',
    summary: 'Página visual do capítulo para inspeção de sequência, reordenação de páginas e costura de cenas duplas (spreads).',
    details: [
      'Clique: Seleciona ou desmarca a página (selecione exatamente 2 para unir em cena dupla).',
      'Arrastar e Soltar: Move a página para reposicioná-la na ordem cronológica de leitura.',
      'Duplo Clique: Abre esta página diretamente no Estúdio para edição gráfica de balões.'
    ],
    tip: 'Se a ordem física das páginas for alterada, clique no botão "Salvar Ordem" no topo para renomear os arquivos no Windows.'
  },

  // =========================================================================
  // 09. BIBLIOTECA (ROTEIRO & DIAGRAMAÇÃO)
  // =========================================================================
  {
    id: 'library-progress-pill',
    selector: '.chapter-progress-pill',
    priority: 95,
    category: 'Biblioteca • Diagramação',
    title: 'Medidor de Balões Copiados (Progresso do Letrista)',
    summary: 'Informa quantos balões deste capítulo já foram copiados para o Photoshop/Clip Studio (ex: 24/60 • 40%).',
    details: [
      'A cada fala copiada, a barra avança e o balão fica verde.',
      'O botão circular ao lado zera a contagem caso queira revisar o capítulo de novo.'
    ]
  },
  {
    id: 'library-typography-btn',
    selector: '.content-header .dropdown-wrapper:nth-of-type(1) .btn-lib-cta',
    priority: 96,
    category: 'Biblioteca • Tipografia Editorial',
    title: 'Regras de Formatação Tipográfica ao Copiar',
    summary: 'Menu de regras automatizadas aplicadas no instante em que você copia qualquer fala.',
    details: [
      'Travessão (—): Substitui hífens simples por travessão de diálogo editorial padrão.',
      'Reticências (…): Converte 3 pontos soltos em caractere único tipográfico.',
      'FORÇAR CAIXA ALTA: Converte automaticamente todo o texto para letras MAIÚSCULAS (padrão de lettering em quadrinhos).'
    ]
  },
  {
    id: 'library-export-btn',
    selector: '.content-header .dropdown-wrapper:nth-of-type(2) .btn-lib-cta',
    priority: 96,
    category: 'Biblioteca • Exportação Externa',
    title: 'Exportar Roteiro (.TXT Limpo ou Word .RTF)',
    summary: 'Gera uma versão externa formatada do roteiro para envio a letristas, revisores ou clientes.',
    details: [
      'Roteiro Limpo (.txt): Texto estruturado sem códigos binários.',
      'Formato Word (.rtf): Abre no Microsoft Word e Google Docs com formatação rica de páginas e cabeçalhos.'
    ]
  },
  {
    id: 'library-mode-split',
    selector: '.view-mode-selector .view-mode-btn:nth-child(2)',
    priority: 96,
    category: 'Biblioteca • Modos de Trabalho',
    title: 'Modo Lado a Lado (Split View Interativo)',
    summary: 'Divide a tela mostrando a página do mangá à esquerda e as falas traduzidas à direita.',
    details: [
      'Clicar em qualquer balão desenhado na imagem copia a tradução e marca o card correspondente na hora.',
      'Ideal para diagramar com duas janelas lado a lado na tela.'
    ]
  },
  {
    id: 'balloon-row-btn-copy',
    selector: '.btn-quick-copy, .copied-badge-main',
    priority: 99,
    category: 'Biblioteca • Cópia Rápida',
    title: 'Copiar Fala para o Editor (1 Clique)',
    summary: 'Copia o texto traduzido formatado para a área de transferência do Windows e marca o balão como "✓ Colado".',
    details: [
      'Basta dar Ctrl+V na ferramenta de texto do Photoshop ou Clip Studio Paint.'
    ]
  },

  // =========================================================================
  // 10. MÓDULOS (IA & HARDWARE)
  // =========================================================================
  {
    id: 'modules-vram-btn',
    selector: '.btn-utility-action.vram',
    priority: 98,
    category: 'Módulos • Memória de Vídeo',
    title: 'Botão Liberar VRAM (Purga de GPU)',
    summary: 'Descarrega os pesos dos modelos neurais da memória da placa de vídeo e limpa caches do PyTorch instantaneamente.',
    details: [
      'Use antes de abrir aplicativos pesados de edição gráfica ou se notar lentidão no sistema.'
    ]
  },
  {
    id: 'modules-active-model-selector',
    selector: '.active-model-pill-trigger',
    priority: 97,
    category: 'Módulos • Tradução',
    title: 'Seletor de Modelo de Tradução Ativo',
    summary: 'Exibe qual modelo LLM local está configurado como tradutor padrão do Estúdio. Clique para alternar entre os modelos instalados no seu disco.'
  },
  {
    id: 'model-card-compat-tag',
    selector: '.meta-compat-tag',
    priority: 99,
    category: 'Módulos • Diagnóstico de Hardware',
    title: 'Compatibilidade com seu PC (100% GPU / Híbrido / CPU)',
    summary: 'Analisa se os pesos deste modelo cabem inteiramente na sua placa de vídeo.',
    details: [
      '100% GPU: Velocidade máxima com todos os tensores na VRAM.',
      'Híbrido (GPU+RAM): Divide camadas entre placa de vídeo e memória RAM.',
      'Modo CPU: Execução no processador principal.'
    ]
  },
  {
    id: 'modules-native-model-card',
    selector: '.native-model-card',
    priority: 95,
    category: 'Módulos • Modelos de Tradução LLM',
    title: 'Modelo de Tradução Local (LLM)',
    summary: 'Modelo neural executado localmente via Ollama para tradução adaptativa de mangás do inglês para o português brasileiro.',
    details: [
      'Execução 100% Offline: Todas as falas são traduzidas diretamente no hardware do seu computador, sem envio de dados para servidores externos e sem cobrança por token.',
      'Adaptação Cultural & Gírias: Modelos especializados compreendem subtexto dramático, gírias jovens, onomatopeias e ritmo de fala oral natural sem calques literais.',
      'Como Ativar no Estúdio: Se o modelo já estiver baixado ("No HD"), clique no botão "Usar" para defini-lo como o tradutor ativo do capítulo.',
      'Selo de Compatibilidade: Analisa a quantidade de VRAM da sua placa de vídeo para informar se o modelo roda 100% em GPU ou em modo Híbrido (GPU+RAM).'
    ],
    tip: 'Modelos de 14B entregam a melhor interpretação dramática e riqueza de vocabulário; modelos de 7B a 8B são ideais para GPUs de 6 a 8 GB.'
  },
  {
    id: 'modules-btn-download-model',
    selector: '.btn-model-action.download',
    priority: 99,
    category: 'Módulos • Ações do Modelo',
    title: 'Botão Baixar Modelo (Download Ollama)',
    summary: 'Inicia o download direto e seguro dos pesos deste modelo para a pasta local do Ollama.',
    details: [
      'Execução em Segundo Plano: O download não interrompe a edição no Estúdio nem a revisão na Biblioteca.',
      'Telemetria em Tempo Real: Exibe taxa de download (MB/s), total transferido e tempo restante estimado (ETA).'
    ]
  },
  {
    id: 'modules-btn-use-model',
    selector: '.btn-model-action.use',
    priority: 99,
    category: 'Módulos • Ações do Modelo',
    title: 'Botão Usar como Tradutor Ativo',
    summary: 'Configura este modelo como o tradutor padrão de todo o Visionary Studio.',
    details: [
      'Todas as próximas execuções de tradução (em lote ou balão a balão) passarão a usar este modelo.',
      'O modelo ativo pode ser conferido e alternado a qualquer momento pelo seletor do topo.'
    ]
  },
  {
    id: 'modules-model-in-use-badge',
    selector: '.in-use-indicator',
    priority: 99,
    category: 'Módulos • Status do Modelo',
    title: 'Crachá: Modelo Ativo do Estúdio (Em Uso)',
    summary: 'Indica que este modelo está carregado no pipeline como tradutor principal ativo.'
  },
  {
    id: 'modules-btn-delete-model',
    selector: '.btn-icon-trash-subtle',
    priority: 99,
    category: 'Módulos • Gerenciamento de Armazenamento',
    title: 'Botão Remover Modelo do Disco (Lixeira)',
    summary: 'Exclui os arquivos de pesos deste modelo do armazenamento do seu computador para liberar espaço em disco.'
  },
  {
    id: 'modules-model-meta-chips',
    selector: '.meta-size-chip, .meta-vram-chip',
    priority: 98,
    category: 'Módulos • Metadados de Hardware',
    title: 'Metadados de Tamanho em Disco e VRAM',
    summary: 'Exibe o tamanho dos tensores (ex: 8.9 GB) e a quantidade mínima de memória de vídeo recomendada para execução sem travamentos.'
  },
  {
    id: 'modules-model-status-badge',
    selector: '.badge-available-tag, .badge-installed-tag, .badge-downloading-tag',
    priority: 98,
    category: 'Módulos • Status do Modelo',
    title: 'Crachá de Disponibilidade no Disco',
    summary: 'Informa se o modelo está "Disponível" para download, "No HD" instalado e pronto para uso, ou "Instalando" no momento.'
  },
  {
    id: 'modules-native-models-grid',
    selector: '.native-models-grid',
    priority: 85,
    category: 'Módulos • Catálogo Neural',
    title: 'Grade de Modelos de Linguagem para Tradução',
    summary: 'Galeria com os modelos LLM recomendados e otimizados para localização de mangás em português brasileiro.'
  },

  // =========================================================================
  // 11. CONFIGURAÇÕES
  // =========================================================================
  {
    id: 'settings-base-folder-bar',
    selector: '.workflow-path-bar',
    priority: 96,
    category: 'Configurações • Workflow',
    title: 'Diretório Raiz Padrão do Explorador',
    summary: 'Define a pasta do seu computador onde suas séries de mangá ficam armazenadas.',
    details: [
      'Ao definir este caminho, o Visionary abrirá diretamente na sua coleção de capítulos toda vez que for iniciado.'
    ]
  },
  {
    id: 'settings-theme-card',
    selector: '.theme-specimen-btn',
    priority: 96,
    category: 'Configurações • Aparência',
    title: 'Seletor de Tema do Estúdio',
    summary: 'Altera paleta de cores, contraste de painéis e estilo do Canvas (Pro Studio, Paperwhite, Cyber CAD, E-Ink, Neo-Tokyo ou Estúdio Neutro).'
  },

  // =========================================================================
  // 12. BARRA FLUTUANTE DE SÍMBOLOS RÁPIDOS
  // =========================================================================
  {
    id: 'quick-symbol-bar-container',
    selector: '.quick-symbol-bar',
    priority: 95,
    category: 'Estúdio • Edição Rápida',
    title: 'Barra Flutuante de Caracteres & Símbolos',
    summary: 'Bandeja retrátil ancorada na parte inferior da tela para inserção ágil de caracteres gráficos e pontuações especiais em balões selecionados.',
    details: [
      'Inserção Direta: Clicar em qualquer caractere da barra insere-o na posição do cursor no campo de texto ativo sem precisar digitar atalhos de teclado.',
      'Cópia Automática: Além de inserir no campo, o símbolo é copiado para a área de transferência do Windows para uso imediato em softwares externos.',
      'Recolhível: Clique na aba superior "Símbolos" para minimizar e deixar a visão do canvas desobstruída.'
    ],
    tip: 'Útil para inserir rapidamente reticências, símbolos sonoros (♪) ou pontuações duplas (!?) durante a transcrição.'
  },
  {
    id: 'quick-symbol-toggle-btn',
    selector: '.quick-symbol-toggle-btn, button[title="Teclado Virtual de Símbolos"]',
    priority: 98,
    category: 'Estúdio • Edição Rápida',
    title: 'Alternador da Barra de Símbolos',
    summary: 'Expande ou recolhe a gaveta inferior de caracteres especiais.',
    details: [
      'Mantenha recolhida durante a navegação visual para maximizar o campo de visão da página.',
      'Abra quando estiver revisando falas e precisando de pontuações frequentes.'
    ]
  },
  {
    id: 'quick-symbol-key',
    selector: '.quick-symbol-key',
    priority: 99,
    category: 'Estúdio • Edição Rápida',
    title: 'Tecla de Inserção Rápida de Caractere',
    summary: 'Insere instantaneamente este caractere no campo de texto em foco (OCR ou Tradução) e copia para o clipboard.',
    tip: 'Funciona tanto em caixas de texto do Modo Texto quanto nos campos de edição da barra lateral.'
  },

  // =========================================================================
  // 13. MÓDULOS • MOTORES DE PIPELINE (IA & DETECÇÃO)
  // =========================================================================
  {
    id: 'modules-engine-pytorch',
    selector: '.pipeline-engine-card:nth-child(1)',
    priority: 97,
    category: 'Módulos • Motor Neural',
    title: 'Motor PyTorch Core (Aceleração CUDA & FP16)',
    summary: 'Núcleo de computação tensorial responsável pela inferência acelerada por placa de vídeo NVIDIA (tensores de meia precisão FP16).',
    details: [
      'Modo CUDA: Quando sua GPU é compatível, o PyTorch processa balões e tensores de visão com velocidade máxima de hardware.',
      'Modo CPU Fallback: Em computadores sem GPU dedicada compatível, opera automaticamente pelo processador com tensores FP32.',
      'Isolamento Completo: Executa em um ambiente Python embutido no Visionary sem alterar o Python instalado no seu Windows.'
    ],
    tip: 'Verifique se o selo indica "CUDA · FP16" para garantir o melhor desempenho de processamento em lote.'
  },
  {
    id: 'modules-engine-yolo',
    selector: '.pipeline-engine-card:nth-child(2)',
    priority: 97,
    category: 'Módulos • Motor de Visão',
    title: 'Comic-YOLO (Detector de Balões de Mangá)',
    summary: 'Rede neural convolucional ultraleve (~59 MB) treinada especificamente para localizar balões de fala, elipses, caixas narrativas e balões de grito.',
    details: [
      'Detecção de Polígonos: Traça o contorno dos balões adaptando-se a formatos orgânicos e arredondados sem invadir a arte do mangá.',
      'Filtro de Ruído: Ignora fundos desenhados e foca unicamente em recipientes de texto latino/japonês.',
      'Velocidade Extrema: Processa uma página completa em menos de 100 milissegundos em placas modernas.'
    ]
  },
  {
    id: 'modules-engine-florence',
    selector: '.pipeline-engine-card:nth-child(3)',
    priority: 97,
    category: 'Módulos • Motor de Visão e OCR',
    title: 'Florence-2 (Reconhecimento Óptico de Caracteres & Classificador SFX)',
    summary: 'Modelo de visão multimodal avançado da Microsoft especializado em transcrição de texto denso em imagens e classificação de onomatopeias.',
    details: [
      'Versão Large (0.77B · ~1.56 GB): Maior precisão para fontes estilizadas, pontuações finas (... e ?!) e balões com fundo desenhado.',
      'Versão Base (0.23B · ~465 MB): Opção mais leve para computadores com menor quantidade de VRAM disponível.',
      'Classificador SFX Integrado: Identifica grafias onomatopeicas artísticas para filtragem automática durante a fase de Layout.'
    ],
    tip: 'Se tiver 6 GB ou mais de VRAM, utilize sempre a versão Large para máxima fidelidade na leitura dos caracteres em inglês.'
  },
  {
    id: 'modules-engine-install-action',
    selector: '.btn-engine-action, .btn-icon-trash',
    priority: 99,
    category: 'Módulos • Gerenciamento de Motores',
    title: 'Instalar / Desinstalar Motor Neural',
    summary: 'Gerencia o download ou exclusão dos pesos do modelo selecionado no disco rígido do computador.',
    details: [
      'Instalar: Faz o download seguro do repositório oficial com verificação de integridade SHA-256 e barra de progresso.',
      'Desinstalar (Lixeira): Remove os arquivos de pesos da pasta local liberando espaço em disco sem afetar outros modelos.'
    ]
  },
  {
    id: 'modules-ollama-service-box',
    selector: '.pipeline-utility-box',
    priority: 96,
    category: 'Módulos • Infraestrutura LLM',
    title: 'Serviço Ollama Local (Backend de Tradução)',
    summary: 'Gerenciador do servidor local isolado (porta 127.0.0.1:11435) que executa os modelos de linguagem (LLMs) para tradução de inglês para português.',
    details: [
      'Execução 100% Offline: Nenhum texto ou diálogo é transmitido para servidores da nuvem; todo o processamento ocorre no seu computador.',
      'Status em Tempo Real: Indica se o serviço está Online (porta ativa), Iniciando ou Offline.',
      'Isolamento de Porta: Utiliza porta dedicada para evitar conflitos com outras instâncias de IA que você possua no Windows.'
    ]
  },
  {
    id: 'modules-service-verify-btn',
    selector: '.btn-utility-action[title*="Reverificar"]',
    priority: 98,
    category: 'Módulos • Diagnóstico',
    title: 'Botão Reverificar Conexão dos Motores',
    summary: 'Executa um teste imediato de ping e integridade em todos os subsistemas de IA para atualizar crachás de status.',
    details: [
      'Verifica comunicação com a API do Ollama e drivers de aceleração CUDA da GPU.',
      'Útil após instalar um novo modelo pelo terminal externo ou se o serviço tiver sido reiniciado.'
    ]
  },
  {
    id: 'modules-factory-reset-btn',
    selector: '.btn-utility-action.destructive',
    priority: 98,
    category: 'Módulos • Manutenção Crítica',
    title: 'Botão Reset de Fábrica (Limpeza Profunda)',
    summary: 'Ação de manutenção profunda que descarrega modelos corrompidos e redefine configurações para o padrão original.',
    details: [
      'Exige confirmação para prevenir acidentes.',
      'Não apaga suas pastas de mangás RAW nem seus arquivos de tradução gerados.'
    ]
  },
  {
    id: 'modules-cuda-warning-banner',
    selector: '.pipeline-engine-warning-banner',
    priority: 98,
    category: 'Módulos • Diagnóstico de GPU',
    title: 'Alerta de Compatibilidade de Driver / CUDA',
    summary: 'Aviso do assistente de hardware informando divergência entre o driver da placa NVIDIA e a versão do PyTorch.',
    details: [
      'Informa se o driver de vídeo do Windows precisa ser atualizado para liberar aceleração neural FP16.',
      'Sugere a ação recomendada para obter ganho de velocidade no pipeline.'
    ]
  },

  // =========================================================================
  // 14. BIBLIOTECA • FERRAMENTAS DO MODO LADO A LADO (SPLIT VIEW)
  // =========================================================================
  {
    id: 'library-split-zoom-out',
    selector: '.btn-split-tool[title*="Reduzir Zoom"]',
    priority: 99,
    category: 'Biblioteca • Split View',
    title: 'Reduzir Zoom da Imagem (-)',
    summary: 'Diminui a escala da página no painel de visualização lado a lado.',
    tip: 'Você também pode usar a roda do mouse (Scroll) diretamente sobre a imagem no painel da esquerda.'
  },
  {
    id: 'library-split-zoom-reset',
    selector: '.btn-split-tool.zoom-val',
    priority: 99,
    category: 'Biblioteca • Split View',
    title: 'Redefinir Zoom para 100%',
    summary: 'Restaura a imagem para a escala natural de pixels (1:1).',
    details: [
      'Exibe a porcentagem atual de ampliação.',
      'Clique para voltar instantaneamente à proporção nativa da imagem.'
    ]
  },
  {
    id: 'library-split-zoom-in',
    selector: '.btn-split-tool[title*="Aumentar Zoom"]',
    priority: 99,
    category: 'Biblioteca • Split View',
    title: 'Aumentar Zoom da Imagem (+)',
    summary: 'Aumenta a aproximação da imagem até o limite de 800% para conferência de lettering detalhado.'
  },
  {
    id: 'library-split-fit-screen',
    selector: '.btn-split-tool.reset, .btn-split-tool[title*="Centralizar"]',
    priority: 99,
    category: 'Biblioteca • Split View',
    title: 'Ajustar Imagem à Tela Inteira',
    summary: 'Enquadra e centraliza a página do mangá inteira dentro do painel visual da esquerda sem cortes.',
    details: [
      'Calcula a proporção ideal entre altura e largura do painel.',
      'Ideal para ter a visão geral da composição da página antes de diagramar balão por balão.'
    ]
  },
  {
    id: 'library-split-auto-zoom',
    selector: '.btn-split-tool[title*="Auto-Zoom"]',
    priority: 99,
    category: 'Biblioteca • Split View',
    title: 'Alternador de Auto-Zoom no Balão Ativo (Z)',
    shortcut: 'Z',
    summary: 'Aproxima e centraliza a câmera na imagem automaticamente sempre que você seleciona ou foca uma fala na lista da direita.',
    details: [
      'Elimina a necessidade de rolar e dar zoom manualmente para conferir onde cada diálogo fica.',
      'Pressione a tecla Z a qualquer momento para ligar ou desligar este recurso.'
    ]
  },
  {
    id: 'library-split-show-markers',
    selector: '.btn-split-tool[title*="Mostrar marcações"]',
    priority: 99,
    category: 'Biblioteca • Split View',
    title: 'Alternador de Marcadores Numerados (#)',
    summary: 'Exibe ou oculta os círculos numerados com a ordem de leitura sobrepostos na imagem do mangá.',
    details: [
      'Ligado: Permite visualizar exatamente a qual balão da arte cada linha de texto traduzido pertence.',
      'Desligado: Deixa a visualização da arte 100% limpa para conferir a estética original.'
    ]
  },
  {
    id: 'library-split-hide-english',
    selector: '.btn-split-tool[title*="Mostrar linha com o texto em inglês"]',
    priority: 99,
    category: 'Biblioteca • Split View',
    title: 'Alternador de Texto Bilíngue (EN:)',
    summary: 'Controla a exibição da linha de texto original em inglês abaixo de cada tradução em português na coluna de roteiro.',
    details: [
      'Ligado (EN ativo): Permite comparar o original em inglês com a tradução em português para checagem rápida de contexto.',
      'Desligado: Oculta a linha de inglês, deixando a lista mais compacta para focar exclusivamente na diagramação em português.'
    ]
  },
  {
    id: 'library-script-page-header',
    selector: '.script-page-header',
    priority: 95,
    category: 'Biblioteca • Roteiro',
    title: 'Cabeçalho de Página do Roteiro',
    summary: 'Barra divisória de cada página do capítulo contendo número da página, nome do arquivo e ações em lote daquela página.',
    details: [
      'Clique no cabeçalho: Recolhe ou expande todos os balões da página para facilitar a rolagem de capítulos longos.',
      'Ações Rápidas: Permite abrir a página no modo Lado a Lado, abrir no Estúdio ou copiar todas as falas de uma só vez.'
    ]
  },
  {
    id: 'library-btn-open-split',
    selector: '.btn-open-split-view',
    priority: 98,
    category: 'Biblioteca • Navegação',
    title: 'Botão Abrir em Modo Lado a Lado',
    summary: 'Carrega esta página específica na visualização dividida (imagem à esquerda e diálogos à direita) para cópia ágil.'
  },
  {
    id: 'library-btn-open-studio',
    selector: '.btn-open-studio',
    priority: 98,
    category: 'Biblioteca • Navegação',
    title: 'Botão Abrir Página no Estúdio',
    summary: 'Muda diretamente para a aba Estúdio com esta página carregada no Canvas para correção de polígonos ou reordenação de balões.'
  },
  {
    id: 'library-btn-copy-full-page',
    selector: '.btn-copy-page',
    priority: 98,
    category: 'Biblioteca • Diagramação Rápida',
    title: 'Botão Copiar Todos os Balões da Página',
    summary: 'Copia o conjunto completo de falas traduzidas desta página formatadas com quebras de linha para a área de transferência.',
    details: [
      'Aplica as regras tipográficas ativas (travessão, reticências, caixa alta).',
      'Marca instantaneamente todos os balões desta página como copiados.'
    ]
  },
  {
    id: 'library-empty-page-notice',
    selector: '.empty-page-notice',
    priority: 97,
    category: 'Biblioteca • Roteiro',
    title: 'Aviso: Página sem Balões Detectados',
    summary: 'Indica que esta página não possui diálogos registrados no arquivo de metadados do capítulo.',
    details: [
      'Pode se tratar de uma página dupla sem texto, página de créditos ou capa ilustrada.',
      'Se a página possuir diálogos que não foram detectados, clique no botão "Studio" para delimitá-los manualmente.'
    ]
  },

  // =========================================================================
  // 15. CONFIGURAÇÕES • ERGONOMIA, TIPOGRAFIA & ÁUDIO
  // =========================================================================
  {
    id: 'settings-scale-btn',
    selector: '.scale-btn',
    priority: 97,
    category: 'Configurações • Ergonomia',
    title: 'Seletor de Zoom da Interface (Escala)',
    summary: 'Ajusta a escala de DPI de todos os componentes da interface (90%, 100%, 110% ou 120%).',
    details: [
      '90%: Aumenta o espaço útil de tela em notebooks ou monitores menores.',
      '100%: Escala padrão de desenvolvimento.',
      '110% / 120%: Aumenta a legibilidade de textos e botões em monitores 2K e 4K.'
    ]
  },
  {
    id: 'settings-density-btn',
    selector: '.density-btn',
    priority: 97,
    category: 'Configurações • Ergonomia',
    title: 'Seletor de Densidade de Menus (Confortável vs Compacta)',
    summary: 'Altera o espaçamento vertical entre linhas de listas, tabelas e cards.',
    details: [
      'Confortável: Espaçamento generoso para maior clareza visual.',
      'Compacta: Reduz o padding para exibir mais itens simultâneos na tela.'
    ]
  },
  {
    id: 'settings-font-specimen',
    selector: '.font-specimen-btn',
    priority: 97,
    category: 'Configurações • Tipografia',
    title: 'Seletor de Família Tipográfica da Interface',
    summary: 'Define a fonte renderizada nos menus, abas e controles (Inter Moderno, Windows Segoe ou JetBrains Mono).',
    details: [
      'Inter: Sans-serif geométrica moderna de altíssima legibilidade.',
      'Segoe UI: Tipografia padrão nativa do Windows.',
      'JetBrains Mono: Tipografia monospaçada técnica de alta precisão para diagnóstico.'
    ]
  },
  {
    id: 'settings-accent-swatch',
    selector: '.accent-swatches .swatch',
    priority: 97,
    category: 'Configurações • Aparência',
    title: 'Paleta de Cores de Destaque (Tokens de Foco)',
    summary: 'Define a cor de acento de botões primários, crachás ativos, seletores e bordas de foco de todo o Visionary Studio.',
    tip: 'Escolha cores que ofereçam bom contraste com o tema de estúdio selecionado.'
  },
  {
    id: 'settings-audio-test-btn',
    selector: '.audio-btn-test',
    priority: 98,
    category: 'Configurações • Acústica',
    title: 'Botão Testar Timbre Acústico',
    summary: 'Dispara um sinal sonoro de teste para aferição de volume e timbre sonoro nos alto-falantes.'
  },
  {
    id: 'settings-audio-style-btn',
    selector: '.audio-style-btn',
    priority: 98,
    category: 'Configurações • Acústica',
    title: 'Seletor de Timbre Acústico (Harmônico / Pop / Tech)',
    summary: 'Define o estilo da onda sonora de feedback ao concluir processamento de lotes.',
    details: [
      'Harmônico: Acorde tríade suave em frequências puras (C5–E5–G5).',
      'Pop Sutil: Microestalinho duplo suave para feedback tátil.',
      'Tech Bip: Pulsos eletrônicos sintéticos modernos.'
    ]
  },

  // =========================================================================
  // 16. FILA DE PROCESSAMENTO & TERMINAL TÉCNICO DE LOGS
  // =========================================================================
  {
    id: 'queue-header-actions',
    selector: '.queue-header-actions, .queue-btn-icon[title*="Limpar"]',
    priority: 98,
    category: 'Fila de Tarefas • Gerenciamento',
    title: 'Botão Limpar Tarefas Concluídas da Fila',
    summary: 'Remove tarefas já finalizadas ou canceladas da listagem lateral liberando visualização para os trabalhos ativos.'
  },
  {
    id: 'queue-btn-terminal',
    selector: '.queue-btn-icon[title*="Telemetria"], .queue-btn-icon[title*="Terminal"]',
    priority: 99,
    category: 'Fila de Tarefas • Telemetria',
    title: 'Botão Abrir Console de Telemetria (>_)',
    summary: 'Abre a gaveta flutuante do terminal com o fluxo contínuo de logs em tempo real do Python e dos motores neurais.',
    details: [
      'Permite acompanhar diagnósticos linha a linha de cada requisição.',
      'Exibe tempos de resposta, tensores alocados e status de cada página.'
    ]
  },
  {
    id: 'queue-btn-cancel-job',
    selector: '.queue-btn-icon.danger, .queue-btn-icon[title*="Interromper"]',
    priority: 99,
    category: 'Fila de Tarefas • Controle de Execução',
    title: 'Botão Interromper Tarefa em Andamento',
    summary: 'Cancela imediatamente o trabalho em processamento sem afetar as páginas que já foram salvas anteriormente.'
  },
  {
    id: 'queue-terminal-modal',
    selector: '.log-drawer',
    priority: 94,
    category: 'Fila de Tarefas • Console de Telemetria',
    title: 'Console de Telemetria em Tempo Real (Terminal HUD)',
    summary: 'Janela de diagnóstico técnico conectada via WebSocket que transmite toda a saída de depuração dos scripts Python do Visionary.',
    details: [
      'Filtragem por Severidade: Alterne entre abas Todos, Erros, Avisos e Concluídos para isolar falhas.',
      'Busca Integrada: Digite palavras-chave para localizar páginas, tensores ou exceções específicas.',
      'Copiar Logs: Exporta o log formatado para o clipboard para envio em relatórios de suporte.'
    ],
    tip: 'Pressione Esc ou clique fora do console para fechar o terminal flutuante.'
  },

  // =========================================================================
  // 17. ESTADO INICIAL DO ESTÚDIO (EMPTY STATE SEM CAPÍTULO)
  // =========================================================================
  {
    id: 'studio-empty-onboarding',
    selector: '.empty-state.onboarding-card',
    priority: 93,
    category: 'Estúdio • Iniciação',
    title: 'Estação de Trabalho do Estúdio (Aguardando Capítulo)',
    summary: 'Área principal de edição e OCR aguardando a seleção de uma pasta de mangá para carregar o Canvas.',
    details: [
      'Como Carregar um Capítulo: No Explorador Lateral (à esquerda), navegue até suas pastas de mangá e clique em qualquer pasta contendo imagens (.jpg, .png, .webp).',
      'Fluxo Imediato: A primeira página do capítulo será carregada em alta resolução no Canvas central, liberando os modos de Layout (1), OCR (2) e Tradução (3).',
      'Diretório Padrão: Você pode fixar sua pasta principal de mangás em Configurações -> Workflow para que o Explorador abra nela automaticamente.'
    ],
    tip: 'O Visionary não move nem altera suas imagens originais; todas as coordenadas e falas ficam salvas no arquivo _map.json.'
  },
  {
    id: 'studio-onboarding-step',
    selector: '.onboarding-step-card',
    priority: 96,
    category: 'Estúdio • Iniciação',
    title: 'Etapa do Fluxo de Trabalho (Guia Rápido)',
    summary: 'Roteiro sequencial de produção: (1) Escolha o capítulo -> (2) Ajuste polígonos no Estúdio -> (3) Traduza e diagrame na Biblioteca.',
    details: [
      'Passo 1 (Pasta RAW): Selecione a pasta com as páginas no Explorador Lateral.',
      'Passo 2 (Layout & OCR): Confira se os polígonos englobam todo o texto em inglês e ordene as falas da direita para a esquerda.',
      'Passo 3 (Tradução & Roteiro): Dispare o lote com o modelo LLM e use a Biblioteca para colar as falas no Photoshop com 1 clique.'
    ]
  }
];

export {
  resolveKonvaCanvasBubble,
  computeKonvaBubbleRect,
  resolveHelpStackForElement,
  resolveHelpItemForElement,
} from '../utils/helpInspectorResolver';

