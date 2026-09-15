const {contextBridge,ipcRenderer}=require('electron');
contextBridge.exposeInMainWorld('worldEngine',Object.freeze({
 call:(action,value)=>ipcRenderer.invoke('client-command',action,value),
 listen:callback=>{ipcRenderer.on('client-event',(_event,value)=>callback(value));}
}));
