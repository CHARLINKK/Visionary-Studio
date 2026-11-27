import React, { useState, useEffect, useRef } from "react";
import {
  Database,
  Star,
  Download,
  ChevronDown,
  Check,
  CheckCircle2,
  X,
  Trash2,
  Info
} from "lucide-react";
import { formatDownloadTelemetry } from "../../utils/downloadFormatters";
import { RECOMMENDED_MODELS, ModelLogo } from "./recommendedModelsCatalog";
import ConfirmModal from "../ConfirmModal";

const TranslationModelsGrid = React.memo(function TranslationModelsGrid({
  children,
  ollamaModels,
  ollamaModelsDetails = {},
  ollamaModelsTags,
  userSettings,
  setUserSettings,
  hardwareStats,
  pullOllamaModel,
  deleteOllamaModel,
  cancelOllamaDownload,
}) {
  const [modelFilter, setModelFilter] = useState(`all`);
  const [modelSearchQuery, setModelSearchQuery] = useState(``);
  const [isActiveSelectorOpen, setIsActiveSelectorOpen] = useState(false);
  const [pendingDeleteModel, setPendingDeleteModel] = useState(null);
  const activeSelectorRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (activeSelectorRef.current && !activeSelectorRef.current.contains(e.target)) {
        setIsActiveSelectorOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleSearchSubmit = (e) => {
    e.preventDefault();
    if (modelSearchQuery.trim()) {
      pullOllamaModel(modelSearchQuery.trim());
      setModelSearchQuery(``);
    }
  };

  const getModelSuitability = (vramReq) => {
    let vram = hardwareStats.vram_reserved_gb || 0;
    let ram = hardwareStats.ram_total_gb || 0;
    return vram === 0
      ? { type: `cpu`, label: `Modo CPU`, desc: `Sem GPU dedicada detectada` }
      : vram >= vramReq
        ? { type: `gpu`, label: `100% GPU`, desc: `Carregamento total na VRAM` }
        : vram + ram >= vramReq
          ? { type: `hybrid`, label: `Híbrido (GPU+RAM)`, desc: `Carregamento repartido` }
          : { type: `cpu`, label: `Modo CPU`, desc: `Execução no processador` };
  };

  const communityModels = ollamaModels
    .filter((modelName) => {
      if (
        RECOMMENDED_MODELS.some(
          (rec) =>
            rec.name === modelName ||
            rec.name.split(`:`)[0] === modelName ||
            modelName.startsWith(rec.name.split(`:`)[0])
        )
      ) {
        return false;
      }
      const lower = modelName.toLowerCase();
      if (
        (lower.includes("amadeus") || lower.includes("av-bi")) &&
        (lower.includes("hf.co") || lower.includes("mradermacher"))
      ) {
        return false;
      }
      return true;
    })
    .map((modelName) => {
      const modelDetail = ollamaModelsDetails?.[modelName];
      const displaySize = modelDetail?.sizeFormatted || `Local`;
      return {
        name: modelName,
        title: modelName.split(`:`)[0].charAt(0).toUpperCase() + modelName.split(`:`)[0].slice(1),
        version: modelName.split(`:`)[1] || `latest`,
        tag: `Local / Comunidade`,
        tagType: `community`,
        vram: `Auto`,
        vramNum: 8,
        speedScore: 4,
        qualityScore: 4,
        sizeEst: displaySize,
        developer: `Ollama`,
        iconTheme: modelName.toLowerCase().includes('amadeus') ? 'amadeus' : modelName.toLowerCase().includes('qwen') ? 'qwen' : (modelName.toLowerCase().includes('deepseek') || modelName.toLowerCase().includes('r1')) ? 'deepseek' : 'custom',
        desc: `Modelo local instalado no Ollama. Disponível para tradução e benchmark.`,
      };
    });

  const allModels = [...RECOMMENDED_MODELS, ...communityModels];

  const filteredModels = allModels.filter((model) => {
    let isDownloaded = ollamaModels.some((dl) => dl === model.name);
    return modelFilter === `installed`
      ? isDownloaded
      : modelFilter !== `recommended` ||
        model.tagType === `fast` ||
        model.tagType === `reasoning` ||
        model.tagType === `balanced` ||
        model.tagType === `heavy` ||
        model.tagType === `featured` ||
        model.tagType === `standard`;
  });

  return (
    <div className={`modules-translation-panel`}>
      {children}
      <div className={`translation-panel-header`}>
        <div className={`section-title-wrap`}>
          <Database size={14} className={`brand-purple-icon`} />
          <div className={`section-heading`}>{`Modelos de Tradução`}</div>
        </div>
        <div className={`native-filter-group`}>
          <button
            type="button"
            className={`native-filter-btn ${modelFilter === `all` ? `active` : ``}`}
            onClick={() => setModelFilter(`all`)}
          >
            {`Todos `}
            <div className={`filter-count`}>{allModels.length}</div>
          </button>
          <button
            type="button"
            className={`native-filter-btn ${modelFilter === `installed` ? `active` : ``}`}
            onClick={() => setModelFilter(`installed`)}
          >
            {`No HD `}
            <div className={`filter-count`}>{ollamaModels.length}</div>
          </button>
          <button
            type="button"
            className={`native-filter-btn ${modelFilter === `recommended` ? `active` : ``}`}
            onClick={() => setModelFilter(`recommended`)}
          >
            <Star size={11} className={modelFilter === `recommended` ? `brand-purple-icon` : ``} />
            {`Recomendados`}
          </button>
        </div>
        <form className={`native-pull-form`} onSubmit={handleSearchSubmit}>
          <input
            type={`text`}
            className={`native-pull-input`}
            placeholder={`Baixar do Ollama...`}
            value={modelSearchQuery}
            onChange={(e) => setModelSearchQuery(e.target.value)}
          />
          <button
            type={`submit`}
            className={`btn-pull-submit`}
            disabled={!modelSearchQuery.trim()}
            title={`Baixar modelo`}
          >
            <Download size={11} />
          </button>
        </form>
        <div className={`custom-active-selector-wrap`} ref={activeSelectorRef}>
          {(() => {
            const isAnyModelOnDisk = Array.isArray(ollamaModels) && ollamaModels.length > 0;
            const isSelectedModelOnDisk = isAnyModelOnDisk && ollamaModels.some((m) => {
              const mName = typeof m === 'string' ? m : m?.name;
              return mName === userSettings.transPol || (mName && userSettings.transPol && mName.split(':')[0] === userSettings.transPol.split(':')[0]);
            });

            const found = allModels.find((m) => m.name === userSettings.transPol);
            const modelDisplayName = found ? found.title : (userSettings.transPol ? userSettings.transPol.split(':')[0] : 'Selecionar');

            let dotClass = 'inactive';
            let pillLabel = 'Disco:';
            let pillVal = 'Nenhum baixado';
            let pillTitle = 'Nenhum modelo Ollama baixado no disco.';

            if (!isAnyModelOnDisk) {
              dotClass = 'inactive';
              pillLabel = 'Disco:';
              pillVal = 'Nenhum baixado';
              pillTitle = 'Nenhum modelo Ollama baixado no disco.';
            } else if (isSelectedModelOnDisk) {
              dotClass = 'ready';
              pillLabel = 'Ativo:';
              pillVal = modelDisplayName;
              pillTitle = `Modelo ativo para tradução: ${userSettings.transPol}`;
            } else {
              dotClass = 'warning';
              pillLabel = 'Pendente:';
              pillVal = modelDisplayName;
              pillTitle = `O modelo selecionado (${userSettings.transPol || 'nenhum'}) não está baixado. Selecione um modelo em disco.`;
            }

            return (
              <button
                type="button"
                className={`active-model-pill-trigger ${isActiveSelectorOpen ? 'open' : ''}`}
                onClick={() => setIsActiveSelectorOpen((prev) => !prev)}
                disabled={!isAnyModelOnDisk}
                title={pillTitle}
              >
                <div className={`active-status-dot ${dotClass}`} />
                <span className={`active-pill-label`}>{pillLabel}</span>
                <span className={`active-pill-val`}>{pillVal}</span>
                <ChevronDown size={12} className={`active-chevron ${isActiveSelectorOpen ? 'rotate' : ''}`} />
              </button>
            );
          })()}

          {isActiveSelectorOpen && (
            <div className={`active-model-dropdown-menu`}>
              <div className={`dropdown-menu-header`}>
                <span>{`Modelo Padrão para Tradução`}</span>
              </div>
              <div className={`dropdown-menu-list`}>
                {ollamaModels.length === 0 ? (
                  <div className={`dropdown-empty-state`}>{`Nenhum modelo instalado localmente.`}</div>
                ) : (
                  ollamaModels.map((modelName) => {
                    const modelObj = allModels.find((m) => m.name === modelName);
                    const isQwen = modelName.toLowerCase().includes('qwen');
                    const theme = modelObj?.iconTheme || (isQwen ? 'qwen' : 'custom');
                    const title = modelObj ? modelObj.title : modelName.split(':')[0];
                    const isSelected = userSettings.transPol === modelName;
                    return (
                      <button
                        key={modelName}
                        type="button"
                        className={`dropdown-model-item ${isSelected ? 'selected' : ''}`}
                        onClick={() => {
                          setUserSettings({
                            ...userSettings,
                            transPol: modelName,
                          });
                          setIsActiveSelectorOpen(false);
                        }}
                      >
                        <div className={`dropdown-item-left`}>
                          <div className={`dropdown-item-icon-box ${theme}`}>
                            <ModelLogo theme={theme} />
                          </div>
                          <div className={`dropdown-item-texts`}>
                            <span className={`dropdown-item-name`}>{title}</span>
                            <span className={`dropdown-item-sub`}>{modelName}</span>
                          </div>
                        </div>
                        {isSelected && <Check size={14} className={`dropdown-check-icon`} />}
                      </button>
                    );
                  })
                )}
              </div>
            </div>
          )}
        </div>
      </div>
      <div className={`native-models-grid`}>
        {filteredModels.map((model) => {
          const isDownloaded = ollamaModels.some(
            (dl) => dl === model.name || (model.pullTarget && (dl === model.pullTarget || dl === model.pullTarget.replace(/^hf\.co\//, "")))
          );
          const isActiveModel = isDownloaded && (
            userSettings.transPol === model.name || (model.pullTarget && userSettings.transPol === model.pullTarget)
          );
          const downloadInfo = ollamaModelsTags[model.name] || (model.pullTarget ? ollamaModelsTags[model.pullTarget] : null) || {};
          const isDownloading = Boolean(
            downloadInfo &&
              downloadInfo.progress !== undefined &&
              downloadInfo.status !== `installed` &&
              downloadInfo.status !== `completed` &&
              downloadInfo.status !== `success` &&
              !isDownloaded
          );
          const suitability = getModelSuitability(model.vramNum || 8);
          const displaySize = (isDownloaded && ollamaModelsDetails?.[model.name]?.sizeFormatted)
            ? ollamaModelsDetails[model.name].sizeFormatted
            : model.sizeEst;
          return (
            <div
              key={model.name}
              className={`native-model-card ${isActiveModel ? `active-model` : ``} ${isDownloaded ? `installed-model` : ``}`}
            >
              <div className={`model-card-header`}>
                <div className={`model-brand-icon ${model.iconTheme}`}>
                  <ModelLogo theme={model.iconTheme} />
                </div>
                <div className={`model-card-titles`}>
                  <div className={`model-name-title`}>{model.title}</div>
                  <div className={`model-version-sub`}>
                    {model.version}
                    {` · `}
                    {model.developer || `Ollama`}
                  </div>
                </div>
                <div className={`model-badge-slot`}>
                  {isDownloading ? (
                    <div className={`badge-downloading-tag`}>
                      <span className={`dl-pulse-dot`} />
                      {(downloadInfo.progress || 0) >= 99
                        ? `Instalando`
                        : `${Math.min(100, Math.max(0, downloadInfo.progress || 0)).toFixed(0)}%`}
                    </div>
                  ) : isDownloaded ? (
                    <div className={`badge-installed-tag`}>
                      <CheckCircle2 size={10} />
                      {` No HD`}
                    </div>
                  ) : (
                    <div className={`badge-available-tag`}>{`Disponível`}</div>
                  )}
                </div>
              </div>
              <div className={`model-desc-snippet`} title={model.desc}>
                {model.desc}
              </div>
              <div className={`model-meta-strip`}>
                <div className={`meta-size-chip`}>{displaySize}</div>
                <div className={`meta-vram-chip`}>{model.vram || model.vramReq}</div>
                <div
                  className={`meta-compat-tag ${suitability.type}`}
                  title={suitability.desc}
                >
                  {suitability.label}
                </div>
              </div>
              <div className={`model-card-footer`}>
                {isDownloading ? (
                  <div className={`model-telemetry-block`}>
                    <div className={`telemetry-meta-row`}>
                      <span className={`telemetry-text`} title={downloadInfo.text || ""}>
                        {formatDownloadTelemetry({
                          progress: downloadInfo.progress || 0,
                          speed_mbps: downloadInfo.speed_mbps || 0,
                          eta_seconds: downloadInfo.eta_seconds || 0,
                          downloaded_bytes: downloadInfo.downloaded_bytes || 0,
                          total_bytes: downloadInfo.total_bytes || 0,
                          text: downloadInfo.text || "",
                          fallbackSize: model.sizeEst || displaySize,
                        })}
                      </span>
                      <button
                        type="button"
                        onClick={() => cancelOllamaDownload(model.name)}
                        className={`btn-cancel-dl-subtle`}
                        title={`Cancelar download`}
                        aria-label={`Cancelar download`}
                      >
                        <X size={11} />
                      </button>
                    </div>
                    <div className={`sober-progress-track`}>
                      <div
                        className={`sober-progress-fill`}
                        style={{
                          width: `${Math.min(100, Math.max(2, downloadInfo.progress || 0))}%`,
                        }}
                      />
                    </div>
                  </div>
                ) : isDownloaded ? (
                  <div className={`model-action-buttons`}>
                    {isActiveModel ? (
                      <div className={`in-use-indicator`}>
                        <Check size={11} />
                        {` Em Uso`}
                      </div>
                    ) : (
                      <button
                        type="button"
                        className={`btn-model-action use`}
                        onClick={() =>
                          setUserSettings({
                            ...userSettings,
                            transPol: model.name,
                          })
                        }
                        title={`Definir como modelo ativo do estúdio`}
                      >
                        {`Usar`}
                      </button>
                    )}
                    <button
                      type="button"
                      className={`btn-icon-trash-subtle`}
                      onClick={() => setPendingDeleteModel(model)}
                      title={`Remover modelo do disco`}
                    >
                      <Trash2 size={11} />
                    </button>
                  </div>
                ) : (
                  <div className={`model-download-row`}>
                    <button
                      type="button"
                      className={`btn-model-action download`}
                      onClick={() => pullOllamaModel(model.name)}
                      title={`Baixar modelo do Ollama`}
                    >
                      <Download size={11} />
                      {` Baixar Modelo`}
                    </button>
                    <div
                      className={`info-tooltip-wrap`}
                      title={`${model.desc}\n\nDesenvolvedor: ${model.developer}\nQualidade: ${model.qualityScore}/5 | Velocidade: ${model.speedEst || `${model.speedScore}/5`}`}
                    >
                      <Info size={12} className={`text-muted`} />
                    </div>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <ConfirmModal
        isOpen={Boolean(pendingDeleteModel)}
        title="Remover Modelo do Disco?"
        message={`Deseja excluir permanentemente o modelo "${pendingDeleteModel?.title || pendingDeleteModel?.name}" (${pendingDeleteModel?.sizeEst || ''})? O arquivo será apagado do Ollama e precisará ser baixado novamente caso queira usá-lo.`}
        confirmText="Excluir Definitivamente"
        cancelText="Cancelar"
        onConfirm={() => {
          if (pendingDeleteModel) {
            const delName = pendingDeleteModel.name;
            const delBase = delName.includes(":") ? delName.split(":")[0] : delName;
            deleteOllamaModel(delName);
            const currentActive = userSettings?.transPol || "";
            const currentBase = currentActive.includes(":") ? currentActive.split(":")[0] : currentActive;
            if (currentActive === delName || currentBase === delBase) {
              const remaining = (ollamaModels || []).filter(
                (m) => m !== delName && m !== `${delBase}:latest` && m !== delBase && (typeof m === 'string' ? m.split(':')[0] !== delBase : true)
              );
              const nextActive = remaining.length > 0 ? (typeof remaining[0] === 'string' ? remaining[0] : remaining[0]?.name || "") : "";
              if (setUserSettings) {
                setUserSettings((prev) => ({
                  ...prev,
                  transPol: nextActive,
                  corr: nextActive,
                  trans: nextActive,
                }));
              }
            }
            setPendingDeleteModel(null);
          }
        }}
        onClose={() => setPendingDeleteModel(null)}
      />
    </div>
  );
});

export default TranslationModelsGrid;
