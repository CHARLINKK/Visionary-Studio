import { describe, it, expect, vi, beforeEach } from 'vitest';
import { getServerUrl, setServerUrl, resolveInitialServerUrl, callRpc, clientApi, ServerEventBus, eventBus } from '../bridge';

describe('bridge universal client', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setServerUrl('http://127.0.0.1:5000');
  });

  it('should get and set server URL correctly', () => {
    expect(getServerUrl()).toBe('http://127.0.0.1:5000');
    setServerUrl('http://localhost:8080///');
    expect(getServerUrl()).toBe('http://localhost:8080');
  });

  it('should resolve synchronous loopback serverUrl query param and reject external URLs', () => {
    expect(resolveInitialServerUrl('?serverUrl=http%3A%2F%2F127.0.0.1%3A5012')).toBe('http://127.0.0.1:5012');
    expect(resolveInitialServerUrl('?serverUrl=http%3A%2F%2Flocalhost%3A5099%2F')).toBe('http://localhost:5099');
    expect(resolveInitialServerUrl('?serverUrl=https%3A%2F%2Fevil.example.com')).toBe('http://127.0.0.1:5000');
  });

  it('should dispatch callRpc with serialized payload and return result', async () => {
    const mockResponse = { success: true, result: { pages: ['001.png', '002.png'] } };
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockResponse,
    });

    const result = await callRpc('list_pages', 'chapter_1', { detailed: true });
    expect(global.fetch).toHaveBeenCalledWith(
      'http://127.0.0.1:5000/api/rpc/list_pages',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ args: ['chapter_1', { detailed: true }], kwargs: {} }),
      })
    );
    expect(result).toEqual({ pages: ['001.png', '002.png'] });
  });

  it('should throw when server returns HTTP error status', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
    });

    await expect(callRpc('fail_endpoint')).rejects.toThrow('HTTP 500: Internal Server Error');
    consoleSpy.mockRestore();
  });

  it('should throw when server response contains success: false and error payload', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ success: false, error: 'Database connection failed' }),
    });

    await expect(callRpc('faulty_rpc')).rejects.toThrow('Database connection failed');
    consoleSpy.mockRestore();
  });

  it('should route window operations to window.electronAPI via clientApi Proxy', () => {
    clientApi.minimize();
    expect(window.electronAPI.minimize).toHaveBeenCalled();

    clientApi.toggle_maximize();
    expect(window.electronAPI.toggleMaximize).toHaveBeenCalled();

    clientApi.close();
    expect(window.electronAPI.close).toHaveBeenCalled();
  });
});

describe('ServerEventBus', () => {
  let mockWsInstances = [];
  const originalWs = global.WebSocket;

  class MockWebSocket {
    static OPEN = 1;
    static CONNECTING = 0;
    static CLOSING = 2;
    static CLOSED = 3;

    constructor(url) {
      this.url = url;
      this.readyState = MockWebSocket.CONNECTING;
      this.send = vi.fn();
      this.close = vi.fn(() => {
        this.readyState = MockWebSocket.CLOSED;
        if (this.onclose) this.onclose();
      });
      mockWsInstances.push(this);
    }
  }

  beforeEach(() => {
    mockWsInstances = [];
    global.WebSocket = MockWebSocket;
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    global.WebSocket = originalWs;
  });

  it('should connect to ws://.../ws/logs and notify subscribers on message', () => {
    const bus = new ServerEventBus(1000);
    const callback = vi.fn();
    const unsubscribe = bus.subscribe(callback);

    expect(mockWsInstances.length).toBe(1);
    const ws = mockWsInstances[0];
    expect(ws.url).toBe('ws://127.0.0.1:5000/ws/logs');

    ws.readyState = MockWebSocket.OPEN;
    ws.onopen();

    ws.onmessage({ data: JSON.stringify({ type: 'progress', progress: 50 }) });
    expect(callback).toHaveBeenCalledWith({ type: 'progress', progress: 50 });

    unsubscribe();
    bus.cleanupSocket();
  });

  it('should handle "pong" response silently without error', () => {
    const bus = new ServerEventBus(1000);
    const callback = vi.fn();
    bus.subscribe(callback);

    const ws = mockWsInstances[0];
    ws.readyState = MockWebSocket.OPEN;
    ws.onopen();

    expect(() => ws.onmessage({ data: 'pong' })).not.toThrow();
    expect(callback).not.toHaveBeenCalled();
    bus.cleanupSocket();
  });

  it('should send ping on heartbeat interval and trigger reconnect on socket close', () => {
    const bus = new ServerEventBus(500);
    bus.subscribe(vi.fn());

    const ws = mockWsInstances[0];
    ws.readyState = MockWebSocket.OPEN;
    ws.onopen();

    vi.advanceTimersByTime(500);
    expect(ws.send).toHaveBeenCalledWith('ping');

    ws.onclose();
    expect(bus.heartbeatTimer).toBeNull();

    vi.advanceTimersByTime(2000);
    expect(mockWsInstances.length).toBe(2);
    bus.cleanupSocket();
  });

  it('should accurately report isConnected status based on readyState', () => {
    const bus = new ServerEventBus(1000);
    expect(bus.isConnected()).toBe(false);

    bus.connect();
    const ws = mockWsInstances[0];
    expect(bus.isConnected()).toBe(false); // CONNECTING

    ws.readyState = MockWebSocket.OPEN;
    expect(bus.isConnected()).toBe(true);

    ws.readyState = MockWebSocket.CLOSING;
    expect(bus.isConnected()).toBe(false);

    ws.readyState = MockWebSocket.CLOSED;
    expect(bus.isConnected()).toBe(false);

    bus.cleanupSocket();
    expect(bus.isConnected()).toBe(false);
  });

  it('should safely return false from isConnected if WebSocket is undefined', () => {
    const bus = new ServerEventBus(1000);
    const saved = global.WebSocket;
    try {
      delete global.WebSocket;
      expect(bus.isConnected()).toBe(false);
    } finally {
      global.WebSocket = saved;
    }
  });

  it('should expose isConnected method on singleton eventBus export', () => {
    expect(typeof eventBus.isConnected).toBe('function');
  });

  it('should dispatch downloads_progress custom_event payload to subscribers', () => {
    const bus = new ServerEventBus(1000);
    const callback = vi.fn();
    bus.subscribe(callback);

    const ws = mockWsInstances[0];
    ws.readyState = MockWebSocket.OPEN;
    ws.onopen();

    const dlPayload = {
      type: 'custom_event',
      event_name: 'downloads_progress',
      payload: {
        success: true,
        ollama: { 'qwen2.5:7b': { progress: 75, status: 'downloading' } },
        hf: { florence2: { progress: 100, status: 'installed' } },
      },
    };

    ws.onmessage({ data: JSON.stringify(dlPayload) });
    expect(callback).toHaveBeenCalledWith(dlPayload);
    bus.cleanupSocket();
  });

  it('should automatically reconnect eventBus to the new WebSocket port when setServerUrl changes', () => {
    const callback = vi.fn();
    const unsubscribe = eventBus.subscribe(callback);

    const initialWs = mockWsInstances[mockWsInstances.length - 1];
    expect(initialWs.url).toBe('ws://127.0.0.1:5000/ws/logs');

    // Altera a porta dinamicamente (ex: 5001)
    setServerUrl('http://127.0.0.1:5001');

    const updatedWs = mockWsInstances[mockWsInstances.length - 1];
    expect(updatedWs.url).toBe('ws://127.0.0.1:5001/ws/logs');
    expect(initialWs.close).toHaveBeenCalled();

    unsubscribe();
    eventBus.cleanupSocket();
  });
});

