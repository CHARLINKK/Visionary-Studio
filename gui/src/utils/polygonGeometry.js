/**
 * Utilitários matemáticos e geométricos para polígonos de balões (Visionary Studio).
 * Inclui:
 * 1. Escalonamento proporcional (scalePolygon) para esticar contornos junto com a bounding box.
 * 2. Simplificação Douglas-Peucker (RDP) para converter 20-30 vértices da IA em 6-8 nós mestres.
 * 3. Cálculo de bounding box a partir de vértices arbitrários.
 */

/**
 * Distância perpendicular de um ponto P até o segmento de reta formado por P1 e P2.
 * @param {[number, number]} p
 * @param {[number, number]} p1
 * @param {[number, number]} p2
 * @returns {number}
 */
export function perpendicularDistance(p, p1, p2) {
  const dx = p2[0] - p1[0];
  const dy = p2[1] - p1[1];
  const mag = Math.hypot(dx, dy);
  if (mag === 0) return Math.hypot(p[0] - p1[0], p[1] - p1[1]);
  return Math.abs(dy * p[0] - dx * p[1] + p2[0] * p1[1] - p2[1] * p1[0]) / mag;
}

/**
 * Algoritmo Ramer-Douglas-Peucker (RDP) clássico para simplificação de polilinhas.
 * @param {Array<[number, number]>} points
 * @param {number} epsilon
 * @returns {Array<[number, number]>}
 */
export function rdp(points, epsilon) {
  if (!points || points.length <= 2) return points ? [...points] : [];
  let maxDist = 0;
  let index = 0;
  const last = points.length - 1;

  for (let i = 1; i < last; i++) {
    const dist = perpendicularDistance(points[i], points[0], points[last]);
    if (dist > maxDist) {
      maxDist = dist;
      index = i;
    }
  }

  if (maxDist > epsilon) {
    const left = rdp(points.slice(0, index + 1), epsilon);
    const right = rdp(points.slice(index), epsilon);
    return left.slice(0, left.length - 1).concat(right);
  }
  return [points[0], points[last]];
}

/**
 * Simplifica um polígono fechado preservando os cantos mais salientes (âncoras mestres).
 * @param {Array<[number, number]>} polygon
 * @param {number} [epsilonPercent=0.035] - Tolerância em porcentagem da diagonal do balão (~3.5%)
 * @param {number} [minPoints=4]
 * @param {number} [maxPoints=10]
 * @returns {Array<[number, number]>}
 */
export function simplifyPolygon(polygon, epsilonPercent = 0.035, minPoints = 4, _maxPoints = 10) {
  if (!polygon || !Array.isArray(polygon) || polygon.length <= minPoints) {
    return polygon ? polygon.map((pt) => [...pt]) : [];
  }

  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;

  for (const [x, y] of polygon) {
    if (x < minX) minX = x;
    if (x > maxX) maxX = x;
    if (y < minY) minY = y;
    if (y > maxY) maxY = y;
  }

  const diag = Math.hypot(maxX - minX, maxY - minY);
  const epsPx = Math.max(3, diag * epsilonPercent);

  // Divide o anel fechado em duas metades para não achatar o início/fim
  const half = Math.floor(polygon.length / 2);
  const part1 = rdp(polygon.slice(0, half + 1), epsPx);
  const part2 = rdp(polygon.slice(half).concat([polygon[0]]), epsPx);

  let result = part1.slice(0, -1).concat(part2.slice(0, -1));

  // Remove pontos idênticos consecutivos
  result = result.filter((pt, i) => {
    const prev = result[(i - 1 + result.length) % result.length];
    return Math.hypot(pt[0] - prev[0], pt[1] - prev[1]) > 2;
  });

  if (result.length < minPoints) {
    const step = Math.max(1, Math.floor(polygon.length / 6));
    return polygon.filter((_, idx) => idx % step === 0);
  }

  return result;
}

/**
 * Escala proporcionalmente as coordenadas de um polígono quando a BBox é redimensionada.
 * Permite esticar a caixa de seleção e o contorno orgânico acompanhar perfeitamente.
 * @param {Array<[number, number]>} polygon
 * @param {{ x1: number, y1: number, x2: number, y2: number }} oldBbox
 * @param {{ x1: number, y1: number, x2: number, y2: number }} newBbox
 * @returns {Array<[number, number]>}
 */
export function scalePolygon(polygon, oldBbox, newBbox) {
  if (!polygon || !Array.isArray(polygon) || polygon.length === 0) return polygon;
  const { x1: ox1, y1: oy1, x2: ox2, y2: oy2 } = oldBbox;
  const { x1: nx1, y1: ny1, x2: nx2, y2: ny2 } = newBbox;

  const oldW = Math.max(1, ox2 - ox1);
  const oldH = Math.max(1, oy2 - oy1);
  const newW = Math.max(1, nx2 - nx1);
  const newH = Math.max(1, ny2 - ny1);

  return polygon.map(([px, py]) => {
    const normX = (px - ox1) / oldW;
    const normY = (py - oy1) / oldH;
    return [
      Math.round(nx1 + normX * newW),
      Math.round(ny1 + normY * newH),
    ];
  });
}

/**
 * Deforma elasticamente as bordas de um polígono com atenuação direcional suave (Padrão Ouro).
 * Ao puxar o topo, somente os pontos superiores sobem; o fundo e a cauda permanecem ancorados.
 * @param {Array<[number, number]>} polygon
 * @param {{ x1: number, y1: number, x2: number, y2: number }} oldBbox
 * @param {{ x1: number, y1: number, x2: number, y2: number }} newBbox
 * @returns {Array<[number, number]>}
 */
export function elasticDeformPolygon(polygon, oldBbox, newBbox) {
  if (!polygon || !Array.isArray(polygon) || polygon.length === 0) return polygon;
  const { x1: ox1, y1: oy1, x2: ox2, y2: oy2 } = oldBbox;
  const { x1: nx1, y1: ny1, x2: nx2, y2: ny2 } = newBbox;

  const dx1 = nx1 - ox1; // movimento da borda esquerda
  const dx2 = nx2 - ox2; // movimento da borda direita
  const dy1 = ny1 - oy1; // movimento da borda superior
  const dy2 = ny2 - oy2; // movimento da borda inferior

  // Se nada moveu, retorna cópia idêntica
  if (dx1 === 0 && dx2 === 0 && dy1 === 0 && dy2 === 0) {
    return polygon.map((pt) => [...pt]);
  }

  const oldW = Math.max(1, ox2 - ox1);
  const oldH = Math.max(1, oy2 - oy1);

  return polygon.map(([px, py]) => {
    const u = Math.max(0, Math.min(1, (px - ox1) / oldW));
    const v = Math.max(0, Math.min(1, (py - oy1) / oldH));

    // Pesos com atenuação suave exponencial (preserva a cauda oposta estável)
    const wLeft = Math.pow(1 - u, 1.25);
    const wRight = Math.pow(u, 1.25);
    const wTop = Math.pow(1 - v, 1.25);
    const wBottom = Math.pow(v, 1.25);

    const newX = Math.round(px + dx1 * wLeft + dx2 * wRight);
    const newY = Math.round(py + dy1 * wTop + dy2 * wBottom);
    return [newX, newY];
  });
}

/**
 * Expande ou contrai uniformemente o polígono em relação ao seu centro geométrico (+/- deltaPx).
 * Permite adicionar margem de segurança de OCR com 1 único clique no inspetor.
 * @param {Array<[number, number]>} polygon
 * @param {number} deltaPx
 * @returns {Array<[number, number]>}
 */
export function inflatePolygon(polygon, deltaPx) {
  if (!polygon || !Array.isArray(polygon) || polygon.length === 0 || !deltaPx) {
    return polygon ? polygon.map((pt) => [...pt]) : [];
  }

  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;

  for (const [x, y] of polygon) {
    if (x < minX) minX = x;
    if (x > maxX) maxX = x;
    if (y < minY) minY = y;
    if (y > maxY) maxY = y;
  }

  const cx = (minX + maxX) / 2;
  const cy = (minY + maxY) / 2;

  return polygon.map(([px, py]) => {
    const dx = px - cx;
    const dy = py - cy;
    const dist = Math.hypot(dx, dy);
    if (dist === 0) return [px, py];
    return [
      Math.round(px + (dx / dist) * deltaPx),
      Math.round(py + (dy / dist) * deltaPx),
    ];
  });
}

/**
 * Calcula a bounding box mínima envolvente para uma lista de vértices.
 * @param {Array<[number, number]>} polygon
 * @returns {{ x1: number, y1: number, x2: number, y2: number }}
 */
export function computeBboxFromPolygon(polygon) {
  if (!polygon || !Array.isArray(polygon) || polygon.length === 0) {
    return { x1: 0, y1: 0, x2: 0, y2: 0 };
  }
  let x1 = Infinity;
  let y1 = Infinity;
  let x2 = -Infinity;
  let y2 = -Infinity;

  for (const [x, y] of polygon) {
    if (x < x1) x1 = x;
    if (x > x2) x2 = x;
    if (y < y1) y1 = y;
    if (y > y2) y2 = y;
  }

  return {
    x1: Math.round(x1),
    y1: Math.round(y1),
    x2: Math.round(x2),
    y2: Math.round(y2),
  };
}
