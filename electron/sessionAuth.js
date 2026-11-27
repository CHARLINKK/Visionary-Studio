const crypto = require('crypto');

const TOKEN_HEADER = 'X-Visionary-Token';

let sessionToken = null;

/**
 * Segredo efêmero desta execução do Electron (32 bytes aleatórios, hex). É gerado uma única vez,
 * entregue ao backend Python por variável de ambiente e injetado nas requisições da janela para o
 * backend. Nunca é exposto ao renderer (preload) nem escrito em disco.
 */
function getSessionToken() {
  if (!sessionToken) {
    sessionToken = crypto.randomBytes(32).toString('hex');
  }
  return sessionToken;
}

function buildBackendUrlFilter(port) {
  const hosts = ['127.0.0.1', 'localhost'];
  return { urls: hosts.flatMap((host) => [`http://${host}:${port}/*`, `ws://${host}:${port}/*`]) };
}

/**
 * Faz o processo main anexar `X-Visionary-Token` a toda requisição (HTTP e handshake de WebSocket)
 * da sessão para o backend local. Cobre <img>, canvas/Konva, fetch e `new WebSocket`, que no
 * navegador não permitem cabeçalhos customizados, sem expor o segredo ao código da página.
 *
 * Um cabeçalho com o mesmo nome vindo da página é descartado, para o valor do main prevalecer.
 */
function installSessionAuth(electronSession, token, port) {
  if (!token) {
    throw new Error('[SessionAuth] token de sessão ausente');
  }

  electronSession.webRequest.onBeforeSendHeaders(buildBackendUrlFilter(port), (details, callback) => {
    try {
      const requestHeaders = {};
      for (const [name, value] of Object.entries(details.requestHeaders || {})) {
        if (name.toLowerCase() !== TOKEN_HEADER.toLowerCase()) {
          requestHeaders[name] = value;
        }
      }
      requestHeaders[TOKEN_HEADER] = token;
      callback({ requestHeaders });
    } catch (err) {
      console.error('[SessionAuth] Erro ao injetar cabeçalho de autenticação:', err);
      callback({ requestHeaders: details.requestHeaders || {} });
    }
  });
}

module.exports = {
  TOKEN_HEADER,
  getSessionToken,
  installSessionAuth,
};
