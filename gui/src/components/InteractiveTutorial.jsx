import React, { useState, useMemo } from 'react';
import {
  BookOpen, Search, X, Folder,
  Maximize, Crosshair, RotateCcw, Trash2,
  MousePointer, Square, PenTool, Link2, Zap, ArrowUpDown, Sliders,
  Play, Terminal, Download, Columns, Scissors, Cpu,
  Wrench, Check, ChevronLeft, ChevronRight, RefreshCw
} from 'lucide-react';
import './InteractiveTutorial.css';

// ============================================================================
// ESPECIFICAÇÃO TÉCNICA E ANATOMIA COMPLETA DO VISIONARY STUDIO
// ============================================================================
const DOCUMENTATION_CHAPTERS = [
  {
    id: 'sec-01',
    index: '01',
    title: 'Arquitetura de Fluxo, Calibração Inicial e Barra Superior',
    eyebrow: '01 // ARQUITETURA & ESCOPO OPERACIONAL',
    description:
      'O Visionary Studio opera exclusivamente na extração óptica (OCR), tradução contextual assistida por IA local (Inglês EN para Português PT-BR) e geração de roteiros estruturados (.txt e _map.json). Os arquivos gráficos originais são preservados sem alterações de pixels ou inpainting.',
    blueprintTitle: 'PRANCHA 01 — ANATOMIA DA BARRA DE TÍTULO E DO CALIBRADOR DE HARDWARE',
    specs: [
      {
        pin: '01',
        name: 'Perfil Studio Elite (32B)',
        shortcut: '22,9 GB • Wizard Inicial',
        desc: 'Configuração de instalação recomendada para estações com 16 GB+ de VRAM ou 32 GB de RAM. Instala os motores visuais (Comic-YOLO e Florence-2 Large) combinados ao modelo de tradução de 32 bilhões de parâmetros.',
        usage: 'Priorize quando o foco for máxima precisão semântica e adaptação literária.'
      },
      {
        pin: '02',
        name: 'Perfil Ágil (7B)',
        shortcut: '5,8 GB • Wizard Inicial',
        desc: 'Configuração otimizada para placas de vídeo de 6 GB a 8 GB de VRAM. Instala os motores visuais e o modelo de 7 bilhões de parâmetros, executando 100% em memória de vídeo com alta taxa de tokens por segundo.',
        usage: 'Recomendado para máxima velocidade de tradução em lote sem sobrecarga de hardware.'
      },
      {
        pin: '03',
        name: 'Execução em Segundo Plano & Pílula de Progresso',
        shortcut: 'Barra de Título Superior',
        desc: 'Ao fechar o assistente inicial com a opção de segundo plano ativa, uma pílula indicadora ("Baixando IA X%") permanece visível na barra de título superior. Clicar sobre ela restaura a janela detalhada de transferência.',
        usage: 'Permite organizar pastas e preparar imagens na Lightbox enquanto os modelos são baixados.'
      },
      {
        pin: '04',
        name: 'Identificador de Capítulo & Trilha de Diretório',
        shortcut: 'Topo Central / Direito',
        desc: 'Exibe o nome da pasta de capítulo atualmente ativa no centro da barra de título e os dois últimos níveis do caminho de diretório no canto direito da barra de abas.',
        usage: 'Referência visual constante para evitar processamento acidental no diretório incorreto.'
      },
      {
        pin: '05',
        name: 'Indicador de Edição (PRO / DEV)',
        shortcut: 'Canto Superior Esquerdo',
        desc: 'Identifica o modo de operação atual da suíte. Alterna de PRO para DEV quando o painel de diagnóstico técnico está habilitado na sessão.',
        usage: 'Cinco cliques consecutivos sobre o logotipo ou Ctrl+Shift+D acionam a autenticação de diagnóstico.'
      }
    ]
  },
  {
    id: 'sec-02',
    index: '02',
    title: 'Barra Lateral Esquerda: Explorador de Diretórios e Capítulos',
    eyebrow: '02 // NAVEGAÇÃO DE ARQUIVOS E ROTEIROS',
    description:
      'A coluna lateral esquerda opera em dois estados contextuais: atua como Explorador de Diretórios do sistema nas abas operacionais (Estúdio, Lightbox, Módulos, Configurações) e alterna automaticamente para a listagem de roteiros consolidados (.txt) quando a aba Biblioteca é selecionada.',
    blueprintTitle: 'PRANCHA 02 — ANATOMIA ESPACIAL DA BARRA LATERAL (EXPLORADOR VS. BIBLIOTECA)',
    specs: [
      {
        pin: '01',
        name: 'Subir Nível / Unidades de Disco',
        shortcut: 'Botão ↑',
        desc: 'Retorna ao diretório pai imediato. Quando acionado na raiz de uma partição, lista todas as unidades de armazenamento disponíveis no sistema (C:, D:, etc.).',
        usage: 'Navegação livre entre discos quando não há um Diretório Raiz fixado nas configurações.'
      },
      {
        pin: '02',
        name: 'Atualizar Diretório & Redimensionamento',
        shortcut: 'Botão ↻ / Divisória',
        desc: 'O botão de atualização reescaneia o diretório em tempo real e recalcula o status dos capítulos. O botão "−" recolhe a barra lateral, e a borda direita pode ser arrastada para ajustar a largura.',
        usage: 'Acione após adicionar, renomear ou mover pastas de capítulos externamente pelo Windows.'
      },
      {
        pin: '03',
        name: 'Filtro Rápido de Listagem',
        shortcut: 'Campo de Busca',
        desc: 'Filtra instantaneamente os diretórios ou arquivos .txt exibidos na barra lateral conforme o termo digitado.',
        usage: 'Localização imediata em diretórios com dezenas de volumes ou capítulos.'
      },
      {
        pin: '04',
        name: 'Classificação de Diretório & Contador de Páginas',
        shortcut: 'Ícone + Etiqueta X págs',
        desc: 'Diretórios comuns exibem ícone de pasta. Diretórios que contêm arquivos de imagem são reconhecidos como capítulos, recebendo ícone de livro aberto e etiqueta com a contagem exata de páginas.',
        usage: 'Clicar em um diretório de capítulo carrega suas páginas diretamente no Estúdio ou na Lightbox.'
      },
      {
        pin: '05',
        name: 'Indicadores Cromáticos de Progresso',
        shortcut: 'Pontos Verde / Amarelo / Azul',
        desc: 'Ponto Verde indica capítulo com tradução concluída; Ponto Amarelo indica processamento parcial (layout ou OCR gerados, mas tradução incompleta); Ponto Azul indica diretório organizador comum.',
        usage: 'Auditoria visual imediata do estado de produção de uma coleção inteira.'
      },
      {
        pin: '06',
        name: 'Modo Biblioteca: Ação Direta ao Explorer',
        shortcut: 'Botão Biblioteca',
        desc: 'Visível no topo da barra lateral quando a aba Biblioteca está ativa. Abre o diretório onde os arquivos .txt consolidados estão armazenados diretamente no Windows Explorer.',
        usage: 'Acesso rápido aos arquivos de texto brutos para backup ou envio externo.'
      },
      {
        pin: '07',
        name: 'Modo Biblioteca: Etiquetas Pronto / Pendentes e Exclusão',
        shortcut: 'Cartão de Arquivo .txt',
        desc: 'Cada cartão exibe data de modificação, tamanho em KB, etiqueta "Pronto" (quando 100% dos balões possuem tradução) ou contador de pendências (indicando quantos balões aguardam tradução), além do botão de exclusão (lixeira).',
        usage: 'Permite identificar capítulos com falas não traduzidas antes de iniciar a diagramação.'
      }
    ]
  },
  {
    id: 'sec-03',
    index: '03',
    title: 'Estúdio — Barra Superior do Editor, Canvas e Modo Visualizar',
    eyebrow: '03 // INSPEÇÃO DE PÁGINA & CONTROLES DE CÂMERA',
    description:
      'O espaço central do Estúdio compreende a barra superior de controle da página ativa, o canvas interativo de alta precisão (com suporte a zoom de 10% a 1000%) e o painel lateral de diagnóstico do modo Visualizar.',
    blueprintTitle: 'PRANCHA 03 — ANATOMIA DA BARRA DO EDITOR, GEOMETRIA DO BALÃO E INSPETOR VISUALIZAR',
    specs: [
      {
        pin: '01',
        name: 'Seletor de Página & Indicador de Restauração',
        shortcut: 'A / D ou PgUp / PgDn',
        desc: 'Alterna entre as páginas do capítulo ativo e exibe o nome do arquivo atual. Um ícone azul ao lado do nome indica que a página possui histórico de Ponto de Restauração ativo.',
        usage: 'Navegação sequencial rápida durante a conferência visual das páginas.'
      },
      {
        pin: '02',
        name: 'Seletor de Modos de Operação',
        shortcut: 'Teclas 1, 2, 3',
        desc: 'Alterna a interface do editor entre os quatro estados: Visualizar (diagnóstico geral), Layout (tecla 1 — geometria e ordem), OCR (tecla 2 — texto original em inglês) e Tradução (tecla 3 — texto em português).',
        usage: 'Permite focar em uma etapa específica de revisão sem poluição visual.'
      },
      {
        pin: '03',
        name: 'Indicador de Persistência Automática',
        shortcut: 'Ctrl + S (Forçar)',
        desc: 'Exibe em tempo real o estado de gravação em disco: "Salvo" (verde), "Salvando..." (azul), "Não salvo..." (amarelo) ou botão de repetição "Erro ao salvar · Repetir" (vermelho).',
        usage: 'Garante que todas as edições de coordenadas e textos sejam gravadas sem ação manual.'
      },
      {
        pin: '04',
        name: 'Enquadramento de Página (Ajustar X%)',
        shortcut: 'Tecla F ou 0',
        desc: 'Redefine a escala de visualização e centraliza a página inteira dentro da área útil do canvas, exibindo a porcentagem de zoom resultante.',
        usage: 'Retorno rápido à visão macro da página após edições em zoom elevado.'
      },
      {
        pin: '05',
        name: 'Foco Automático no Balão (Auto-Zoom)',
        shortcut: 'Tecla Z',
        desc: 'Quando habilitado (indicador luminoso ativo), selecionar qualquer balão pela lista ou pelo teclado (W/S) move e aproxima automaticamente a câmera sobre aquele balão específico.',
        usage: 'Essencial para revisar textos de páginas densas sem precisar arrastar o canvas manualmente.'
      },
      {
        pin: '06',
        name: 'Código Cromático do Crachá Numerado',
        shortcut: 'Canto Sup. Esquerdo do Balão',
        desc: 'Verde = Balão em modo Contorno Orgânico; Azul = Balão em modo Caixa Retangular; Roxo = Marcado como efeito sonoro (SFX) ou selecionado no sequenciamento 1-a-1; Laranja = Em reordenação ou sinalizado para descarte.',
        usage: 'Identificação instantânea da natureza geométrica e semântica de cada detecção.'
      },
      {
        pin: '07',
        name: 'Ações Flutuantes no Balão: Excluir (X) e Restaurar (↺)',
        shortcut: 'Canto Sup. Direito do Balão',
        desc: 'O botão circular vermelho (X) remove o balão imediatamente (equivalente à tecla Delete). O botão circular azul (↺) surge exclusivamente quando o balão foi movido ou redimensionado, revertendo-o à posição original detectada pela IA.',
        usage: 'Correção ágil de falsos positivos ou reversão individual de ajustes geométricos.'
      },
      {
        pin: '08',
        name: 'Sistema de 8 Alças Elásticas de Borda',
        shortcut: '4 Vértices + 4 Bordas',
        desc: 'As 4 alças brancas nos cantos redimensionam diagonalmente. As 4 alças azuis no centro das bordas deslocam apenas aquela extremidade de forma elástica, mantendo o lado oposto e a rabeta do balão ancorados.',
        usage: 'Puxe a alça azul correspondente sempre que uma letra ou pontuação ficar fora da borda.'
      },
      {
        pin: '09',
        name: 'Inspetor "Visualizar": Próximo Passo, Etapas e Métricas',
        shortcut: 'Modo Visualizar',
        desc: 'Exibe recomendação dinâmica da próxima ação necessária na página, status individual de Layout/OCR/Tradução (Pronto ou Ausente), dimensões em pixels, contagem de diálogos, total de SFX e volume de caracteres.',
        usage: 'Visão executiva do estado de completude da página atual.'
      },
      {
        pin: '10',
        name: 'Ver Roteiro da Página (.txt) & Redefinir Página',
        shortcut: 'Modo Visualizar',
        desc: '"Ver Roteiro da Página" abre uma gaveta com o texto consolidado da folha e botão de cópia rápida. Na Zona de Risco, "Redefinir Página (Apagar Tudo)" limpa todas as detecções da folha atual mediante confirmação.',
        usage: 'Utilize Redefinir Página quando desejar descartar integralmente os dados de uma única folha.'
      }
    ]
  },
  {
    id: 'sec-04',
    index: '04',
    title: 'Estúdio — Modo Layout (1): Ferramentas Vetoriais, Ordem e Propriedades',
    eyebrow: '04 // DELIMITAÇÃO GEOMÉTRICA E SEQUENCIAMENTO ORIENTAL',
    description:
      'O modo Layout (atalho 1) concentra as ferramentas de precisão para garantir que 100% dos caracteres em inglês e pontuações ("?!", "...") estejam contidos dentro dos polígonos e que a sequência numérica siga a ordem de leitura oriental.',
    blueprintTitle: 'PRANCHA 04 — ANATOMIA DO DOCK DE LAYOUT, ORDEM DE LEITURA E PROPRIEDADES',
    specs: [
      {
        pin: '01',
        name: 'Ferramenta Seleção',
        shortcut: 'Tecla V',
        desc: 'Ferramenta padrão de inspeção. Permite selecionar balões no canvas, deslocar caixas inteiras, manipular alças elásticas ou arrastar a página (pan).',
        usage: 'Mantenha ativa para ajustes gerais de posicionamento e seleção.'
      },
      {
        pin: '02',
        name: 'Ferramenta Retângulo',
        shortcut: 'Tecla B',
        desc: 'Cria manualmente uma nova caixa delimitadora retangular ao clicar e arrastar sobre qualquer região da página não detectada automaticamente.',
        usage: 'Ideal para adicionar caixas narrativas quadradas ou balões simples omitidos.'
      },
      {
        pin: '03',
        name: 'Ferramenta Caneta de 4 Cliques',
        shortcut: 'Tecla P (Esc cancela)',
        desc: 'Desenha polígonos adaptados a balões inclinados ou irregulares: clique sequencialmente nos 4 extremos ao redor do texto; no 4º clique o polígono é fechado e registrado automaticamente.',
        usage: 'Utilize em falas inclinadas onde um retângulo comum capturaria elementos indesejados da arte.'
      },
      {
        pin: '04',
        name: 'Ferramenta Vincular Grupo (Balão Duplo)',
        shortcut: 'Tecla L',
        desc: 'Conecta dois ou mais balões que compõem uma única fala dividida (balões geminados). Clique no primeiro balão e em seguida no segundo para estabelecer uma ligação tracejada.',
        usage: 'Garante que o motor de tradução processe as duas partes com contexto unificado.'
      },
      {
        pin: '05',
        name: 'Ferramenta Alternar SFX',
        shortcut: 'Tecla S',
        desc: 'Alterna a classificação do polígono selecionado entre Diálogo de Fala (crachá verde/azul) e Efeito Sonoro / Onomatopeia (crachá roxo SFX).',
        usage: 'Separa onomatopeias dos diálogos principais na estruturação do roteiro .txt.'
      },
      {
        pin: '06',
        name: 'Seletor de Formato: Contorno Orgânico vs. Caixa',
        shortcut: 'Barra de Formato',
        desc: 'Alterna a representação geométrica entre Contorno Orgânico (polígono que acompanha a curvatura interna do balão via OpenCV) e Caixa Retangular padrão.',
        usage: 'Contorno Orgânico evita que a caixa invada desenhos próximos em layouts diagonais.'
      },
      {
        pin: '07',
        name: 'Sub-Aba Ordem de Leitura: Auto-Ordenar e Marcar 1-a-1',
        shortcut: 'Tecla R (Modo 1-a-1)',
        desc: '"Auto-Ordenar Mangá" recalcula toda a sequência no sentido japonês (Direita para Esquerda, Topo para Base). "Marcar 1-a-1" (tecla R) permite clicar nos balões do canvas na ordem exata desejada; ao concluir todos os balões da página, a nova ordem é salva e aplicada automaticamente.',
        usage: 'Use Marcar 1-a-1 em páginas com diagramação não convencional onde a ordem exigir ajuste fino.'
      },
      {
        pin: '08',
        name: 'Cartão de Balão: Mini-Mapa Vetorial e Arrasto',
        shortcut: 'Duplo Clique = Propriedades',
        desc: 'Cada item da lista exibe um Mini-Mapa proporcional da folha indicando a coordenada do balão (Topo Dir, Centro, Base Esq), dimensões em pixels e botões rápidos (SFX, Restaurar posição e Propriedades). Suporta reordenação por arrasto.',
        usage: 'Dê duplo clique sobre qualquer cartão da lista para abrir imediatamente a sub-aba Propriedades.'
      },
      {
        pin: '09',
        name: 'Sub-Aba Propriedades: Modos Bordas (8), Vértices e Todos Nós',
        shortcut: 'Edição de Polígono',
        desc: 'Controla a granularidade de edição do Contorno Orgânico: "Bordas (8)" opera pelas 8 alças elásticas; "Vértices" expõe de 6 a 10 nós mestres verdes na curva; "Todos Nós" expõe todos os vértices brutos do contorno.',
        usage: 'Utilize Bordas (8) para ajustes rápidos e Vértices para contornar obstáculos específicos.'
      },
      {
        pin: '10',
        name: 'Expansão e Contração Simétrica (+6px / -6px Margem)',
        shortcut: 'Sub-Aba Propriedades',
        desc: 'Expande ou contrai radialmente o polígono selecionado em 6 pixels em todas as direções a cada clique.',
        usage: 'Recurso principal para assegurar que pontuações periféricas ("?!", "...") não sejam cortadas no OCR.'
      }
    ]
  },
  {
    id: 'sec-05',
    index: '05',
    title: 'Estúdio — Modos OCR (2), Tradução (3) e Barra de Símbolos',
    eyebrow: '05 // AUDITORIA DE TEXTO EXTRAÍDO E ADAPTAÇÃO TRADUTÓRIA',
    description:
      'Nos modos OCR (atalho 2) e Tradução (atalho 3), o painel lateral direito apresenta os blocos textuais estruturados na ordem de leitura, permitindo edição direta, reordenação numérica instantânea, descarte de ruídos e comparação com a tradução original da IA.',
    blueprintTitle: 'PRANCHA 05 — ANATOMIA DO BLOCO DE TEXTO, TRIAGEM DE RUÍDO E BARRA DE SÍMBOLOS',
    specs: [
      {
        pin: '01',
        name: 'Cabeçalho BLOCO # com Índice Numérico Editável',
        shortcut: 'Digitação Direta / Arrasto',
        desc: 'Exibe a alça de arrasto e um campo numérico editável com a posição atual do bloco. Digitar um novo número no campo reposiciona o balão imediatamente na sequência da página.',
        usage: 'Método mais rápido para mover um balão distante na ordem sem precisar arrastar pela lista.'
      },
      {
        pin: '02',
        name: 'Triagem de Ruído: Sugerido para Descarte',
        shortcut: 'Ações: Manter / Descartar',
        desc: 'Quando a validação visual identifica um polígono contendo apenas ruído gráfico ou onomatopeia sem diálogo, o cartão recebe destaque âmbar com as opções "Manter" (confirma como fala válida) ou "Descartar" (exclui o bloco).',
        usage: 'Limpa falsos positivos antes que cheguem ao roteiro final da Biblioteca.'
      },
      {
        pin: '03',
        name: 'Quadro de Referência TEXTO ORIGINAL OCR',
        shortcut: 'Modo Tradução (3)',
        desc: 'Exibe permanentemente a transcrição em inglês extraída do balão logo acima do campo de tradução em português.',
        usage: 'Permite auditar fidelidade e nuances sem precisar alternar de volta para o modo OCR (2).'
      },
      {
        pin: '04',
        name: 'Memória IA ORIGINAL & Botão Restaurar IA',
        shortcut: 'Reversão com 1 Clique',
        desc: 'Ao editar manualmente qualquer tradução, o sistema preserva o texto original gerado pelo modelo no quadro superior ("IA ORIGINAL - EDITADO MANUALMENTE") e habilita o botão "Restaurar IA".',
        usage: 'Permite testar adaptações livres mantendo a tradução original da IA sempre recuperável.'
      },
      {
        pin: '05',
        name: 'Campo de Texto Editável & Restauração de Coordenada',
        shortcut: 'Corretor pt-BR Ativo',
        desc: 'Área de edição multilinha com verificação ortográfica em português. Caso o balão tenha sido deslocado no canvas, exibe também a faixa "Voltar ao local inicial".',
        usage: 'Todas as alterações digitadas são salvas automaticamente no mapeamento da página.'
      },
      {
        pin: '06',
        name: 'Barra Retrátil de Símbolos Especiais',
        shortcut: 'Aba Símbolos no Rodapé',
        desc: 'Localizada na borda inferior central da tela. Ao expandir, disponibiliza botões rápidos para os caracteres (! @ # $ % ¨ & * ( )), copiando-os e inserindo-os diretamente na posição atual do cursor de texto.',
        usage: 'Acesso rápido a caracteres de marcação utilizados em scripts de letreiramento.'
      }
    ]
  },
  {
    id: 'sec-06',
    index: '06',
    title: 'Estúdio — Processamento em Lote, Fila de Tarefas e Console',
    eyebrow: '06 // ORQUESTRAÇÃO DO PIPELINE E TELEMETRIA DE EXECUÇÃO',
    description:
      'A coluna direita do Estúdio gerencia a execução automatizada do capítulo. Permite processar todas as etapas em sequência ou acionar individualmente Layout, OCR ou Tradução sobre um subconjunto selecionado de páginas.',
    blueprintTitle: 'PRANCHA 06 — ANATOMIA DO PAINEL DE LOTE, TRILHO DE 3 PONTOS E CONSOLE (> _)',
    specs: [
      {
        pin: '01',
        name: 'Lista de Páginas & Micro-Trilho de 3 Pontos',
        shortcut: 'Botão Todas / Desmarcar',
        desc: 'Lista todas as imagens do capítulo com caixas de seleção. À direita de cada arquivo, três indicadores luminosos informam o estado daquela página: 1º ponto = Layout concluído; 2º ponto = OCR extraído; 3º ponto = Tradução concluída.',
        usage: 'Identifique visualmente quais páginas já possuem cada etapa concluída no capítulo.'
      },
      {
        pin: '02',
        name: 'Limpeza Seletiva por Etapa (3 Lixeiras)',
        shortcut: 'Tradução | OCR | Tudo',
        desc: 'Opera sobre as páginas selecionadas: a lixeira "Tradução" remove apenas os textos em português; "OCR" remove o inglês e o português preservando os balões desenhados; "Tudo" remove balões, OCR e traduções.',
        usage: 'Use a lixeira "Tradução" quando quiser retraduzir páginas com outro modelo sem refazer o OCR.'
      },
      {
        pin: '03',
        name: 'Etapa 1. Layout + Chave Filtro SFX + Play Individual',
        shortcut: 'Execução Isolada',
        desc: 'O botão Play executa somente a detecção de balões nas páginas marcadas. A pílula "Filtro SFX", quando ativa, aciona uma verificação secundária via modelo de visão para descartar caixas vazias e onomatopeias.',
        usage: 'Rode primeiro apenas o Layout caso queira revisar todas as caixas antes de extrair o texto.'
      },
      {
        pin: '04',
        name: 'Etapas 2. OCR e 3. Tradução (Play Individual)',
        shortcut: 'Execução Isolada',
        desc: 'Permitem executar exclusivamente a extração óptica (OCR) ou exclusivamente a tradução neural nas páginas selecionadas, respeitando integralmente os polígonos e ordens ajustados manualmente.',
        usage: 'Fluxo recomendado após corrigir margens ou desenhar novos balões no modo Layout.'
      },
      {
        pin: '05',
        name: 'Opção Sobrescrever Dados Existentes',
        shortcut: 'Caixa de Seleção',
        desc: 'Quando desmarcada (padrão seguro), preserva os dados já existentes e processa apenas páginas ou balões pendentes. Quando marcada, força o reprocessamento completo das páginas selecionadas.',
        usage: 'Mantenha desmarcada para proteger revisões manuais ao complementar um capítulo.'
      },
      {
        pin: '06',
        name: 'Ação Principal: Executar Pipeline Completa',
        shortcut: 'Botão Mestre',
        desc: 'Enfileira a execução sequencial completa (1. Layout ➔ 2. OCR ➔ 3. Tradução ➔ Exportação de Roteiro) para todas as páginas selecionadas.',
        usage: 'Processamento automatizado de ponta a ponta para capítulos novos.'
      },
      {
        pin: '07',
        name: 'Fila de Tarefas (Progresso e Interrupção)',
        shortcut: 'Rodapé da Coluna Direita',
        desc: 'Exibe os lotes ativos e concluídos com barra percentual de progresso, botão "X" para interromper imediatamente o processamento atual e botão "Limpar" para remover registros finalizados.',
        usage: 'Controle total para pausar ou cancelar lotes a qualquer instante.'
      },
      {
        pin: '08',
        name: 'Console de Execução (>_) & Monitor de VRAM',
        shortcut: 'Ícone de Terminal na Fila',
        desc: 'Abre a gaveta técnica de acompanhamento contendo: cronômetro de execução, linha do tempo das 4 fases, medidor de VRAM em tempo real (detalhando o consumo por modelo carregado), contadores clicáveis de Erros/Avisos, busca grep e trava de rolagem.',
        usage: 'Auditoria técnica em tempo real da velocidade de geração (tok/s) e alocação de GPU.'
      }
    ]
  },
  {
    id: 'sec-07',
    index: '07',
    title: 'Biblioteca — Central de Roteiro, Modo Lado a Lado e Tipografia',
    eyebrow: '07 // PRODUTIVIDADE DE LETREIRAMENTO E EXPORTAÇÃO EDITORIAL',
    description:
      'A aba Biblioteca organiza os roteiros traduzidos para a etapa de diagramação externa (Photoshop, Clip Studio Paint, InDesign). Automatiza a formatação tipográfica no momento da cópia e controla individualmente quais balões já foram colados.',
    blueprintTitle: 'PRANCHA 07 — ANATOMIA DA BIBLIOTECA, TIPOGRAFIA E VISÃO LADO A LADO',
    specs: [
      {
        pin: '01',
        name: 'Medidor de Progresso de Cópia & Reinicialização',
        shortcut: 'Copiados / Total (X%)',
        desc: 'Contabiliza quantas falas do capítulo já foram copiadas para a área de transferência. O botão de reversão (↺) ao lado permite zerar as marcações de cópia do capítulo.',
        usage: 'Acompanhamento preciso do andamento da diagramação do capítulo.'
      },
      {
        pin: '02',
        name: 'Ação Sincronizar .TXT',
        shortcut: 'Cabeçalho da Biblioteca',
        desc: 'Recompila o arquivo .txt consolidado da Biblioteca a partir dos mapeamentos atuais das páginas lá no Estúdio, preservando o histórico de balões já marcados como colados.',
        usage: 'Acione sempre que fizer ajustes tardios de texto ou ordem no Estúdio.'
      },
      {
        pin: '03',
        name: 'Menu Tipografia (Regras de Formatação na Cópia)',
        shortcut: '3 Chaves Independentes',
        desc: 'Aplica transformações automáticas ao texto enviado para o Ctrl+V: 1. Travessão (converte hifens iniciais em travessão longo —); 2. Reticências tipográficas (converte "..." no caractere único …); 3. FORÇAR CAIXA ALTA.',
        usage: 'Elimina a necessidade de formatar travessões e caixa alta manualmente no editor gráfico.'
      },
      {
        pin: '04',
        name: 'Menu Exportar (.TXT / .RTF), Expandir e Copiar Tudo',
        shortcut: 'Exportação Externa',
        desc: 'Permite exportar o script como "Roteiro Limpo (.txt)" ou "Formato Word (.rtf)" com formatação editorial. Os botões adjacentes expandem/recolhem todas as páginas ou copiam o capítulo inteiro.',
        usage: 'Use o formato .rtf quando precisar enviar o roteiro para revisão ortográfica no Word.'
      },
      {
        pin: '05',
        name: 'Seletor de Visão: Roteiro, Lado a Lado e Texto Puro',
        shortcut: '3 Modos de Exibição',
        desc: '"Roteiro" exibe todas as páginas em lista contínua (com botões rápidos Lado a Lado, Studio e Copiar Página em cada folha). "Lado a Lado" divide a tela entre a imagem da página e as falas. "Texto Puro" exibe o .txt bruto clicável.',
        usage: 'No modo Texto Puro, clicar sobre qualquer linha numerada salta diretamente para aquele balão no modo Lado a Lado.'
      },
      {
        pin: '06',
        name: 'Próxima Pendente, Auto-Retomar e Busca Global',
        shortcut: 'Ctrl + F (Enter / Shift+Enter)',
        desc: '"Próxima Pendente" salta para a primeira página que ainda possui balões não copiados. "Auto-Retomar" posiciona automaticamente o capítulo na primeira fala pendente ao abri-lo. A busca localiza termos em todo o capítulo.',
        usage: 'Permite retomar capítulos longos exatamente do ponto onde a diagramação parou.'
      },
      {
        pin: '07',
        name: 'Barra do Modo Lado a Lado: Mira (Auto-Zoom), Olho e EN',
        shortcut: 'Tecla Z (Auto-Zoom)',
        desc: 'Controles exclusivos da divisão de tela: Zoom (- / 100% / + e Enquadrar), Mira (Auto-Zoom que aproxima a imagem no balão copiado), Olho (exibe/oculta as marcações #1, #2 sobre a arte) e botão EN (exibe/oculta o inglês original nos cartões).',
        usage: 'Habilite o botão EN para conferir o texto original enquanto copia as falas.'
      },
      {
        pin: '08',
        name: 'Cópia Direta na Imagem ou Linha & Controle Colado',
        shortcut: 'Espaço / ↓ (Copiar) | U (Desmarcar)',
        desc: 'No modo Lado a Lado, clicar diretamente sobre a caixa do balão na imagem (ou clicar na linha da fala / pressionar Espaço) copia o texto formatado e marca como "Colado". Pressionar U (ou clicar no ícone ↺ ao lado de Colado) desmarca.',
        usage: 'Fluxo de letreiramento de alta velocidade sem perder a referência visual de quem está falando.'
      },
      {
        pin: '09',
        name: 'Edição Rápida Inline da Tradução na Biblioteca',
        shortcut: 'Duplo Clique na Fala / Enter',
        desc: 'Dar duplo clique sobre qualquer frase em português na Biblioteca (ou clicar no ícone de engrenagem da linha) abre o campo de edição rápida: pressionar Enter grava a correção diretamente no arquivo .txt.',
        usage: 'Corrige pequenos detalhes de tradução na hora de diagramar sem precisar voltar à aba Estúdio.'
      }
    ]
  },
  {
    id: 'sec-08',
    index: '08',
    title: 'Lightbox (Preparação de Páginas) e Central de Módulos (IA e VRAM)',
    eyebrow: '08 // MONTAGEM DE PÁGINAS DUPLAS E GERENCIAMENTO DE MOTORES NEURAIS',
    description:
      'A aba Lightbox realiza o preparo físico dos arquivos de imagem antes do pipeline (junção de páginas duplas, corte vertical e reordenação). A aba Módulos monitora o hardware e gerencia os motores visuais e modelos de tradução locais.',
    blueprintTitle: 'PRANCHA 08 — ANATOMIA DA LIGHTBOX E DA CENTRAL DE MÓDULOS / OLLAMA',
    specs: [
      {
        pin: '01',
        name: 'Lightbox: Seleção e Direção de Costura',
        shortcut: 'Mangá (Dir ➔ Esq) | Ocidental',
        desc: 'Os botões "Tudo" e "Limpar" gerenciam a seleção. O seletor "Costura" define a ordem geométrica de montagem: no modo Mangá (Dir ➔ Esq), a primeira página selecionada é posicionada à direita e a segunda à esquerda.',
        usage: 'Certifique-se de que o modo Mangá esteja ativo antes de unir páginas de obras orientais.'
      },
      {
        pin: '02',
        name: 'Lightbox: Unir Páginas (Spread) e Dividir ao Meio',
        shortcut: 'Operações de Imagem',
        desc: '"Unir Páginas" combina 2 ou mais imagens selecionadas lado a lado em um único arquivo horizontal. "Dividir" secciona 1 página dupla selecionada exatamente ao meio na vertical, gerando duas páginas individuais.',
        usage: 'Una páginas duplas antes de rodar o Layout para evitar que balões centrais fiquem divididos.'
      },
      {
        pin: '03',
        name: 'Lightbox: Arrastar e Soltar, Salvar Ordem e Densidade',
        shortcut: '1 col a 8 col | Duplo Clique',
        desc: 'Arraste os cartões para corrigir a sequência de páginas; o botão "Salvar Ordem" surge na barra para renomear os arquivos fisicamente no disco. Inclui botão "Excluir", controle de colunas (1 a 8) e duplo clique para abrir no Estúdio.',
        usage: 'Remova páginas de créditos extras e grave a numeração correta antes de processar o capítulo.'
      },
      {
        pin: '04',
        name: 'Módulos: Painel de Telemetria em Tempo Real (4 Cartões)',
        shortcut: 'GPU | CPU | RAM | Disco',
        desc: 'Monitora continuamente: modelo da GPU, versão CUDA, temperatura em °C, alocação de VRAM (GB usados / total), carga de CPU (núcleos/threads), memória RAM livre e espaço em disco ocupado pelos modelos.',
        usage: 'Verifique a disponibilidade de VRAM antes de selecionar modelos de grande porte.'
      },
      {
        pin: '05',
        name: 'Módulos: Motores do Pipeline (PyTorch, YOLO, Florence-2)',
        shortcut: 'Coluna Esquerda (3/3 Prontos)',
        desc: 'Gerencia a instalação dos 3 componentes base: 1. PyTorch Core (aceleração CUDA FP16 e alerta de driver); 2. Comic-YOLO (~59 MB — detecção de balões e ordem); 3. Florence-2 Large (~1,56 GB) ou Base (~465 MB) para leitura óptica.',
        usage: 'Permite baixar ou reinstalar individualmente qualquer motor visual.'
      },
      {
        pin: '06',
        name: 'Serviço Ollama: Verificar, Liberar VRAM e Restaurar',
        shortcut: 'Servidor Local 127.0.0.1:11435',
        desc: 'Exibe o estado do motor de tradução local. "Verificar" testa a conexão; "Liberar VRAM" descarrega imediatamente todos os modelos da memória da placa de vídeo e limpa o cache CUDA; "Restaurar Ambiente" executa reset de fábrica.',
        usage: 'Clique em "Liberar VRAM" ao concluir suas traduções para liberar 100% da GPU para o Photoshop.'
      },
      {
        pin: '07',
        name: 'Catálogo de Modelos: Amadeus Verbo 7B, 14B e 32B',
        shortcut: 'Filtros + Download Customizado',
        desc: 'Disponibiliza os 3 perfis otimizados: 7B (~4,7 GB · ~42 tok/s · 100% GPU em 6–8 GB), 14B (~9,0 GB · ~20 tok/s · equilíbrio GPU/Híbrido) e 32B (~19,8 GB · ~7 tok/s · precisão máxima), além de campo para baixar qualquer modelo oficial do Ollama.',
        usage: 'Cada cartão calcula automaticamente a compatibilidade com seu PC (100% GPU, Híbrido ou CPU).'
      }
    ]
  },
  {
    id: 'sec-09',
    index: '09',
    title: 'Configurações (5 Sub-Abas) e Painel de Diagnóstico',
    eyebrow: '09 // PERSONALIZAÇÃO DE INTERFACE, FLUXO E AUDITORIA DE SISTEMA',
    description:
      'A aba Configurações armazena instantaneamente todas as preferências visuais e operacionais no perfil do usuário. O Painel de Diagnóstico provê ferramentas avançadas de inspeção e geração de mapas visuais.',
    blueprintTitle: 'PRANCHA 09 — ANATOMIA DAS CONFIGURAÇÕES E DO MODO DE DIAGNÓSTICO',
    specs: [
      {
        pin: '01',
        name: 'Sub-Aba 1: Interface (UX) — Temas, Fontes, Zoom e Cores',
        shortcut: '6 Temas + Seletor RGB',
        desc: 'Oferece 6 temas (Pro Studio, Paperwhite claro para leitura prolongada, Cyber CAD preto OLED, E-Ink Matte fosco, Neo-Tokyo e Estúdio Neutro), 3 famílias tipográficas, escala de interface (90% a 120%), densidade de menus e 9 cores de destaque.',
        usage: 'Alterne para o tema Paperwhite ou Estúdio Neutro durante sessões longas de revisão textual.'
      },
      {
        pin: '02',
        name: 'Sub-Aba 2: Workflow & Pastas — Diretório Raiz e Automação',
        shortcut: 'Preferências de Produtividade',
        desc: 'Permite definir um "Diretório Raiz do Explorador" fixo e controlar chaves de produtividade: Contador de Páginas, Indicador de Status, Auto-Retomar na 1ª Pendente, Auto-Avanço de Página na Biblioteca, Auto-Zoom e Barra de Símbolos.',
        usage: 'Com "Auto-Avanço de Página" ativo, copiar o último balão de uma folha na Biblioteca avança automaticamente para a página seguinte.'
      },
      {
        pin: '03',
        name: 'Sub-Aba 3: Áudio & Sistema — Timbres e Bandeja (System Tray)',
        shortcut: 'Comportamento do Botão X',
        desc: 'Configura o aviso sonoro de conclusão (Harmônico, Pop Sutil, Tech Bip e volume), notificações nativas do Windows e o comportamento ao fechar a janela: modo "Inteligente" (minimiza para a bandeja apenas se houver tarefa ativa), "Sempre Bandeja" ou "Encerrar".',
        usage: 'Inclui opções para desativar o Vidro Acrílico e Reduzir Animações visando desempenho máximo.'
      },
      {
        pin: '04',
        name: 'Sub-Abas 4 e 5: Atalhos de Teclado e Sobre o App',
        shortcut: 'Consulta & Arquitetura',
        desc: 'Apresentam o resumo de teclas de atalho e as especificações da versão instalada, confirmação de operação 100% offline (zero telemetria externa) e arquitetura neural de 4 estágios.',
        usage: 'Verificação rápida do modo de privacidade local e versão do motor.'
      },
      {
        pin: '05',
        name: 'Painel Oculto de Diagnóstico & Mapas Visuais (Debug)',
        shortcut: 'Ctrl + Shift + D (ou 5 cliques no logo)',
        desc: 'Habilitado mediante credencial autorizada (ex: guest ou dev). Adiciona a aba Diagnóstico contendo: chave "Mapas Visuais (Debug)" (salva imagens [página]_mapa.jpg na pasta output/ com caixas azuis de painéis e vermelhas de balões), testes do Wizard e console de eventos.',
        usage: 'Habilite Mapas Visuais quando desejar auditar geometricamente a detecção bruta do lote.'
      }
    ]
  }
];

const SHORTCUTS_SPEC = [
  { group: 'ESTÚDIO — NAVEGAÇÃO E MODOS', key: 'W / S  ou  ↑ / ↓', action: 'Selecionar balão anterior / próximo balão na Ordem de Leitura' },
  { group: 'ESTÚDIO — NAVEGAÇÃO E MODOS', key: 'A / D  ou  PgUp / PgDn', action: 'Navegar para a página anterior / próxima página do capítulo' },
  { group: 'ESTÚDIO — NAVEGAÇÃO E MODOS', key: '1 / 2 / 3', action: 'Alternar diretamente entre os modos Layout (1), OCR (2) e Tradução (3)' },
  { group: 'ESTÚDIO — NAVEGAÇÃO E MODOS', key: 'Z', action: 'Ativar / Desativar Auto-Zoom automático no balão selecionado' },
  { group: 'ESTÚDIO — NAVEGAÇÃO E MODOS', key: 'F  ou  0', action: 'Enquadrar a página inteira na área útil da tela (Ajustar)' },
  { group: 'ESTÚDIO — FERRAMENTAS DE LAYOUT', key: 'V / B / P', action: 'Ativar ferramentas Seleção (V), Retângulo (B) ou Caneta de 4 cliques (P)' },
  { group: 'ESTÚDIO — FERRAMENTAS DE LAYOUT', key: 'L', action: 'Ativar ferramenta Vincular Grupo (conectar balões duplos)' },
  { group: 'ESTÚDIO — FERRAMENTAS DE LAYOUT', key: 'S (Modo Layout)', action: 'Alternar classificação do balão selecionado entre Fala e SFX' },
  { group: 'ESTÚDIO — FERRAMENTAS DE LAYOUT', key: 'R', action: 'Iniciar / Encerrar modo de sequenciamento manual Marcar 1-a-1' },
  { group: 'ESTÚDIO — EDIÇÃO E PERSISTÊNCIA', key: 'Delete', action: 'Excluir o balão atualmente selecionado' },
  { group: 'ESTÚDIO — EDIÇÃO E PERSISTÊNCIA', key: 'Esc', action: 'Desmarcar seleção atual ou cancelar traçado da Caneta' },
  { group: 'ESTÚDIO — EDIÇÃO E PERSISTÊNCIA', key: 'Ctrl + Z / Ctrl + Y', action: 'Desfazer / Refazer alterações na página (até 50 estados)' },
  { group: 'ESTÚDIO — EDIÇÃO E PERSISTÊNCIA', key: 'Ctrl + S', action: 'Forçar gravação imediata do mapeamento em disco' },
  { group: 'BIBLIOTECA — LETREIRAMENTO', key: 'Espaço  ou  ↓', action: 'Copiar fala atual formatada, marcar como Colado e avançar para a próxima' },
  { group: 'BIBLIOTECA — LETREIRAMENTO', key: '↑', action: 'Retornar para a fala imediatamente anterior' },
  { group: 'BIBLIOTECA — LETREIRAMENTO', key: 'U  ou  Backspace', action: 'Desmarcar status "Colado" do balão atualmente selecionado' },
  { group: 'BIBLIOTECA — LETREIRAMENTO', key: 'Duplo Clique na Fala', action: 'Abrir edição rápida inline da tradução diretamente na Biblioteca' },
  { group: 'BIBLIOTECA — LETREIRAMENTO', key: 'Enter / Esc (Edição)', action: 'Confirmar gravação no arquivo .txt / Cancelar edição inline' },
  { group: 'BIBLIOTECA — LETREIRAMENTO', key: 'Ctrl + F', action: 'Localizar termo no capítulo inteiro (Enter avança, Shift+Enter recua)' },
  { group: 'SISTEMA GLOBAL', key: 'F1', action: 'Abrir esta Documentação Técnica e Guia de Referência' },
  { group: 'SISTEMA GLOBAL', key: 'Ctrl + Shift + D', action: 'Acionar modal de autenticação do Painel de Diagnóstico' }
];

// Renderizador de Diagrama Espacial de Anatomia por Seção
function ChapterAnatomyBlueprint({ chapterId, hoveredPinKey, setHoveredPinKey }) {
  const mkProps = (pin) => {
    const key = `${chapterId}-${pin}`;
    return {
      className: `anatomy-target ${hoveredPinKey === key ? 'highlighted' : ''}`,
      onMouseEnter: () => setHoveredPinKey(key),
      onMouseLeave: () => setHoveredPinKey(null)
    };
  };

  if (chapterId === 'sec-01') {
    return (
      <div className="anatomy-stage">
        <div className="anatomy-bar">
          <div {...mkProps('05')}>
            <span className="pin-badge">05</span>
            <span>VISIONARY STUDIO [PRO / DEV]</span>
          </div>
          <div {...mkProps('04')}>
            <span className="pin-badge">04</span>
            <Folder size={13} />
            <span>Capítulo Ativo / Trilha de Diretório</span>
          </div>
          <div {...mkProps('03')}>
            <span className="pin-badge">03</span>
            <span>Baixando IA (64%)</span>
          </div>
        </div>
        <div className="anatomy-grid-2">
          <div {...mkProps('01')} style={{ justifyContent: 'space-between', padding: '10px 14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="pin-badge">01</span>
              <span>Perfil Studio Elite (32B)</span>
            </div>
            <span style={{ fontFamily: 'monospace', fontSize: '11px', opacity: 0.7 }}>22,9 GB • Fidelidade Máxima</span>
          </div>
          <div {...mkProps('02')} style={{ justifyContent: 'space-between', padding: '10px 14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span className="pin-badge">02</span>
              <span>Perfil Ágil (7B)</span>
            </div>
            <span style={{ fontFamily: 'monospace', fontSize: '11px', opacity: 0.7 }}>5,8 GB • 100% GPU Rápido</span>
          </div>
        </div>
      </div>
    );
  }

  if (chapterId === 'sec-02') {
    return (
      <div className="anatomy-stage">
        <div className="anatomy-grid-2">
          <div className="anatomy-card">
            <div style={{ fontSize: '11px', fontFamily: 'monospace', color: 'var(--text-muted)' }}>ESTADO A: MODO EXPLORADOR</div>
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
              <div {...mkProps('01')}><span className="pin-badge">01</span><span>↑ Subir / Discos</span></div>
              <div {...mkProps('02')}><span className="pin-badge">02</span><RefreshCw size={12} /><span>Atualizar / Redimensionar</span></div>
            </div>
            <div {...mkProps('03')} style={{ width: '100%' }}>
              <span className="pin-badge">03</span><Search size={12} /><span>Buscar capítulos (ex: cap 1)...</span>
            </div>
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
              <div {...mkProps('04')}><span className="pin-badge">04</span><BookOpen size={12} /><span>Capítulo 01 [24 págs]</span></div>
              <div {...mkProps('05')}>
                <span className="pin-badge">05</span>
                <span style={{ width: 8, height: 8, borderRadius: 99, background: '#10b981', display: 'inline-block' }} />
                <span style={{ width: 8, height: 8, borderRadius: 99, background: '#f59e0b', display: 'inline-block' }} />
                <span style={{ width: 8, height: 8, borderRadius: 99, background: '#38bdf8', display: 'inline-block' }} />
                <span>Status</span>
              </div>
            </div>
          </div>

          <div className="anatomy-card">
            <div style={{ fontSize: '11px', fontFamily: 'monospace', color: 'var(--text-muted)' }}>ESTADO B: MODO BIBLIOTECA (.TXT)</div>
            <div {...mkProps('06')}>
              <span className="pin-badge">06</span><Folder size={12} /><span>Botão Biblioteca (Abrir no Explorer)</span>
            </div>
            <div {...mkProps('07')} style={{ justifyContent: 'space-between', width: '100%' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '7px' }}>
                <span className="pin-badge">07</span>
                <span>Capítulo_01.txt • Pronto / Pendentes</span>
              </div>
              <Trash2 size={13} />
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (chapterId === 'sec-03') {
    return (
      <div className="anatomy-stage">
        <div className="anatomy-bar">
          <div {...mkProps('01')}><span className="pin-badge">01</span><ChevronLeft size={12} /><span>1 / 24</span><ChevronRight size={12} /><span>001.png</span></div>
          <div {...mkProps('02')}><span className="pin-badge">02</span><span>Visualizar | Layout (1) | OCR (2) | Tradução (3)</span></div>
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
            <div {...mkProps('03')}><span className="pin-badge">03</span><span>Salvo</span></div>
            <div {...mkProps('04')}><span className="pin-badge">04</span><Maximize size={12} /><span>Ajustar (85%)</span></div>
            <div {...mkProps('05')}><span className="pin-badge">05</span><Crosshair size={12} /><span>Auto-Zoom</span></div>
          </div>
        </div>
        <div className="anatomy-grid-2">
          <div className="anatomy-card">
            <div style={{ fontSize: '11px', fontFamily: 'monospace', color: 'var(--text-muted)' }}>ELEMENTOS DO BALÃO NO CANVAS</div>
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
              <div {...mkProps('06')}><span className="pin-badge">06</span><span>Crachá Numerado (Verde / Azul / Roxo / Laranja)</span></div>
              <div {...mkProps('07')}><span className="pin-badge">07</span><span>Botões Flutuantes: Excluir (X) e Restaurar (↺)</span></div>
              <div {...mkProps('08')}><span className="pin-badge">08</span><span>8 Alças Elásticas (4 Vértices + 4 Bordas)</span></div>
            </div>
          </div>
          <div className="anatomy-card">
            <div style={{ fontSize: '11px', fontFamily: 'monospace', color: 'var(--text-muted)' }}>INSPETOR DO MODO VISUALIZAR</div>
            <div {...mkProps('09')}><span className="pin-badge">09</span><span>Próximo Passo Recomendado + Status + Métricas (px)</span></div>
            <div {...mkProps('10')}><span className="pin-badge">10</span><span>Ver Roteiro da Página (.txt) + Redefinir Página</span></div>
          </div>
        </div>
      </div>
    );
  }

  if (chapterId === 'sec-04') {
    return (
      <div className="anatomy-stage">
        <div className="anatomy-bar">
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
            <div {...mkProps('01')}><span className="pin-badge">01</span><MousePointer size={12} /><span>Seleção (V)</span></div>
            <div {...mkProps('02')}><span className="pin-badge">02</span><Square size={12} /><span>Retângulo (B)</span></div>
            <div {...mkProps('03')}><span className="pin-badge">03</span><PenTool size={12} /><span>Caneta 4 Cliques (P)</span></div>
            <div {...mkProps('04')}><span className="pin-badge">04</span><Link2 size={12} /><span>Vincular Grupo (L)</span></div>
            <div {...mkProps('05')}><span className="pin-badge">05</span><Zap size={12} /><span>Alternar SFX (S)</span></div>
          </div>
          <div {...mkProps('06')}><span className="pin-badge">06</span><span>Contorno Orgânico | Caixa Retangular</span></div>
        </div>
        <div className="anatomy-grid-2">
          <div className="anatomy-card">
            <div style={{ fontSize: '11px', fontFamily: 'monospace', color: 'var(--text-muted)' }}>SUB-ABA 1: ORDEM DE LEITURA</div>
            <div {...mkProps('07')}><span className="pin-badge">07</span><ArrowUpDown size={12} /><span>Auto-Ordenar Mangá | Marcar 1-a-1 (R)</span></div>
            <div {...mkProps('08')}><span className="pin-badge">08</span><span>Cartão #01 + Mini-Mapa da Folha + Arrastar</span></div>
          </div>
          <div className="anatomy-card">
            <div style={{ fontSize: '11px', fontFamily: 'monospace', color: 'var(--text-muted)' }}>SUB-ABA 2: PROPRIEDADES DO BALÃO</div>
            <div {...mkProps('09')}><span className="pin-badge">09</span><Sliders size={12} /><span>Modo de Edição: Bordas (8) | Vértices | Todos Nós</span></div>
            <div {...mkProps('10')}><span className="pin-badge">10</span><span>Margem OCR: [+6px Margem] e [-6px Margem]</span></div>
          </div>
        </div>
      </div>
    );
  }

  if (chapterId === 'sec-05') {
    return (
      <div className="anatomy-stage">
        <div className="anatomy-grid-2">
          <div className="anatomy-card">
            <div style={{ fontSize: '11px', fontFamily: 'monospace', color: 'var(--text-muted)' }}>ESTRUTURA DO CARTÃO DE TEXTO</div>
            <div {...mkProps('01')}><span className="pin-badge">01</span><span>BLOCO # [ 1 ] (Índice Numérico Editável + Arrasto)</span></div>
            <div {...mkProps('03')}><span className="pin-badge">03</span><span>Quadro: TEXTO ORIGINAL OCR (Inglês)</span></div>
            <div {...mkProps('04')}><span className="pin-badge">04</span><RotateCcw size={12} /><span>Quadro: IA ORIGINAL + Botão Restaurar IA</span></div>
            <div {...mkProps('05')}><span className="pin-badge">05</span><span>Caixa de Edição (pt-BR) + Voltar ao Local Inicial</span></div>
          </div>
          <div className="anatomy-card">
            <div style={{ fontSize: '11px', fontFamily: 'monospace', color: 'var(--text-muted)' }}>TRIAGEM DE RUÍDO E RODAPÉ</div>
            <div {...mkProps('02')}><span className="pin-badge">02</span><span>Sugerido para Descarte (Ruído / SFX): [Manter] [Descartar]</span></div>
            <div {...mkProps('06')}><span className="pin-badge">06</span><span>Barra Flutuante Símbolos: ! @ # $ % ¨ &amp; * ( )</span></div>
          </div>
        </div>
      </div>
    );
  }

  if (chapterId === 'sec-06') {
    return (
      <div className="anatomy-stage">
        <div className="anatomy-grid-2">
          <div className="anatomy-card">
            <div style={{ fontSize: '11px', fontFamily: 'monospace', color: 'var(--text-muted)' }}>COLUNA DE PROCESSAMENTO EM LOTE</div>
            <div {...mkProps('01')}><span className="pin-badge">01</span><span>Lista de Páginas + Micro-Trilho de 3 Pontos (Layout / OCR / Trad)</span></div>
            <div {...mkProps('02')}><span className="pin-badge">02</span><Trash2 size={12} /><span>3 Lixeiras Seletivas: [Tradução] [OCR] [Tudo]</span></div>
            <div {...mkProps('03')}><span className="pin-badge">03</span><Play size={12} /><span>1. Layout + Chave [Filtro SFX] + Play</span></div>
            <div {...mkProps('04')}><span className="pin-badge">04</span><Play size={12} /><span>2. OCR (Play) &amp; 3. Tradução (Play)</span></div>
          </div>
          <div className="anatomy-card">
            <div style={{ fontSize: '11px', fontFamily: 'monospace', color: 'var(--text-muted)' }}>EXECUÇÃO, FILA E CONSOLE</div>
            <div {...mkProps('05')}><span className="pin-badge">05</span><span>Caixa: Sobrescrever dados existentes</span></div>
            <div {...mkProps('06')}><span className="pin-badge">06</span><Play size={12} /><span>Botão Mestre: Executar Pipeline Completa</span></div>
            <div {...mkProps('07')}><span className="pin-badge">07</span><span>Fila de Tarefas (Progresso % + Interromper X)</span></div>
            <div {...mkProps('08')}><span className="pin-badge">08</span><Terminal size={12} /><span>Console de Execução (&gt;_): 4 Fases, VRAM, Erros/Avisos e Grep</span></div>
          </div>
        </div>
      </div>
    );
  }

  if (chapterId === 'sec-07') {
    return (
      <div className="anatomy-stage">
        <div className="anatomy-bar">
          <div {...mkProps('01')}><span className="pin-badge">01</span><span>Progresso: Copiados / Total (X%) + Reset</span></div>
          <div {...mkProps('02')}><span className="pin-badge">02</span><RefreshCw size={12} /><span>Sincronizar .TXT</span></div>
          <div {...mkProps('03')}><span className="pin-badge">03</span><span>Menu Tipografia (Travessão — | Reticências … | CAIXA ALTA)</span></div>
          <div {...mkProps('04')}><span className="pin-badge">04</span><Download size={12} /><span>Exportar (.TXT / .RTF) + Copiar Tudo</span></div>
        </div>
        <div className="anatomy-grid-2">
          <div className="anatomy-card">
            <div {...mkProps('05')}><span className="pin-badge">05</span><Columns size={12} /><span>Modos: Roteiro | Lado a Lado | Texto Puro</span></div>
            <div {...mkProps('06')}><span className="pin-badge">06</span><span>Próxima Pendente + Auto-Retomar + Localizar (Ctrl+F)</span></div>
            <div {...mkProps('07')}><span className="pin-badge">07</span><span>Barra Lado a Lado: Zoom | Mira (Auto-Zoom) | Olho | EN</span></div>
          </div>
          <div className="anatomy-card">
            <div {...mkProps('08')}><span className="pin-badge">08</span><Check size={12} /><span>Clique na Imagem/Linha = Copiar e Marcar Colado (U desmarca)</span></div>
            <div {...mkProps('09')}><span className="pin-badge">09</span><span>Duplo Clique na Fala = Edição Rápida Inline (Enter salva)</span></div>
          </div>
        </div>
      </div>
    );
  }

  if (chapterId === 'sec-08') {
    return (
      <div className="anatomy-stage">
        <div className="anatomy-bar">
          <div {...mkProps('01')}><span className="pin-badge">01</span><span>Lightbox: Tudo/Limpar + Costura Mangá (Dir ➔ Esq)</span></div>
          <div {...mkProps('02')}><span className="pin-badge">02</span><Scissors size={12} /><span>Unir Páginas (Spread) | Dividir ao Meio</span></div>
          <div {...mkProps('03')}><span className="pin-badge">03</span><span>Arrastar + Salvar Ordem | Excluir | Grade (1–8 col)</span></div>
        </div>
        <div className="anatomy-grid-2">
          <div className="anatomy-card">
            <div {...mkProps('04')}><span className="pin-badge">04</span><Cpu size={12} /><span>Telemetria: GPU (°C e VRAM) | CPU | RAM | Armazenamento</span></div>
            <div {...mkProps('05')}><span className="pin-badge">05</span><span>Motores: PyTorch Core (CUDA) + Comic-YOLO + Florence-2</span></div>
          </div>
          <div className="anatomy-card">
            <div {...mkProps('06')}><span className="pin-badge">06</span><span>Serviço Ollama: Verificar | Liberar VRAM | Restaurar Ambiente</span></div>
            <div {...mkProps('07')}><span className="pin-badge">07</span><span>Modelos Amadeus Verbo: 7B (~4,7 GB) | 14B (~9,0 GB) | 32B (~19,8 GB)</span></div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="anatomy-stage">
      <div className="anatomy-bar">
        <div {...mkProps('01')}><span className="pin-badge">01</span><span>1. Interface (UX): 6 Temas + Fontes + Zoom + Cores</span></div>
        <div {...mkProps('02')}><span className="pin-badge">02</span><span>2. Workflow: Diretório Raiz + Auto-Avanço de Página</span></div>
        <div {...mkProps('03')}><span className="pin-badge">03</span><span>3. Áudio &amp; Sistema: Timbres + Bandeja Inteligente (Tray)</span></div>
        <div {...mkProps('04')}><span className="pin-badge">04</span><span>4. Atalhos &amp; 5. Sobre o App</span></div>
        <div {...mkProps('05')}><span className="pin-badge">05</span><Wrench size={12} /><span>Diagnóstico (Ctrl+Shift+D): Mapas Visuais (Debug)</span></div>
      </div>
    </div>
  );
}

export default function InteractiveTutorial({ embedded = false, onClose }) {
  const [activeChapterId, setActiveChapterId] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [hoveredPinKey, setHoveredPinKey] = useState(null);

  const filteredChapters = useMemo(() => {
    const q = searchQuery.trim().toLowerCase();
    return DOCUMENTATION_CHAPTERS
      .filter((ch) => activeChapterId === 'all' || ch.id === activeChapterId)
      .map((ch) => {
        if (!q) return ch;
        const matchedSpecs = ch.specs.filter(
          (sp) =>
            sp.name.toLowerCase().includes(q) ||
            sp.shortcut.toLowerCase().includes(q) ||
            sp.desc.toLowerCase().includes(q) ||
            sp.usage.toLowerCase().includes(q)
        );
        return { ...ch, specs: matchedSpecs };
      })
      .filter((ch) => ch.specs.length > 0);
  }, [activeChapterId, searchQuery]);

  const showShortcutsSection =
    activeChapterId === 'all' ||
    activeChapterId === 'sec-shortcuts' ||
    (searchQuery.trim().length > 0 &&
      SHORTCUTS_SPEC.some(
        (s) =>
          s.key.toLowerCase().includes(searchQuery.trim().toLowerCase()) ||
          s.action.toLowerCase().includes(searchQuery.trim().toLowerCase())
      ));

  return (
    <div className={embedded ? 'doc-Embedded' : ''} style={{ height: '100%', width: '100%' }}>
      <div className="doc-viewport fade-in">
        {/* BARRA TÉCNICA SUPERIOR */}
        <header className="doc-topbar">
          <div className="doc-topbar-left">
            <div className="doc-brand-mark">
              <BookOpen size={15} strokeWidth={2} />
            </div>
            <div className="doc-title-group">
              <span className="doc-title">Documentação Técnica &amp; Anatomia da Interface</span>
              <span className="doc-version-tag">ESPECIFICAÇÃO COMPLETA // EN ➔ PT-BR</span>
            </div>
          </div>

          <div className="doc-topbar-right">
            <div className="doc-search-wrapper">
              <Search
                size={13}
                style={{
                  position: 'absolute',
                  left: '10px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  color: 'var(--text-muted)'
                }}
              />
              <input
                type="text"
                className="doc-search-input"
                placeholder="Filtrar componente, função ou atalho..."
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  if (e.target.value.trim() && activeChapterId !== 'all') {
                    setActiveChapterId('all');
                  }
                }}
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery('')}
                  style={{
                    position: 'absolute',
                    right: '8px',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    background: 'transparent',
                    border: 'none',
                    color: 'var(--text-muted)',
                    cursor: 'pointer'
                  }}
                >
                  <X size={13} />
                </button>
              )}
            </div>

            {onClose && (
              <button type="button" className="btn-secondary" onClick={onClose} style={{ padding: '6px 12px', fontSize: '12px' }}>
                Fechar
              </button>
            )}
          </div>
        </header>

        {/* CORPO PRINCIPAL: ÍNDICE TÉCNICO + PRANCHAS DE ESPECIFICAÇÃO */}
        <div className="doc-body">
          <aside className="doc-sidebar">
            <div className="doc-sidebar-label">Índice de Especificação</div>
            <button
              type="button"
              className={`doc-nav-item ${activeChapterId === 'all' ? 'active' : ''}`}
              onClick={() => setActiveChapterId('all')}
            >
              <span className="doc-nav-index">00</span>
              <span>Visão Completa (01–10)</span>
            </button>

            {DOCUMENTATION_CHAPTERS.map((ch) => (
              <button
                key={ch.id}
                type="button"
                className={`doc-nav-item ${activeChapterId === ch.id ? 'active' : ''}`}
                onClick={() => {
                  setSearchQuery('');
                  setActiveChapterId(ch.id);
                }}
              >
                <span className="doc-nav-index">{ch.index}</span>
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {ch.title.split(':')[0]}
                </span>
              </button>
            ))}

            <button
              type="button"
              className={`doc-nav-item ${activeChapterId === 'sec-shortcuts' ? 'active' : ''}`}
              onClick={() => {
                setSearchQuery('');
                setActiveChapterId('sec-shortcuts');
              }}
            >
              <span className="doc-nav-index">10</span>
              <span>Matriz de Atalhos</span>
            </button>
          </aside>

          <main className="doc-content">
            <div className="doc-content-inner">
              {filteredChapters.map((ch) => (
                <section key={ch.id} className="doc-section">
                  <div className="doc-section-header">
                    <span className="doc-section-eyebrow">{ch.eyebrow}</span>
                    <h2 className="doc-section-title">{ch.title}</h2>
                    <p className="doc-section-desc">{ch.description}</p>
                  </div>

                  {/* PRANCHA DE ANATOMIA ESPACIAL DA INTERFACE COM PINOS NUMERADOS */}
                  <div className="blueprint-board">
                    <div className="blueprint-header">
                      <span>{ch.blueprintTitle}</span>
                      <span>PASSE O MOUSE SOBRE OS PINOS [01–{String(ch.specs.length).padStart(2, '0')}] PARA DESTACAR NA TABELA</span>
                    </div>

                    <ChapterAnatomyBlueprint
                      chapterId={ch.id}
                      hoveredPinKey={hoveredPinKey}
                      setHoveredPinKey={setHoveredPinKey}
                    />
                  </div>

                  {/* TABELA DE ESPECIFICAÇÃO FUNCIONAL */}
                  <div className="spec-table-wrap">
                    <table className="spec-table">
                      <thead>
                        <tr>
                          <th>REF</th>
                          <th>COMPONENTE / ACIONAMENTO</th>
                          <th>ESPECIFICAÇÃO TÉCNICA E COMPORTAMENTO</th>
                          <th>DIRETRIZ OPERACIONAL</th>
                        </tr>
                      </thead>
                      <tbody>
                        {ch.specs.map((sp) => {
                          const pinKey = `${ch.id}-${sp.pin}`;
                          const isHighlighted = hoveredPinKey === pinKey;
                          return (
                            <tr
                              key={sp.pin}
                              className={`spec-row ${isHighlighted ? 'highlighted' : ''}`}
                              onMouseEnter={() => setHoveredPinKey(pinKey)}
                              onMouseLeave={() => setHoveredPinKey(null)}
                            >
                              <td className="spec-cell-pin">
                                <span className="pin-badge">{sp.pin}</span>
                              </td>
                              <td className="spec-cell-tool">
                                <div className="spec-tool-name">{sp.name}</div>
                                <span className="spec-kbd">{sp.shortcut}</span>
                              </td>
                              <td className="spec-cell-desc">{sp.desc}</td>
                              <td className="spec-cell-usage">{sp.usage}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </section>
              ))}

              {/* SEÇÃO 10: MATRIZ COMPLETA DE ATALHOS DE TECLADO */}
              {showShortcutsSection && (
                <section className="doc-section">
                  <div className="doc-section-header">
                    <span className="doc-section-eyebrow">10 // MAPEAMENTO DE TECLADO</span>
                    <h2 className="doc-section-title">Matriz Completa de Atalhos Operacionais</h2>
                    <p className="doc-section-desc">
                      Referência consolidada de todos os comandos rápidos de teclado para navegação no canvas, edição vetorial de polígonos, letreiramento na Biblioteca e diagnóstico de sistema.
                    </p>
                  </div>

                  <div className="spec-table-wrap">
                    <table className="spec-table">
                      <thead>
                        <tr>
                          <th style={{ width: '240px' }}>CONTEXTO OPERACIONAL</th>
                          <th style={{ width: '190px' }}>COMBINAÇÃO DE TECLAS</th>
                          <th>AÇÃO EXECUTADA</th>
                        </tr>
                      </thead>
                      <tbody>
                        {SHORTCUTS_SPEC.filter((s) => {
                          const q = searchQuery.trim().toLowerCase();
                          if (!q) return true;
                          return (
                            s.group.toLowerCase().includes(q) ||
                            s.key.toLowerCase().includes(q) ||
                            s.action.toLowerCase().includes(q)
                          );
                        }).map((sc, idx) => (
                          <tr key={idx} className="spec-row">
                            <td className="spec-cell-tool" style={{ fontFamily: 'monospace', fontSize: '11px', color: 'var(--text-muted)' }}>
                              {sc.group}
                            </td>
                            <td className="spec-cell-tool">
                              <span className="spec-kbd" style={{ marginTop: 0 }}>{sc.key}</span>
                            </td>
                            <td className="spec-cell-desc">{sc.action}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              )}
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}
