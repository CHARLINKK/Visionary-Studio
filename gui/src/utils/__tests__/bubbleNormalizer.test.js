import { describe, it, expect } from 'vitest';
import {
  reindexBubbleOrders,
  resolveBubbleBadgeLabel,
  normalizeInspectorBubble,
  hasBubbleMoved,
  isBubbleSfx,
  getBubbleText,
  getBubbleTranslation,
  getBubbleAiTranslation,
  getBubbleGroupId,
  stripBubbleGroupId,
  toggleBubbleSfxState,
} from '../bubbleNormalizer';

describe('bubbleNormalizer', () => {
  describe('reindexBubbleOrders', () => {
    it('returns empty array when input is not an array', () => {
      expect(reindexBubbleOrders(null)).toEqual([]);
      expect(reindexBubbleOrders(undefined)).toEqual([]);
      expect(reindexBubbleOrders('not-an-array')).toEqual([]);
    });

    it('indexes speech bubbles sequentially 1..N', () => {
      const boxes = [
        { id: 'b1', text: 'Hello' },
        { id: 'b2', text: 'World' },
      ];
      const reindexed = reindexBubbleOrders(boxes);
      expect(reindexed[0].order).toBe(1);
      expect(reindexed[1].order).toBe(2);
      expect(reindexed[0].id).toBe('b1');
      expect(reindexed[1].id).toBe('b2');
    });

    it('preserves order: null for SFX boxes and continues sequence for speech', () => {
      const boxes = [
        { id: 'b1', text: 'Boom', is_sfx: true },
        { id: 'b2', text: 'Did you hear that?' },
        { id: 'b3', text: 'Slash', isSfx: true },
        { id: 'b4', text: 'Watch out!', bg_type: 'dialogue' },
        { id: 'b5', text: 'Kaboom', bg_type: 'sfx' },
      ];
      const reindexed = reindexBubbleOrders(boxes);
      expect(reindexed[0].order).toBeNull();
      expect(reindexed[1].order).toBe(1);
      expect(reindexed[2].order).toBeNull();
      expect(reindexed[3].order).toBe(2);
      expect(reindexed[4].order).toBeNull();
    });
  });

  describe('resolveBubbleBadgeLabel', () => {
    it('identifies SFX correctly', () => {
      expect(resolveBubbleBadgeLabel({ is_sfx: true })).toBe('SFX');
      expect(resolveBubbleBadgeLabel({ isSfx: true })).toBe('SFX');
      expect(resolveBubbleBadgeLabel({ label: 'sfx_sound' })).toBe('SFX');
    });

    it('identifies bubble, free and tool correctly', () => {
      expect(resolveBubbleBadgeLabel({ label: 'speech_bubble' })).toBe('BUBBLE');
      expect(resolveBubbleBadgeLabel({ is_bubble: true })).toBe('BUBBLE');
      expect(resolveBubbleBadgeLabel({ label: 'text_free' })).toBe('FREE');
      expect(resolveBubbleBadgeLabel({ label: 'tool_call' })).toBe('TOOL');
      expect(resolveBubbleBadgeLabel({ label: 'unknown' })).toBe('BOX');
    });
  });

  describe('normalizeInspectorBubble', () => {
    it('normalizes basic bubble text and flags', () => {
      const res = normalizeInspectorBubble({
        text: 'Hello',
        translated: 'Olá',
        ai_translated: 'Olá',
      });
      expect(res.text).toBe('Hello');
      expect(res.translated).toBe('Olá');
      expect(res.isEdited).toBe(false);
      expect(res.isDeleted).toBe(false);
      expect(res.badgeLabel).toBe('BOX');
    });

    it('flags edited bubble when user edits translation', () => {
      const res = normalizeInspectorBubble({
        text: 'Hello',
        translated: 'E aí',
        ai_translated: 'Olá',
      });
      expect(res.isEdited).toBe(true);
    });

    it('flags deleted bubble when marked with [DELETE]', () => {
      const res = normalizeInspectorBubble({
        text: '[DELETE]',
        translated: '',
      });
      expect(res.isDeleted).toBe(true);
    });

    it('reports hasMoved correctly in normalizeInspectorBubble', () => {
      const unmoved = normalizeInspectorBubble({
        x1: 10, y1: 10, x2: 50, y2: 50,
        initial_box: [10, 10, 50, 50],
      });
      expect(unmoved.hasMoved).toBe(false);

      const moved = normalizeInspectorBubble({
        x1: 20, y1: 10, x2: 60, y2: 50,
        initial_box: [10, 10, 50, 50],
      });
      expect(moved.hasMoved).toBe(true);
    });
  });

  describe('hasBubbleMoved', () => {
    it('returns false when bubble is falsy or has no valid initial_box', () => {
      expect(hasBubbleMoved(null)).toBe(false);
      expect(hasBubbleMoved({})).toBe(false);
      expect(hasBubbleMoved({ x1: 10, y1: 20 })).toBe(false);
      expect(hasBubbleMoved({ x1: 10, initial_box: [10, 20] })).toBe(false);
    });

    it('returns false when coordinates and polygon match initial_box and initial_polygon', () => {
      const box = {
        x1: 100, y1: 150, x2: 300, y2: 400,
        initial_box: [100, 150, 300, 400],
        polygon: [[100, 150], [300, 150], [300, 400], [100, 400]],
        initial_polygon: [[100, 150], [300, 150], [300, 400], [100, 400]],
      };
      expect(hasBubbleMoved(box)).toBe(false);
    });

    it('returns true when coordinates differ from initial_box', () => {
      const box = {
        x1: 105, y1: 150, x2: 305, y2: 400,
        initial_box: [100, 150, 300, 400],
      };
      expect(hasBubbleMoved(box)).toBe(true);
    });

    it('returns true when polygon differs from initial_polygon', () => {
      const box = {
        x1: 100, y1: 150, x2: 300, y2: 400,
        initial_box: [100, 150, 300, 400],
        polygon: [[100, 150], [310, 150], [300, 400], [100, 400]],
        initial_polygon: [[100, 150], [300, 150], [300, 400], [100, 400]],
      };
      expect(hasBubbleMoved(box)).toBe(true);
    });
  });

  describe('canonical bubble contract helpers', () => {
    it('isBubbleSfx unifies is_sfx, isSfx, bg_type and label', () => {
      expect(isBubbleSfx(null)).toBe(false);
      expect(isBubbleSfx({})).toBe(false);
      expect(isBubbleSfx({ is_sfx: true })).toBe(true);
      expect(isBubbleSfx({ isSfx: true })).toBe(true);
      expect(isBubbleSfx({ bg_type: 'sfx' })).toBe(true);
      expect(isBubbleSfx({ label: 'sfx_onomatopoeia' })).toBe(true);
      expect(isBubbleSfx({ label: 'text_bubble', bg_type: 'white' })).toBe(false);
    });

    it('getBubbleText and getBubbleTranslation unify canonical and legacy fields', () => {
      expect(getBubbleText({ text: 'Hello' })).toBe('Hello');
      expect(getBubbleText({ original: 'Original EN' })).toBe('Original EN');
      expect(getBubbleText({ ocr_raw: 'Raw OCR' })).toBe('Raw OCR');
      expect(getBubbleText({ original: { text: 'Nested EN' } })).toBe('Nested EN');

      expect(getBubbleTranslation({ translated: 'Olá' })).toBe('Olá');
      expect(getBubbleTranslation({ translated_text: 'Olá legado' })).toBe('Olá legado');
      expect(getBubbleTranslation({ text_ptbr: 'Olá v2' })).toBe('Olá v2');
      expect(getBubbleTranslation({ translated: { text: 'Olá objeto' } })).toBe('Olá objeto');
    });

    it('getBubbleAiTranslation handles object, string and unedited fallback', () => {
      expect(getBubbleAiTranslation({ ai_translated: 'IA 1' })).toBe('IA 1');
      expect(getBubbleAiTranslation({ ai_translated_text: 'IA 2' })).toBe('IA 2');
      expect(getBubbleAiTranslation({ ai_translated: { text: 'IA Obj' } })).toBe('IA Obj');
      expect(getBubbleAiTranslation({ translated_text: 'Auto', user_edited: false })).toBe('Auto');
      expect(getBubbleAiTranslation({ translated_text: 'Manual', user_edited: true })).toBe('');
    });

    it('getBubbleGroupId and stripBubbleGroupId handle both group_id and groupId', () => {
      expect(getBubbleGroupId({ group_id: 'g1' })).toBe('g1');
      expect(getBubbleGroupId({ groupId: 'g2' })).toBe('g2');
      expect(getBubbleGroupId({})).toBeNull();

      const stripped = stripBubbleGroupId({ id: 1, group_id: 'g1', groupId: 'g1', text: 'Hi' });
      expect(stripped).toEqual({ id: 1, text: 'Hi' });
      expect('group_id' in stripped).toBe(false);
      expect('groupId' in stripped).toBe(false);
    });

    it('toggleBubbleSfxState synchronizes canonical and legacy SFX fields', () => {
      const asSfx = toggleBubbleSfxState({ id: 'b1', is_sfx: false });
      expect(asSfx.is_sfx).toBe(true);
      expect(asSfx.isSfx).toBe(true);
      expect(asSfx.is_bubble).toBe(false);
      expect(asSfx.bg_type).toBe('sfx');
      expect(asSfx.label).toBe('text_free');
      expect(asSfx.user_edited).toBe(true);

      const asSpeech = toggleBubbleSfxState(asSfx);
      expect(asSpeech.is_sfx).toBe(false);
      expect(asSpeech.isSfx).toBe(false);
      expect(asSpeech.is_bubble).toBe(true);
      expect(asSpeech.bg_type).toBe('white');
      expect(asSpeech.label).toBe('text_bubble');
    });
  });
});
