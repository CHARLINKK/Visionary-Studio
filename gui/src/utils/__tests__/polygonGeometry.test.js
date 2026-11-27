import { describe, it, expect } from "vitest";
import {
  perpendicularDistance,
  rdp,
  simplifyPolygon,
  scalePolygon,
  computeBboxFromPolygon,
  elasticDeformPolygon,
  inflatePolygon,
} from "../polygonGeometry";

describe("polygonGeometry utility", () => {
  it("computes perpendicular distance accurately", () => {
    const p1 = [0, 0];
    const p2 = [10, 0];
    const p = [5, 5];
    expect(perpendicularDistance(p, p1, p2)).toBeCloseTo(5);
  });

  it("simplifies straight line segments with RDP", () => {
    const line = [
      [0, 0],
      [1, 0.1],
      [2, 0],
      [3, -0.1],
      [10, 0],
    ];
    const simplified = rdp(line, 1.0);
    expect(simplified.length).toBe(2);
    expect(simplified[0]).toEqual([0, 0]);
    expect(simplified[1]).toEqual([10, 0]);
  });

  it("simplifies a dense polygon (20 points) into 4-8 master anchors", () => {
    // Cria elipse com 20 pontos
    const denseEllipse = [];
    const cx = 100, cy = 100, rx = 50, ry = 80;
    for (let i = 0; i < 20; i++) {
      const angle = (i / 20) * 2 * Math.PI;
      denseEllipse.push([
        Math.round(cx + rx * Math.cos(angle)),
        Math.round(cy + ry * Math.sin(angle)),
      ]);
    }

    const simplified = simplifyPolygon(denseEllipse, 0.05, 4, 10);
    expect(simplified.length).toBeGreaterThanOrEqual(4);
    expect(simplified.length).toBeLessThan(denseEllipse.length);
  });

  it("scales polygon proportionally when bounding box changes", () => {
    const poly = [
      [10, 10],
      [20, 10],
      [20, 30],
      [10, 30],
    ];
    const oldBbox = { x1: 10, y1: 10, x2: 20, y2: 30 };
    // Dobra o tamanho
    const newBbox = { x1: 10, y1: 10, x2: 30, y2: 50 };

    const scaled = scalePolygon(poly, oldBbox, newBbox);
    expect(scaled[0]).toEqual([10, 10]);
    expect(scaled[1]).toEqual([30, 10]);
    expect(scaled[2]).toEqual([30, 50]);
    expect(scaled[3]).toEqual([10, 50]);
  });

  it("computes tight bounding box from polygon vertices", () => {
    const poly = [
      [120, 45],
      [200, 100],
      [80, 150],
      [95, 20],
    ];
    const bbox = computeBboxFromPolygon(poly);
    expect(bbox).toEqual({
      x1: 80,
      y1: 20,
      x2: 200,
      y2: 150,
    });
  });

  it("deforms polygon boundaries elastically, anchoring the opposite edge", () => {
    // Balão retangular de (0, 0) até (100, 100)
    const poly = [
      [20, 10],   // Perto do topo
      [80, 10],   // Perto do topo
      [80, 100],  // Borda inferior (ancorada)
      [20, 100],  // Borda inferior (ancorada)
    ];
    const oldBbox = { x1: 0, y1: 0, x2: 100, y2: 100 };
    // Puxa o topo para cima em -20px (y1: -20)
    const newBbox = { x1: 0, y1: -20, x2: 100, y2: 100 };

    const deformed = elasticDeformPolygon(poly, oldBbox, newBbox);
    // Pontos do topo devem subir consideravelmente
    expect(deformed[0][1]).toBeLessThan(0);
    expect(deformed[1][1]).toBeLessThan(0);
    // Pontos da borda oposta devem permanecer 100% ancorados
    expect(deformed[2][1]).toBe(100);
    expect(deformed[3][1]).toBe(100);
    // Coordenadas X não devem ter mudado
    expect(deformed[0][0]).toBe(20);
    expect(deformed[1][0]).toBe(80);
  });

  it("inflates polygon radially from center", () => {
    const poly = [
      [10, 10],
      [90, 10],
      [90, 90],
      [10, 90],
    ];
    const inflated = inflatePolygon(poly, 10);
    // Centro é (50, 50). Top-left (10, 10) deve se afastar do centro (valores menores)
    expect(inflated[0][0]).toBeLessThan(10);
    expect(inflated[0][1]).toBeLessThan(10);
    // Bottom-right (90, 90) deve se afastar (valores maiores)
    expect(inflated[2][0]).toBeGreaterThan(90);
    expect(inflated[2][1]).toBeGreaterThan(90);
  });

  it("handles null or empty inputs gracefully", () => {
    expect(scalePolygon(null, {}, {})).toBeNull();
    expect(simplifyPolygon([])).toEqual([]);
    expect(computeBboxFromPolygon(null)).toEqual({ x1: 0, y1: 0, x2: 0, y2: 0 });
    expect(elasticDeformPolygon(null, {}, {})).toBeNull();
    expect(inflatePolygon(null, 5)).toEqual([]);
  });
});
