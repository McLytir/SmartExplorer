const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('smxDesktop', {
  isDesktop: true,
  signInSharePoint: async (baseUrl) => {
    return ipcRenderer.invoke('smx:sp-auth-flow', { baseUrl });
  },
});
