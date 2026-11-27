import { Bubble, PageData } from './bubble';

export interface DirectoryItem {
  name: string;
  path: string;
  isImage?: boolean;
  isDirectory?: boolean;
  size?: number;
}

export interface ListDirectoryResult {
  items: DirectoryItem[];
  success?: boolean;
  error?: string;
}

export interface ApiRpcResult<T = any> {
  success: boolean;
  result?: T;
  error?: string;
  message?: string;
}

export interface ClientApi {
  getPageData(imagePath: string): Promise<PageData & { success?: boolean; error?: string }>;
  get_page_data(imagePath: string): Promise<PageData & { success?: boolean; error?: string }>;
  save_page_layout(imagePath: string, boxes: Bubble[], panels?: any[]): Promise<ApiRpcResult>;
  savePageLayout(imagePath: string, boxes: Bubble[], panels?: any[]): Promise<ApiRpcResult>;
  detect_page_bubbles(imagePath: string, whiteOnly?: boolean): Promise<ApiRpcResult>;
  detectPageBubbles(imagePath: string, whiteOnly?: boolean): Promise<ApiRpcResult>;
  listDirectory(path?: string): Promise<ListDirectoryResult>;
  list_directory(path?: string): Promise<ListDirectoryResult>;
  reorder_pages(chapterPath: string, filePaths: any[]): Promise<ApiRpcResult>;
  reorderPages(chapterPath: string, filePaths: any[]): Promise<ApiRpcResult>;
  merge_pages(chapterPath: string, leftImagePath: string, rightImagePath: string, direction?: string): Promise<ApiRpcResult>;
  mergePages(chapterPath: string, leftImagePath: string, rightImagePath: string, direction?: string): Promise<ApiRpcResult>;
  split_page(imagePath: string): Promise<ApiRpcResult>;
  splitPage(imagePath: string): Promise<ApiRpcResult>;
  delete_page(imagePath: string): Promise<ApiRpcResult>;
  deletePage(imagePath: string): Promise<ApiRpcResult>;
  clearPageData(imagePaths: string[], stages: string[]): Promise<ApiRpcResult>;
  clear_page_data(imagePaths: string[], stages: string[]): Promise<ApiRpcResult>;
  autoSortBoxes(imagePath: string, boxes: Bubble[]): Promise<ApiRpcResult>;
  auto_sort_boxes(imagePath: string, boxes: Bubble[]): Promise<ApiRpcResult>;
  [methodName: string]: (...args: any[]) => Promise<any>;
}

declare global {
  interface Window {
    pywebview?: {
      api?: ClientApi;
    };
  }
}
