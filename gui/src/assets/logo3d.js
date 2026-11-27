export const LOGO_3D_BASE64 = `data:image/svg+xml;utf8,<svg width="100%" height="100%" viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="vgrad1" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:%23c4b5fd;stop-opacity:1" />
      <stop offset="100%" style="stop-color:%237c3aed;stop-opacity:1" />
    </linearGradient>
    <linearGradient id="vgrad2" x1="100%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:%23a78bfa;stop-opacity:1" />
      <stop offset="100%" style="stop-color:%235b21b6;stop-opacity:1" />
    </linearGradient>
  </defs>
  <!-- Outer V -->
  <path d="M2 4 L14 28 L18 28 L30 4 L24 4 L16 20 L8 4 Z" fill="url(%23vgrad1)"/>
  <!-- Inner overlapping V to create the 3D layered look -->
  <path d="M8 4 L16 22 L24 4 L19 4 L16 13 L13 4 Z" fill="url(%23vgrad2)"/>
</svg>`;
