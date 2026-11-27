import { create } from 'zustand';

export const useLibraryViewerStore = create((set, get) => ({
  // Viewer UI State
  zoomScale: 1,
  panPos: { x: 0, y: 0 },
  isPanning: false,
  autoZoomEnabled: (() => {
    try {
      let val = localStorage.getItem(`visionary_auto_zoom`);
      return val !== null && val === `true`;
    } catch {
      return false;
    }
  })(),
  showMarkers: true,
  hideEnglish: (() => {
    try {
      return localStorage.getItem(`visionary_library_hide_en`) === `true`;
    } catch {
      return false;
    }
  })(),
  activePageIndex: 0,
  imageSize: { width: 0, height: 0 },
  isImageLoading: false,
  imageError: false,
  activeSearchQuery: '',
  pageImages: [],
  currentImageIndex: 0,
  activeBlockId: null,
  zoomTargetRect: null,

  // Actions
  setZoomScale: (scale) => set({ zoomScale: typeof scale === 'function' ? scale(get().zoomScale) : scale }),
  setPanPos: (pos) => set({ panPos: typeof pos === 'function' ? pos(get().panPos) : pos }),
  setIsPanning: (is) => set({ isPanning: is }),
  setAutoZoomEnabled: (enabled) => {
    set({ autoZoomEnabled: enabled });
    try {
      localStorage.setItem(`visionary_auto_zoom`, JSON.stringify(enabled));
    } catch {}
  },
  setShowMarkers: (show) => set({ showMarkers: show }),
  setHideEnglish: (hide) => {
    set({ hideEnglish: hide });
    try {
      localStorage.setItem(`visionary_library_hide_en`, JSON.stringify(hide));
    } catch {}
  },
  setActivePageIndex: (idx) => set({ activePageIndex: typeof idx === 'function' ? idx(get().activePageIndex) : idx }),
  setImageSize: (size) => set({ imageSize: typeof size === 'function' ? size(get().imageSize) : size }),
  setIsImageLoading: (is) => set({ isImageLoading: is }),
  setImageError: (is) => set({ imageError: is }),
  setActiveSearchQuery: (query) => set({ activeSearchQuery: query }),
  setPageImages: (images) => set({ pageImages: images }),
  setCurrentImageIndex: (idx) => set({ currentImageIndex: typeof idx === 'function' ? idx(get().currentImageIndex) : idx }),
  setActiveBlockId: (id) => set({ activeBlockId: id }),
  setZoomTargetRect: (rect) => set({ zoomTargetRect: rect }),

  // High Level Actions
  resetZoom: () => set({ zoomScale: 1, panPos: { x: 0, y: 0 } })
}));
