
const EXT_IMAGE = new Set(['.png','.jpg','.jpeg','.gif','.bmp','.webp','.svg']);
const EXT_VIDEO = new Set(['.mp4','.webm','.mov','.mkv','.avi']);
const EXT_AUDIO = new Set(['.mp3','.wav','.ogg','.m4a']);
const EXT_PDF = new Set(['.pdf']);
const EXT_TEXT = new Set(['.txt','.md','.json','.yaml','.yml','.xml','.csv','.log','.py','.js','.ts','.html','.css','.ini','.cfg']);
const AI_MODEL_PRESETS = {
  openai: ['gpt-5.2','gpt-5.2-pro','gpt-5','gpt-5-mini','gpt-5-nano','gpt-4.1-mini','gpt-4.1','gpt-4.1-nano','gpt-4o','gpt-4o-mini','o4-mini'],
  claude: ['claude-sonnet-4-20250514','claude-opus-4-20250514','claude-3-7-sonnet-latest','claude-3-5-sonnet-latest','claude-3-5-haiku-latest'],
  gemini: ['gemini-2.5-flash','gemini-2.5-pro','gemini-2.0-flash','gemini-1.5-pro','gemini-1.5-flash'],
};

const state = {
  left: paneState('left'),
  right: paneState('right'),
  activePane: 'left',
  clipboard: { op: null, sources: [] },
  translationEnabled: false,
  language: 'English',
  favorites: [],
  layouts: [],
  recent: [],
  spRenameUndoStack: [],
  versionsCache: [],
  operationLog: [],
  sessions: [],
  activeSessionId: '',
  metadataFields: [],
  searchFilters: [],
  searchResults: [],
  jobs: [],
  activeJobId: '',
  jobRunnerActive: false,
  retryQueue: [],
  bulkDryRun: null,
  dragPayload: null,
  shortcutBindings: {},
  notifications: [],
  desktopNotify: false,
  lastDesktopNotifyAt: 0,
  automationRules: [],
  jobEvents: [],
  glossary: [],
  translationLocalCache: {},
  pdfBookmarks: [],
  migrationLog: [],
  aiRenameLog: [],
  aiRenameUndoStack: [],
  splitViewEnabled: false,
  splitCompareSessionId: '',
  splitRuntime: {},
  splitTransferMode: 'copy',
  appView: 'workspace',
  migrationBookmarkExportFormat: 'json',
  relinkImports: [],
  relinkExports: [],
  splitClickTimers: {},
};

function paneState(key){
  return { key, kind:'local', path:'', items:[], selected:new Set(), translations:new Map(), site:'', siteTitle:'', library:'', sites:[], libraries:[], filterText:'' };
}

const el = {
  appModeBar:id('appModeBar'), sessionBar:id('sessionBar'), workspaceToolsBar:id('workspaceToolsBar'),
  splitViewToggleBtn:id('splitViewToggleBtn'), splitTransferModeBtn:id('splitTransferModeBtn'), splitCompareSessionSelect:id('splitCompareSessionSelect'), splitSessionsHost:id('splitSessionsHost'), mainWorkspaceView:id('mainWorkspaceView'),
  appWorkspaceTabBtn:id('appWorkspaceTabBtn'), appRelinkingTabBtn:id('appRelinkingTabBtn'), relinkingWorkspaceView:id('relinkingWorkspaceView'),
  inspectorActionsPanel:id('inspectorActionsPanel'),
  openSettingsBtn:id('openSettingsBtn'), settingsModal:id('settingsModal'), settingsCloseBtn:id('settingsCloseBtn'), settingsApplyBtn:id('settingsApplyBtn'),
  aiProviderSelect:id('aiProviderSelect'), aiModelInput:id('aiModelInput'), openAiApiKeyInput:id('openAiApiKeyInput'), claudeApiKeyInput:id('claudeApiKeyInput'), geminiApiKeyInput:id('geminiApiKeyInput'), aiProviderSaveBtn:id('aiProviderSaveBtn'), openAiApiKeyClearBtn:id('openAiApiKeyClearBtn'), claudeApiKeyClearBtn:id('claudeApiKeyClearBtn'), geminiApiKeyClearBtn:id('geminiApiKeyClearBtn'), aiApiKeyState:id('aiApiKeyState'),
  status: id('status'), uiVersionSelect:id('uiVersionSelect'), langInput: id('langInput'), toggleTranslateBtn: id('toggleTranslateBtn'),
  renameTranslatedBtn: id('renameTranslatedBtn'), undoRenameBtn: id('undoRenameBtn'), copyBtn: id('copyBtn'), cutBtn: id('cutBtn'), pasteBtn: id('pasteBtn'),
  renameBtn: id('renameBtn'), aiRenameBtn:id('aiRenameBtn'), deleteBtn: id('deleteBtn'), mkdirBtn: id('mkdirBtn'), openBtn: id('openBtn'), revealBtn: id('revealBtn'), addFavoriteBtn: id('addFavoriteBtn'), exportConfigBtn:id('exportConfigBtn'), importConfigBtn:id('importConfigBtn'), importConfigInput:id('importConfigInput'),
  layoutTabs:id('layoutTabs'),
  sessionTabs:id('sessionTabs'), newSessionBtn:id('newSessionBtn'), duplicateSessionBtn:id('duplicateSessionBtn'), renameSessionBtn:id('renameSessionBtn'), closeSessionBtn:id('closeSessionBtn'),
  leftKind:id('leftKind'), leftSite:id('leftSite'), leftLibrary:id('leftLibrary'), leftPath:id('leftPath'), leftGo:id('leftGo'), leftList:id('leftList'), leftUploadBtn:id('leftUploadBtn'), leftUploadInput:id('leftUploadInput'), leftFilterInput:id('leftFilterInput'),
  rightKind:id('rightKind'), rightSite:id('rightSite'), rightLibrary:id('rightLibrary'), rightPath:id('rightPath'), rightGo:id('rightGo'), rightList:id('rightList'), rightUploadBtn:id('rightUploadBtn'), rightUploadInput:id('rightUploadInput'), rightFilterInput:id('rightFilterInput'),
  favoriteNameInput:id('favoriteNameInput'), saveFavoriteBtn:id('saveFavoriteBtn'), favoritesList:id('favoritesList'),
  layoutNameInput:id('layoutNameInput'), saveLayoutBtn:id('saveLayoutBtn'), layoutsList:id('layoutsList'), recentList:id('recentList'),
  opLogOutput:id('opLogOutput'), desktopNotifyBtn:id('desktopNotifyBtn'), clearNotificationsBtn:id('clearNotificationsBtn'), notificationsList:id('notificationsList'),
  searchQueryInput:id('searchQueryInput'), searchRunBtn:id('searchRunBtn'), searchIncludeLocal:id('searchIncludeLocal'), searchIncludeSp:id('searchIncludeSp'), searchExtInput:id('searchExtInput'), searchMaxInput:id('searchMaxInput'), searchFilterSelect:id('searchFilterSelect'), searchFilterSaveBtn:id('searchFilterSaveBtn'), searchFilterDeleteBtn:id('searchFilterDeleteBtn'), searchResults:id('searchResults'),
  spBaseUrlInput:id('spBaseUrlInput'), spSitesListInput:id('spSitesListInput'), spCookieHeaderInput:id('spCookieHeaderInput'), spSaveAuthBtn:id('spSaveAuthBtn'), spRefreshAuthBtn:id('spRefreshAuthBtn'), spEmbeddedSigninBtn:id('spEmbeddedSigninBtn'), spAuthState:id('spAuthState'),
  bulkOpType:id('bulkOpType'), bulkTargetPane:id('bulkTargetPane'), bulkConflictPolicy:id('bulkConflictPolicy'), bulkDryRunBtn:id('bulkDryRunBtn'), bulkQueueBtn:id('bulkQueueBtn'), bulkDryRunOutput:id('bulkDryRunOutput'),
  jobsPauseBtn:id('jobsPauseBtn'), jobsResumeBtn:id('jobsResumeBtn'), jobsCancelBtn:id('jobsCancelBtn'), jobsRetryFailedBtn:id('jobsRetryFailedBtn'), jobsExportBtn:id('jobsExportBtn'), jobsClearFinishedBtn:id('jobsClearFinishedBtn'), jobsList:id('jobsList'), queueMetrics:id('queueMetrics'),
  scCopy:id('scCopy'), scCut:id('scCut'), scPaste:id('scPaste'), scDelete:id('scDelete'), scRename:id('scRename'), scMkdir:id('scMkdir'), scRefresh:id('scRefresh'), saveShortcutsBtn:id('saveShortcutsBtn'), resetShortcutsBtn:id('resetShortcutsBtn'),
  glossarySourceInput:id('glossarySourceInput'), glossaryTargetInput:id('glossaryTargetInput'), addGlossaryBtn:id('addGlossaryBtn'), glossaryList:id('glossaryList'),
  ruleMatchInput:id('ruleMatchInput'), ruleActionSelect:id('ruleActionSelect'), ruleValueInput:id('ruleValueInput'), addRuleBtn:id('addRuleBtn'), applyRulesBtn:id('applyRulesBtn'), rulesList:id('rulesList'),
  tagInput:id('tagInput'), saveTagsBtn:id('saveTagsBtn'), tagSearchInput:id('tagSearchInput'), searchTagsBtn:id('searchTagsBtn'), tagResults:id('tagResults'),
  propertiesBtn:id('propertiesBtn'), permissionsBtn:id('permissionsBtn'), propertiesOutput:id('propertiesOutput'), permissionsOutput:id('permissionsOutput'),
  metadataLoadBtn:id('metadataLoadBtn'), metadataApplyBtn:id('metadataApplyBtn'), metadataInput:id('metadataInput'), metadataOutput:id('metadataOutput'), metadataForm:id('metadataForm'), metadataValidation:id('metadataValidation'), metadataDiff:id('metadataDiff'),
  renamePreviewModal:id('renamePreviewModal'), renamePreviewSummary:id('renamePreviewSummary'), renamePreviewConflicts:id('renamePreviewConflicts'), renamePreviewCancelBtn:id('renamePreviewCancelBtn'), renamePreviewProceedBtn:id('renamePreviewProceedBtn'),
  aiRenamePreviewModal:id('aiRenamePreviewModal'), aiRenamePreviewSummary:id('aiRenamePreviewSummary'), aiRenamePreviewConflicts:id('aiRenamePreviewConflicts'), aiRenamePreviewCancelBtn:id('aiRenamePreviewCancelBtn'), aiRenamePreviewProceedBtn:id('aiRenamePreviewProceedBtn'),
  transferPreviewModal:id('transferPreviewModal'), transferPreviewSummary:id('transferPreviewSummary'), transferPreviewList:id('transferPreviewList'), transferSelectSafeBtn:id('transferSelectSafeBtn'), transferSelectNoneBtn:id('transferSelectNoneBtn'), transferPreviewConflicts:id('transferPreviewConflicts'), transferPreviewCancelBtn:id('transferPreviewCancelBtn'), transferPreviewProceedBtn:id('transferPreviewProceedBtn'),
  newFolderModal:id('newFolderModal'), newFolderSummary:id('newFolderSummary'), newFolderNameInput:id('newFolderNameInput'), newFolderCancelBtn:id('newFolderCancelBtn'), newFolderCreateBtn:id('newFolderCreateBtn'),
  renameModal:id('renameModal'), renameSummary:id('renameSummary'), renameNameInput:id('renameNameInput'), renameCancelBtn:id('renameCancelBtn'), renameApplyBtn:id('renameApplyBtn'),
  previewBtn:id('previewBtn'), extractBtn:id('extractBtn'), summaryBtn:id('summaryBtn'), questionInput:id('questionInput'), askBtn:id('askBtn'), previewFrame:id('previewFrame'), previewText:id('previewText'),
  pdfPageInput:id('pdfPageInput'), pdfJumpBtn:id('pdfJumpBtn'), pdfBookmarkAddBtn:id('pdfBookmarkAddBtn'), pdfBookmarksList:id('pdfBookmarksList'),
  checkoutBtn:id('checkoutBtn'), checkinBtn:id('checkinBtn'), undoCheckoutBtn:id('undoCheckoutBtn'), loadVersionsBtn:id('loadVersionsBtn'), versionsSelect:id('versionsSelect'), downloadVersionBtn:id('downloadVersionBtn'), restoreVersionBtn:id('restoreVersionBtn'), versionsOutput:id('versionsOutput'),
  migrationResolveInput:id('migrationResolveInput'), migrationResolveBtn:id('migrationResolveBtn'), migrationFilterInput:id('migrationFilterInput'), migrationImportBtn:id('migrationImportBtn'), migrationImportInput:id('migrationImportInput'), migrationBookmarkInput:id('migrationBookmarkInput'), migrationConvertBookmarkJsonBtn:id('migrationConvertBookmarkJsonBtn'), migrationConvertBookmarkCsvBtn:id('migrationConvertBookmarkCsvBtn'), migrationResolveOutput:id('migrationResolveOutput'), migrationCopyResolvedBtn:id('migrationCopyResolvedBtn'), migrationOpenResolvedBtn:id('migrationOpenResolvedBtn'), migrationExportJsonBtn:id('migrationExportJsonBtn'), migrationExportCsvBtn:id('migrationExportCsvBtn'), migrationLogList:id('migrationLogList'),
  migrationClearBtn:id('migrationClearBtn'),
  relinkImportHtmlBtn:id('relinkImportHtmlBtn'), relinkImportHtmlInput:id('relinkImportHtmlInput'), relinkImportsList:id('relinkImportsList'), relinkExportsList:id('relinkExportsList'), relinkClearImportsBtn:id('relinkClearImportsBtn'), relinkClearExportsBtn:id('relinkClearExportsBtn'),
  aiRenameFilterInput:id('aiRenameFilterInput'), aiRenameExportJsonBtn:id('aiRenameExportJsonBtn'), aiRenameExportCsvBtn:id('aiRenameExportCsvBtn'), aiRenameLogList:id('aiRenameLogList'),
};

function id(x){ return document.getElementById(x); }
function paneEls(key){ return key==='left' ? {kind:el.leftKind,site:el.leftSite,library:el.leftLibrary,path:el.leftPath,go:el.leftGo,list:el.leftList,uploadBtn:el.leftUploadBtn,uploadInput:el.leftUploadInput,filter:el.leftFilterInput} : {kind:el.rightKind,site:el.rightSite,library:el.rightLibrary,path:el.rightPath,go:el.rightGo,list:el.rightList,uploadBtn:el.rightUploadBtn,uploadInput:el.rightUploadInput,filter:el.rightFilterInput}; }
function setModalOpen(node, open){
  if(!node) return;
  node.classList.toggle('hidden', !open);
  node.setAttribute('aria-hidden', open ? 'false' : 'true');
}
function isSettingsModalOpen(){
  return !!(el.settingsModal && !el.settingsModal.classList.contains('hidden'));
}
function isNewFolderModalOpen(){
  return !!(el.newFolderModal && !el.newFolderModal.classList.contains('hidden'));
}
function syncSettingsUi(){
  if(el.langInput) el.langInput.value=state.language||'English';
  if(el.uiVersionSelect) el.uiVersionSelect.value=document.body.getAttribute('data-ui-version')||'v1';
  if(el.openAiApiKeyInput) el.openAiApiKeyInput.value='';
  if(el.claudeApiKeyInput) el.claudeApiKeyInput.value='';
  if(el.geminiApiKeyInput) el.geminiApiKeyInput.value='';
  renderAiModelOptions(el.aiProviderSelect?.value||'openai', el.aiModelInput?.value||'');
  renderShortcuts();
  renderNotifications();
}
async function applySettingsFromModal(){
  const nextLanguage=(el.langInput?.value||'English').trim()||'English';
  const languageChanged=nextLanguage!==state.language;
  state.language=nextLanguage;
  const aiProvider=String(el.aiProviderSelect?.value||'openai').trim()||'openai';
  const aiModel=String(el.aiModelInput?.value||'').trim();
  const spBase=String(el.spBaseUrlInput?.value||'').trim();
  const spSites=parseSharePointSitesInput(el.spSitesListInput?.value||'');
  saveCurrentSessionSnapshot();
  persistSessions();
  try{
    await apiPost('/api/settings',{
      target_language:state.language,
      ai_provider:aiProvider,
      ai_model:aiModel,
      sp_base_url:spBase||null,
      sp_site_allowlist:spSites,
    });
    await refreshSpAuthPanel();
    await refreshAiKeyPanel();
  }catch(e){
    setStatus(`Settings save failed: ${err(e)}`);
    return;
  }
  if(languageChanged && state.translationEnabled){
    await refreshTranslations('left');
    await refreshTranslations('right');
    renderPane('left');
    renderPane('right');
  }
  setStatus(languageChanged?'Settings applied and translation language updated.':'Settings applied.');
}
async function openSettingsModal(){
  if(!el.settingsModal) return;
  syncSettingsUi();
  await refreshAiKeyPanel();
  await refreshSpAuthPanel();
  el.settingsModal.classList.remove('hidden');
  el.settingsModal.setAttribute('aria-hidden','false');
}
function closeSettingsModal(){
  if(!el.settingsModal) return;
  setModalOpen(el.settingsModal, false);
}
function renderAiKeyState(settings){
  if(!el.aiApiKeyState) return;
  const provider=String(settings?.ai_provider||'openai').trim()||'openai';
  const model=String(settings?.ai_model||settings?.model||'').trim()||'';
  const hasOpenAi=!!settings?.has_openai_api_key;
  const hasClaude=!!settings?.has_anthropic_api_key;
  const hasGemini=!!settings?.has_gemini_api_key;
  const activeReady=provider==='openai' ? hasOpenAi : provider==='claude' ? hasClaude : hasGemini;
  if(el.aiProviderSelect) el.aiProviderSelect.value=provider;
  renderAiModelOptions(provider, model);
  el.aiApiKeyState.textContent=`Provider: ${provider} | Active key: ${activeReady?'configured':'missing'} | OpenAI: ${hasOpenAi?'yes':'no'} | Claude: ${hasClaude?'yes':'no'} | Gemini: ${hasGemini?'yes':'no'} | Model: ${model}`;
}
async function refreshAiKeyPanel(){
  try{
    const settings=await apiGet('/api/settings');
    renderAiKeyState(settings);
  }catch(e){
    if(el.aiApiKeyState) el.aiApiKeyState.textContent=`Key status: failed to load (${err(e)})`;
  }
}
async function saveAiApiKeyFromPortal(){
  const provider=String(el.aiProviderSelect?.value||'openai').trim()||'openai';
  const model=String(el.aiModelInput?.value||'').trim();
  const openAiKey=String(el.openAiApiKeyInput?.value||'').trim();
  const claudeKey=String(el.claudeApiKeyInput?.value||'').trim();
  const geminiKey=String(el.geminiApiKeyInput?.value||'').trim();
  if(!model) return setStatus('Enter a model before saving AI settings.');
  if(!openAiKey && !claudeKey && !geminiKey) return setStatus('Enter at least one key to save, or use the clear actions.');
  try{
    const payload={ai_provider:provider, ai_model:model};
    if(openAiKey) payload.openai_api_key=openAiKey;
    if(claudeKey) payload.anthropic_api_key=claudeKey;
    if(geminiKey) payload.gemini_api_key=geminiKey;
    await apiPost('/api/settings',payload);
    if(el.openAiApiKeyInput) el.openAiApiKeyInput.value='';
    if(el.claudeApiKeyInput) el.claudeApiKeyInput.value='';
    if(el.geminiApiKeyInput) el.geminiApiKeyInput.value='';
    await refreshAiKeyPanel();
    setStatus('AI provider settings saved securely.');
  }catch(e){
    setStatus(`AI settings save failed: ${err(e)}`);
  }
}
async function clearAiApiKeyFromPortal(secretField){
  try{
    const payload={};
    payload[secretField]='';
    await apiPost('/api/settings',payload);
    if(secretField==='openai_api_key' && el.openAiApiKeyInput) el.openAiApiKeyInput.value='';
    if(secretField==='anthropic_api_key' && el.claudeApiKeyInput) el.claudeApiKeyInput.value='';
    if(secretField==='gemini_api_key' && el.geminiApiKeyInput) el.geminiApiKeyInput.value='';
    await refreshAiKeyPanel();
    setStatus('AI API key cleared.');
  }catch(e){
    setStatus(`AI API key clear failed: ${err(e)}`);
  }
}
function resolveCreateFolderContext(){
  const p=activePane();
  const selection=selectedItems(p);
  const selectedDir=selection.length===1 && selection[0]?.isDir ? selection[0].path : '';
  const targetParent=p.kind==='local'
    ? (selectedDir || p.path)
    : normalizeSpPath(selectedDir || p.path || p.library || '/');
  return { pane:p, targetParent };
}
function openNewFolderModal(){
  const ctx=resolveCreateFolderContext();
  if(!ctx.targetParent) return setStatus('No target folder is available.');
  if(el.newFolderSummary){
    const label=ctx.pane.kind==='sharepoint'
      ? `Create a SharePoint folder in ${ctx.targetParent}`
      : `Create a folder in ${ctx.targetParent}`;
    el.newFolderSummary.textContent=label;
  }
  if(el.newFolderNameInput) el.newFolderNameInput.value='';
  setModalOpen(el.newFolderModal, true);
  if(el.newFolderNameInput) el.newFolderNameInput.focus();
  setStatus(`Ready to create folder in ${ctx.targetParent}`);
}
function closeNewFolderModal(){
  setModalOpen(el.newFolderModal, false);
}
function loadNotificationPrefs(){
  state.desktopNotify=localStorage.getItem('smx_web_desktop_notify')==='1';
}
function applyUiVersion(version){
  const v=(version==='v2'||version==='v3')?version:'v1';
  document.body.setAttribute('data-ui-version',v);
  if(el.uiVersionSelect) el.uiVersionSelect.value=v;
}
function loadUiVersion(){
  const stored=localStorage.getItem('smx_web_ui_version')||'v1';
  applyUiVersion(stored);
}
function setUiVersion(version){
  applyUiVersion(version);
  localStorage.setItem('smx_web_ui_version',document.body.getAttribute('data-ui-version')||'v1');
  setStatus(`UI architecture set to ${document.body.getAttribute('data-ui-version')}.`);
}
function persistNotificationPrefs(){
  localStorage.setItem('smx_web_desktop_notify',state.desktopNotify?'1':'0');
}
function renderNotifications(){
  if(el.desktopNotifyBtn) el.desktopNotifyBtn.textContent=`Desktop Alerts: ${state.desktopNotify?'On':'Off'}`;
  if(!el.notificationsList) return;
  el.notificationsList.innerHTML='';
  if(!state.notifications.length){
    el.notificationsList.innerHTML='<small style="color:#94a3b8">No notifications.</small>';
    return;
  }
  state.notifications.forEach((n)=>{
    const row=document.createElement('div');
    row.className=`notification-row ${n.level||'info'}`;
    const count=(Number(n.count||1)>1)?` (x${Number(n.count||1)})`:'';
    row.innerHTML=`<div>${escapeHtml(n.message||'')}${escapeHtml(count)}</div><small>${escapeHtml(n.ts||'')}</small>`;
    el.notificationsList.appendChild(row);
  });
}
function classifyStatusLevel(msg){
  const t=String(msg||'').toLowerCase();
  if(t.includes('failed')||t.includes('error')||t.includes('blocked')) return 'error';
  if(t.includes('warning')||t.includes('skipped')) return 'warn';
  return 'info';
}
function pushNotification(message,level='info',desktop=false){
  const now=Date.now();
  const msg=String(message||'');
  const top=state.notifications[0];
  if(top && top.message===msg && top.level===level && (now-Number(top._tsms||0))<5000){
    top.count=Number(top.count||1)+1;
    top._tsms=now;
    top.ts=new Date().toLocaleTimeString();
  }else{
    const item={message:msg,level,count:1,ts:new Date().toLocaleTimeString(),_tsms:now};
    state.notifications.unshift(item);
    state.notifications=state.notifications.slice(0,200);
  }
  renderNotifications();
  const allowDesktop=state.desktopNotify && (desktop||level==='error') && (now-state.lastDesktopNotifyAt>3000);
  if(allowDesktop && typeof Notification!=='undefined' && Notification.permission==='granted'){
    try{
      state.lastDesktopNotifyAt=now;
      new Notification('SmartExplorer',{body:msg});
    }catch{}
  }
}
async function toggleDesktopNotifications(){
  if(typeof Notification==='undefined'){
    setStatus('Desktop notifications are not supported in this shell.');
    return;
  }
  if(Notification.permission==='granted'){
    state.desktopNotify=!state.desktopNotify;
    persistNotificationPrefs();
    renderNotifications();
    setStatus(`Desktop alerts ${state.desktopNotify?'enabled':'disabled'}.`);
    return;
  }
  const p=await Notification.requestPermission();
  state.desktopNotify=(p==='granted');
  persistNotificationPrefs();
  renderNotifications();
  setStatus(state.desktopNotify?'Desktop alerts enabled.':'Desktop alerts unavailable (permission denied).');
}
function clearNotifications(){
  state.notifications=[];
  renderNotifications();
  setStatus('Notifications cleared.');
}
function setStatus(v){
  el.status.textContent=v||'';
  if(!v) return;
  state.operationLog.unshift(`${new Date().toLocaleTimeString()} | ${v}`);
  state.operationLog=state.operationLog.slice(0,160);
  if(el.opLogOutput) el.opLogOutput.textContent=state.operationLog.join('\n');
  pushNotification(v,classifyStatusLevel(v),false);
}
function err(e){ return String(e).slice(0,180); }
function basename(p){ return (p||'').split(/[\\/]/).filter(Boolean).pop()||p; }
function drivePrefix(path){
  const raw=String(path||'').trim();
  const m=raw.match(/^[A-Za-z]:/);
  return m ? m[0].toUpperCase() : '';
}
function extname(p){ const n=basename(p).toLowerCase(); const i=n.lastIndexOf('.'); return i>=0?n.slice(i):''; }
function activePane(){ return state[state.activePane]; }
function selectedItems(p){ return p.items.filter(i=>p.selected.has(i.path)); }
function selectedSinglePath(){ const a=Array.from(activePane().selected); return a.length===1?a[0]:null; }
function csvCell(v){ const s=String(v??''); return `"${s.replaceAll('"','""')}"`; }
function fmtSize(bytes){ if(!bytes) return ''; const u=['B','KB','MB','GB','TB']; let n=Number(bytes),i=0; while(n>=1024&&i<u.length-1){ n/=1024;i++; } return `${n.toFixed(i?1:0)} ${u[i]}`; }
function parentPath(path){
  const raw=String(path||'').trim();
  if(!raw) return raw;
  if(/^[A-Za-z]:\\?$/.test(raw)) return raw.endsWith('\\') ? raw : `${raw}\\`;
  if(raw.includes('\\') || /^[A-Za-z]:/.test(raw)){
    const trimmed=raw.replace(/[\\\/]+$/,'');
    if(/^[A-Za-z]:$/.test(trimmed)) return `${trimmed}\\`;
    const idx=trimmed.lastIndexOf('\\');
    if(idx<0) return trimmed;
    if(idx===2 && /^[A-Za-z]:/.test(trimmed)) return `${trimmed.slice(0,3)}`;
    return trimmed.slice(0, idx);
  }
  if(raw.startsWith('/')){
    const trimmed=raw.replace(/\/+$/,'') || '/';
    if(trimmed==='/') return '/';
    const idx=trimmed.lastIndexOf('/');
    return idx<=0 ? '/' : trimmed.slice(0, idx);
  }
  const trimmed=raw.replace(/[\\\/]+$/,'');
  const idx=Math.max(trimmed.lastIndexOf('/'),trimmed.lastIndexOf('\\'));
  return idx<=0 ? trimmed : trimmed.slice(0, idx);
}
function findSiteTitle(site, sites, fallback=''){
  const key=String(site||'').trim();
  if(key && Array.isArray(sites)){
    const match=sites.find((s)=>String(s?.site||'').trim()===key);
    if(match?.title) return String(match.title).trim();
  }
  if(fallback) return String(fallback).trim();
  if(!key) return 'Default Site';
  const slug=key.split('/').filter(Boolean).pop()||key;
  return slug
    .replace(/([a-z])([A-Z])/g,'$1 $2')
    .replace(/[-_]+/g,' ')
    .replace(/\s+/g,' ')
    .trim() || key;
}
function localSessionLabel(path){
  const raw=String(path||'').trim();
  if(!raw) return 'Local';
  if(/^[A-Za-z]:\\?$/.test(raw)) return raw.endsWith('\\') ? raw : `${raw}\\`;
  const trimmed=raw.replace(/[\\\/]+$/,'');
  const drive=drivePrefix(trimmed);
  if(!drive) return basename(trimmed)||trimmed||'Local';
  const leaf=basename(trimmed);
  return leaf && leaf.toUpperCase()!==drive ? `${drive}\\${leaf}` : `${drive}\\`;
}
function sharePointSessionLabel(pane){
  const siteTitle=findSiteTitle(pane?.site, pane?.sites, pane?.siteTitle||'');
  const folder=basename(String(pane?.path||pane?.library||'').replace(/\/+$/,'')) || '';
  return folder ? `${siteTitle} - ${folder}` : siteTitle || 'SharePoint';
}
function sessionLabelFromPane(pane){
  const kind=String(pane?.kind||'local').toLowerCase();
  if(kind==='sharepoint') return sharePointSessionLabel(pane);
  return localSessionLabel(pane?.path||'');
}
function sessionLabelFromSnapshot(snapshot){
  const snap=snapshot||{};
  const side=preferredSplitSide(snap);
  return sessionLabelFromPane(snap?.[side]||snap?.left||snap?.right||{});
}
function sessionLabelById(sessionId){
  return sessionLabelFromSnapshot(splitSnapshotForSession(sessionId));
}
function isMedia(path){ const e=extname(path); return EXT_IMAGE.has(e)||EXT_VIDEO.has(e)||EXT_AUDIO.has(e)||EXT_PDF.has(e); }
function normalizeSpFieldType(t){ return String(t||'').toLowerCase(); }
function escapeHtml(s){ return String(s??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;'); }
function toDateTimeLocal(value){
  const raw=String(value||'').trim();
  if(!raw) return '';
  const d=new Date(raw);
  if(Number.isNaN(d.getTime())) return '';
  const pad=(n)=>String(n).padStart(2,'0');
  return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
function syncMetadataJsonFromForm(){
  if(!el.metadataForm||!el.metadataInput) return;
  const out={};
  const nodes=el.metadataForm.querySelectorAll('[data-field-name]');
  nodes.forEach((node)=>{
    const name=node.getAttribute('data-field-name');
    if(!name) return;
    let value='';
    if(node.dataset.inputType==='boolean'){
      value=node.checked?'1':'0';
    }else{
      value=String(node.value??'').trim();
    }
    out[name]=value;
  });
  el.metadataInput.value=JSON.stringify(out,null,2);
  refreshMetadataValidationAndDiff();
}
function fieldByInternalName(name){
  return (state.metadataFields||[]).find((f)=>String(f.internal_name||'')===String(name||''));
}
function stringifyValue(v){ return v==null?'':String(v).trim(); }
function clearMetadataFieldErrors(){
  if(!el.metadataForm) return;
  el.metadataForm.querySelectorAll('.meta-field').forEach((node)=>{
    node.classList.remove('invalid');
    const errNode=node.querySelector('.meta-field-error');
    if(errNode) errNode.remove();
  });
}
function showMetadataFieldError(name,message){
  if(!el.metadataForm) return;
  const input=Array.from(el.metadataForm.querySelectorAll('[data-field-name]')).find((n)=>n.getAttribute('data-field-name')===String(name||''));
  if(!input) return;
  const container=input.closest('.meta-field');
  if(!container) return;
  container.classList.add('invalid');
  const old=container.querySelector('.meta-field-error');
  if(old) old.remove();
  const msg=document.createElement('div');
  msg.className='meta-field-error';
  msg.textContent=message;
  container.appendChild(msg);
}
function validateMetadataPayload(payload){
  const errors=[];
  const editable=(state.metadataFields||[]).filter((f)=>!f.hidden&&!f.read_only&&f.internal_name);
  const editableNames=new Set(editable.map((f)=>String(f.internal_name)));

  editable.forEach((f)=>{
    const name=String(f.internal_name);
    const type=normalizeSpFieldType(f.type);
    const raw=payload[name];
    const val=stringifyValue(raw);
    if(f.required&&val===''){
      errors.push({field:name,message:'Required field is empty.'});
      return;
    }
    if(val==='') return;
    if((type.includes('number')||type.includes('currency')||type.includes('integer'))&&Number.isNaN(Number(val))){
      errors.push({field:name,message:'Expected a numeric value.'});
    }else if(type.includes('boolean')&&!['0','1','true','false','yes','no'].includes(val.toLowerCase())){
      errors.push({field:name,message:'Expected boolean value (0/1/true/false).'});
    }else if(type.includes('datetime')||type==='date'){
      const dt=new Date(val);
      if(Number.isNaN(dt.getTime())) errors.push({field:name,message:'Expected a valid date/time.'});
    }else if((type.includes('choice')||type.includes('multichoice'))&&Array.isArray(f.choices)&&f.choices.length){
      const options=new Set(f.choices.map((x)=>String(x)));
      if(!options.has(val)) errors.push({field:name,message:'Value is not one of the available choices.'});
    }
  });

  Object.keys(payload||{}).forEach((name)=>{
    if(!editableNames.has(String(name))){
      errors.push({field:String(name),message:'Field is not editable or not loaded.'});
    }
  });
  return errors;
}
function renderMetadataValidation(jsonError,errors){
  if(!el.metadataValidation) return;
  clearMetadataFieldErrors();
  const lines=[];
  if(jsonError) lines.push(`JSON parse error: ${jsonError}`);
  (errors||[]).forEach((e)=>{ lines.push(`${e.field}: ${e.message}`); showMetadataFieldError(e.field,e.message); });
  el.metadataValidation.textContent=lines.join('\n');
}
function renderMetadataDiff(payload){
  if(!el.metadataDiff) return;
  const rows=[];
  Object.keys(payload||{}).forEach((name)=>{
    const def=fieldByInternalName(name);
    const current=def?stringifyValue(def.value):'';
    const pending=stringifyValue(payload[name]);
    const changed=current!==pending;
    rows.push({name,title:def?.title||name,current,pending,changed});
  });
  if(!rows.length){
    el.metadataDiff.innerHTML='<small style="color:#94a3b8;display:block;padding:8px;">No pending metadata changes.</small>';
    return;
  }
  const header='<table><thead><tr><th>Field</th><th>Current</th><th>Pending</th></tr></thead><tbody>';
  const body=rows.map((r)=>`<tr><td>${escapeHtml(r.title)}<br/><small>${escapeHtml(r.name)}</small></td><td>${escapeHtml(r.current)}</td><td class="${r.changed?'changed':''}">${escapeHtml(r.pending)}</td></tr>`).join('');
  const foot='</tbody></table>';
  el.metadataDiff.innerHTML=header+body+foot;
}
function refreshMetadataValidationAndDiff(){
  if(!el.metadataInput) return {payload:{},jsonError:'',errors:[]};
  const raw=(el.metadataInput.value||'').trim();
  if(!raw){
    renderMetadataValidation('',[]);
    renderMetadataDiff({});
    return {payload:{},jsonError:'',errors:[]};
  }
  let payload;
  try{
    payload=JSON.parse(raw);
    if(!payload||typeof payload!=='object'||Array.isArray(payload)) throw new Error('Root must be an object.');
    Object.keys(payload).forEach((k)=>{ payload[k]=payload[k]==null?'':String(payload[k]); });
  }catch(e){
    const msg=err(e);
    renderMetadataValidation(msg,[]);
    renderMetadataDiff({});
    return {payload:{},jsonError:msg,errors:[]};
  }
  const errors=validateMetadataPayload(payload);
  renderMetadataValidation('',errors);
  renderMetadataDiff(payload);
  return {payload,jsonError:'',errors};
}
function renderMetadataForm(fields){
  if(!el.metadataForm) return;
  el.metadataForm.innerHTML='';
  const editable=(fields||[]).filter((f)=>!f.read_only&&!f.hidden&&f.internal_name);
  if(!editable.length){
    el.metadataForm.innerHTML='<small style="color:#94a3b8">No editable metadata fields were returned for this item.</small>';
    if(el.metadataInput) el.metadataInput.value='{}';
    refreshMetadataValidationAndDiff();
    return;
  }
  editable.forEach((f)=>{
    const wrap=document.createElement('div');
    wrap.className='meta-field';
    const type=normalizeSpFieldType(f.type);
    const title=escapeHtml(f.title||f.internal_name);
    const note=`${f.internal_name}${f.type?` | ${f.type}`:''}${f.required?' | required':''}`;
    const label=document.createElement('label');
    label.innerHTML=`<strong>${title}</strong><br/><small>${escapeHtml(note)}</small>`;
    wrap.appendChild(label);

    let input;
    if(type.includes('boolean')){
      input=document.createElement('input');
      input.type='checkbox';
      input.checked=['1','true','yes'].includes(String(f.value||'').trim().toLowerCase());
      input.dataset.inputType='boolean';
    }else if(type.includes('datetime')||type==='date'){
      input=document.createElement('input');
      input.type='datetime-local';
      input.value=toDateTimeLocal(f.value);
    }else if(type.includes('number')||type.includes('currency')||type.includes('integer')){
      input=document.createElement('input');
      input.type='number';
      input.step='any';
      input.value=String(f.value??'');
    }else if((type.includes('choice')||type.includes('multichoice'))&&Array.isArray(f.choices)&&f.choices.length){
      input=document.createElement('select');
      const blank=document.createElement('option');
      blank.value='';
      blank.textContent='(empty)';
      input.appendChild(blank);
      f.choices.forEach((c)=>{
        const opt=document.createElement('option');
        opt.value=String(c);
        opt.textContent=String(c);
        input.appendChild(opt);
      });
      input.value=String(f.value??'');
    }else if(type.includes('note')||type.includes('multiline')){
      input=document.createElement('textarea');
      input.rows=3;
      input.value=String(f.value??'');
    }else{
      input=document.createElement('input');
      input.type='text';
      input.value=String(f.value??'');
    }
    input.setAttribute('data-field-name',f.internal_name);
    input.oninput=syncMetadataJsonFromForm;
    input.onchange=syncMetadataJsonFromForm;
    wrap.appendChild(input);
    el.metadataForm.appendChild(wrap);
  });
  syncMetadataJsonFromForm();
}
function collectMetadataPayload(){
  const {payload,jsonError,errors}=refreshMetadataValidationAndDiff();
  if(jsonError) throw new Error(`Metadata payload JSON error: ${jsonError}`);
  if(errors.length){
    const first=errors[0];
    throw new Error(`Metadata validation failed (${errors.length}): ${first.field} - ${first.message}`);
  }
  return payload;
}
function showRenamePreviewModal(okRows,badRows){
  if(!el.renamePreviewModal||!el.renamePreviewProceedBtn||!el.renamePreviewCancelBtn){
    return Promise.resolve(confirm(`Preview found ${badRows.length} conflict(s). Continue with ${okRows.length} safe rename(s)?`));
  }
  return new Promise((resolve)=>{
    const summary=`${okRows.length} safe rename(s) ready. ${badRows.length} conflict(s) will be skipped.`;
    const lines=badRows.length?badRows.slice(0,120).map((r)=>`${basename(r.path)} -> ${r.new_name} [${r.reason}]`).join('\n'):'No conflicts.';
    el.renamePreviewSummary.textContent=summary;
    el.renamePreviewConflicts.textContent=lines;
    el.renamePreviewModal.classList.remove('hidden');
    el.renamePreviewModal.setAttribute('aria-hidden','false');
    const close=(approved)=>{
      el.renamePreviewModal.classList.add('hidden');
      el.renamePreviewModal.setAttribute('aria-hidden','true');
      el.renamePreviewProceedBtn.onclick=null;
      el.renamePreviewCancelBtn.onclick=null;
      document.removeEventListener('keydown',onKey);
      resolve(approved);
    };
    const onKey=(ev)=>{ if(ev.key==='Escape') close(false); };
    document.addEventListener('keydown',onKey);
    el.renamePreviewProceedBtn.onclick=()=>close(true);
    el.renamePreviewCancelBtn.onclick=()=>close(false);
  });
}
function showAiRenamePreviewModal(rows,summary,warnings){
  if(!el.aiRenamePreviewModal||!el.aiRenamePreviewProceedBtn||!el.aiRenamePreviewCancelBtn){
    const okRows=(rows||[]).filter((r)=>!r.conflict && r.action!=='Keep');
    const badRows=(rows||[]).filter((r)=>r.conflict);
    return Promise.resolve(confirm(`${summary}\n\n${okRows.length} safe operation(s) ready. ${badRows.length} blocked operation(s). Continue?`));
  }
  return new Promise((resolve)=>{
    const okRows=(rows||[]).filter((r)=>!r.conflict && r.action!=='Keep');
    const badRows=(rows||[]).filter((r)=>r.conflict);
    const warnLines=Array.isArray(warnings)?warnings:[];
    const lines=[
      ...warnLines.map((w)=>`[warn] ${w}`),
      ...rows.slice(0,160).map((r)=>`${r.conflict?'[blocked]':'[ready]'} ${r.action}: ${r.currentRelativePath||'.'} -> ${r.targetRelativePath||'.'} | ${r.status||''} | ${r.reason||''}`)
    ].join('\n');
    el.aiRenamePreviewSummary.textContent=`${summary||'AI rename plan ready.'} ${okRows.length} safe operation(s). ${badRows.length} blocked operation(s).`;
    el.aiRenamePreviewConflicts.textContent=lines||'No details.';
    el.aiRenamePreviewModal.classList.remove('hidden');
    el.aiRenamePreviewModal.setAttribute('aria-hidden','false');
    const close=(approved)=>{
      el.aiRenamePreviewModal.classList.add('hidden');
      el.aiRenamePreviewModal.setAttribute('aria-hidden','true');
      el.aiRenamePreviewProceedBtn.onclick=null;
      el.aiRenamePreviewCancelBtn.onclick=null;
      document.removeEventListener('keydown',onKey);
      resolve(approved);
    };
    const onKey=(ev)=>{ if(ev.key==='Escape') close(false); };
    document.addEventListener('keydown',onKey);
    el.aiRenamePreviewProceedBtn.onclick=()=>close(true);
    el.aiRenamePreviewCancelBtn.onclick=()=>close(false);
  });
}
function showTransferPreviewModal(rows,sourceMap,operationLabel){
  if(!el.transferPreviewModal||!el.transferPreviewProceedBtn||!el.transferPreviewCancelBtn){
    const okRows=(rows||[]).filter((r)=>r.status!=='blocked');
    const badRows=(rows||[]).filter((r)=>r.status==='blocked');
    return Promise.resolve(confirm(`Transfer preview: ${badRows.length} conflict(s). Continue with ${okRows.length} safe ${operationLabel}(s)?`)).then((approved)=>({approved,selectedPaths:new Set(okRows.map((r)=>String(r.path||''))),overwritePaths:new Set()}));
  }
  return new Promise((resolve)=>{
    const okRows=(rows||[]).filter((r)=>r.status!=='blocked');
    const badRows=(rows||[]).filter((r)=>r.status==='blocked');
    const summary=`${okRows.length} safe ${operationLabel}(s) ready. ${badRows.length} conflict(s) detected.`;
    const lines=badRows.length?badRows.slice(0,120).map((r)=>`${basename(r.path||'')} [${r.reason||'blocked'}]`).join('\n'):'No conflicts.';
    el.transferPreviewSummary.textContent=summary;
    el.transferPreviewConflicts.textContent=lines;
    if(el.transferPreviewList){
      el.transferPreviewList.innerHTML='';
      (rows||[]).forEach((r,idx)=>{
        const src=sourceMap.get(String(r.path||''))||{};
        const canOverwrite=!!(r.status==='blocked' && !src.isDir);
        const item=document.createElement('div');
        item.className=`transfer-preview-item${r.status==='blocked'?' blocked':''}`;
        const checked=(r.status!=='blocked');
        item.innerHTML=`<input type="checkbox" data-i="${idx}" ${checked?'checked':''}><div><strong>${escapeHtml(basename(r.path||''))}</strong><small>${escapeHtml(r.path||'')}</small></div><select data-action="${idx}"><option value="skip"${r.status==='blocked'?' selected':''}>Skip</option>${canOverwrite?'<option value="overwrite">Overwrite</option>':''}<option value="include"${r.status!=='blocked'?' selected':''}>Include</option></select>`;
        el.transferPreviewList.appendChild(item);
      });
    }
    el.transferPreviewModal.classList.remove('hidden');
    el.transferPreviewModal.setAttribute('aria-hidden','false');
    if(el.transferSelectSafeBtn) el.transferSelectSafeBtn.onclick=()=>{ el.transferPreviewList?.querySelectorAll('input[type="checkbox"]').forEach((cb)=>{ cb.checked=true; }); };
    if(el.transferSelectNoneBtn) el.transferSelectNoneBtn.onclick=()=>{ el.transferPreviewList?.querySelectorAll('input[type="checkbox"]').forEach((cb)=>{ cb.checked=false; }); };
    const close=(approved)=>{
      el.transferPreviewModal.classList.add('hidden');
      el.transferPreviewModal.setAttribute('aria-hidden','true');
      el.transferPreviewProceedBtn.onclick=null;
      el.transferPreviewCancelBtn.onclick=null;
      if(el.transferSelectSafeBtn) el.transferSelectSafeBtn.onclick=null;
      if(el.transferSelectNoneBtn) el.transferSelectNoneBtn.onclick=null;
      document.removeEventListener('keydown',onKey);
      if(!approved){
        resolve({approved:false,selectedPaths:new Set(),overwritePaths:new Set()});
        return;
      }
      const selectedPaths=new Set();
      const overwritePaths=new Set();
      (rows||[]).forEach((r,idx)=>{
        const cb=el.transferPreviewList?.querySelector(`input[data-i="${idx}"]`);
        const act=el.transferPreviewList?.querySelector(`select[data-action="${idx}"]`);
        if(!cb||!cb.checked) return;
        selectedPaths.add(String(r.path||''));
        if(act && act.value==='overwrite') overwritePaths.add(String(r.path||''));
      });
      resolve({approved:true,selectedPaths,overwritePaths});
    };
    const onKey=(ev)=>{ if(ev.key==='Escape') close(false); };
    document.addEventListener('keydown',onKey);
    el.transferPreviewProceedBtn.onclick=()=>close(true);
    el.transferPreviewCancelBtn.onclick=()=>close(false);
  });
}
function showRenameModal(currentName){
  if(!el.renameModal||!el.renameNameInput||!el.renameApplyBtn||!el.renameCancelBtn){
    return Promise.resolve((prompt('New name:',currentName)||'').trim());
  }
  return new Promise((resolve)=>{
    if(el.renameSummary) el.renameSummary.textContent=`Rename "${currentName}" to:`;
    el.renameNameInput.value=String(currentName||'');
    el.renameModal.classList.remove('hidden');
    el.renameModal.setAttribute('aria-hidden','false');
    setTimeout(()=>{
      el.renameNameInput?.focus();
      el.renameNameInput?.select();
    },0);
    const close=(value)=>{
      el.renameModal.classList.add('hidden');
      el.renameModal.setAttribute('aria-hidden','true');
      el.renameApplyBtn.onclick=null;
      el.renameCancelBtn.onclick=null;
      if(el.renameNameInput) el.renameNameInput.onkeydown=null;
      document.removeEventListener('keydown',onKey);
      resolve(value);
    };
    const onKey=(ev)=>{ if(ev.key==='Escape') close(''); };
    document.addEventListener('keydown',onKey);
    el.renameApplyBtn.onclick=()=>close(String(el.renameNameInput.value||'').trim());
    el.renameCancelBtn.onclick=()=>close('');
    el.renameNameInput.onkeydown=(ev)=>{ if(ev.key==='Enter'){ ev.preventDefault(); close(String(el.renameNameInput.value||'').trim()); } };
  });
}
function parseExtFilterInput(raw){
  const txt=String(raw||'').trim();
  if(!txt) return [];
  return txt.split(',').map((s)=>s.trim().toLowerCase()).filter(Boolean).map((e)=>e.startsWith('.')?e:`.${e}`);
}
function dirnameForKind(kind,path){
  if(!path) return '';
  if(kind==='local') return parentPath(path);
  const p=String(path).replace(/\/+$/,'');
  const i=p.lastIndexOf('/');
  return i<=0?'/':p.slice(0,i);
}
function upPathForPaneState(pane){
  if(!pane) return '';
  if(pane.kind==='sharepoint'){
    const current=normalizeSpPath(pane.path||pane.library||'/');
    return dirnameForKind('sharepoint', current);
  }
  return dirnameForKind('local', String(pane.path||'').trim());
}
async function navigatePaneUp(key){
  const pane=state[key];
  if(!pane) return;
  const target=upPathForPaneState(pane);
  if(!target || target===pane.path) return setStatus('Already at the top folder.');
  await loadPane(key, target);
}

function focusSplitSession(sessionId){
  const runtime=hydrateSplitRuntime(sessionId);
  if(sessionId===state.activeSessionId){
    syncActiveSessionFromSplitRuntime(runtime);
    return runtime;
  }
  saveCurrentSessionSnapshot();
  state.activeSessionId=sessionId;
  syncActiveSessionFromSplitRuntime(runtime);
  renderSessionTabs();
  return runtime;
}

function focusSplitPane(sessionId, side){
  const wasActive=(sessionId===state.activeSessionId);
  const runtime=focusSplitSession(sessionId);
  if(!runtime) return null;
  runtime.activePane=(side==='right'?'right':'left');
  persistSplitRuntimeSession(sessionId);
  if(!wasActive) renderSplitSessions();
  return runtime;
}

async function navigateSplitPaneUp(sessionId, side){
  const runtime=focusSplitSession(sessionId);
  const pane=runtime?.[side];
  if(!pane) return;
  const target=upPathForPaneState(pane);
  if(!target || target===pane.path) return setStatus('Already at the top folder.');
  await loadSplitPane(sessionId, side, target);
}
function sleep(ms){ return new Promise((resolve)=>setTimeout(resolve,ms)); }
const DEFAULT_RETRY_POLICY={max_attempts:3,base_delay_ms:1500,max_delay_ms:30000};
function defaultShortcuts(){
  return {copy:'Ctrl+C',cut:'Ctrl+X',paste:'Ctrl+V',delete:'Delete',rename:'F2',mkdir:'Ctrl+Shift+N',refresh:'F5'};
}
function normalizeShortcutString(raw){
  const t=String(raw||'').trim();
  if(!t) return '';
  const parts=t.replace(/\s+/g,'').split('+').filter(Boolean);
  const mods=[];
  let key='';
  parts.forEach((p)=>{
    const low=p.toLowerCase();
    if(low==='ctrl'||low==='control') mods.push('Ctrl');
    else if(low==='shift') mods.push('Shift');
    else if(low==='alt') mods.push('Alt');
    else if(low==='meta'||low==='cmd'||low==='command'||low==='win') mods.push('Meta');
    else key=p.length===1?p.toUpperCase():p[0].toUpperCase()+p.slice(1);
  });
  const uniq=[...new Set(mods)];
  return [...uniq,key].filter(Boolean).join('+');
}
function shortcutFromEvent(e){
  const mods=[];
  if(e.ctrlKey) mods.push('Ctrl');
  if(e.shiftKey) mods.push('Shift');
  if(e.altKey) mods.push('Alt');
  if(e.metaKey) mods.push('Meta');
  let key=e.key||'';
  if(key===' ') key='Space';
  if(key.length===1) key=key.toUpperCase();
  else key=key[0]?.toUpperCase()+key.slice(1);
  return [...mods,key].filter(Boolean).join('+');
}
function loadShortcuts(){
  try{
    const raw=JSON.parse(localStorage.getItem('smx_web_shortcuts')||'{}');
    state.shortcutBindings={...defaultShortcuts(),...(raw||{})};
  }catch{ state.shortcutBindings=defaultShortcuts(); }
}
function persistShortcuts(){
  localStorage.setItem('smx_web_shortcuts',JSON.stringify(state.shortcutBindings||defaultShortcuts()));
}
function renderShortcuts(){
  const s={...defaultShortcuts(),...(state.shortcutBindings||{})};
  if(el.scCopy) el.scCopy.value=s.copy||'';
  if(el.scCut) el.scCut.value=s.cut||'';
  if(el.scPaste) el.scPaste.value=s.paste||'';
  if(el.scDelete) el.scDelete.value=s.delete||'';
  if(el.scRename) el.scRename.value=s.rename||'';
  if(el.scMkdir) el.scMkdir.value=s.mkdir||'';
  if(el.scRefresh) el.scRefresh.value=s.refresh||'';
}
function saveShortcutsFromUi(){
  const next={
    copy:normalizeShortcutString(el.scCopy?.value||''),
    cut:normalizeShortcutString(el.scCut?.value||''),
    paste:normalizeShortcutString(el.scPaste?.value||''),
    delete:normalizeShortcutString(el.scDelete?.value||''),
    rename:normalizeShortcutString(el.scRename?.value||''),
    mkdir:normalizeShortcutString(el.scMkdir?.value||''),
    refresh:normalizeShortcutString(el.scRefresh?.value||''),
  };
  const used=new Set();
  for(const k of Object.keys(next)){
    const v=next[k];
    if(!v) continue;
    if(used.has(v)) return setStatus(`Duplicate shortcut: ${v}`);
    used.add(v);
  }
  state.shortcutBindings=next;
  persistShortcuts();
  renderShortcuts();
  setStatus('Shortcuts saved.');
}
function resetShortcuts(){
  state.shortcutBindings=defaultShortcuts();
  persistShortcuts();
  renderShortcuts();
  setStatus('Shortcuts reset.');
}
function buildShortcutActionMap(){
  return {
    copy:()=>setClipboard('copy'),
    cut:()=>setClipboard('cut'),
    paste:()=>pasteClipboard(),
    delete:()=>deleteSelected(),
    rename:()=>renameSelected(),
    mkdir:()=>createFolder(),
    refresh:()=>loadPane(activePane().key,activePane().path),
  };
}
function handleGlobalShortcutKeydown(e){
  const t=e.target;
  const inEditable=t && (t.tagName==='INPUT' || t.tagName==='TEXTAREA' || t.isContentEditable);
  if(inEditable) return;
  const combo=normalizeShortcutString(shortcutFromEvent(e));
  if(!combo) return;
  const bindings=state.shortcutBindings||defaultShortcuts();
  const actionKey=Object.keys(bindings).find((k)=>normalizeShortcutString(bindings[k])===combo);
  if(!actionKey) return;
  const fn=buildShortcutActionMap()[actionKey];
  if(!fn) return;
  e.preventDefault();
  fn();
}
function normalizeJobItem(it){
  if(!it||typeof it!=='object') return {kind:'local',path:'',isDir:false,name:'',site:'',attempt_count:0,next_retry_at:0,last_error:''};
  if(typeof it.attempt_count!=='number') it.attempt_count=0;
  if(typeof it.next_retry_at!=='number') it.next_retry_at=0;
  if(typeof it.last_error!=='string') it.last_error='';
  if(!('isDir' in it)) it.isDir=false;
  if(!('site' in it)) it.site='';
  return it;
}
function loadJobsState(){
  try{
    const jobs=JSON.parse(localStorage.getItem('smx_web_jobs')||'[]');
    state.jobs=Array.isArray(jobs)?jobs:[];
  }catch{ state.jobs=[]; }
  try{
    const retry=JSON.parse(localStorage.getItem('smx_web_retry_queue')||'[]');
    state.retryQueue=Array.isArray(retry)?retry:[];
  }catch{ state.retryQueue=[]; }
  state.jobs.forEach((j)=>{
    if(j.status==='running') j.status='queued';
    if(!Array.isArray(j.items)) j.items=[];
    j.items=j.items.map((it)=>normalizeJobItem(it));
    if(!Array.isArray(j.failures)) j.failures=[];
    j.failures=j.failures.map((it)=>normalizeJobItem(it));
    if(typeof j.index!=='number') j.index=0;
    if(typeof j.done!=='number') j.done=0;
    if(typeof j.failed!=='number') j.failed=0;
    if(!j.opts||typeof j.opts!=='object') j.opts={};
    j.opts.retry_policy={...DEFAULT_RETRY_POLICY,...(j.opts.retry_policy||{})};
  });
  const active=localStorage.getItem('smx_web_active_job_id')||'';
  state.activeJobId=(active&&state.jobs.find((j)=>j.id===active)?.id)||state.jobs[0]?.id||'';
}
function persistJobsState(){
  localStorage.setItem('smx_web_jobs',JSON.stringify(state.jobs||[]));
  localStorage.setItem('smx_web_retry_queue',JSON.stringify(state.retryQueue||[]));
  localStorage.setItem('smx_web_active_job_id',state.activeJobId||'');
}
function loadSearchFilters(){
  try{
    state.searchFilters=JSON.parse(localStorage.getItem('smx_web_search_filters')||'[]');
    if(!Array.isArray(state.searchFilters)) state.searchFilters=[];
  }catch{ state.searchFilters=[]; }
}
function loadAutomationRules(){
  try{
    const raw=JSON.parse(localStorage.getItem('smx_web_rules')||'[]');
    state.automationRules=Array.isArray(raw)?raw:[];
  }catch{ state.automationRules=[]; }
}
function loadGlossary(){
  try{
    const raw=JSON.parse(localStorage.getItem('smx_web_glossary')||'[]');
    state.glossary=Array.isArray(raw)?raw:[];
  }catch{ state.glossary=[]; }
}
function persistGlossary(){
  localStorage.setItem('smx_web_glossary',JSON.stringify(state.glossary||[]));
}
function renderGlossary(){
  if(!el.glossaryList) return;
  el.glossaryList.innerHTML='';
  if(!state.glossary.length){
    el.glossaryList.innerHTML='<small style="color:#94a3b8">No glossary entries.</small>';
    return;
  }
  state.glossary.forEach((g,idx)=>{
    const row=document.createElement('div');
    row.className='rule-row';
    row.innerHTML=`<div><strong>${escapeHtml(g.source||'')}</strong><small>${escapeHtml(g.target||'')}</small></div>`;
    const del=document.createElement('button');
    del.textContent='X';
    del.onclick=()=>{ state.glossary.splice(idx,1); persistGlossary(); renderGlossary(); };
    row.appendChild(del);
    el.glossaryList.appendChild(row);
  });
}
function addGlossaryEntry(){
  const source=(el.glossarySourceInput?.value||'').trim();
  const target=(el.glossaryTargetInput?.value||'').trim();
  if(!source||!target) return setStatus('Glossary requires source and target.');
  state.glossary=state.glossary.filter((g)=>String(g.source||'').toLowerCase()!==source.toLowerCase());
  state.glossary.unshift({source,target});
  state.glossary=state.glossary.slice(0,400);
  persistGlossary();
  renderGlossary();
  if(el.glossarySourceInput) el.glossarySourceInput.value='';
  if(el.glossaryTargetInput) el.glossaryTargetInput.value='';
  setStatus('Glossary entry added.');
}
function applyGlossary(text){
  let out=String(text||'');
  for(const g of (state.glossary||[])){
    const src=String(g.source||'');
    const tgt=String(g.target||'');
    if(!src||!tgt) continue;
    out=out.split(src).join(tgt);
  }
  return out;
}
function loadTranslationLocalCache(){
  try{
    const raw=JSON.parse(localStorage.getItem('smx_web_translation_cache')||'{}');
    state.translationLocalCache=(raw&&typeof raw==='object')?raw:{};
  }catch{ state.translationLocalCache={}; }
}
function persistTranslationLocalCache(){
  localStorage.setItem('smx_web_translation_cache',JSON.stringify(state.translationLocalCache||{}));
}
function translationCacheKey(language,name){
  return `${String(language||'English').toLowerCase()}|${String(name||'').toLowerCase()}`;
}
function rememberTranslation(language,name,translated){
  if(!name||!translated) return;
  state.translationLocalCache[translationCacheKey(language,name)]=String(translated);
}
function getCachedTranslation(language,name){
  return state.translationLocalCache[translationCacheKey(language,name)]||'';
}
function loadPdfBookmarks(){
  try{
    const raw=JSON.parse(localStorage.getItem('smx_web_pdf_bookmarks')||'[]');
    state.pdfBookmarks=Array.isArray(raw)?raw:[];
  }catch{ state.pdfBookmarks=[]; }
}
function persistPdfBookmarks(){
  localStorage.setItem('smx_web_pdf_bookmarks',JSON.stringify(state.pdfBookmarks||[]));
}
function renderPdfBookmarks(){
  if(!el.pdfBookmarksList) return;
  el.pdfBookmarksList.innerHTML='';
  const p=activePane(), path=selectedSinglePath();
  const rows=(state.pdfBookmarks||[]).filter((b)=>b.kind===p.kind && b.path===path && (p.kind!=='sharepoint' || (b.site||'')===(p.site||'')));
  if(!rows.length){
    el.pdfBookmarksList.innerHTML='<small style="color:#94a3b8">No PDF bookmarks for current file.</small>';
    return;
  }
  rows.forEach((b,idx)=>{
    const row=document.createElement('div');
    row.className='rule-row';
    row.innerHTML=`<div><strong>Page ${Number(b.page||1)}</strong><small>${escapeHtml(b.note||'bookmark')}</small></div>`;
    const act=document.createElement('div');
    const go=document.createElement('button');
    go.textContent='Go';
    go.onclick=()=>jumpToPdfPage(Number(b.page||1));
    const del=document.createElement('button');
    del.textContent='X';
    del.onclick=()=>{
      const all=state.pdfBookmarks||[];
      const matchIndex=all.findIndex((x)=>x.id===b.id);
      if(matchIndex>=0) all.splice(matchIndex,1);
      persistPdfBookmarks(); renderPdfBookmarks();
    };
    act.appendChild(go); act.appendChild(del);
    row.appendChild(act);
    el.pdfBookmarksList.appendChild(row);
  });
}
function jumpToPdfPage(page){
  const p=activePane(), path=selectedSinglePath();
  if(!path||extname(path)!=='.pdf') return setStatus('Select one PDF first.');
  const n=Math.max(1,Number(page||1)||1);
  const url=`${downloadUrl(p,path)}#page=${n}`;
  el.previewFrame.innerHTML=`<iframe src="${url}"></iframe>`;
  setStatus(`Jumped to PDF page ${n}.`);
}
function addPdfBookmark(){
  const p=activePane(), path=selectedSinglePath();
  if(!path||extname(path)!=='.pdf') return setStatus('Select one PDF first.');
  const page=Math.max(1,Number(el.pdfPageInput?.value||1)||1);
  const note=(prompt('Bookmark note (optional):','')||'').trim();
  state.pdfBookmarks.unshift({id:`pb-${Date.now()}-${Math.floor(Math.random()*1000)}`,kind:p.kind,path,site:p.site||'',page,note});
  state.pdfBookmarks=state.pdfBookmarks.slice(0,1000);
  persistPdfBookmarks(); renderPdfBookmarks();
  setStatus(`PDF bookmark added (page ${page}).`);
}
function persistAutomationRules(){
  localStorage.setItem('smx_web_rules',JSON.stringify(state.automationRules||[]));
}
function renderAutomationRules(){
  if(!el.rulesList) return;
  el.rulesList.innerHTML='';
  if(!state.automationRules.length){
    el.rulesList.innerHTML='<small style="color:#94a3b8">No rules configured.</small>';
    return;
  }
  state.automationRules.forEach((r,idx)=>{
    const row=document.createElement('div');
    row.className='rule-row';
    row.innerHTML=`<div><strong>${escapeHtml(r.match||'')}</strong><small>${escapeHtml(r.action||'')} -> ${escapeHtml(r.value||'')}</small></div>`;
    const del=document.createElement('button');
    del.textContent='X';
    del.onclick=()=>{ state.automationRules.splice(idx,1); persistAutomationRules(); renderAutomationRules(); };
    row.appendChild(del);
    el.rulesList.appendChild(row);
  });
}
function addAutomationRule(){
  const match=(el.ruleMatchInput?.value||'').trim().toLowerCase();
  const action=(el.ruleActionSelect?.value||'add_tag').trim();
  const value=(el.ruleValueInput?.value||'').trim();
  if(!match||!value) return setStatus('Rule requires match and value.');
  state.automationRules.unshift({id:`r-${Date.now()}`,match,action,value});
  state.automationRules=state.automationRules.slice(0,120);
  persistAutomationRules();
  renderAutomationRules();
  if(el.ruleMatchInput) el.ruleMatchInput.value='';
  if(el.ruleValueInput) el.ruleValueInput.value='';
  setStatus('Automation rule added.');
}
async function applyAutomationRulesToSelection(){
  const p=activePane();
  const items=selectedItems(p);
  if(!items.length) return setStatus('Select item(s) first.');
  if(!state.automationRules.length) return setStatus('No automation rules configured.');
  let touched=0;
  for(const it of items){
    const name=String(it.name||'').toLowerCase();
    const matched=state.automationRules.filter((r)=>name.includes(String(r.match||'')));
    for(const r of matched){
      try{
        if(r.action==='add_tag'){
          const d=await apiGet(`/api/tags/get?${new URLSearchParams({kind:p.kind,identifier:it.path}).toString()}`);
          const tags=new Set((d.tags||[]).map((t)=>String(t)));
          tags.add(String(r.value));
          await apiPost('/api/tags/set',{kind:p.kind,identifier:it.path,tags:Array.from(tags)});
          touched++;
        }else if(r.action==='rename_prefix'){
          const newName=String(r.value||'') + String(it.name||'');
          if(newName!==it.name){
            if(p.kind==='local') await apiPost('/api/local/rename',{path:it.path,new_name:newName});
            else await apiPost('/api/sp/rename',{server_relative_url:it.path,new_name:newName,is_folder:!!it.isDir,site_relative_url:p.site||null});
            touched++;
          }
        }else if(r.action==='move_to_pane'){
          const targetKey=(String(r.value||'').toLowerCase()==='left')?'left':'right';
          const target=state[targetKey];
          if(target.path){
            await executeTransfer([{kind:p.kind,path:it.path,isDir:!!it.isDir,site:p.site||''}],{kind:target.kind,path:target.path,site:target.site||''},true,true);
            touched++;
          }
        }
      }catch{
        // continue with next rule/item
      }
    }
  }
  await loadPane('left',state.left.path); await loadPane('right',state.right.path);
  setStatus(`Automation rules applied. Actions executed: ${touched}`);
}
function saveSearchFilters(){
  localStorage.setItem('smx_web_search_filters',JSON.stringify(state.searchFilters||[]));
}
function currentSearchFilterFromUi(){
  return {
    query:(el.searchQueryInput?.value||'').trim(),
    include_local:!!el.searchIncludeLocal?.checked,
    include_sharepoint:!!el.searchIncludeSp?.checked,
    extensions:parseExtFilterInput(el.searchExtInput?.value||''),
    max_results:Math.max(10,Math.min(2000,Number(el.searchMaxInput?.value||200)||200)),
  };
}
function applySearchFilterToUi(f){
  if(!f) return;
  if(el.searchQueryInput) el.searchQueryInput.value=f.query||'';
  if(el.searchIncludeLocal) el.searchIncludeLocal.checked=!!f.include_local;
  if(el.searchIncludeSp) el.searchIncludeSp.checked=!!f.include_sharepoint;
  if(el.searchExtInput) el.searchExtInput.value=Array.isArray(f.extensions)?f.extensions.join(','):'';
  if(el.searchMaxInput) el.searchMaxInput.value=String(f.max_results||200);
}
function renderSearchFilters(){
  if(!el.searchFilterSelect) return;
  el.searchFilterSelect.innerHTML='';
  const blank=document.createElement('option');
  blank.value='';
  blank.textContent='Saved filters';
  el.searchFilterSelect.appendChild(blank);
  state.searchFilters.forEach((f,idx)=>{
    const o=document.createElement('option');
    o.value=String(idx);
    o.textContent=f.name||`Filter ${idx+1}`;
    el.searchFilterSelect.appendChild(o);
  });
}
function renderSearchResults(){
  if(!el.searchResults) return;
  el.searchResults.innerHTML='';
  if(!state.searchResults.length){
    el.searchResults.innerHTML='<small style="color:#94a3b8">No results.</small>';
    return;
  }
  state.searchResults.forEach((r)=>{
    const row=document.createElement('div');
    row.className='search-row';
    const info=document.createElement('div');
    info.innerHTML=`<strong>${escapeHtml(r.name||'')}</strong><small>${escapeHtml(r.kind||'')} | ${escapeHtml(r.path||'')}</small>`;
    const act=document.createElement('div');
    const open=document.createElement('button');
    open.textContent='Open';
    open.onclick=async()=>{
      const pane=activePane();
      if(r.kind==='sharepoint'){
        pane.kind='sharepoint';
        pane.site=r.site_relative_url||pane.site||'';
        if(pane.kind==='sharepoint'){ await loadSitesForPane(pane); await loadLibrariesForPane(pane); }
        pane.path=r.isDir?r.path:dirnameForKind('sharepoint',r.path);
      }else{
        pane.kind='local';
        pane.path=r.isDir?r.path:dirnameForKind('local',r.path);
      }
      updatePaneControls(pane.key);
      await loadPane(pane.key,pane.path);
      pane.selected.clear();
      pane.selected.add(r.path);
      renderPane(pane.key);
      setStatus(`Opened search result: ${r.name}`);
    };
    act.appendChild(open);
    row.appendChild(info);
    row.appendChild(act);
    el.searchResults.appendChild(row);
  });
}
async function runGlobalSearch(){
  const active=activePane();
  const payload=currentSearchFilterFromUi();
  payload.local_root=state.left.kind==='local'?state.left.path:(state.right.kind==='local'?state.right.path:'');
  if(active.kind==='sharepoint'){
    payload.site_relative_url=active.site||null;
    payload.library_server_relative_url=active.library||active.path||null;
  }else{
    const spPane=state.left.kind==='sharepoint'?state.left:(state.right.kind==='sharepoint'?state.right:null);
    if(spPane){
      payload.site_relative_url=spPane.site||null;
      payload.library_server_relative_url=spPane.library||spPane.path||null;
    }
  }
  try{
    const d=await apiPost('/api/search/global',payload);
    state.searchResults=d.results||[];
    renderSearchResults();
    const errs=(d.errors||[]);
    setStatus(`Search complete: ${state.searchResults.length} result(s).${errs.length?` ${errs.length} warning(s).`:''}`);
  }catch(e){ setStatus(`Search failed: ${err(e)}`); }
}
function saveCurrentSearchFilter(){
  const name=(prompt('Filter name:','')||'').trim();
  if(!name) return;
  const f=currentSearchFilterFromUi();
  state.searchFilters=state.searchFilters.filter((x)=>x.name!==name);
  state.searchFilters.unshift({name,...f});
  state.searchFilters=state.searchFilters.slice(0,40);
  saveSearchFilters();
  renderSearchFilters();
  setStatus(`Saved search filter: ${name}`);
}
function applySelectedSearchFilter(){
  const idx=Number(el.searchFilterSelect?.value||'-1');
  if(Number.isNaN(idx)||idx<0||idx>=state.searchFilters.length) return;
  applySearchFilterToUi(state.searchFilters[idx]);
}
function deleteSelectedSearchFilter(){
  const idx=Number(el.searchFilterSelect?.value||'-1');
  if(Number.isNaN(idx)||idx<0||idx>=state.searchFilters.length) return;
  const removed=state.searchFilters.splice(idx,1)[0];
  saveSearchFilters();
  renderSearchFilters();
  setStatus(`Deleted search filter: ${removed?.name||'item'}`);
}
function newJob(type,items,opts){
  const retry_policy={...DEFAULT_RETRY_POLICY,...(opts?.retry_policy||{})};
  return {
    id:`job-${Date.now()}-${Math.floor(Math.random()*100000)}`,
    type,
    status:'queued',
    items:(items||[]).map((it)=>normalizeJobItem({...it})),
    index:0,
    done:0,
    failed:0,
    failures:[],
    opts:{...(opts||{}),retry_policy},
    createdAt:new Date().toISOString(),
  };
}
function activeJob(){
  return state.jobs.find((j)=>j.id===state.activeJobId)||null;
}
function exportJobsHistory(){
  const payload={exportedAt:new Date().toISOString(),jobs:state.jobs,retryQueue:state.retryQueue};
  const blob=new Blob([JSON.stringify(payload,null,2)],{type:'application/json'});
  const a=document.createElement('a');
  a.href=URL.createObjectURL(blob);
  a.download=`smx-jobs-history-${Date.now()}.json`;
  a.click();
  URL.revokeObjectURL(a.href);
  setStatus('Exported jobs history.');
}
function clearFinishedJobs(){
  const before=state.jobs.length;
  state.jobs=state.jobs.filter((j)=>!['done','failed','canceled'].includes(j.status));
  if(!state.jobs.find((j)=>j.id===state.activeJobId)) state.activeJobId=state.jobs[0]?.id||'';
  renderJobs();
  setStatus(`Cleared ${before-state.jobs.length} finished job(s).`);
}
function renderJobs(){
  if(!el.jobsList) return;
  persistJobsState();
  el.jobsList.innerHTML='';
  if(!state.jobs.length){
    el.jobsList.innerHTML='<small style="color:#94a3b8">No jobs queued.</small>';
    return;
  }
  state.jobs.forEach((j)=>{
    const row=document.createElement('div');
    row.className=`job-row${j.id===state.activeJobId?' active':''}`;
    const total=(j.items||[]).length;
    row.innerHTML=`<strong>${escapeHtml(j.type||'job')}</strong><small>${escapeHtml(j.status)} | ${j.done||0}/${total} done | ${j.failed||0} failed</small>`;
    const nextItem=(j.items||[])[j.index];
    if(nextItem&&nextItem.next_retry_at&&nextItem.next_retry_at>Date.now()){
      const secs=Math.max(1,Math.ceil((nextItem.next_retry_at-Date.now())/1000));
      row.innerHTML += `<small>next retry in ${secs}s | attempts ${nextItem.attempt_count||0}/${j.opts?.retry_policy?.max_attempts||DEFAULT_RETRY_POLICY.max_attempts}</small>`;
    }
    row.onclick=()=>{ state.activeJobId=j.id; renderJobs(); };
    el.jobsList.appendChild(row);
  });
  renderQueueMetrics();
}
function renderQueueMetrics(){
  if(!el.queueMetrics) return;
  const jobs=state.jobs||[];
  const queued=jobs.filter((j)=>j.status==='queued').length;
  const running=jobs.filter((j)=>j.status==='running').length;
  const paused=jobs.filter((j)=>j.status==='paused').length;
  const done=jobs.filter((j)=>j.status==='done').length;
  const failed=jobs.filter((j)=>j.status==='failed').length;
  const canceled=jobs.filter((j)=>j.status==='canceled').length;
  const now=Date.now();
  const recent=(state.jobEvents||[]).filter((e)=>now-Number(e.ts||0)<=5*60*1000);
  const doneRecent=recent.filter((e)=>e.outcome==='done').length;
  const failRecent=recent.filter((e)=>e.outcome==='failed').length;
  const throughputPerMin=((doneRecent/5)||0).toFixed(1);
  const totalRecent=doneRecent+failRecent;
  const successRate=totalRecent?`${Math.round((doneRecent/totalRecent)*100)}%`:'n/a';
  el.queueMetrics.innerHTML=
    `<div class="metric-card"><strong>Queue</strong>queued ${queued} | running ${running} | paused ${paused}</div>`+
    `<div class="metric-card"><strong>Finished</strong>done ${done} | failed ${failed} | canceled ${canceled}</div>`+
    `<div class="metric-card"><strong>Throughput</strong>${throughputPerMin} items/min (5m)</div>`+
    `<div class="metric-card"><strong>Success Rate</strong>${successRate} (5m)</div>`;
}
async function dryRunBulkOperation(){
  const srcPane=activePane();
  const items=selectedItems(srcPane).map((it)=>({kind:srcPane.kind,path:it.path,isDir:!!it.isDir,name:it.name,site:srcPane.site||''}));
  if(!items.length) return setStatus('Select one or more items for bulk operation.');
  const type=el.bulkOpType?.value||'copy';
  const targetPaneKey=el.bulkTargetPane?.value||'right';
  const policy=el.bulkConflictPolicy?.value||'skip';
  const targetPane=state[targetPaneKey];
  if(type!=='delete' && !targetPane?.path) return setStatus('Target pane must have a destination path.');
  let dry;
  try{
    dry=await apiPost('/api/bulk/dry-run',{
      operation:type,
      conflict_policy:policy,
      destination_kind:type==='delete'?null:targetPane.kind,
      destination_path:type==='delete'?null:(targetPane.path||''),
      destination_site_relative_url:type==='delete'?null:(targetPane.site||null),
      sources:items.map((it)=>({kind:it.kind,path:it.path,isDir:!!it.isDir,name:it.name,site_relative_url:it.site||null})),
    });
  }catch(e){
    return setStatus(`Dry run failed: ${err(e)}`);
  }
  const rows=dry.rows||[];
  const blocked=rows.filter((r)=>r.status==='blocked').length;
  state.bulkDryRun={type,targetPaneKey,policy,rows,items,summary:dry.summary||null,errors:dry.errors||[]};
  if(el.bulkDryRunOutput) el.bulkDryRunOutput.textContent=JSON.stringify(state.bulkDryRun,null,2);
  setStatus(`Dry run complete: ${rows.length-blocked} ready, ${blocked} blocked.`);
}
function buildDryRunPayloadForItems(job,items){
  const type=job.type;
  const destPane=state[job.opts.targetPane||'right'];
  return {
    operation:type,
    conflict_policy:job.opts.policy||'skip',
    destination_kind:type==='delete'?null:destPane.kind,
    destination_path:type==='delete'?null:(destPane.path||''),
    destination_site_relative_url:type==='delete'?null:(destPane.site||null),
    sources:(items||[]).map((it)=>({kind:it.kind,path:it.path,isDir:!!it.isDir,name:it.name||basename(it.path),site_relative_url:it.site||null})),
  };
}
async function preflightSingleItem(job,item){
  if(job.type==='delete') return {ok:true,row:{status:'ok'}};
  const d=await apiPost('/api/bulk/dry-run',buildDryRunPayloadForItems(job,[item]));
  const row=(d.rows||[])[0]||{status:'blocked',reason:'unknown'};
  return {ok:row.status!=='blocked',row,raw:d};
}
function isRetryableError(message){
  const m=String(message||'').toLowerCase();
  if(!m) return true;
  const nonRetryable=['target_exists_skip','target_exists_fail','preflight_blocked','not_supported','invalid','missing_path','permission denied','403','401'];
  return !nonRetryable.some((x)=>m.includes(x));
}
function computeBackoffDelay(attempt,retryPolicy){
  const p={...DEFAULT_RETRY_POLICY,...(retryPolicy||{})};
  const exp=Math.max(0,(attempt||1)-1);
  const raw=p.base_delay_ms*Math.pow(2,exp);
  const jitter=Math.floor(Math.random()*300);
  return Math.min(p.max_delay_ms,raw+jitter);
}
async function executeSingleJobItem(job,item){
  const type=job.type;
  const destPane=state[job.opts.targetPane||'right'];
  const policy=job.opts.policy||'skip';
  const pre=await preflightSingleItem(job,item);
  if(!pre.ok){
    if(policy==='skip') throw new Error(`preflight_blocked_skip:${pre.row.reason||'blocked'}`);
    throw new Error(`preflight_blocked:${pre.row.reason||'blocked'}`);
  }
  if(type==='delete'){
    if(item.kind==='local') return apiPost('/api/local/delete',{sources:[item.path]});
    return apiPost('/api/sp/delete',{server_relative_url:item.path,is_folder:!!item.isDir,site_relative_url:item.site||null,recycle:true});
  }
  const targetPath=destPane.path||'';
  const targetName=basename(item.path);
  if(destPane.kind==='local' && policy==='overwrite'){
    const sep=(targetPath.includes('\\')?'\\':'/');
    const destFull=targetPath.replace(/[\\\/]+$/,'') + (targetPath.endsWith('\\')||targetPath.endsWith('/')?'':sep) + targetName;
    const list=await apiGet(`/api/local/list?${new URLSearchParams({path:targetPath}).toString()}`);
    const exists=(list.items||[]).some((x)=>String(x.name||'').toLowerCase()===String(targetName).toLowerCase());
    if(exists) await apiPost('/api/local/delete',{sources:[destFull]});
  }
  if(destPane.kind==='local'){
    if(item.kind==='local'){
      return apiPost(type==='move'?'/api/local/move':'/api/local/copy',{sources:[item.path],destination:targetPath});
    }
    return apiPost('/api/transfer/sp-to-local',{
      site_relative_url:item.site||null,
      server_relative_urls:[item.path],
      source_items:[{
        kind:'sharepoint',
        path:item.path,
        isDir:!!item.isDir,
        name:targetName,
        site_relative_url:item.site||null,
      }],
      destination_dir:targetPath,
      move:type==='move',
    });
  }
  if(item.kind==='sharepoint'){
    const dst=`${(targetPath||'/').replace(/\/+$/,'')}/${targetName}`;
    const result=await apiPost(type==='move'?'/api/sp/move':'/api/sp/copy',{source_server_relative_url:item.path,target_server_relative_url:dst,is_folder:!!item.isDir,overwrite:policy==='overwrite',site_relative_url:item.site||destPane.site||null});
    if(type==='move') recordMigration('move',item.isDir?'folder':'file',item.path,dst,item.site||'',destPane.site||item.site||'');
    return result;
  }
  if(item.isDir) throw new Error('local_folder_to_sp_not_supported');
  return apiPost('/api/transfer/local-to-sp',{site_relative_url:destPane.site||null,source_paths:[item.path],destination_server_relative_url:targetPath,move:type==='move',overwrite:policy==='overwrite'});
}
async function runJobLoop(){
  if(state.jobRunnerActive) return;
  state.jobRunnerActive=true;
  try{
    while(true){
      const now=Date.now();
      let job=null;
      let nearestDue=0;
      for(const j of state.jobs){
        if(!(j.status==='queued'||j.status==='running')) continue;
        if(j.status==='queued') j.status='running';
        if(j.status==='paused' || j.status==='canceled') continue;
        if(j.index>=j.items.length){
          j.status=j.failed?'failed':'done';
          continue;
        }
        j.items[j.index]=normalizeJobItem(j.items[j.index]);
        const due=Number(j.items[j.index].next_retry_at||0);
        if(due<=now){ job=j; break; }
        if(!nearestDue||due<nearestDue) nearestDue=due;
      }
      if(!job){
        if(nearestDue){
          await sleep(Math.max(40,Math.min(1000,nearestDue-Date.now())));
          continue;
        }
        break;
      }
      const itemIndex=job.index;
      const item=normalizeJobItem(job.items[itemIndex]);
      job.items[itemIndex]=item;
      item.attempt_count=(item.attempt_count||0)+1;
      item.next_retry_at=0;
      try{
        await executeSingleJobItem(job,item);
        job.done++;
        state.jobEvents.unshift({ts:Date.now(),outcome:'done',jobId:job.id,path:item.path||''});
        state.jobEvents=state.jobEvents.slice(0,2000);
        job.index++;
      }catch(e){
        const message=err(e);
        item.last_error=message;
        const retryable=isRetryableError(message);
        const retryPolicy={...DEFAULT_RETRY_POLICY,...(job.opts?.retry_policy||{})};
        if(retryable && item.attempt_count < retryPolicy.max_attempts){
          item.next_retry_at=Date.now()+computeBackoffDelay(item.attempt_count,retryPolicy);
        }else{
          job.failed++;
          state.jobEvents.unshift({ts:Date.now(),outcome:'failed',jobId:job.id,path:item.path||'',error:message});
          state.jobEvents=state.jobEvents.slice(0,2000);
          const fail={...item,error:message,jobId:job.id,attempt_count:item.attempt_count};
          job.failures.push(fail);
          state.retryQueue.push(fail);
          job.index++;
        }
      }finally{
        job.items[itemIndex]=item;
        renderJobs();
      }
      await sleep(30);
    }
  }finally{
    state.jobRunnerActive=false;
    renderJobs();
  }
}
function queueBulkOperationJob(){
  const srcPane=activePane();
  const items=selectedItems(srcPane).map((it)=>({kind:srcPane.kind,path:it.path,isDir:!!it.isDir,name:it.name,site:srcPane.site||''}));
  if(!items.length) return setStatus('Select one or more items for bulk operation.');
  const type=el.bulkOpType?.value||'copy';
  const targetPane=el.bulkTargetPane?.value||'right';
  const policy=el.bulkConflictPolicy?.value||'skip';
  if(type!=='delete' && !state[targetPane]?.path) return setStatus('Target pane must have a destination path.');
  const job=newJob(type,items,{targetPane,policy});
  state.jobs.unshift(job);
  state.activeJobId=job.id;
  renderJobs();
  setStatus(`Queued job ${job.id} (${type}, ${items.length} item(s)).`);
  runJobLoop();
}
function pauseActiveJob(){ const j=activeJob(); if(!j) return; j.status='paused'; renderJobs(); setStatus(`Paused ${j.id}`); }
function resumeActiveJob(){ const j=activeJob(); if(!j) return; if(j.status==='paused'||j.status==='queued'){ j.status='running'; renderJobs(); setStatus(`Resumed ${j.id}`); runJobLoop(); } }
function cancelActiveJob(){ const j=activeJob(); if(!j) return; j.status='canceled'; renderJobs(); setStatus(`Canceled ${j.id}`); }
function retryFailedItems(){
  const j=activeJob();
  const failed=(j&&Array.isArray(j.failures)&&j.failures.length)?j.failures:state.retryQueue;
  if(!failed.length) return setStatus('No failed items to retry.');
  const type=el.bulkOpType?.value||'copy';
  const targetPane=el.bulkTargetPane?.value||'right';
  const policy=el.bulkConflictPolicy?.value||'skip';
  const job=newJob(type,failed.map((x)=>({kind:x.kind,path:x.path,isDir:!!x.isDir,name:basename(x.path),site:x.site||'',attempt_count:0,next_retry_at:0,last_error:''})),{targetPane,policy});
  state.jobs.unshift(job);
  state.activeJobId=job.id;
  if(j&&j.failures) j.failures=[];
  state.retryQueue=[];
  renderJobs();
  setStatus(`Queued retry job ${job.id} (${job.items.length} item(s)).`);
  runJobLoop();
}

async function apiGet(url){ const r=await fetch(url); if(!r.ok) throw new Error(await r.text()); return r.json(); }
async function apiPost(url,body){ const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body||{})}); if(!r.ok) throw new Error(await r.text()); return r.json(); }
function fillSelect(sel,rows,val,label,selected=''){ sel.innerHTML=''; rows.forEach(r=>{ const o=document.createElement('option'); o.value=String(r[val]??''); o.textContent=String(r[label]??r[val]??''); if(String(o.value)===String(selected)) o.selected=true; sel.appendChild(o); }); }
function aiModelPresets(provider){
  const key=String(provider||'openai').trim().toLowerCase();
  return Array.isArray(AI_MODEL_PRESETS[key]) ? [...AI_MODEL_PRESETS[key]] : [...AI_MODEL_PRESETS.openai];
}
function renderAiModelOptions(provider, selected=''){
  if(!el.aiModelInput) return;
  const presets=aiModelPresets(provider);
  const current=String(selected||'').trim();
  const values=current && !presets.includes(current) ? [...presets, current] : presets;
  el.aiModelInput.innerHTML='';
  values.forEach((model)=>{
    const option=document.createElement('option');
    option.value=model;
    option.textContent=model;
    if(model===current) option.selected=true;
    el.aiModelInput.appendChild(option);
  });
  if(current){
    el.aiModelInput.value=current;
  }else if(values.length){
    el.aiModelInput.value=values[0];
  }
}

function renderSpAuthState(settings){
  if(!el.spAuthState) return;
  const base=String(settings?.sp_base_url||'').trim();
  const hasCookies=!!settings?.sp_has_cookies;
  const baseLabel=base?`Base URL: ${base}`:'Base URL: not configured';
  const cookieLabel=`Cookies: ${hasCookies?'loaded':'missing'}`;
  el.spAuthState.textContent=`Status: ${baseLabel} | ${cookieLabel}`;
}

function parseSharePointSitesInput(raw){
  const rows=String(raw||'').replaceAll(',', '\n').split('\n');
  const out=[];
  const seen=new Set();
  for(const row of rows){
    let value=String(row||'').trim();
    if(!value) continue;
    if(/^https?:\/\//i.test(value)){
      try{
        value=new URL(value).pathname||'/';
      }catch{}
    }
    if(!value.startsWith('/')) value='/'+value;
    value=value.replace(/\/+$/,'')||'/';
    const key=value.toLowerCase();
    if(seen.has(key)) continue;
    seen.add(key);
    out.push(value);
  }
  return out;
}

async function refreshSpAuthPanel(){
  try{
    const settings=await apiGet('/api/settings');
    if(el.spBaseUrlInput) el.spBaseUrlInput.value=String(settings?.sp_base_url||'');
    if(el.spSitesListInput) el.spSitesListInput.value=(settings?.sp_site_allowlist||[]).join('\n');
    renderSpAuthState(settings);
  }catch(e){
    if(el.spAuthState) el.spAuthState.textContent=`Status: failed to load (${err(e)})`;
  }
}

async function saveSpAuthFromPortal(){
  const base=String(el.spBaseUrlInput?.value||'').trim();
  const allowlist=parseSharePointSitesInput(el.spSitesListInput?.value||'');
  const cookieHeader=String(el.spCookieHeaderInput?.value||'').trim();
  if(!base && !allowlist.length) return setStatus('Enter SharePoint site URL or site list before saving access.');
  try{
    await apiPost('/api/settings',{sp_base_url:base||null, sp_site_allowlist:allowlist});
    if(cookieHeader){
      if(!base) return setStatus('Enter SharePoint site URL to save cookies.');
      await apiPost('/api/sp/cookies',{base_url:base,cookie_header:cookieHeader});
      if(el.spCookieHeaderInput) el.spCookieHeaderInput.value='';
    }
    await refreshSpAuthPanel();
    setStatus(cookieHeader?'SharePoint settings and cookies saved.':'SharePoint settings saved.');
  }catch(e){
    setStatus(`SharePoint access save failed: ${err(e)}`);
  }
}

async function startEmbeddedSharePointSignIn(){
  const base=String(el.spBaseUrlInput?.value||'').trim();
  if(!base) return setStatus('Enter SharePoint site URL first.');
  if(!window.smxDesktop || typeof window.smxDesktop.signInSharePoint!=='function'){
    return setStatus('Embedded sign-in is only available in Electron WebShell.');
  }
  setStatus('Opening SharePoint sign-in window...');
  try{
    const result=await window.smxDesktop.signInSharePoint(base);
    if(result?.ok){
      await refreshSpAuthPanel();
      setStatus(result.message||'SharePoint sign-in completed and cookies captured.');
      return;
    }
    setStatus(`Embedded sign-in failed: ${result?.message||'Unknown error'}`);
  }catch(e){
    setStatus(`Embedded sign-in failed: ${err(e)}`);
  }
}

function updatePaneControls(key){
  const p=state[key], ui=paneEls(key);
  ui.kind.value=p.kind; ui.path.value=p.path||'';
  if(ui.filter) ui.filter.value=p.filterText||'';
  const sp=p.kind==='sharepoint';
  ui.site.classList.toggle('hidden',!sp); ui.library.classList.toggle('hidden',!sp);
  ui.uploadBtn.classList.toggle('hidden',!p.path);
}

function inferSharePointSiteFromPath(path){
  const raw=String(path||'').trim();
  if(!raw.startsWith('/')) return '';
  const parts=raw.split('/').filter(Boolean);
  if(parts.length>=2 && (parts[0].toLowerCase()==='sites' || parts[0].toLowerCase()==='teams')){
    return `/${parts[0]}/${parts[1]}`;
  }
  return '';
}

async function loadSitesForPane(p){
  try{
    const d=await apiGet('/api/sp/sites');
    p.sites=(d.sites||[]).map(s=>({site:s.server_relative_url||s.serverRelativeUrl||'',title:s.title||s.url||'Site'})).filter((s)=>String(s.site||'').trim());
    if(!p.sites.length) p.sites=[{site:'',title:'Auto (from path)'}];
    if(!p.site&&p.sites.length) p.site=p.sites[0].site||'';
  }catch{ p.sites=[{site:'',title:'Auto (from path)'}]; p.site=''; }
  p.siteTitle=findSiteTitle(p.site,p.sites,p.siteTitle||'');
  fillSelect(paneEls(p.key).site,p.sites,'site','title',p.site);
}

async function loadLibrariesForPane(p){
  try{
    const query=new URLSearchParams();
    if(p.site) query.set('site_relative_url',p.site);
    const d=await apiGet(`/api/sp/libraries?${query.toString()}`);
    p.libraries=(d.libraries||[]).map(l=>({path:l.server_relative_url||l.serverRelativeUrl||'',title:l.title||l.name||'Library'})).filter(x=>x.path);
    const hasCurrent=p.libraries.some((lib)=>String(lib.path||'')===String(p.library||''));
    if(!hasCurrent) p.library=p.libraries.length ? p.libraries[0].path : '';
  }catch{ p.libraries=[]; }
  fillSelect(paneEls(p.key).library,p.libraries,'path','title',p.library);
}

async function switchPaneKind(key,kind){
  const p=state[key]; p.kind=kind; p.selected.clear(); p.items=[]; p.translations.clear();
  if(kind==='local'){
    const h=await apiGet('/api/local/home'); p.path=h.path; updatePaneControls(key); await loadPane(key,p.path); return;
  }
  await loadSitesForPane(p); await loadLibrariesForPane(p); p.path=p.library||p.site||'/'; updatePaneControls(key); if(p.path) await loadPane(key,p.path);
}
function rememberRecent(p){
  if(!p.path) return;
  const key=`${p.kind}|${p.site||''}|${p.path}`;
  state.recent=state.recent.filter(x=>x.key!==key);
  state.recent.unshift({key,kind:p.kind,site:p.site||'',path:p.path,at:new Date().toISOString()});
  state.recent=state.recent.slice(0,60);
  localStorage.setItem('smx_web_recent',JSON.stringify(state.recent));
  renderRecent();
}

async function refreshTranslations(key){
  const p=state[key]; p.translations.clear();
  if(!state.translationEnabled||!p.items.length) return;
  try{
    const d=await apiPost('/api/translate',{language:state.language,items:p.items.map(it=>({name:it.name,path:it.path,mtime:it.mtime||0}))});
    (d.translations||[]).forEach((t,i)=>{
      const name=p.items[i]?.name||'';
      const translated=applyGlossary(t||name);
      p.translations.set(p.items[i].path,translated);
      rememberTranslation(state.language,name,translated);
    });
    persistTranslationLocalCache();
  }catch(e){
    // Offline-first fallback: reuse local translation cache by name
    p.items.forEach((it)=>{
      const cached=getCachedTranslation(state.language,it.name);
      if(cached) p.translations.set(it.path,applyGlossary(cached));
    });
    setStatus(`Translation failed; fallback cache applied: ${err(e)}`);
  }
}

async function loadPane(key,path,quiet=false){
  const p=state[key];
  try{
    let d;
    if(p.kind==='local'){
      const q=new URLSearchParams(); if(path) q.set('path',path); d=await apiGet(`/api/local/list?${q.toString()}`);
    }else{
      let targetPath=normalizeSpPath(path||p.library||p.site||'/');
      const sitePath=normalizeSpPath(p.site||'');
      if(sitePath){
        const underSite=targetPath===sitePath || targetPath.startsWith(sitePath+'/');
        if(!underSite){
          const libPath=normalizeSpPath(p.library||'');
          const libUnderSite=libPath && (libPath===sitePath || libPath.startsWith(sitePath+'/'));
          targetPath=libUnderSite ? libPath : sitePath;
        }
      }
      const q=new URLSearchParams({folder_server_relative_url:targetPath});
      if(p.site) q.set('site_relative_url',p.site);
      d=await apiGet(`/api/sp/list?${q.toString()}`);
    }
    p.path=d.path; p.items=d.items||[]; p.selected.clear(); p.translations.clear();
    updatePaneControls(key); await refreshTranslations(key); renderPane(key); rememberRecent(p);
    saveCurrentSessionSnapshot();
    if(state.splitViewEnabled) void refreshSplitView(true);
    if(!quiet) setStatus(`Loaded ${key} (${p.kind}): ${p.path}`);
  }catch(e){ setStatus(`Load failed: ${err(e)}`); }
}

function renderPane(key){
  const p=state[key], list=paneEls(key).list; list.innerHTML='';
  list.ondragover=(ev)=>{ ev.preventDefault(); list.classList.add('drag-target'); };
  list.ondragleave=()=>{ list.classList.remove('drag-target'); };
  list.ondrop=async(ev)=>{ ev.preventDefault(); list.classList.remove('drag-target'); await handleDropToTarget(key,p.path,ev); };
  const up=document.createElement('div');
  up.className='item up'; up.innerHTML='<span></span><span class="name">..</span><span class="meta">Up</span>'; up.onclick=()=>navigatePaneUp(key); list.appendChild(up);

  const query=(p.filterText||'').trim().toLowerCase();
  p.items.filter((it)=>!query||String(it.name||'').toLowerCase().includes(query)).forEach(it=>{
    const row=document.createElement('div'); row.className=`item${p.selected.has(it.path)?' active':''}`;
    row.draggable=true;
    const cb=document.createElement('input'); cb.type='checkbox'; cb.checked=p.selected.has(it.path);
    cb.onchange=()=>{
      state.activePane=key;
      cb.checked?p.selected.add(it.path):p.selected.delete(it.path);
      saveCurrentSessionSnapshot();
      renderPane(key);
    };
    const nm=document.createElement('span'); nm.className='name';
    const tr=p.translations.get(it.path); const trHtml=state.translationEnabled&&tr&&tr!==it.name?`<span class="translated">${tr}</span>`:'';
    nm.innerHTML=`${it.isDir?'📁':'📄'} ${it.name}${trHtml}`;
    const meta=document.createElement('span'); meta.className='meta'; meta.textContent=it.isDir?'Dir':fmtSize(it.size);
    row.appendChild(cb); row.appendChild(nm); row.appendChild(meta);
    row.onclick=(ev)=>{ state.activePane=key; saveCurrentSessionSnapshot(); if(!ev.ctrlKey&&!ev.metaKey) p.selected.clear(); p.selected.add(it.path); renderPane(key); renderPane(key==='left'?'right':'left'); loadTagsForSelection(); };
    row.ondblclick=()=>it.isDir?loadPane(key,it.path):openSelected(false);
    row.ondragstart=(ev)=>{ state.activePane=key; saveCurrentSessionSnapshot(); startDragFromItem(key,it.path,ev); };
    if(it.isDir){
      row.ondragover=(ev)=>{ ev.preventDefault(); row.classList.add('drop-folder'); };
      row.ondragleave=()=>{ row.classList.remove('drop-folder'); };
      row.ondrop=async(ev)=>{ ev.preventDefault(); row.classList.remove('drop-folder'); await handleDropToTarget(key,it.path,ev); };
    }
    list.appendChild(row);
  });
}

function createSplitPaneState(sessionId, side, source){
  return {
    key:`split:${sessionId}:${side}`,
    side,
    sessionId,
    kind:source?.kind||'local',
    path:source?.path||'',
    items:[],
    selected:new Set(),
    translations:new Map(),
    site:source?.site||'',
    siteTitle:source?.siteTitle||'',
    library:source?.library||'',
    sites:[],
    libraries:[],
    filterText:source?.filterText||'',
  };
}

function sessionRecordById(sessionId){
  return state.sessions.find((s)=>s.id===sessionId) || null;
}

function splitSessionIds(){
  if(!state.splitViewEnabled) return [];
  return state.sessions.map((s)=>s.id).filter(Boolean);
}

function splitSnapshotForSession(sessionId){
  if(sessionId===state.activeSessionId){
    const runtime=state.splitRuntime[sessionId];
    if(state.splitViewEnabled && runtime) return splitRuntimeSnapshot(runtime);
    return currentWorkspaceSnapshot();
  }
  return sessionRecordById(sessionId)?.snapshot || currentWorkspaceSnapshot();
}

function preferredSplitSide(snapshot){
  const preferred=String(snapshot?.activePane||'').toLowerCase();
  if(preferred==='left' || preferred==='right') return preferred;
  const left=snapshot?.left||{};
  const right=snapshot?.right||{};
  const leftReady=!!String(left.path||'').trim() || left.kind==='sharepoint';
  const rightReady=!!String(right.path||'').trim() || right.kind==='sharepoint';
  if(leftReady && !rightReady) return 'left';
  if(rightReady && !leftReady) return 'right';
  if(left.kind==='sharepoint' && right.kind!=='sharepoint') return 'left';
  if(right.kind==='sharepoint' && left.kind!=='sharepoint') return 'right';
  return 'left';
}

function splitPrimarySideForSession(sessionId){
  const runtime=state.splitRuntime[sessionId];
  if(runtime?.activePane==='left' || runtime?.activePane==='right') return runtime.activePane;
  return preferredSplitSide(splitSnapshotForSession(sessionId));
}

function hydrateSplitRuntime(sessionId){
  const record=sessionRecordById(sessionId);
  const snap=splitSnapshotForSession(sessionId);
  let runtime=state.splitRuntime[sessionId];
  if(!runtime){
    runtime={
      id:sessionId,
      name:sessionLabelById(sessionId),
      language:snap.language||state.language||'English',
      translationEnabled:!!snap.translationEnabled,
      activePane:preferredSplitSide(snap),
      left:createSplitPaneState(sessionId,'left',snap.left||{}),
      right:createSplitPaneState(sessionId,'right',snap.right||{}),
    };
    state.splitRuntime[sessionId]=runtime;
    return runtime;
  }
  runtime.name=sessionLabelById(sessionId);
  runtime.language=snap.language||state.language||'English';
  runtime.translationEnabled=!!snap.translationEnabled;
  runtime.activePane=preferredSplitSide(snap);
  for(const side of ['left','right']){
    const pane=runtime[side];
    const src=snap[side]||{};
    const pathChanged=pane.path!==String(src.path||'');
    const kindChanged=pane.kind!==String(src.kind||'local');
    const siteChanged=pane.site!==String(src.site||'');
    const libraryChanged=pane.library!==String(src.library||'');
    pane.kind=src.kind||'local';
    pane.site=src.site||'';
    pane.siteTitle=src.siteTitle||pane.siteTitle||'';
    pane.library=src.library||'';
    pane.path=src.path||'';
    pane.filterText=src.filterText||'';
    if(pathChanged||kindChanged||siteChanged||libraryChanged){
      pane.items=[];
      pane.selected.clear();
      pane.translations.clear();
    }
  }
  return runtime;
}

function saveSessionSnapshotById(sessionId, snapshot){
  const idx=state.sessions.findIndex((s)=>s.id===sessionId);
  if(idx<0) return;
  state.sessions[idx].snapshot=snapshot;
  persistSessions();
}

function splitRuntimeSnapshot(runtime){
  return {
    language:runtime.language||state.language||'English',
    translationEnabled:!!runtime.translationEnabled,
    activePane:(runtime.activePane==='right'?'right':'left'),
    left:{kind:runtime.left.kind,site:runtime.left.site||'',siteTitle:findSiteTitle(runtime.left.site,runtime.left.sites,runtime.left.siteTitle||''),library:runtime.left.library||'',path:runtime.left.path||'',filterText:runtime.left.filterText||''},
    right:{kind:runtime.right.kind,site:runtime.right.site||'',siteTitle:findSiteTitle(runtime.right.site,runtime.right.sites,runtime.right.siteTitle||''),library:runtime.right.library||'',path:runtime.right.path||'',filterText:runtime.right.filterText||''},
  };
}

function syncActiveSessionFromSplitRuntime(runtime){
  if(!runtime) return;
  const snapshot=splitRuntimeSnapshot(runtime);
  state.language=snapshot.language||state.language||'English';
  state.translationEnabled=!!snapshot.translationEnabled;
  state.activePane=(snapshot.activePane==='right'?'right':'left');
  for(const side of ['left','right']){
    const src=snapshot[side]||{};
    const target=state[side];
    target.kind=src.kind||'local';
    target.site=src.site||'';
    target.library=src.library||'';
    target.path=src.path||'';
    target.filterText=src.filterText||'';
    target.items=(runtime[side]?.items||[]).slice();
    target.selected=new Set(runtime[side]?.selected||[]);
    target.translations=new Map(runtime[side]?.translations||[]);
  }
  const idx=state.sessions.findIndex((s)=>s.id===state.activeSessionId);
  if(idx>=0){
    state.sessions[idx].snapshot=snapshot;
    persistSessions();
  }
}

function persistSplitRuntimeSession(sessionId){
  const runtime=state.splitRuntime[sessionId];
  if(!runtime) return;
  if(sessionId===state.activeSessionId){
    syncActiveSessionFromSplitRuntime(runtime);
    return;
  }
  saveSessionSnapshotById(sessionId, splitRuntimeSnapshot(runtime));
}

function splitPaneDomId(sessionId, side, part){
  const token=String(sessionId||'session').replace(/[^a-zA-Z0-9_-]/g,'_');
  return `split-${token}-${side}-${part}`;
}

function splitPaneElements(sessionId, side){
  return {
    list:id(splitPaneDomId(sessionId,side,'list')),
    filter:id(splitPaneDomId(sessionId,side,'filter')),
    path:id(splitPaneDomId(sessionId,side,'path')),
    pathInput:id(splitPaneDomId(sessionId,side,'path-input')),
    up:id(splitPaneDomId(sessionId,side,'up')),
  };
}

async function refreshSplitTranslations(sessionId, side){
  const runtime=hydrateSplitRuntime(sessionId);
  const pane=runtime[side];
  pane.translations.clear();
  if(!runtime.translationEnabled || !pane.items.length) return;
  try{
    const d=await apiPost('/api/translate',{language:runtime.language,items:pane.items.map((it)=>({name:it.name,path:it.path,mtime:it.mtime||0}))});
    (d.translations||[]).forEach((t,i)=>{
      const name=pane.items[i]?.name||'';
      const translated=applyGlossary(t||name);
      pane.translations.set(pane.items[i].path,translated);
      rememberTranslation(runtime.language,name,translated);
    });
    persistTranslationLocalCache();
  }catch(e){
    pane.items.forEach((it)=>{
      const cached=getCachedTranslation(runtime.language,it.name);
      if(cached) pane.translations.set(it.path,applyGlossary(cached));
    });
  }
}

async function loadSplitPane(sessionId, side, path, quiet=false){
  const runtime=hydrateSplitRuntime(sessionId);
  const pane=runtime[side];
  try{
    let d;
    if(pane.kind==='local'){
      const q=new URLSearchParams();
      if(path) q.set('path',path);
      d=await apiGet(`/api/local/list?${q.toString()}`);
    }else{
      let targetPath=normalizeSpPath(path||pane.library||pane.site||'/');
      const sitePath=normalizeSpPath(pane.site||'');
      if(sitePath){
        const underSite=targetPath===sitePath || targetPath.startsWith(sitePath+'/');
        if(!underSite){
          const libPath=normalizeSpPath(pane.library||'');
          const libUnderSite=libPath && (libPath===sitePath || libPath.startsWith(sitePath+'/'));
          targetPath=libUnderSite ? libPath : sitePath;
        }
      }
      const q=new URLSearchParams({folder_server_relative_url:targetPath});
      if(pane.site) q.set('site_relative_url',pane.site);
      d=await apiGet(`/api/sp/list?${q.toString()}`);
    }
    pane.path=d.path;
    pane.items=d.items||[];
    pane.selected.clear();
    pane.translations.clear();
    await refreshSplitTranslations(sessionId, side);
    persistSplitRuntimeSession(sessionId);
    renderSplitPane(sessionId, side);
    if(!quiet) setStatus(`Loaded ${runtime.name} ${side} (${pane.kind}): ${pane.path}`);
  }catch(e){
    setStatus(`Split load failed: ${err(e)}`);
  }
}

function selectedItemsFromPane(pane){
  return (pane.items||[]).filter((it)=>pane.selected.has(it.path));
}

function renderSplitPane(sessionId, side){
  const runtime=hydrateSplitRuntime(sessionId);
  const pane=runtime[side];
  const ui=splitPaneElements(sessionId, side);
  if(!ui.list) return;
  if(ui.path) ui.path.textContent=pane.path||'(empty)';
  if(ui.pathInput && document.activeElement!==ui.pathInput) ui.pathInput.value=pane.path||'';
  if(ui.filter && document.activeElement!==ui.filter) ui.filter.value=pane.filterText||'';
  ui.list.innerHTML='';
  ui.list.ondragover=(ev)=>{ ev.preventDefault(); ui.list.classList.add('drag-target'); };
  ui.list.ondragleave=()=>{ ui.list.classList.remove('drag-target'); };
  ui.list.ondrop=async(ev)=>{ ev.preventDefault(); ui.list.classList.remove('drag-target'); await handleSplitDrop(sessionId, side, pane.path, ev); };
  const up=document.createElement('div');
  up.className='item up';
  up.innerHTML='<span></span><span class="name">..</span><span class="meta">Up</span>';
  up.onclick=()=>navigateSplitPaneUp(sessionId, side);
  ui.list.appendChild(up);
  const query=(pane.filterText||'').trim().toLowerCase();
  pane.items.filter((it)=>!query||String(it.name||'').toLowerCase().includes(query)).forEach((it)=>{
    const row=document.createElement('div');
    row.className=`item${pane.selected.has(it.path)?' active':''}`;
    row.draggable=true;
    const cb=document.createElement('input');
    cb.type='checkbox';
    cb.checked=pane.selected.has(it.path);
    cb.onchange=()=>{
      focusSplitPane(sessionId, side);
      cb.checked?pane.selected.add(it.path):pane.selected.delete(it.path);
      persistSplitRuntimeSession(sessionId);
      renderSplitPane(sessionId, side);
    };
    const nm=document.createElement('span');
    nm.className='name';
    const tr=pane.translations.get(it.path);
    const trHtml=runtime.translationEnabled&&tr&&tr!==it.name?`<span class="translated">${tr}</span>`:'';
    nm.innerHTML=`${it.isDir?'📁':'📄'} ${it.name}${trHtml}`;
    const meta=document.createElement('span');
    meta.className='meta';
    meta.textContent=it.isDir?'Dir':fmtSize(it.size);
    row.appendChild(cb); row.appendChild(nm); row.appendChild(meta);
    row.onclick=(ev)=>{
      ev.stopPropagation();
      const timerKey=`${sessionId}:${side}`;
      if(state.splitClickTimers[timerKey]) clearTimeout(state.splitClickTimers[timerKey]);
      state.splitClickTimers[timerKey]=setTimeout(()=>{
        focusSplitPane(sessionId, side);
        if(!ev.ctrlKey&&!ev.metaKey) pane.selected.clear();
        pane.selected.add(it.path);
        persistSplitRuntimeSession(sessionId);
        renderSplitPane(sessionId, side);
        state.splitClickTimers[timerKey]=null;
      }, 220);
    };
    row.ondblclick=()=>{
      const timerKey=`${sessionId}:${side}`;
      if(state.splitClickTimers[timerKey]){
        clearTimeout(state.splitClickTimers[timerKey]);
        state.splitClickTimers[timerKey]=null;
      }
      focusSplitPane(sessionId, side);
      return it.isDir?loadSplitPane(sessionId, side, it.path):window.open(downloadUrl(pane,it.path),'_blank');
    };
    row.ondragstart=(ev)=>startSplitDrag(sessionId, side, it.path, ev);
    if(it.isDir){
      row.ondragover=(ev)=>{ ev.preventDefault(); row.classList.add('drop-folder'); };
      row.ondragleave=()=>{ row.classList.remove('drop-folder'); };
      row.ondrop=async(ev)=>{ ev.preventDefault(); row.classList.remove('drop-folder'); await handleSplitDrop(sessionId, side, it.path, ev); };
    }
    ui.list.appendChild(row);
  });
}

function startSplitDrag(sessionId, side, itemPath, ev){
  const runtime=hydrateSplitRuntime(sessionId);
  const pane=runtime[side];
  const selected=selectedItemsFromPane(pane);
  const anchorSelected=selected.some((it)=>it.path===itemPath);
  const use=anchorSelected&&selected.length?selected:(pane.items.filter((it)=>it.path===itemPath));
  const sources=use.map((it)=>({kind:pane.kind,path:it.path,isDir:!!it.isDir,site:pane.site||''}));
  state.dragPayload={from:`split:${sessionId}:${side}`,sources};
  try{
    ev.dataTransfer.effectAllowed='copyMove';
    ev.dataTransfer.setData('application/x-smx-drag',JSON.stringify(state.dragPayload));
  }catch{}
}

async function refreshSplitView(quiet=true){
  if(!state.splitViewEnabled || !el.splitSessionsHost) return;
  const ids=splitSessionIds();
  if(!ids.length) return;
  renderSplitSessions();
  for(const sessionId of ids){
    const runtime=hydrateSplitRuntime(sessionId);
    const side=splitPrimarySideForSession(sessionId);
    const pane=runtime[side];
    if(!pane.path && pane.kind==='sharepoint') pane.path=pane.library||'/';
    await loadSplitPane(sessionId, side, pane.path||(pane.kind==='local'?'':pane.library||'/'), quiet);
  }
}

async function handleSplitDrop(sessionId, side, targetPath, ev){
  const runtime=hydrateSplitRuntime(sessionId);
  const pane=runtime[side];
  if(!pane || !targetPath) return;
  let payload=state.dragPayload;
  try{
    const raw=ev.dataTransfer?.getData('application/x-smx-drag');
    if(raw) payload=JSON.parse(raw);
  }catch{}
  if(!payload||!Array.isArray(payload.sources)||!payload.sources.length) return;
  const move=state.splitTransferMode==='move';
  try{
    await executeTransfer(payload.sources,{kind:pane.kind,path:targetPath,site:pane.site||''},move,true);
    await loadPane('left',state.left.path,true);
    await loadPane('right',state.right.path,true);
    await refreshSplitView(true);
    setStatus(`${move?'Move':'Copy'} via split drag-and-drop complete.`);
  }catch(e){
    setStatus(`Split drag-and-drop failed: ${err(e)}`);
    pushNotification(`Split drag-and-drop failed: ${err(e)}`,'error',true);
  }finally{
    state.dragPayload=null;
  }
}

function toggleSplitTransferMode(){
  state.splitTransferMode=state.splitTransferMode==='move' ? 'copy' : 'move';
  renderSplitSessionOptions();
  setStatus(`Split drag-and-drop mode: ${state.splitTransferMode}.`);
}

function renderSplitSessionOptions(){
  if(el.splitViewToggleBtn) el.splitViewToggleBtn.textContent=`Split View: ${state.splitViewEnabled?'On':'Off'}`;
  if(el.splitTransferModeBtn){
    el.splitTransferModeBtn.textContent=`Split Drop: ${state.splitTransferMode==='move'?'Move':'Copy'}`;
    el.splitTransferModeBtn.classList.toggle('hidden', !state.splitViewEnabled);
  }
  if(el.splitCompareSessionSelect){
    el.splitCompareSessionSelect.classList.add('hidden');
    el.splitCompareSessionSelect.disabled=true;
  }
}

function renderSplitSessions(){
  renderSplitSessionOptions();
  if(!el.splitSessionsHost) return;
  const ids=splitSessionIds();
  const shouldShow=state.appView==='workspace' && state.splitViewEnabled && ids.length>0;
  if(el.mainWorkspaceView) el.mainWorkspaceView.classList.toggle('hidden', shouldShow || state.appView==='relinking');
  el.splitSessionsHost.classList.toggle('hidden', !shouldShow);
  if(!shouldShow){
    el.splitSessionsHost.innerHTML='';
    renderAppView();
    return;
  }
  el.splitSessionsHost.className='split-sessions-host min-h-0 flex-1 overflow-auto border-b border-slate-200 px-4 py-3 dark:border-slate-800';
  const splitTiles=[];
  for(const sessionId of ids){
    const runtime=hydrateSplitRuntime(sessionId);
    const side=splitPrimarySideForSession(sessionId);
    const pane=runtime[side];
    splitTiles.push(`
      <section class="split-pane-card${sessionId===state.activeSessionId?' active':''}" data-split-session="${sessionId}" data-split-side="${side}">
        <div class="split-pane-head">
          <div>
            <strong>${escapeHtml(runtime.name||'Session')} · ${escapeHtml(pane.kind)}</strong>
            <small id="${splitPaneDomId(sessionId,side,'path')}">${escapeHtml(pane.path||'(empty)')}</small>
          </div>
          <div class="split-pane-actions">
            <button id="${splitPaneDomId(sessionId,'session','focus')}" type="button">Focus</button>
            <button id="${splitPaneDomId(sessionId,side,'up')}" type="button">Up</button>
            <button id="${splitPaneDomId(sessionId,'session','close')}" type="button">Close</button>
          </div>
        </div>
        <div class="split-pane-pathbar">
          <input id="${splitPaneDomId(sessionId,side,'path-input')}" type="text" spellcheck="false" placeholder="${pane.kind==='sharepoint'?'SharePoint path...':'Local path...'}" value="${escapeHtml(pane.path||'')}" />
        </div>
        <div class="split-pane-filter">
          <input id="${splitPaneDomId(sessionId,side,'filter')}" type="text" spellcheck="false" placeholder="Filter..." value="${escapeHtml(pane.filterText||'')}" />
        </div>
        <div id="${splitPaneDomId(sessionId,side,'list')}" class="list se-list se-scroll split-pane-list"></div>
      </section>
    `);
  }
  el.splitSessionsHost.innerHTML=splitTiles.join('');
  ids.forEach((sessionId)=>{
    const runtime=hydrateSplitRuntime(sessionId);
    const side=splitPrimarySideForSession(sessionId);
    const pane=runtime[side];
    const focusBtn=id(splitPaneDomId(sessionId,'session','focus'));
    if(focusBtn) focusBtn.onclick=()=>focusSplitSession(sessionId);
    const closeBtn=id(splitPaneDomId(sessionId,'session','close'));
    if(closeBtn) closeBtn.onclick=(ev)=>{ ev.stopPropagation(); closeSessionById(sessionId); };
    const card=el.splitSessionsHost?.querySelector(`[data-split-session="${sessionId}"][data-split-side="${side}"]`);
    if(card) card.onclick=()=>focusSplitPane(sessionId, side);
    const ui=splitPaneElements(sessionId, side);
    if(ui.filter) ui.filter.oninput=()=>{ focusSplitPane(sessionId, side); pane.filterText=ui.filter.value||''; persistSplitRuntimeSession(sessionId); renderSplitPane(sessionId, side); };
    if(ui.pathInput) ui.pathInput.onkeydown=async(ev)=>{ if(ev.key==='Enter'){ focusSplitPane(sessionId, side); await loadSplitPane(sessionId, side, (ui.pathInput.value||'').trim()); } };
    if(ui.pathInput) ui.pathInput.onchange=async()=>{ focusSplitPane(sessionId, side); await loadSplitPane(sessionId, side, (ui.pathInput.value||'').trim(), true); };
    if(ui.up) ui.up.onclick=()=>navigateSplitPaneUp(sessionId, side);
    renderSplitPane(sessionId, side);
  });
  renderAppView();
}

function setClipboard(op){
  const p=activePane();
  state.clipboard={op,sources:selectedItems(p).map(it=>({kind:p.kind,path:it.path,isDir:!!it.isDir,site:p.site||''}))};
  setStatus(`${op==='cut'?'Cut':'Copied'} ${state.clipboard.sources.length} item(s).`);
}

function startDragFromItem(key,itemPath,ev){
  const p=state[key];
  const selected=selectedItems(p);
  const anchorSelected=selected.some((it)=>it.path===itemPath);
  const use=anchorSelected&&selected.length?selected:(p.items.filter((it)=>it.path===itemPath));
  const sources=use.map((it)=>({kind:p.kind,path:it.path,isDir:!!it.isDir,site:p.site||''}));
  state.dragPayload={from:key,sources};
  try{
    ev.dataTransfer.effectAllowed='copyMove';
    ev.dataTransfer.setData('application/x-smx-drag',JSON.stringify(state.dragPayload));
  }catch{}
}
async function executeTransfer(sources,target,move,withPreview=true){
  let effectiveSources=(sources||[]).slice();
  let overwritePaths=new Set();
  if(withPreview && effectiveSources.length){
    const op=move?'move':'copy';
    const dry=await apiPost('/api/bulk/dry-run',{
      operation:op,
      conflict_policy:'skip',
      destination_kind:target.kind,
      destination_path:target.path||'',
      destination_site_relative_url:target.site||null,
      sources:effectiveSources.map((s)=>({kind:s.kind,path:s.path,isDir:!!s.isDir,name:basename(s.path),site_relative_url:s.site||null})),
    });
    const rows=dry.rows||[];
    const sourceMap=new Map(effectiveSources.map((s)=>[String(s.path||''),s]));
    const decision=await showTransferPreviewModal(rows,sourceMap,op);
    if(!decision.approved) throw new Error('transfer_canceled');
    overwritePaths=decision.overwritePaths||new Set();
    effectiveSources=effectiveSources.filter((s)=>decision.selectedPaths.has(String(s.path||'')));
    if(!effectiveSources.length) throw new Error('transfer_no_items_selected');
  }
  if(target.kind==='local'){
    const localSources=effectiveSources.filter((s)=>s.kind==='local');
    const sharepointSources=effectiveSources.filter((s)=>s.kind==='sharepoint');
    for(const s of localSources){
      const name=basename(s.path);
      const shouldOverwrite=overwritePaths.has(String(s.path||''));
      const sep=(target.path.includes('\\')?'\\':'/');
      const destFull=target.path.replace(/[\\\/]+$/,'') + (target.path.endsWith('\\')||target.path.endsWith('/')?'':sep) + name;
      if(shouldOverwrite){
        try{ await apiPost('/api/local/delete',{sources:[destFull]}); }catch{}
      }
      await apiPost(move?'/api/local/move':'/api/local/copy',{sources:[s.path],destination:target.path});
    }
    const spBySite=new Map();
    for(const s of sharepointSources){
      const siteKey=String(s.site||'');
      if(!spBySite.has(siteKey)) spBySite.set(siteKey,[]);
      spBySite.get(siteKey).push(s);
      if(overwritePaths.has(String(s.path||''))){
        const name=basename(s.path);
        const sep=(target.path.includes('\\')?'\\':'/');
        const destFull=target.path.replace(/[\\\/]+$/,'') + (target.path.endsWith('\\')||target.path.endsWith('/')?'':sep) + name;
        try{ await apiPost('/api/local/delete',{sources:[destFull]}); }catch{}
      }
    }
    for(const [siteKey, rows] of spBySite.entries()){
      await apiPost('/api/transfer/sp-to-local',{
        site_relative_url:siteKey||null,
        server_relative_urls:rows.map((s)=>s.path),
        source_items:rows.map((s)=>({
          kind:'sharepoint',
          path:s.path,
          isDir:!!s.isDir,
          name:basename(s.path),
          site_relative_url:siteKey||null,
        })),
        destination_dir:target.path,
        move,
      });
    }
    return;
  }
  for(const s of effectiveSources){
    const name=basename(s.path);
    const shouldOverwrite=overwritePaths.has(String(s.path||''));
    if(s.kind==='sharepoint'){
      const dst=`${target.path.replace(/\/+$/,'')}/${name}`;
      await apiPost(move?'/api/sp/move':'/api/sp/copy',{source_server_relative_url:s.path,target_server_relative_url:dst,is_folder:s.isDir,overwrite:shouldOverwrite,site_relative_url:s.site||target.site||null});
      if(move) recordMigration('move',s.isDir?'folder':'file',s.path,dst,s.site||'',target.site||s.site||'');
    }else{
      if(s.isDir) throw new Error('local_folder_to_sp_not_supported');
      await apiPost('/api/transfer/local-to-sp',{site_relative_url:target.site||null,source_paths:[s.path],destination_server_relative_url:target.path,move,overwrite:shouldOverwrite});
    }
  }
}
async function handleDropToTarget(targetKey,targetPath,ev){
  const pane=state[targetKey];
  if(!pane||!targetPath) return;
  let payload=state.dragPayload;
  try{
    const raw=ev.dataTransfer?.getData('application/x-smx-drag');
    if(raw) payload=JSON.parse(raw);
  }catch{}
  if(!payload||!Array.isArray(payload.sources)||!payload.sources.length) return;
  const move=!!ev.shiftKey;
  try{
    await executeTransfer(payload.sources,{kind:pane.kind,path:targetPath,site:pane.site||''},move,true);
    await loadPane('left',state.left.path,true); await loadPane('right',state.right.path,true);
    await refreshSplitView(true);
    setStatus(`${move?'Move':'Copy'} via drag-and-drop complete.`);
  }catch(e){ setStatus(`Drag-and-drop failed: ${err(e)}`); pushNotification(`Drag-and-drop failed: ${err(e)}`,'error',true); }
  finally{ state.dragPayload=null; }
}

async function pasteClipboard(){
  const c=state.clipboard; if(!c.op||!c.sources.length) return;
  const target=activePane(), move=c.op==='cut';
  if(!target.path) return setStatus('Target path is not set.');
  try{
    await executeTransfer(c.sources,target,move,true);
    if(move) state.clipboard={op:null,sources:[]};
    await loadPane('left',state.left.path,true); await loadPane('right',state.right.path,true);
    await refreshSplitView(true);
    setStatus('Paste complete.');
  }catch(e){ setStatus(`Paste failed: ${err(e)}`); pushNotification(`Paste failed: ${err(e)}`,'error',true); }
}

async function fileToBase64(file){
  const buf=await file.arrayBuffer(); let bin=''; const bytes=new Uint8Array(buf), chunk=0x8000;
  for(let i=0;i<bytes.length;i+=chunk) bin+=String.fromCharCode(...bytes.subarray(i,i+chunk));
  return btoa(bin);
}

async function uploadToPane(key,file){
  const p=state[key];
  try{
    const content=await fileToBase64(file);
    if(p.kind==='local') await apiPost('/api/local/write',{destination_dir:p.path,filename:file.name,content_base64:content,overwrite:false});
    else await apiPost('/api/sp/upload',{site_relative_url:p.site||null,parent_server_relative_url:p.path,name:file.name,content_base64:content,overwrite:false});
    await loadPane(key,p.path); setStatus(`Uploaded: ${file.name}`);
  }catch(e){ setStatus(`Upload failed: ${err(e)}`); }
}
async function collectAiRenameItems(p,items,recursive,includeRoot=false){
  if(!recursive) return items.slice();
  const out=[], seen=new Set();
  for(const it of items){
    if(includeRoot && it?.path && !seen.has(it.path)){
      out.push(it);
      seen.add(it.path);
    }
    if(!it?.isDir){
      if(it?.path&&!seen.has(it.path)){ out.push(it); seen.add(it.path); }
      continue;
    }
    if(p.kind==='local') await collectLocalDescendants(it.path,out,seen);
    else await collectSpDescendants(p.site||'',it.path,out,seen);
  }
  return out;
}
async function collectLocalDescendants(path,out,seen){
  const d=await apiGet(`/api/local/list?${new URLSearchParams({path}).toString()}`);
  for(const it of (d.items||[])){
    if(!it?.path||seen.has(it.path)) continue;
    out.push(it); seen.add(it.path);
    if(it.isDir) await collectLocalDescendants(it.path,out,seen);
  }
}
async function collectSpDescendants(site,path,out,seen){
  const d=await apiGet(`/api/sp/list?${new URLSearchParams({site_relative_url:site||'',folder_server_relative_url:path}).toString()}`);
  for(const it of (d.items||[])){
    if(!it?.path||seen.has(it.path)) continue;
    out.push(it); seen.add(it.path);
    if(it.isDir) await collectSpDescendants(site,it.path,out,seen);
  }
}
function commonParentForAi(paths,sharepoint){
  if(!paths.length) return sharepoint?'/':'';
  if(sharepoint){
    let common=(parentPath(paths[0]).replace(/\\/g,'/')||'/').replace(/\/+$/,'')||'/';
    for(const p of paths.slice(1)){
      const parent=(parentPath(p).replace(/\\/g,'/')||'/').replace(/\/+$/,'')||'/';
      while(common!=='/' && !(parent===common || parent.startsWith(common+'/'))){
        common=common.split('/').slice(0,-1).join('/')||'/';
      }
    }
    return common||'/';
  }
  const parts=paths.map((p)=>parentPath(p).split(/[\\/]+/));
  const common=[];
  for(let i=0;;i++){
    const token=parts[0][i];
    if(token===undefined) break;
    if(parts.every((row)=>row[i]===token)) common.push(token); else break;
  }
  return common.join('\\') || parentPath(paths[0]);
}
function relativeUnderRoot(rootPath,targetPath,sharepoint){
  if(sharepoint){
    const root=String(rootPath||'').replace(/\/+$/,'');
    const target=String(targetPath||'').replace(/\/+$/,'');
    return target.startsWith(root)?target.slice(root.length).replace(/^\/+/,''):target.replace(/^\/+/,'');
  }
  return targetPath.replace(rootPath,'').replace(/^[\\/]+/,'').replace(/\\/g,'/');
}
function joinRootRelative(rootPath,relativePath,sharepoint){
  const rel=String(relativePath||'').trim().replace(/\\/g,'/').replace(/^\/+|\/+$/g,'');
  if(sharepoint){
    const base=String(rootPath||'').replace(/\/+$/,'')||'/';
    return rel?`${base}/${rel}`:base;
  }
  const base=String(rootPath||'');
  return rel?`${base.replace(/[\\/]+$/,'')}\\${rel.replace(/\//g,'\\')}`:base;
}
function isTargetWithinRoot(rootPath,targetPath,sharepoint){
  if(sharepoint){
    const root=(String(rootPath||'').replace(/\/+$/,'')||'/');
    const target=(String(targetPath||'').replace(/\/+$/,'')||'/');
    return target===root || target.startsWith(root+'/');
  }
  const root=String(rootPath||'').toLowerCase().replace(/[\\/]+$/,'');
  const target=String(targetPath||'').toLowerCase();
  return target===root || target.startsWith(root+'\\') || target.startsWith(root+'/');
}
async function listChildNamesForAi(kind,site,parentPath,cache){
  const key=`${kind}|${site||''}|${parentPath||''}`;
  if(cache.has(key)) return cache.get(key);
  let items=[];
  try{
    if(kind==='local'){
      const d=await apiGet(`/api/local/list?${new URLSearchParams({path:parentPath}).toString()}`);
      items=d.items||[];
    }else{
      const d=await apiGet(`/api/sp/list?${new URLSearchParams({site_relative_url:site||'',folder_server_relative_url:parentPath}).toString()}`);
      items=d.items||[];
    }
  }catch{}
  const names=new Set(items.map((it)=>String(it?.name||'').trim()).filter(Boolean));
  cache.set(key,names);
  return names;
}
async function ensureLocalFolderTree(rootPath,targetFolder){
  const root=String(rootPath||'').replace(/[\\/]+$/,'');
  const target=String(targetFolder||'');
  if(!target || target===root) return;
  const rel=target.replace(root,'').replace(/^[\\/]+/,'').split(/[\\/]+/).filter(Boolean);
  let current=root;
  for(const seg of rel){
    try{ await apiPost('/api/local/mkdir',{path:current,name:seg}); }catch{}
    current=`${current}\\${seg}`;
  }
}
async function ensureSpFolderTree(site,rootPath,targetFolder){
  const root=String(rootPath||'').replace(/\/+$/,'')||'/';
  const target=String(targetFolder||'').replace(/\/+$/,'')||'/';
  if(!target || target===root) return;
  const rel=target.startsWith(root)?target.slice(root.length).replace(/^\/+/,''):target.replace(/^\/+/,'');
  let current=root;
  for(const seg of rel.split('/').filter(Boolean)){
    try{ await apiPost('/api/sp/folder',{site_relative_url:site||null,parent_server_relative_url:current,name:seg}); }catch{}
    current=current==='/'?`/${seg}`:`${current}/${seg}`;
  }
}
async function validateAiRenameCandidates(planRows,ctx){
  const targetMap=new Map(), parentCache=new Map();
  for(const row of planRows){
    if(row.action==='Keep'){ row.status='No change'; row.conflict=false; continue; }
    const targetPath=joinRootRelative(ctx.rootPath,row.targetRelativePath,ctx.kind==='sharepoint');
    row.targetPath=targetPath;
    if(targetPath===row.sourcePath){ row.status='No change'; row.conflict=false; continue; }
    if(!isTargetWithinRoot(ctx.rootPath,targetPath,ctx.kind==='sharepoint')){ row.status='Blocked: target escapes selected root'; row.conflict=true; continue; }
    if(targetMap.has(targetPath) && targetMap.get(targetPath)!==row.sourcePath){ row.status='Blocked: duplicate target in plan'; row.conflict=true; continue; }
    targetMap.set(targetPath,row.sourcePath);
    const parent=parentPath(targetPath);
    const name=basename(targetPath);
    const names=await listChildNamesForAi(ctx.kind,ctx.site,parent,parentCache);
    if(names.has(name) && targetPath!==row.sourcePath){ row.status='Blocked: target already exists'; row.conflict=true; continue; }
    row.status='Ready'; row.conflict=false;
  }
  return planRows;
}
function recordAiRenameBatch(entry){
  state.aiRenameLog.push(entry);
  state.aiRenameLog=state.aiRenameLog.slice(-200);
  saveAiRenameLog();
  renderAiRenameLogPanel();
}
async function aiRenameAndOrganize(){
  const p=activePane();
  let items=selectedItems(p);
  const scopeMode=chooseAiRenameScope(items.length>0,p.path);
  if(!scopeMode) return;
  const recursive=scopeMode!=='selected';
  const includeRoot=scopeMode==='folder_with_root';
  if(scopeMode!=='selected'){
    if(!p.path) return setStatus('Open the folder you want to scan first.');
    items=[{path:p.path,isDir:true,name:basename(p.path)}];
  }
  const instruction=(prompt('Describe the naming and sorting goal:','Rename items consistently and organize related content into clear folders. If they look like episodes, group them by series and Season 01, Season 02, etc.')||'').trim();
  if(!instruction) return;
  try{
    items=await collectAiRenameItems(p,items,recursive,includeRoot);
    if(!items.length) return setStatus('No items available after recursive expansion.');
    const rootPath=scopeMode==='selected' ? commonParentForAi(items.map((it)=>it.path),p.kind==='sharepoint') : p.path;
    const requestItems=items.map((it)=>({source_path:it.path,current_relative_path:relativeUnderRoot(rootPath,it.path,p.kind==='sharepoint'),is_folder:!!it.isDir}));
    const plan=await apiPost('/api/ai/rename-plan',{kind:p.kind,site_relative_url:p.kind==='sharepoint'?p.site||null:null,root_name:basename(rootPath)||rootPath,instruction,items:requestItems});
    let rows=(plan.operations||[]).map((op)=>{
      const current=requestItems.find((it)=>it.source_path===op.source_path);
      const currentRelativePath=current?.current_relative_path||'';
      const targetRelativePath=String(op?.target_relative_path||currentRelativePath||'').replace(/\\/g,'/').replace(/^\/+|\/+$/g,'')||currentRelativePath;
      const currentName=basename(currentRelativePath), targetName=basename(targetRelativePath);
      const currentDir=parentPath(currentRelativePath).replace(/\\/g,'/'), targetDir=parentPath(targetRelativePath).replace(/\\/g,'/');
      const action=targetRelativePath===currentRelativePath?'Keep':(currentDir===targetDir?'Rename':(currentName===targetName?'Move':'Move + Rename'));
      return {sourcePath:op.source_path,currentRelativePath,targetRelativePath,reason:String(op?.reason||'').trim()||'AI suggestion',action,isDir:!!current?.is_folder,status:'',conflict:false};
    });
    const ctx={kind:p.kind,site:p.site||'',rootPath,instruction,recursive,includeRoot,scopeMode,summary:String(plan.summary||''),warnings:Array.isArray(plan.warnings)?plan.warnings:[]};
    rows=await validateAiRenameCandidates(rows,ctx);
    const safeRows=rows.filter((r)=>!r.conflict && r.action!=='Keep');
    if(!safeRows.length) return setStatus('AI plan produced no safe operations.');
    const approved=await showAiRenamePreviewModal(rows,ctx.summary,ctx.warnings);
    if(!approved) return;
    await applyAiRenamePlan(p,ctx,safeRows);
  }catch(e){ setStatus(`AI rename failed: ${err(e)}`); }
}
function chooseAiRenameScope(hasSelection,currentPath){
  const options=[];
  if(hasSelection) options.push({value:'selected',label:'1. Scan selected items'});
  if(currentPath){
    options.push({value:'folder',label:'2. Scan current folder'});
    options.push({value:'folder_with_root',label:'3. Scan current folder and rename root folder too'});
  }
  if(!options.length){ setStatus('Select files/folders or open the folder you want to scan first.'); return null; }
  const message=`Choose AI rename scope:\n${options.map((o)=>o.label).join('\n')}\n\nEnter 1, 2, or 3.`;
  const raw=(prompt(message, options[0].label.charAt(0))||'').trim();
  const chosen=options.find((o)=>o.label.startsWith(`${raw}.`));
  return chosen ? chosen.value : null;
}
async function applyAiRenamePlan(p,ctx,rows){
  const logOps=[], undoBatch=[];
  const folderTargets=[...new Set(rows.map((r)=>parentPath(r.targetPath)))].sort((a,b)=>String(a).length-String(b).length);
  try{
    if(ctx.kind==='local'){
      for(const folder of folderTargets){ if(folder) await ensureLocalFolderTree(ctx.rootPath,folder); }
    }else{
      for(const folder of folderTargets){ if(folder) await ensureSpFolderTree(ctx.site,ctx.rootPath,folder.replace(/\\/g,'/')); }
    }
    for(const row of rows){
      try{
        if(ctx.kind==='local'){
          const sourceParent=parentPath(row.sourcePath), targetParent=parentPath(row.targetPath), targetName=basename(row.targetPath);
          if(sourceParent===targetParent){
            await apiPost('/api/local/rename',{path:row.sourcePath,new_name:targetName});
          }else{
            await apiPost('/api/local/move',{sources:[row.sourcePath],destination:targetParent});
            const movedPath=`${targetParent}\\${basename(row.sourcePath)}`;
            if(basename(movedPath)!==targetName){
              await apiPost('/api/local/rename',{path:movedPath,new_name:targetName});
            }
          }
        }else{
          const sourceParent=(row.sourcePath||'').replace(/\/+$/,'').split('/').slice(0,-1).join('/')||'/';
          const targetParent=(row.targetPath||'').replace(/\/+$/,'').split('/').slice(0,-1).join('/')||'/';
          const targetName=basename(row.targetPath);
          if(sourceParent===targetParent && basename(row.sourcePath)!==targetName){
            await apiPost('/api/sp/rename',{server_relative_url:row.sourcePath,new_name:targetName,is_folder:!!row.isDir,site_relative_url:ctx.site||null});
          }else{
            await apiPost('/api/sp/move',{source_server_relative_url:row.sourcePath,target_server_relative_url:row.targetPath,is_folder:!!row.isDir,overwrite:false,site_relative_url:ctx.site||null});
          }
          recordMigration(row.action==='Rename'?'rename':'move',row.isDir?'folder':'file',row.sourcePath,row.targetPath,ctx.site||'',ctx.site||'');
        }
        row.status='applied';
        undoBatch.push({kind:ctx.kind,site:ctx.site||'',oldPath:row.sourcePath,newPath:row.targetPath,isDir:!!row.isDir});
        logOps.push({source_path:row.sourcePath,target_path:row.targetPath,action:row.action,reason:row.reason,is_dir:!!row.isDir,status:'applied'});
      }catch(e){
        row.status='failed';
        logOps.push({source_path:row.sourcePath,target_path:row.targetPath,action:row.action,reason:row.reason,is_dir:!!row.isDir,status:'failed',error:err(e)});
      }
    }
  }finally{
    if(undoBatch.length) state.aiRenameUndoStack.push(undoBatch);
    recordAiRenameBatch({id:`ai-batch-${Date.now()}`,timestamp:new Date().toISOString(),kind:ctx.kind,site_relative_url:ctx.site||'',root_path:ctx.rootPath,instruction:ctx.instruction,recursive:!!ctx.recursive,summary:ctx.summary||'AI rename batch',warnings:ctx.warnings||[],operations:logOps});
    await loadPane('left',state.left.path); await loadPane('right',state.right.path);
  }
  const applied=logOps.filter((op)=>op.status==='applied').length, failed=logOps.filter((op)=>op.status==='failed').length;
  setStatus(`AI rename applied ${applied} operation(s).${failed?` ${failed} failed.`:''}`);
}
async function renameSelected(){
  let p=activePane(), path=selectedSinglePath(), splitSessionId='', splitSide='';
  if(!path){
    const paneCandidates=['left','right']
      .map((key)=>({pane:state[key],selected:Array.from(state[key]?.selected||[])}))
      .filter((x)=>x.selected.length===1);
    if(paneCandidates.length===1){
      p=paneCandidates[0].pane;
      path=paneCandidates[0].selected[0];
    }
  }
  if(state.splitViewEnabled){
    const sessionId=state.activeSessionId||splitSessionIds()[0]||'';
    if(sessionId){
      const runtime=hydrateSplitRuntime(sessionId);
      const splitCandidates=['left','right']
        .map((side)=>({side,pane:runtime?.[side],selected:Array.from(runtime?.[side]?.selected||[])}))
        .filter((x)=>x.selected.length===1);
      if(splitCandidates.length===1){
        p=splitCandidates[0].pane;
        path=splitCandidates[0].selected[0];
        splitSessionId=sessionId;
        splitSide=splitCandidates[0].side;
      }else{
        const side=(runtime?.activePane==='right'?'right':'left');
        const pane=runtime?.[side];
        const selected=Array.from(pane?.selected||[]);
        if(selected.length===1){
          p=pane;
          path=selected[0];
          splitSessionId=sessionId;
          splitSide=side;
        }
      }
    }
  }
  if(!path) return setStatus('Select exactly one item.');
  const newName=String(await showRenameModal(basename(path))||'').trim();
  if(!newName||newName===basename(path)) return;
  try{
    if(p.kind==='local') await apiPost('/api/local/rename',{path,new_name:newName});
    else{
      const it=p.items.find(x=>x.path===path);
      await apiPost('/api/sp/rename',{server_relative_url:path,new_name:newName,is_folder:!!it?.isDir,site_relative_url:p.site||null});
      const parent=normalizeSpPath(path).split('/').slice(0,-1).join('/')||'/';
      recordMigration('rename',it?.isDir?'folder':'file',path,`${parent}/${newName}`,p.site||'',p.site||'');
    }
    if(splitSessionId && splitSide){
      await loadSplitPane(splitSessionId, splitSide, p.path, true);
      if(splitSessionId===state.activeSessionId){
        syncActiveSessionFromSplitRuntime(hydrateSplitRuntime(splitSessionId));
      }
      setStatus('Renamed.');
      return;
    }
    await loadPane(p.key,p.path); setStatus('Renamed.');
  }catch(e){ setStatus(`Rename failed: ${err(e)}`); }
}

async function applyTranslationRename(){
  const p=activePane(); if(!state.translationEnabled) return setStatus('Enable translation first.');
  const ops=selectedItems(p).map(it=>({it,newName:p.translations.get(it.path)})).filter(x=>x.newName&&x.newName!==x.it.name);
  if(!ops.length) return setStatus('No translated names to apply.');
  try{
    const payloadItems = ops.map(o=>({path:o.it.path,new_name:o.newName,is_folder:!!o.it.isDir}));
    const preview = p.kind==='local'
      ? await apiPost('/api/local/rename-preview',{items:payloadItems})
      : await apiPost('/api/sp/rename-preview',{site_relative_url:p.site||null,items:payloadItems.map(x=>({path:x.path,new_name:x.new_name,is_folder:x.is_folder}))});
    const results = (preview.items||[]);
    const okRows = results.filter(r=>r.ok);
    const badRows = results.filter(r=>!r.ok);
    if(!okRows.length){
      return setStatus(`Rename preview blocked all items (${badRows.length} conflicts).`);
    }
    if(badRows.length){
      const proceed = await showRenamePreviewModal(okRows,badRows);
      if(!proceed) return;
    }

    if(p.kind==='local'){
      await apiPost('/api/local/bulk-rename',{items:okRows.map(r=>({path:r.path,new_name:r.new_name}))});
    }else{
      const undo=[];
      for(const r of okRows){
        const before=r.path;
        const match=ops.find(o=>o.it.path===before);
        const isDir=!!(match&&match.it&&match.it.isDir);
        await apiPost('/api/sp/rename',{server_relative_url:before,new_name:r.new_name,is_folder:isDir,site_relative_url:p.site||null});
        const parent=before.replace(/\/+$/,'').split('/').slice(0,-1).join('/')||'/';
        recordMigration('rename',isDir?'folder':'file',before,`${parent}/${r.new_name}`,p.site||'',p.site||'');
        undo.push({site:p.site||'',oldPath:before,newPath:`${parent}/${r.new_name}`,isDir});
      }
      if(undo.length) state.spRenameUndoStack.push(undo);
    }
    await loadPane(p.key,p.path); setStatus(`Renamed ${okRows.length} item(s).${badRows.length?` Skipped ${badRows.length} conflict(s).`:''}`);
  }catch(e){ setStatus(`Apply rename failed: ${err(e)}`); }
}

async function undoRename(){
  const p=activePane();
  try{
    const aiBatch=state.aiRenameUndoStack.pop();
    if(aiBatch&&aiBatch.length){
      for(const op of aiBatch.reverse()){
        if(op.kind==='local'){
          const targetParent=parentPath(op.oldPath), targetName=basename(op.oldPath);
          await ensureLocalFolderTree(commonParentForAi([op.oldPath],false),targetParent);
          await apiPost('/api/local/move',{sources:[op.newPath],destination:targetParent});
          const movedPath=`${targetParent}\\${basename(op.newPath)}`;
          if(basename(movedPath)!==targetName){
            await apiPost('/api/local/rename',{path:movedPath,new_name:targetName});
          }
        }else{
          const oldParent=(op.oldPath||'').replace(/\/+$/,'').split('/').slice(0,-1).join('/')||'/';
          const newParent=(op.newPath||'').replace(/\/+$/,'').split('/').slice(0,-1).join('/')||'/';
          const oldName=basename(op.oldPath);
          if(oldParent===newParent && basename(op.newPath)!==oldName){
            await apiPost('/api/sp/rename',{server_relative_url:op.newPath,new_name:oldName,is_folder:op.isDir,site_relative_url:op.site||null});
          }else{
            await ensureSpFolderTree(op.site||'', commonParentForAi([op.oldPath],true), oldParent);
            await apiPost('/api/sp/move',{source_server_relative_url:op.newPath,target_server_relative_url:op.oldPath,is_folder:op.isDir,overwrite:false,site_relative_url:op.site||null});
          }
          recordMigration('move',op.isDir?'folder':'file',op.newPath,op.oldPath,op.site||'',op.site||'');
        }
      }
      await loadPane('left',state.left.path); await loadPane('right',state.right.path); return setStatus('AI rename undo complete.');
    }
    if(p.kind==='local') await apiPost('/api/local/undo-rename',{});
    else{
      const batch=state.spRenameUndoStack.pop();
      if(!batch||!batch.length) return setStatus('No SharePoint rename batch to undo.');
      for(const op of batch.reverse()){
        await apiPost('/api/sp/rename',{server_relative_url:op.newPath,new_name:basename(op.oldPath),is_folder:op.isDir,site_relative_url:op.site||null});
        recordMigration('rename',op.isDir?'folder':'file',op.newPath,op.oldPath,op.site||'',op.site||'');
      }
    }
    await loadPane('left',state.left.path); await loadPane('right',state.right.path); setStatus('Undo complete.');
  }catch(e){ setStatus(`Undo failed: ${err(e)}`); }
}

async function deleteSelected(){
  const p=activePane(), items=selectedItems(p);
  if(!items.length||!confirm(`Delete ${items.length} item(s)?`)) return;
  try{
    if(p.kind==='local') await apiPost('/api/local/delete',{sources:items.map(i=>i.path)});
    else for(const it of items) await apiPost('/api/sp/delete',{server_relative_url:it.path,is_folder:!!it.isDir,site_relative_url:p.site||null,recycle:true});
    await loadPane(p.key,p.path); setStatus('Deleted.');
  }catch(e){ setStatus(`Delete failed: ${err(e)}`); }
}

async function createFolder(){
  const { pane:p, targetParent } = resolveCreateFolderContext();
  const name=String(el.newFolderNameInput?.value||'').trim();
  if(!name) return setStatus('Enter a folder name.');
  if(!targetParent) return setStatus('No target folder is available.');
  try{
    if(p.kind==='local') await apiPost('/api/local/mkdir',{path:targetParent,name});
    else await apiPost('/api/sp/folder',{site_relative_url:p.site||null,parent_server_relative_url:targetParent,name});
    closeNewFolderModal();
    await loadPane(p.key,p.path); setStatus('Folder created.');
  }catch(e){ setStatus(`Create failed: ${err(e)}`); }
}

async function openSelected(reveal){
  const p=activePane(), path=selectedSinglePath();
  if(!path) return setStatus('Select exactly one item.');
  try{
    if(p.kind==='local') await apiPost('/api/local/open',{path,reveal:!!reveal});
    else{
      const d=await apiPost('/api/sp/share-link',{server_relative_url:path,site_relative_url:p.site||null});
      if(d.url) window.open(d.url,'_blank');
    }
    setStatus(reveal?'Revealed.':'Opened.');
  }catch(e){ setStatus(`Open failed: ${err(e)}`); }
}

async function toggleTranslation(){
  state.translationEnabled=!state.translationEnabled;
  state.language=(el.langInput.value||'English').trim()||'English';
  el.toggleTranslateBtn.textContent=`Translate: ${state.translationEnabled?'On':'Off'}`;
  await refreshTranslations('left'); await refreshTranslations('right'); renderPane('left'); renderPane('right');
  saveCurrentSessionSnapshot();
}
function clearPreview(){ el.previewFrame.innerHTML='<small style="color:#94a3b8">No preview loaded.</small>'; }
function downloadUrl(p,path){ return p.kind==='local'?`/api/local/download?${new URLSearchParams({path}).toString()}`:`/api/sp/download?${new URLSearchParams({server_relative_url:path,site_relative_url:p.site||''}).toString()}`; }

async function previewSelected(){
  const p=activePane(), items=selectedItems(p);
  if(items.length!==1) return setStatus('Select exactly one item to preview.');
  const it=items[0]; if(it.isDir){ clearPreview(); el.previewText.textContent='Folder selected.'; return; }
  const e=extname(it.path), url=downloadUrl(p,it.path); el.previewText.textContent='';
  if(EXT_IMAGE.has(e)) return void (el.previewFrame.innerHTML=`<img src="${url}" alt="preview">`);
  if(EXT_VIDEO.has(e)) return void (el.previewFrame.innerHTML=`<video controls src="${url}"></video>`);
  if(EXT_AUDIO.has(e)) return void (el.previewFrame.innerHTML=`<audio controls src="${url}"></audio>`);
  if(EXT_PDF.has(e)){ el.previewFrame.innerHTML=`<iframe src="${url}"></iframe>`; renderPdfBookmarks(); return; }
  clearPreview(); await extractText();
}

async function extractText(){
  const p=activePane(), path=selectedSinglePath();
  if(!path) return setStatus('Select one file first.');
  try{
    const d=p.kind==='local' ? await apiGet(`/api/local/extract-text?${new URLSearchParams({path,limit:'12000'}).toString()}`) : await apiPost('/api/extract-text-item',{kind:'sharepoint',path,site_relative_url:p.site||null});
    el.previewText.textContent=d.text||''; setStatus('Text extracted.');
  }catch(e){ setStatus(`Extract failed: ${err(e)}`); }
}

async function summarizeSelected(){
  const p=activePane(), path=selectedSinglePath(); if(!path) return setStatus('Select one file first.');
  try{
    const d=await apiPost('/api/ai/summary-item',{kind:p.kind,path,site_relative_url:p.kind==='sharepoint'?p.site||null:null,preset:'short',tone:'neutral'});
    el.previewText.textContent=d.summary||''; setStatus('Summary ready.');
  }catch(e){ setStatus(`Summary failed: ${err(e)}`); }
}

async function askQuestion(){
  const p=activePane(), path=selectedSinglePath(), q=(el.questionInput.value||'').trim();
  if(!path||!q) return setStatus('Select a file and enter a question.');
  try{
    const d=await apiPost('/api/ai/question-item',{kind:p.kind,path,site_relative_url:p.kind==='sharepoint'?p.site||null:null,question:q});
    el.previewText.textContent=d.answer||''; setStatus('Answer ready.');
  }catch(e){ setStatus(`Question failed: ${err(e)}`); }
}

async function loadTagsForSelection(){
  const p=activePane(), path=selectedSinglePath(); if(!path){ el.tagInput.value=''; renderPdfBookmarks(); return; }
  try{ const d=await apiGet(`/api/tags/get?${new URLSearchParams({kind:p.kind,identifier:path}).toString()}`); el.tagInput.value=(d.tags||[]).join(','); }
  catch{ el.tagInput.value=''; }
  renderPdfBookmarks();
}
async function saveTags(){ const p=activePane(), path=selectedSinglePath(); if(!path) return setStatus('Select one item to set tags.'); try{ await apiPost('/api/tags/set',{kind:p.kind,identifier:path,tags:(el.tagInput.value||'').split(',').map(s=>s.trim()).filter(Boolean)}); setStatus('Tags updated.'); }catch(e){ setStatus(`Tag update failed: ${err(e)}`);} }
async function searchTags(){ const p=activePane(); try{ const d=await apiPost('/api/tags/search',{kind:p.kind,tags:(el.tagSearchInput.value||'').split(',').map(s=>s.trim()).filter(Boolean)}); const rows=d.results||[]; el.tagResults.textContent=rows.length?rows.map(r=>`${r.path}\n  matched: ${r.matched.join(', ')}\n  tags: ${r.tags.join(', ')}`).join('\n\n'):'No results'; }catch(e){ setStatus(`Tag search failed: ${err(e)}`);} }

async function loadProperties(){
  const p=activePane(), items=selectedItems(p); if(items.length!==1) return setStatus('Select exactly one item for properties.');
  const it=items[0];
  try{
    if(p.kind==='sharepoint'){
      const d=await apiPost('/api/sp/properties',{site_relative_url:p.site||null,server_relative_url:it.path,is_folder:!!it.isDir});
      el.propertiesOutput.textContent=JSON.stringify(d,null,2);
    }else{
      el.propertiesOutput.textContent=JSON.stringify({name:it.name,path:it.path,isDir:!!it.isDir,size:it.size||0,mtime:it.mtime||0},null,2);
    }
    setStatus('Properties loaded.');
  }catch(e){ setStatus(`Properties failed: ${err(e)}`); }
}
async function loadPermissionsProbe(){
  const p=activePane(), items=selectedItems(p);
  if(items.length!==1) return setStatus('Select exactly one item for permissions.');
  const it=items[0];
  try{
    const d=await apiPost('/api/permissions/probe',{
      kind:p.kind,
      path:it.path,
      is_folder:!!it.isDir,
      site_relative_url:p.kind==='sharepoint'?(p.site||null):null,
    });
    if(el.permissionsOutput) el.permissionsOutput.textContent=JSON.stringify(d,null,2);
    setStatus('Permissions loaded.');
  }catch(e){ setStatus(`Permissions probe failed: ${err(e)}`); }
}

async function spLoadMetadataFields(){
  const p=activePane(), items=selectedItems(p);
  if(p.kind!=='sharepoint') return setStatus('Metadata fields are only available for SharePoint items.');
  if(items.length!==1) return setStatus('Select exactly one SharePoint item.');
  const it=items[0];
  try{
    const d=await apiPost('/api/sp/metadata-fields',{site_relative_url:p.site||null,server_relative_url:it.path,is_folder:!!it.isDir});
    const rows=(d.fields||[]);
    state.metadataFields=rows;
    el.metadataOutput.textContent=JSON.stringify(rows,null,2);
    renderMetadataForm(rows);
    refreshMetadataValidationAndDiff();
    setStatus(`Loaded ${rows.length} metadata field(s).`);
  }catch(e){ setStatus(`Metadata load failed: ${err(e)}`); }
}

async function spApplyMetadata(){
  const p=activePane(), items=selectedItems(p);
  if(p.kind!=='sharepoint') return setStatus('Metadata update is only available for SharePoint items.');
  if(items.length!==1) return setStatus('Select exactly one SharePoint item.');
  const it=items[0];
  let fields;
  try{
    fields=collectMetadataPayload();
  }catch(parseErr){
    return setStatus(`Metadata JSON is invalid: ${err(parseErr)}`);
  }
  const keys=Object.keys(fields);
  if(!keys.length) return setStatus('No metadata fields to update.');
  try{
    const d=await apiPost('/api/sp/metadata-update',{site_relative_url:p.site||null,server_relative_url:it.path,is_folder:!!it.isDir,fields});
    el.metadataOutput.textContent=JSON.stringify(d,null,2);
    if(d.ok){
      setStatus(`Updated metadata fields: ${keys.length}`);
    }else{
      const failed=(d.failures||[]).length;
      setStatus(`Metadata update partially failed (${failed} field error(s)).`);
    }
  }catch(e){ setStatus(`Metadata update failed: ${err(e)}`); }
}

async function spCheckOut(){ const p=activePane(), path=selectedSinglePath(); if(p.kind!=='sharepoint'||!path) return setStatus('Select one SharePoint file.'); try{ await apiPost('/api/sp/checkout',{server_relative_url:path,site_relative_url:p.site||null}); setStatus('Checked out.'); }catch(e){ setStatus(`Check-out failed: ${err(e)}`);} }
async function spCheckIn(){ const p=activePane(), path=selectedSinglePath(); if(p.kind!=='sharepoint'||!path) return setStatus('Select one SharePoint file.'); try{ await apiPost('/api/sp/checkin',{server_relative_url:path,site_relative_url:p.site||null,comment:prompt('Check-in comment:','')||'',checkin_type:1}); setStatus('Checked in.'); }catch(e){ setStatus(`Check-in failed: ${err(e)}`);} }
async function spUndoCheckout(){ const p=activePane(), path=selectedSinglePath(); if(p.kind!=='sharepoint'||!path) return setStatus('Select one SharePoint file.'); try{ await apiPost('/api/sp/undo-checkout',{server_relative_url:path,site_relative_url:p.site||null}); setStatus('Undo check-out complete.'); }catch(e){ setStatus(`Undo check-out failed: ${err(e)}`);} }
async function spLoadVersions(){ const p=activePane(), path=selectedSinglePath(); if(p.kind!=='sharepoint'||!path) return setStatus('Select one SharePoint file.'); try{ const d=await apiGet(`/api/sp/versions?${new URLSearchParams({server_relative_url:path,site_relative_url:p.site||''}).toString()}`); state.versionsCache=d.versions||[]; fillSelect(el.versionsSelect,state.versionsCache.map(v=>({id:v.label||'',title:`${v.label||'n/a'} | ${v.created||''} | ${v.author||''}`})),'id','title',''); el.versionsOutput.textContent=JSON.stringify(state.versionsCache,null,2); setStatus(`Loaded versions: ${state.versionsCache.length}`);}catch(e){ setStatus(`Load versions failed: ${err(e)}`);} }
function spDownloadVersion(){ const p=activePane(), path=selectedSinglePath(), label=el.versionsSelect.value; if(p.kind!=='sharepoint'||!path||!label) return setStatus('Select SharePoint file and version.'); window.open(`/api/sp/download-version?${new URLSearchParams({server_relative_url:path,label,site_relative_url:p.site||''}).toString()}`,'_blank'); }
async function spRestoreVersion(){ const p=activePane(), path=selectedSinglePath(), label=el.versionsSelect.value; if(p.kind!=='sharepoint'||!path||!label) return setStatus('Select SharePoint file and version.'); if(!confirm(`Restore version ${label}?`)) return; try{ await apiPost('/api/sp/restore-version',{server_relative_url:path,label,site_relative_url:p.site||null}); setStatus(`Restored version ${label}.`);}catch(e){ setStatus(`Restore failed: ${err(e)}`);} }

function loadFavorites(){ try{ state.favorites=JSON.parse(localStorage.getItem('smx_web_favorites')||'[]'); if(!Array.isArray(state.favorites)) state.favorites=[]; }catch{ state.favorites=[]; } }
function saveFavorites(){ localStorage.setItem('smx_web_favorites',JSON.stringify(state.favorites)); }
function normalizeSpPath(path){ let v=String(path||'').trim(); if(!v) return ''; if(!v.startsWith('/')) v='/'+v; return v.replace(/\/+$/,'')||'/'; }
function loadMigrationLog(){ try{ state.migrationLog=JSON.parse(localStorage.getItem('smx_web_link_migrations')||'[]'); if(!Array.isArray(state.migrationLog)) state.migrationLog=[]; }catch{ state.migrationLog=[]; } }
function saveMigrationLog(){ localStorage.setItem('smx_web_link_migrations',JSON.stringify(state.migrationLog)); }
function loadAiRenameLog(){ try{ state.aiRenameLog=JSON.parse(localStorage.getItem('smx_web_ai_rename_log')||'[]'); if(!Array.isArray(state.aiRenameLog)) state.aiRenameLog=[]; }catch{ state.aiRenameLog=[]; } }
function saveAiRenameLog(){ localStorage.setItem('smx_web_ai_rename_log',JSON.stringify(state.aiRenameLog)); }
function loadRelinkState(){
  try{ state.relinkImports=JSON.parse(localStorage.getItem('smx_web_relink_imports')||'[]'); if(!Array.isArray(state.relinkImports)) state.relinkImports=[]; }catch{ state.relinkImports=[]; }
  try{ state.relinkExports=JSON.parse(localStorage.getItem('smx_web_relink_exports')||'[]'); if(!Array.isArray(state.relinkExports)) state.relinkExports=[]; }catch{ state.relinkExports=[]; }
  state.relinkImports=state.relinkImports.map((entry)=>({
    source_format:'netscape-html',
    source_browser:'generic',
    status:'imported',
    source_rows:[],
    summary:{total:0,resolved:0,unchanged:0,external:0},
    ...entry,
    source_rows:Array.isArray(entry?.source_rows) ? entry.source_rows : (Array.isArray(entry?.rows) ? entry.rows : []),
  }));
}
function saveRelinkState(){
  localStorage.setItem('smx_web_relink_imports',JSON.stringify(state.relinkImports));
  localStorage.setItem('smx_web_relink_exports',JSON.stringify(state.relinkExports));
}
function loadAppView(){
  state.appView=localStorage.getItem('smx_web_app_view')==='relinking' ? 'relinking' : 'workspace';
}
function buildWebUrlFromPath(path){
  const base=String(el.spBaseUrlInput?.value||'').trim();
  if(!base) return '';
  try{
    const u=new URL(base);
    return new URL(normalizeSpPath(path), `${u.protocol}//${u.host}`).toString();
  }catch{
    return '';
  }
}
function toCsvValue(value){
  const text=String(value ?? '');
  if(/[",\n]/.test(text)) return `"${text.replace(/"/g,'""')}"`;
  return text;
}
function extractServerRelativeBookmarkPath(value){
  const raw=String(value||'').trim();
  if(!raw) return '';
  if(raw.startsWith('/')) return normalizeSpPath(raw);
  try{
    const url=new URL(raw);
    const params=url.searchParams;
    for(const key of ['id','RootFolder','rootfolder','FileRef','SourceUrl','src']){
      const candidate=String(params.get(key)||'').trim();
      if(candidate.startsWith('/')) return normalizeSpPath(decodeURIComponent(candidate));
    }
    let path=decodeURIComponent(url.pathname||'');
    if(path.startsWith('/:') && path.includes('/r/')){
      path=path.split('/r/')[1]||'';
      if(path && !path.startsWith('/')) path=`/${path}`;
    }
    return normalizeSpPath(path);
  }catch{
    return '';
  }
}
function buildResolvedBookmarkUrl(originalUrl, currentPath){
  const direct=buildWebUrlFromPath(currentPath);
  if(direct) return direct;
  try{
    const url=new URL(String(originalUrl||'').trim());
    if(String(currentPath||'').startsWith('/')){
      return new URL(normalizeSpPath(currentPath), `${url.protocol}//${url.host}`).toString();
    }
  }catch{}
  return String(originalUrl||'').trim();
}
function downloadBlob(filename, content, type){
  const blob=new Blob([content],{type});
  const url=URL.createObjectURL(blob);
  const a=document.createElement('a');
  a.href=url;
  a.download=filename;
  a.click();
  URL.revokeObjectURL(url);
}
function parseBookmarkExportHtml(html){
  const parser=new DOMParser();
  const doc=parser.parseFromString(html,'text/html');
  const rows=[];
  function textOf(node){
    return String(node?.textContent||'').replace(/\s+/g,' ').trim();
  }
  function walkDl(dl, folderStack){
    if(!dl) return;
    const children=Array.from(dl.children||[]);
    for(let i=0;i<children.length;i++){
      const child=children[i];
      if(String(child.tagName||'').toUpperCase()!=='DT') continue;
      const folder=child.querySelector(':scope > h3');
      const anchor=child.querySelector(':scope > a[href]');
      if(anchor){
        rows.push({
          title:textOf(anchor)||String(anchor.getAttribute('href')||'').trim(),
          folder_path:folderStack.join(' / '),
          url:String(anchor.getAttribute('href')||'').trim(),
        });
        continue;
      }
      if(folder){
        const name=textOf(folder);
        const next=children[i+1];
        if(next && String(next.tagName||'').toUpperCase()==='DL'){
          walkDl(next, name ? folderStack.concat(name) : folderStack.slice());
        }
      }
    }
  }
  walkDl(doc.querySelector('dl'), []);
  if(!rows.length){
    doc.querySelectorAll('a[href]').forEach((anchor)=>{
      rows.push({
        title:textOf(anchor)||String(anchor.getAttribute('href')||'').trim(),
        folder_path:'',
        url:String(anchor.getAttribute('href')||'').trim(),
      });
    });
  }
  return rows;
}
function detectBookmarkSourceBrowser(html){
  const lowered=String(html||'').toLowerCase();
  if(lowered.includes('netscape-bookmark-file-1')) return 'generic_netscape';
  return 'generic';
}
function convertBookmarkRows(rows){
  return (rows||[]).map((row)=>{
    const originalUrl=String(row?.url||'').trim();
    const originalPath=extractServerRelativeBookmarkPath(originalUrl);
    if(!originalPath){
      return {
        title:String(row?.title||originalUrl||'').trim(),
        folder_path:String(row?.folder_path||'').trim(),
        original_url:originalUrl,
        original_server_relative_url:'',
        current_url:originalUrl,
        current_server_relative_url:'',
        current_site_relative_url:'',
        status:'external',
        notes:'Bookmark does not contain a SharePoint-style server-relative path.',
      };
    }
    const resolved=resolveMigrationTarget(originalPath,'');
    const currentPath=String(resolved?.path||originalPath);
    const currentSite=String(resolved?.site||'').trim();
    return {
      title:String(row?.title||originalUrl||'').trim(),
      folder_path:String(row?.folder_path||'').trim(),
      original_url:originalUrl,
      original_server_relative_url:originalPath,
      current_url:buildResolvedBookmarkUrl(originalUrl,currentPath),
      current_server_relative_url:currentPath,
      current_site_relative_url:currentSite,
      status:resolved?'resolved':'unchanged',
      notes:resolved?'':'No migration record matched this bookmark path.',
    };
  }).filter((row)=>row.original_url);
}
function exportConvertedBookmarkRows(rows, format){
  const safeFormat=format==='csv'?'csv':'json';
  if(safeFormat==='csv'){
    const headers=['title','folder_path','original_url','original_server_relative_url','current_url','current_server_relative_url','current_site_relative_url','status','notes'];
    const lines=[headers.join(',')];
    rows.forEach((row)=>lines.push(headers.map((h)=>toCsvValue(row?.[h] ?? '')).join(',')));
    downloadBlob(`smx-bookmark-resolution-${Date.now()}.csv`,lines.join('\n'),'text/csv');
    return;
  }
  downloadBlob(`smx-bookmark-resolution-${Date.now()}.json`,JSON.stringify(rows,null,2),'application/json');
}
function buildBookmarkHtmlFromRows(rows, title='Bookmarks'){
  const root={folders:new Map(), links:[]};
  (rows||[]).forEach((row)=>{
    const parts=String(row?.folder_path||'').split('/').map((part)=>part.trim()).filter(Boolean);
    let cursor=root;
    parts.forEach((part)=>{
      if(!cursor.folders.has(part)) cursor.folders.set(part,{folders:new Map(),links:[]});
      cursor=cursor.folders.get(part);
    });
    cursor.links.push({title:String(row?.title||row?.current_url||row?.original_url||'').trim(),href:String(row?.current_url||row?.original_url||'').trim()});
  });
  const lines=['<!DOCTYPE NETSCAPE-Bookmark-file-1>','<!-- This file was generated by SmartExplorer -->',`<TITLE>${escapeHtml(title)}</TITLE>`,`<H1>${escapeHtml(title)}</H1>`,'<DL><p>'];
  function emitFolder(node, depth){
    const pad='    '.repeat(depth);
    node.links.forEach((link)=>{
      lines.push(`${pad}<DT><A HREF="${escapeHtml(link.href)}">${escapeHtml(link.title||link.href)}</A>`);
    });
    Array.from(node.folders.entries()).forEach(([name, child])=>{
      lines.push(`${pad}<DT><H3>${escapeHtml(name)}</H3>`);
      lines.push(`${pad}<DL><p>`);
      emitFolder(child, depth+1);
      lines.push(`${pad}</DL><p>`);
    });
  }
  emitFolder(root,1);
  lines.push('</DL><p>');
  return lines.join('\n');
}
async function convertBookmarkExportFile(file, format){
  if(!file) return;
  try{
    const html=await file.text();
    const rows=convertBookmarkRows(parseBookmarkExportHtml(html));
    exportConvertedBookmarkRows(rows, format);
    const resolved=rows.filter((row)=>row.status==='resolved').length;
    const unchanged=rows.filter((row)=>row.status==='unchanged').length;
    const external=rows.filter((row)=>row.status==='external').length;
    setStatus(`Converted ${rows.length} bookmark(s) to ${format.toUpperCase()}. Resolved ${resolved}, unchanged ${unchanged}, external ${external}.`);
  }catch(e){
    setStatus(`Bookmark HTML conversion failed: ${err(e)}`);
  }
}
function renderAppView(){
  const workspaceActive=state.appView!=='relinking';
  if(el.appWorkspaceTabBtn){
    el.appWorkspaceTabBtn.classList.toggle('bg-primary/10', workspaceActive);
    el.appWorkspaceTabBtn.classList.toggle('text-primary', workspaceActive);
  }
  if(el.appRelinkingTabBtn){
    el.appRelinkingTabBtn.classList.toggle('bg-primary/10', !workspaceActive);
    el.appRelinkingTabBtn.classList.toggle('text-primary', !workspaceActive);
  }
  const showRelinking=!workspaceActive;
  const showSessionBar=workspaceActive && !state.splitViewEnabled;
  const showToolsBar=workspaceActive;
  if(el.sessionBar) el.sessionBar.classList.toggle('hidden', !showSessionBar);
  if(el.workspaceToolsBar) el.workspaceToolsBar.classList.toggle('hidden', !showToolsBar);
  if(el.relinkingWorkspaceView) el.relinkingWorkspaceView.classList.toggle('hidden', !showRelinking);
  if(el.mainWorkspaceView) el.mainWorkspaceView.classList.toggle('hidden', showRelinking || (state.splitViewEnabled && splitSessionIds().length>0));
  if(el.splitSessionsHost) el.splitSessionsHost.classList.toggle('hidden', showRelinking || !(state.splitViewEnabled && splitSessionIds().length>0));
}
function openAppView(view){
  state.appView=view==='relinking' ? 'relinking' : 'workspace';
  localStorage.setItem('smx_web_app_view', state.appView);
  renderAppView();
  if(state.appView==='relinking'){
    renderMigrationPanel();
    renderRelinkImports();
    renderRelinkExports();
  }
}
function renderRelinkImports(){
  if(!el.relinkImportsList) return;
  el.relinkImportsList.innerHTML='';
  const rows=state.relinkImports.slice().reverse();
  if(!rows.length){
    el.relinkImportsList.innerHTML='<div class="rounded-lg border border-slate-200 p-2 text-xs text-slate-500 dark:border-slate-700">No bookmark HTML imports yet.</div>';
    return;
  }
  rows.forEach((entry)=>{
    const item=document.createElement('div');
    item.className='rounded-lg border border-slate-200 p-2 text-xs dark:border-slate-700';
    const summary=entry.summary||{};
    item.innerHTML=`<div class="font-semibold">${escapeHtml(entry.name||'Bookmark Import')}</div><div class="mt-1 text-slate-500">${escapeHtml(entry.imported_at||'')}</div><div class="mt-1 text-slate-500">${escapeHtml(entry.source_browser||'generic')} · ${summary.total||0} total bookmark(s) normalized to JSON</div>`;
    const actions=document.createElement('div');
    actions.className='mt-2 flex flex-wrap gap-2';
    const resolveBtn=document.createElement('button');
    resolveBtn.textContent='Resolve & Export HTML';
    resolveBtn.onclick=()=>resolveRelinkImport(entry.id);
    const jsonBtn=document.createElement('button');
    jsonBtn.textContent='Download JSON';
    jsonBtn.onclick=()=>downloadBlob(`${(entry.name||'bookmarks').replace(/\.[^.]+$/,'')}-normalized.json`,JSON.stringify(entry.source_rows||entry.rows||[],null,2),'application/json');
    const deleteBtn=document.createElement('button');
    deleteBtn.textContent='Delete';
    deleteBtn.onclick=()=>deleteRelinkImport(entry.id);
    actions.appendChild(resolveBtn);
    actions.appendChild(jsonBtn);
    actions.appendChild(deleteBtn);
    item.appendChild(actions);
    el.relinkImportsList.appendChild(item);
  });
}
function renderRelinkExports(){
  if(!el.relinkExportsList) return;
  el.relinkExportsList.innerHTML='';
  const rows=state.relinkExports.slice().reverse();
  if(!rows.length){
    el.relinkExportsList.innerHTML='<div class="rounded-lg border border-slate-200 p-2 text-xs text-slate-500 dark:border-slate-700">No resolved bookmark exports yet.</div>';
    return;
  }
  rows.forEach((entry)=>{
    const item=document.createElement('div');
    item.className='rounded-lg border border-slate-200 p-2 text-xs dark:border-slate-700';
    const summary=entry.summary||{};
    item.innerHTML=`<div class="font-semibold">${escapeHtml(entry.name||'Resolved Export')}</div><div class="mt-1 text-slate-500">${escapeHtml(entry.created_at||'')}</div><div class="mt-1 text-slate-500">${summary.total||0} total · ${summary.resolved||0} resolved · ${summary.unchanged||0} unchanged · ${summary.external||0} external</div>`;
    const actions=document.createElement('div');
    actions.className='mt-2 flex flex-wrap gap-2';
    const htmlBtn=document.createElement('button');
    htmlBtn.textContent='Download HTML';
    htmlBtn.onclick=()=>downloadBlob(`${entry.file_stem||'resolved-bookmarks'}.html`,entry.html||'','text/html');
    const jsonBtn=document.createElement('button');
    jsonBtn.textContent='Download JSON';
    jsonBtn.onclick=()=>downloadBlob(`${entry.file_stem||'resolved-bookmarks'}.json`,JSON.stringify(entry.rows||[],null,2),'application/json');
    const deleteBtn=document.createElement('button');
    deleteBtn.textContent='Delete';
    deleteBtn.onclick=()=>deleteRelinkExport(entry.id);
    actions.appendChild(htmlBtn);
    actions.appendChild(jsonBtn);
    actions.appendChild(deleteBtn);
    item.appendChild(actions);
    el.relinkExportsList.appendChild(item);
  });
}
function deleteRelinkImport(importId){
  const entry=state.relinkImports.find((row)=>row.id===importId);
  if(!entry) return;
  if(!confirm(`Delete import "${entry.name||'Bookmark Import'}" and its resolved exports?`)) return;
  state.relinkImports=state.relinkImports.filter((row)=>row.id!==importId);
  state.relinkExports=state.relinkExports.filter((row)=>row.source_import_id!==importId);
  saveRelinkState();
  renderRelinkImports();
  renderRelinkExports();
  setStatus(`Deleted import "${entry.name||'Bookmark Import'}".`);
}
function clearRelinkImports(){
  if(!state.relinkImports.length) return;
  if(!confirm('Delete all imported bookmark artifacts and their resolved exports?')) return;
  const removed=state.relinkImports.length;
  state.relinkImports=[];
  state.relinkExports=[];
  saveRelinkState();
  renderRelinkImports();
  renderRelinkExports();
  setStatus(`Cleared ${removed} import artifact(s).`);
}
function deleteRelinkExport(exportId){
  const entry=state.relinkExports.find((row)=>row.id===exportId);
  if(!entry) return;
  if(!confirm(`Delete resolved export "${entry.name||'Resolved Export'}"?`)) return;
  state.relinkExports=state.relinkExports.filter((row)=>row.id!==exportId);
  saveRelinkState();
  renderRelinkExports();
  setStatus(`Deleted export "${entry.name||'Resolved Export'}".`);
}
function clearRelinkExports(){
  if(!state.relinkExports.length) return;
  if(!confirm('Delete all resolved export artifacts?')) return;
  const removed=state.relinkExports.length;
  state.relinkExports=[];
  saveRelinkState();
  renderRelinkExports();
  setStatus(`Cleared ${removed} export artifact(s).`);
}
async function importRelinkBookmarkFile(file){
  if(!file) return;
  try{
    const html=await file.text();
    const sourceRows=parseBookmarkExportHtml(html);
    const summary={
      total:sourceRows.length,
      resolved:0,
      unchanged:0,
      external:0,
    };
    state.relinkImports.push({
      id:`relink-import-${Date.now()}-${Math.random().toString(36).slice(2,7)}`,
      name:file.name||`bookmark-import-${Date.now()}.html`,
      imported_at:new Date().toISOString(),
      source_format:'netscape-html',
      source_browser:detectBookmarkSourceBrowser(html),
      status:'imported',
      source_rows:sourceRows,
      summary,
    });
    state.relinkImports=state.relinkImports.slice(-50);
    saveRelinkState();
    renderRelinkImports();
    openAppView('relinking');
    setStatus(`Imported bookmark HTML and normalized ${summary.total} bookmark(s) in the background.`);
  }catch(e){
    setStatus(`Bookmark import failed: ${err(e)}`);
  }
}
function resolveRelinkImport(importId){
  const entry=state.relinkImports.find((row)=>row.id===importId);
  if(!entry) return setStatus('Bookmark import not found.');
  const rows=convertBookmarkRows(entry.source_rows||entry.rows||[]);
  const summary={
    total:rows.length,
    resolved:rows.filter((row)=>row.status==='resolved').length,
    unchanged:rows.filter((row)=>row.status==='unchanged').length,
    external:rows.filter((row)=>row.status==='external').length,
  };
  const fileStem=String(entry.name||'resolved-bookmarks').replace(/\.[^.]+$/,'');
  const html=buildBookmarkHtmlFromRows(rows,fileStem);
  state.relinkExports.push({
    id:`relink-export-${Date.now()}-${Math.random().toString(36).slice(2,7)}`,
    source_import_id:entry.id,
    name:`${fileStem} resolved`,
    created_at:new Date().toISOString(),
    source_browser:entry.source_browser||'generic',
    status:'resolved',
    file_stem:`${fileStem}-resolved`,
    rows,
    html,
    summary,
  });
  state.relinkExports=state.relinkExports.slice(-50);
  saveRelinkState();
  renderRelinkExports();
  downloadBlob(`${fileStem}-resolved.html`,html,'text/html');
  setStatus(`Resolved ${summary.total} bookmark(s) and exported HTML.`);
}
function resolveMigrationTarget(path,site){
  let current=normalizeSpPath(path);
  let currentSite=String(site||'').trim();
  let changed=false;
  for(let i=0;i<20;i++){
    let next=null;
    for(let idx=state.migrationLog.length-1; idx>=0; idx--){
      const r=state.migrationLog[idx]||{};
      if(String(r.status||'').toLowerCase()!=='completed') continue;
      const oldPath=normalizeSpPath(r.old_server_relative_url||'');
      const newPath=normalizeSpPath(r.new_server_relative_url||'');
      const srcSite=String(r.source_site_relative_url||'').trim();
      if(currentSite && srcSite && currentSite!==srcSite) continue;
      if(!oldPath || !newPath) continue;
      if(current===oldPath){
        next={path:newPath,site:String(r.target_site_relative_url||currentSite||'').trim()};
        break;
      }
      if(current.startsWith(oldPath.replace(/\/+$/,'') + '/')){
        next={path:newPath.replace(/\/+$/,'') + current.slice(oldPath.length),site:String(r.target_site_relative_url||currentSite||'').trim()};
        break;
      }
    }
    if(!next || next.path===current) break;
    current=next.path;
    currentSite=next.site;
    changed=true;
  }
  return changed ? {path:current,site:currentSite} : null;
}
function renderMigrationPanel(){
  if(el.migrationCopyResolvedBtn) el.migrationCopyResolvedBtn.disabled=true;
  if(el.migrationOpenResolvedBtn) el.migrationOpenResolvedBtn.disabled=true;
  if(el.migrationLogList){
    el.migrationLogList.innerHTML='';
    const query=String(el.migrationFilterInput?.value||'').trim().toLowerCase();
    let rows=state.migrationLog.slice().reverse();
    if(query){
      rows=rows.filter((r)=>{
        const hay=[r.timestamp,r.operation_type,r.item_type,r.old_server_relative_url,r.new_server_relative_url,r.source_site_relative_url,r.target_site_relative_url,r.status].map((x)=>String(x||'').toLowerCase()).join(' ');
        return hay.includes(query);
      });
    }
    rows=rows.slice(0,50);
    if(!rows.length){
      el.migrationLogList.innerHTML='<div class="rounded-lg border border-slate-200 p-2 text-xs text-slate-500 dark:border-slate-700">No migration records yet.</div>';
    }else{
    rows.forEach((r)=>{
      const item=document.createElement('div');
      item.className='rounded-lg border border-slate-200 p-2 text-xs dark:border-slate-700';
      item.innerHTML=`<div class="font-semibold">${escapeHtml(r.operation_type||'move')} · ${escapeHtml(r.item_type||'item')}</div><div class="mt-1 text-slate-500">${escapeHtml(r.old_server_relative_url||'')}</div><div class="mt-1 text-primary">${escapeHtml(r.new_server_relative_url||'')}</div>`;
      const actions=document.createElement('div');
      actions.className='mt-2 flex flex-wrap gap-2';
      const deleteBtn=document.createElement('button');
      deleteBtn.textContent='Delete';
      deleteBtn.onclick=()=>deleteMigrationRecord(String(r.id||''));
      actions.appendChild(deleteBtn);
      item.appendChild(actions);
      el.migrationLogList.appendChild(item);
    });
  }
  }
  if(el.migrationResolveOutput && !el.migrationResolveOutput.dataset.touched){
    el.migrationResolveOutput.textContent=`${state.migrationLog.length} migration record(s) available locally.`;
  }
}
function deleteMigrationRecord(recordId){
  const entry=state.migrationLog.find((row)=>String(row?.id||'')===String(recordId||''));
  if(!entry) return;
  if(!confirm('Delete the selected migration activity record?')) return;
  state.migrationLog=state.migrationLog.filter((row)=>String(row?.id||'')!==String(recordId||''));
  saveMigrationLog();
  renderMigrationPanel();
  setStatus('Deleted selected migration activity.');
}
function clearMigrationLog(){
  if(!state.migrationLog.length) return;
  if(!confirm('Delete all migration activity records?')) return;
  const removed=state.migrationLog.length;
  state.migrationLog=[];
  saveMigrationLog();
  renderMigrationPanel();
  setStatus(`Cleared ${removed} migration record(s).`);
}
function renderAiRenameLogPanel(){
  if(!el.aiRenameLogList) return;
  el.aiRenameLogList.innerHTML='';
  const query=String(el.aiRenameFilterInput?.value||'').trim().toLowerCase();
  let rows=state.aiRenameLog.slice().reverse();
  if(query){
    rows=rows.filter((row)=>{
      const ops=Array.isArray(row?.operations)?row.operations:[];
      const blob=[
        row?.timestamp||'', row?.kind||'', row?.root_path||'', row?.summary||'', row?.instruction||'', row?.site_relative_url||'',
        ...ops.flatMap((op)=>[op?.source_path||'', op?.target_path||'', op?.status||'', op?.action||'', op?.reason||''])
      ].join(' ').toLowerCase();
      return blob.includes(query);
    });
  }
  if(!rows.length){
    el.aiRenameLogList.innerHTML='<div class="rounded-lg border border-slate-200 p-2 text-xs text-slate-500 dark:border-slate-700">No AI rename batches logged yet.</div>';
    return;
  }
  rows.slice(0,20).forEach((row)=>{
    const ops=Array.isArray(row?.operations)?row.operations:[];
    const applied=ops.filter((op)=>String(op?.status||'')==='applied').length;
    const failed=ops.filter((op)=>String(op?.status||'')==='failed').length;
    const item=document.createElement('div');
    item.className='rounded-lg border border-slate-200 p-2 text-xs dark:border-slate-700';
    item.innerHTML=`
      <div class="font-semibold">${escapeHtml(row?.summary||'AI rename batch')}</div>
      <div class="mt-1 text-slate-500">${escapeHtml(row?.timestamp||'')} | ${escapeHtml(row?.kind||'')} | ${row?.recursive?'recursive':'flat'} | ${applied} applied${failed?`, ${failed} failed`:''}</div>
      <div class="mt-1 text-slate-500">${escapeHtml(row?.root_path||'')}</div>
    `;
    el.aiRenameLogList.appendChild(item);
  });
}
function exportAiRenameLogJson(){
  downloadBlob(`smx-ai-rename-log-${Date.now()}.json`,JSON.stringify(state.aiRenameLog,null,2),'application/json');
}
function exportAiRenameLogCsv(){
  const lines=[['batch_id','timestamp','kind','site_relative_url','root_path','recursive','summary','instruction','source_path','target_path','action','reason','is_dir','status','error'].join(',')];
  state.aiRenameLog.forEach((row)=>{
    const ops=Array.isArray(row?.operations)?row.operations:[];
    ops.forEach((op)=>{
      lines.push([
        csvCell(row?.id||''),csvCell(row?.timestamp||''),csvCell(row?.kind||''),csvCell(row?.site_relative_url||''),csvCell(row?.root_path||''),
        csvCell(String(!!row?.recursive)),csvCell(row?.summary||''),csvCell(row?.instruction||''),csvCell(op?.source_path||''),csvCell(op?.target_path||''),
        csvCell(op?.action||''),csvCell(op?.reason||''),csvCell(String(!!op?.is_dir)),csvCell(op?.status||''),csvCell(op?.error||'')
      ].join(','));
    });
  });
  downloadBlob(`smx-ai-rename-log-${Date.now()}.csv`,lines.join('\n'),'text/csv');
}
function resolveMigrationInput(){
  const raw=String(el.migrationResolveInput?.value||'').trim();
  if(!raw){
    if(el.migrationResolveOutput){
      el.migrationResolveOutput.dataset.touched='1';
      el.migrationResolveOutput.textContent='Paste an old SharePoint URL or path first.';
    }
    return;
  }
  let path=raw;
  try{
    const u=new URL(raw);
    path=u.pathname||raw;
  }catch{}
  const resolved=resolveMigrationTarget(path,'');
  if(!el.migrationResolveOutput) return;
  el.migrationResolveOutput.dataset.touched='1';
  if(!resolved){
    el.migrationResolveOutput.textContent='No migration record matched that link.';
    if(el.migrationResolveOutput) el.migrationResolveOutput.dataset.value='';
    if(el.migrationCopyResolvedBtn) el.migrationCopyResolvedBtn.disabled=true;
    if(el.migrationOpenResolvedBtn) el.migrationOpenResolvedBtn.disabled=true;
    return;
  }
  const resolvedUrl=buildWebUrlFromPath(resolved.path);
  const outputValue=resolvedUrl||resolved.path;
  el.migrationResolveOutput.textContent=outputValue;
  el.migrationResolveOutput.dataset.value=outputValue;
  if(el.migrationCopyResolvedBtn) el.migrationCopyResolvedBtn.disabled=!outputValue;
  if(el.migrationOpenResolvedBtn) el.migrationOpenResolvedBtn.disabled=!resolvedUrl;
}
async function copyResolvedMigrationValue(){
  const value=String(el.migrationResolveOutput?.dataset?.value||'').trim();
  if(!value) return setStatus('Resolve a link first.');
  try{
    if(navigator.clipboard && navigator.clipboard.writeText){
      await navigator.clipboard.writeText(value);
    }else{
      const tmp=document.createElement('textarea');
      tmp.value=value;
      document.body.appendChild(tmp);
      tmp.select();
      document.execCommand('copy');
      tmp.remove();
    }
    setStatus('Resolved link copied.');
  }catch(e){
    setStatus(`Copy failed: ${err(e)}`);
  }
}
function openResolvedMigrationValue(){
  const value=String(el.migrationResolveOutput?.dataset?.value||'').trim();
  if(!value) return setStatus('Resolve a link first.');
  try{
    const u=new URL(value);
    window.open(u.toString(), '_blank', 'noopener,noreferrer');
    setStatus('Resolved link opened in a new tab.');
  }catch{
    setStatus('Resolved value is not a browser URL.');
  }
}
function exportMigrationLogJson(){
  downloadBlob(`smx-link-migrations-${Date.now()}.json`,JSON.stringify(state.migrationLog,null,2),'application/json');
  setStatus('Migration log exported as JSON.');
}
function exportMigrationLogCsv(){
  const headers=['timestamp','operation_type','item_type','source_site_relative_url','target_site_relative_url','old_server_relative_url','new_server_relative_url','old_web_url','new_web_url','status'];
  const lines=[headers.join(',')];
  state.migrationLog.forEach((r)=>{
    lines.push(headers.map((h)=>toCsvValue(r?.[h] ?? '')).join(','));
  });
  downloadBlob(`smx-link-migrations-${Date.now()}.csv`,lines.join('\n'),'text/csv');
  setStatus('Migration log exported as CSV.');
}
async function importMigrationLogFile(file){
  if(!file) return;
  try{
    const txt=await file.text();
    const rows=JSON.parse(txt);
    if(!Array.isArray(rows)) throw new Error('Import file must contain a JSON array.');
    const seen=new Set(state.migrationLog.map((r)=>`${r.operation_type||''}|${r.source_site_relative_url||''}|${normalizeSpPath(r.old_server_relative_url||'')}|${r.target_site_relative_url||''}|${normalizeSpPath(r.new_server_relative_url||'')}`));
    const existingSources=new Map();
    state.migrationLog.forEach((r)=>{
      const sourceKey=`${r?.operation_type||''}|${r?.source_site_relative_url||''}|${normalizeSpPath(r?.old_server_relative_url||'')}`;
      const targetKey=`${r?.target_site_relative_url||''}|${normalizeSpPath(r?.new_server_relative_url||'')}`;
      if(!existingSources.has(sourceKey)) existingSources.set(sourceKey,new Set());
      existingSources.get(sourceKey).add(targetKey);
    });
    let added=0;
    let duplicates=0;
    let conflicts=0;
    rows.forEach((r)=>{
      const oldPath=normalizeSpPath(r?.old_server_relative_url||'');
      const newPath=normalizeSpPath(r?.new_server_relative_url||'');
      const key=`${r?.operation_type||''}|${r?.source_site_relative_url||''}|${normalizeSpPath(r?.old_server_relative_url||'')}|${r?.target_site_relative_url||''}|${normalizeSpPath(r?.new_server_relative_url||'')}`;
      if(!oldPath||!newPath) return;
      if(seen.has(key)){ duplicates++; return; }
      const sourceKey=`${r?.operation_type||''}|${r?.source_site_relative_url||''}|${oldPath}`;
      const targetKey=`${r?.target_site_relative_url||''}|${newPath}`;
      if(!existingSources.has(sourceKey)) existingSources.set(sourceKey,new Set());
      const priorTargets=existingSources.get(sourceKey);
      if(Array.from(priorTargets).some((value)=>value!==targetKey)) conflicts++;
      seen.add(key);
      priorTargets.add(targetKey);
      state.migrationLog.push(r);
      added++;
    });
    state.migrationLog=state.migrationLog.slice(-5000);
    saveMigrationLog();
    renderMigrationPanel();
    setStatus(`Imported ${added} migration record(s), skipped ${duplicates} duplicate(s), detected ${conflicts} conflict(s).`);
  }catch(e){
    setStatus(`Migration import failed: ${err(e)}`);
  }
}
function rewriteFavoritePaths(oldPath,newPath,oldSite,newSite){
  const oldNorm=normalizeSpPath(oldPath), newNorm=normalizeSpPath(newPath);
  if(!oldNorm || !newNorm) return 0;
  let updated=0;
  state.favorites.forEach((f)=>{
    if(f.kind!=='sharepoint') return;
    const cur=normalizeSpPath(f.path||'');
    const favSite=String(f.site||'').trim();
    if(oldSite && favSite && favSite!==String(oldSite||'').trim()) return;
    if(cur===oldNorm){
      f.path=newNorm;
      if(newSite) f.site=newSite;
      updated++;
      return;
    }
    if(cur.startsWith(oldNorm.replace(/\/+$/,'') + '/')){
      f.path=newNorm.replace(/\/+$/,'') + cur.slice(oldNorm.length);
      if(newSite) f.site=newSite;
      updated++;
    }
  });
  if(updated) saveFavorites();
  return updated;
}
function recordMigration(operationType,itemType,oldPath,newPath,sourceSite,targetSite){
  const oldNorm=normalizeSpPath(oldPath), newNorm=normalizeSpPath(newPath);
  if(!oldNorm || !newNorm || oldNorm===newNorm) return;
  state.migrationLog.push({
    id:`mig-${Date.now()}-${Math.random().toString(36).slice(2,8)}`,
    timestamp:new Date().toISOString(),
    operation_type:operationType,
    item_type:itemType,
    source_site_relative_url:sourceSite||'',
    target_site_relative_url:targetSite||sourceSite||'',
    old_server_relative_url:oldNorm,
    new_server_relative_url:newNorm,
    old_web_url:buildWebUrlFromPath(oldNorm),
    new_web_url:buildWebUrlFromPath(newNorm),
    status:'completed',
  });
  state.migrationLog=state.migrationLog.slice(-5000);
  saveMigrationLog();
  const updated=rewriteFavoritePaths(oldNorm,newNorm,sourceSite,targetSite||sourceSite);
  renderMigrationPanel();
  if(updated) renderFavorites();
}
function renderFavorites(){ el.favoritesList.innerHTML=''; state.favorites.forEach((f,i)=>{ const row=document.createElement('div'); row.className='favorite'; row.innerHTML=`<div><strong>${f.label||f.path}</strong><small>${f.kind}${f.site?` | ${f.site}`:''}</small></div>`; const act=document.createElement('div'); const open=document.createElement('button'); open.textContent='Open'; open.onclick=async()=>{ const target=(f.kind==='sharepoint'&&f.path)?(resolveMigrationTarget(f.path,f.site)||{path:f.path,site:f.site||''}):{path:f.path,site:f.site||''}; if(f.kind==='sharepoint' && target.path!==f.path){ f.path=target.path; f.site=target.site||f.site||''; saveFavorites(); renderFavorites(); } const p=activePane(); p.kind=f.kind; p.site=target.site||f.site||''; p.path=target.path; if(p.kind==='sharepoint'){ await loadSitesForPane(p); await loadLibrariesForPane(p);} updatePaneControls(p.key); await loadPane(p.key,p.path); }; const del=document.createElement('button'); del.textContent='X'; del.onclick=()=>{ state.favorites.splice(i,1); saveFavorites(); renderFavorites(); }; act.appendChild(open); act.appendChild(del); row.appendChild(act); el.favoritesList.appendChild(row); }); }
function addFavorite(){ const p=activePane(); if(!p.path) return; state.favorites.unshift({label:(el.favoriteNameInput.value||'').trim(),kind:p.kind,path:p.path,site:p.site||''}); state.favorites=state.favorites.slice(0,40); saveFavorites(); renderFavorites(); el.favoriteNameInput.value=''; setStatus('Favorite saved.'); }

function loadLayouts(){ try{ state.layouts=JSON.parse(localStorage.getItem('smx_web_layouts')||'[]'); if(!Array.isArray(state.layouts)) state.layouts=[]; }catch{ state.layouts=[]; } }
function saveLayouts(){ localStorage.setItem('smx_web_layouts',JSON.stringify(state.layouts)); }
async function applyLayout(l){ state.language=l.language||'English'; state.translationEnabled=!!l.translationEnabled; el.langInput.value=state.language; el.toggleTranslateBtn.textContent=`Translate: ${state.translationEnabled?'On':'Off'}`; for(const key of ['left','right']){ const p=state[key], s=l[key]||{}; p.kind=s.kind||'local'; p.site=s.site||''; p.library=s.library||''; p.path=s.path||''; if(p.kind==='sharepoint'){ await loadSitesForPane(p); await loadLibrariesForPane(p); } updatePaneControls(key); await loadPane(key,p.path||(p.kind==='local'?'':p.library||'/')); } }
function renderLayouts(){ el.layoutsList.innerHTML=''; state.layouts.forEach((l,i)=>{ const row=document.createElement('div'); row.className='favorite'; row.innerHTML=`<div><strong>${l.name}</strong><small>${l.at||''}</small></div>`; const act=document.createElement('div'); const open=document.createElement('button'); open.textContent='Load'; open.onclick=async()=>{ await applyLayout(l); setStatus(`Loaded layout: ${l.name}`); }; const del=document.createElement('button'); del.textContent='X'; del.onclick=()=>{ state.layouts.splice(i,1); saveLayouts(); renderLayouts(); }; act.appendChild(open); act.appendChild(del); row.appendChild(act); el.layoutsList.appendChild(row); }); renderLayoutTabs(); }
function renderLayoutTabs(){
  if(!el.layoutTabs) return;
  el.layoutTabs.innerHTML='';
  state.layouts.slice(0,12).forEach((l)=>{
    const b=document.createElement('button');
    b.className='layout-tab';
    b.textContent=l.name||'Layout';
    b.onclick=async()=>{ await applyLayout(l); setStatus(`Loaded layout: ${l.name}`); };
    el.layoutTabs.appendChild(b);
  });
}
function saveCurrentLayout(){ state.layouts.unshift({name:(el.layoutNameInput.value||'').trim()||`Layout ${state.layouts.length+1}`,at:new Date().toISOString(),language:state.language,translationEnabled:state.translationEnabled,left:{kind:state.left.kind,site:state.left.site||'',library:state.left.library||'',path:state.left.path||''},right:{kind:state.right.kind,site:state.right.site||'',library:state.right.library||'',path:state.right.path||''}}); state.layouts=state.layouts.slice(0,30); saveLayouts(); renderLayouts(); el.layoutNameInput.value=''; setStatus('Layout saved.'); }
function loadRecent(){ try{ state.recent=JSON.parse(localStorage.getItem('smx_web_recent')||'[]'); if(!Array.isArray(state.recent)) state.recent=[]; }catch{ state.recent=[]; } }
function renderRecent(){ el.recentList.innerHTML=''; state.recent.forEach((r,i)=>{ const row=document.createElement('div'); row.className='favorite'; row.innerHTML=`<div><strong>${r.path}</strong><small>${r.kind}${r.site?` | ${r.site}`:''}</small></div>`; const act=document.createElement('div'); const open=document.createElement('button'); open.textContent='Open'; open.onclick=async()=>{ const p=activePane(); p.kind=r.kind; p.site=r.site||''; p.path=r.path; if(p.kind==='sharepoint'){ await loadSitesForPane(p); await loadLibrariesForPane(p);} updatePaneControls(p.key); await loadPane(p.key,p.path); }; const del=document.createElement('button'); del.textContent='X'; del.onclick=()=>{ state.recent.splice(i,1); localStorage.setItem('smx_web_recent',JSON.stringify(state.recent)); renderRecent(); }; act.appendChild(open); act.appendChild(del); row.appendChild(act); el.recentList.appendChild(row); }); }

function currentWorkspaceSnapshot(){ return { language:state.language, translationEnabled:state.translationEnabled, activePane:state.activePane||'left', left:{kind:state.left.kind,site:state.left.site||'',siteTitle:findSiteTitle(state.left.site,state.left.sites,state.left.siteTitle||''),library:state.left.library||'',path:state.left.path||'',filterText:state.left.filterText||''}, right:{kind:state.right.kind,site:state.right.site||'',siteTitle:findSiteTitle(state.right.site,state.right.sites,state.right.siteTitle||''),library:state.right.library||'',path:state.right.path||'',filterText:state.right.filterText||''} }; }
async function applyWorkspaceSnapshot(s){ if(!s) return; state.language=s.language||state.language||'English'; state.translationEnabled=!!s.translationEnabled; state.activePane=(s.activePane==='right'?'right':'left'); el.langInput.value=state.language; el.toggleTranslateBtn.textContent=`Translate: ${state.translationEnabled?'On':'Off'}`; for(const key of ['left','right']){ const pane=state[key], src=s[key]||{}; pane.kind=src.kind||'local'; pane.site=src.site||''; pane.siteTitle=src.siteTitle||pane.siteTitle||''; pane.library=src.library||''; pane.path=src.path||''; pane.filterText=src.filterText||''; if(pane.kind==='sharepoint'){ await loadSitesForPane(pane); await loadLibrariesForPane(pane); } updatePaneControls(key); await loadPane(key,pane.path||(pane.kind==='local'?'':pane.library||'/')); } }
function ensureSplitCompareSelection(){ return; }
function activeSessionSnapshot(){
  const runtime=state.splitRuntime[state.activeSessionId];
  if(state.splitViewEnabled && runtime) return splitRuntimeSnapshot(runtime);
  return currentWorkspaceSnapshot();
}
function loadSessions(){
  try{ state.sessions=JSON.parse(localStorage.getItem('smx_web_sessions')||'[]'); if(!Array.isArray(state.sessions)) state.sessions=[]; }catch{ state.sessions=[]; }
  if(!state.sessions.length){ state.sessions=[{id:`s-${Date.now()}`,name:'',snapshot:currentWorkspaceSnapshot()}]; }
  state.activeSessionId=localStorage.getItem('smx_web_active_session')||state.sessions[0].id;
  if(!state.sessions.find(s=>s.id===state.activeSessionId)) state.activeSessionId=state.sessions[0].id;
  state.splitViewEnabled=localStorage.getItem('smx_web_split_view')==='1';
  state.splitCompareSessionId='';
}
function persistSessions(){
  localStorage.setItem('smx_web_sessions',JSON.stringify(state.sessions));
  localStorage.setItem('smx_web_active_session',state.activeSessionId||'');
  localStorage.setItem('smx_web_split_view',state.splitViewEnabled?'1':'0');
}
function saveCurrentSessionSnapshot(){ const idx=state.sessions.findIndex(s=>s.id===state.activeSessionId); if(idx<0) return; state.sessions[idx].snapshot=activeSessionSnapshot(); persistSessions(); renderSessionTabs(); if(state.splitViewEnabled) renderSplitSessions(); }
async function activateSession(id){ saveCurrentSessionSnapshot(); const s=state.sessions.find(x=>x.id===id); if(!s) return; state.activeSessionId=id; delete state.splitRuntime[id]; renderSessionTabs(); await applyWorkspaceSnapshot(s.snapshot||{}); persistSessions(); await refreshSplitView(true); setStatus(`Session active: ${sessionLabelById(id)}`); }
function newSession(){ saveCurrentSessionSnapshot(); const s={id:`s-${Date.now()}`,name:'',snapshot:activeSessionSnapshot()}; state.sessions.unshift(s); state.activeSessionId=s.id; persistSessions(); renderSessionTabs(); renderSplitSessions(); setStatus(`Created ${sessionLabelById(s.id)}`); }
function duplicateSession(){ saveCurrentSessionSnapshot(); const src=state.sessions.find(s=>s.id===state.activeSessionId); if(!src) return; const cp={id:`s-${Date.now()}`,name:'',snapshot:JSON.parse(JSON.stringify(src.snapshot||activeSessionSnapshot()))}; state.sessions.unshift(cp); state.activeSessionId=cp.id; persistSessions(); renderSessionTabs(); renderSplitSessions(); setStatus(`Duplicated session: ${sessionLabelById(cp.id)}`); }
function renameSession(){ setStatus('Session labels are automatic from the current folder or SharePoint location.'); }
async function closeSession(){ return closeSessionById(state.activeSessionId); }
async function closeSessionById(sessionId){
  if(state.sessions.length<=1) return setStatus('At least one session is required.');
  const idx=state.sessions.findIndex((s)=>s.id===sessionId);
  if(idx<0){
    if(!state.sessions.length) return;
    state.activeSessionId=state.sessions[0].id;
    return closeSession();
  }
  const removed=state.sessions.splice(idx,1)[0];
  const removedLabel=sessionLabelFromSnapshot(removed.snapshot||{});
  delete state.splitRuntime[removed.id];
  if(state.activeSessionId===sessionId || !state.sessions.find((s)=>s.id===state.activeSessionId)){
    state.activeSessionId=state.sessions[0].id;
  }
  persistSessions();
  renderSessionTabs();
  renderSplitSessions();
  await activateSession(state.activeSessionId);
  setStatus(`Closed ${removedLabel}`);
}
function toggleSplitView(){ state.splitViewEnabled=!state.splitViewEnabled; persistSessions(); renderSplitSessions(); if(state.splitViewEnabled) refreshSplitView(true); setStatus(`Split view ${state.splitViewEnabled?'enabled':'disabled'}.`); }
async function changeSplitCompareSession(_id){ return; }
function renderSessionTabs(){ if(!el.sessionTabs) return; el.sessionTabs.innerHTML=''; state.sessions.forEach((s)=>{ const b=document.createElement('button'); b.className=`layout-tab${s.id===state.activeSessionId?' active':''}`; b.textContent=sessionLabelById(s.id); b.onclick=()=>activateSession(s.id); el.sessionTabs.appendChild(b); }); renderSplitSessionOptions(); }

function exportConfig(){
  const payload={
    exportedAt:new Date().toISOString(),
    language:state.language,
    translationEnabled:state.translationEnabled,
    favorites:state.favorites,
    migrationLog:state.migrationLog,
    relinkImports:state.relinkImports,
    relinkExports:state.relinkExports,
    aiRenameLog:state.aiRenameLog,
    layouts:state.layouts,
    recent:state.recent,
    sessions:state.sessions,
    activeSessionId:state.activeSessionId,
  };
  const blob=new Blob([JSON.stringify(payload,null,2)],{type:'application/json'});
  const a=document.createElement('a');
  a.href=URL.createObjectURL(blob);
  a.download=`smx-web-config-${Date.now()}.json`;
  a.click();
  URL.revokeObjectURL(a.href);
  setStatus('Config exported.');
}

async function importConfigFromFile(file){
  if(!file) return;
  try{
    const txt=await file.text();
    const data=JSON.parse(txt);
    state.language=(data.language||state.language||'English');
    state.translationEnabled=!!data.translationEnabled;
    state.favorites=Array.isArray(data.favorites)?data.favorites:[];
    state.migrationLog=Array.isArray(data.migrationLog)?data.migrationLog:[];
    state.relinkImports=Array.isArray(data.relinkImports)?data.relinkImports:[];
    state.relinkExports=Array.isArray(data.relinkExports)?data.relinkExports:[];
    state.aiRenameLog=Array.isArray(data.aiRenameLog)?data.aiRenameLog:[];
    state.layouts=Array.isArray(data.layouts)?data.layouts:[];
    state.recent=Array.isArray(data.recent)?data.recent:[];
    state.sessions=Array.isArray(data.sessions)?data.sessions:[];
    state.activeSessionId=data.activeSessionId||'';
    if(!state.sessions.length){
      state.sessions=[{id:`s-${Date.now()}`,name:'',snapshot:currentWorkspaceSnapshot()}];
      state.activeSessionId=state.sessions[0].id;
    }
    ensureSplitCompareSelection();
    saveFavorites(); saveMigrationLog(); saveRelinkState(); saveAiRenameLog(); saveLayouts(); localStorage.setItem('smx_web_recent',JSON.stringify(state.recent));
    persistSessions();
    el.langInput.value=state.language;
    el.toggleTranslateBtn.textContent=`Translate: ${state.translationEnabled?'On':'Off'}`;
    renderFavorites(); renderLayouts(); renderLayoutTabs(); renderRecent(); renderSessionTabs(); renderSplitSessions(); renderMigrationPanel(); renderRelinkImports(); renderRelinkExports(); renderAiRenameLogPanel(); renderAppView();
    const active = state.sessions.find(s=>s.id===state.activeSessionId) || state.sessions[0];
    await applyWorkspaceSnapshot(active.snapshot||currentWorkspaceSnapshot());
    await refreshSplitView(true);
    setStatus('Config imported.');
  }catch(e){ setStatus(`Import failed: ${err(e)}`); }
}

function wirePaneEvents(key){
  const p=state[key], ui=paneEls(key);
  ui.kind.onchange=async()=>{ state.activePane=key; await switchPaneKind(key,ui.kind.value); };
  ui.site.onchange=async()=>{ state.activePane=key; p.site=ui.site.value; p.library=''; p.path=normalizeSpPath(p.site||'/'); await loadLibrariesForPane(p); p.path=p.library||normalizeSpPath(p.site||'/'); updatePaneControls(key); await loadPane(key,p.path); };
  ui.library.onchange=async()=>{ state.activePane=key; p.library=ui.library.value; p.path=p.library; await loadPane(key,p.path); };
  if(ui.go) ui.go.onclick=async()=>{ state.activePane=key; await loadPane(key,ui.path.value.trim()); };
  ui.path.onkeydown=async(e)=>{ if(e.key==='Enter'){ state.activePane=key; await loadPane(key,ui.path.value.trim()); } };
  ui.path.onchange=async()=>{ state.activePane=key; await loadPane(key,ui.path.value.trim(), true); };
  ui.uploadBtn.onclick=()=>ui.uploadInput.click();
  ui.uploadInput.onchange=async()=>{ const f=ui.uploadInput.files&&ui.uploadInput.files[0]; if(!f) return; state.activePane=key; await uploadToPane(key,f); ui.uploadInput.value=''; };
  if(ui.filter){
    ui.filter.oninput=()=>{ p.filterText=ui.filter.value||''; renderPane(key); saveCurrentSessionSnapshot(); };
  }
}

function wireGlobalEvents(){
  if(el.splitViewToggleBtn) el.splitViewToggleBtn.onclick=()=>toggleSplitView();
  if(el.splitTransferModeBtn) el.splitTransferModeBtn.onclick=()=>toggleSplitTransferMode();
  if(el.splitCompareSessionSelect) el.splitCompareSessionSelect.onchange=()=>changeSplitCompareSession(el.splitCompareSessionSelect.value);
  if(el.appWorkspaceTabBtn) el.appWorkspaceTabBtn.onclick=()=>openAppView('workspace');
  if(el.appRelinkingTabBtn) el.appRelinkingTabBtn.onclick=()=>openAppView('relinking');
  if(el.openSettingsBtn) el.openSettingsBtn.onclick=()=>openSettingsModal();
  if(el.settingsCloseBtn) el.settingsCloseBtn.onclick=()=>closeSettingsModal();
  if(el.settingsApplyBtn) el.settingsApplyBtn.onclick=async()=>{ await applySettingsFromModal(); closeSettingsModal(); };
  if(el.aiProviderSaveBtn) el.aiProviderSaveBtn.onclick=saveAiApiKeyFromPortal;
  if(el.aiProviderSelect) el.aiProviderSelect.onchange=()=>renderAiModelOptions(el.aiProviderSelect.value, '');
  if(el.openAiApiKeyClearBtn) el.openAiApiKeyClearBtn.onclick=()=>clearAiApiKeyFromPortal('openai_api_key');
  if(el.claudeApiKeyClearBtn) el.claudeApiKeyClearBtn.onclick=()=>clearAiApiKeyFromPortal('anthropic_api_key');
  if(el.geminiApiKeyClearBtn) el.geminiApiKeyClearBtn.onclick=()=>clearAiApiKeyFromPortal('gemini_api_key');
  if(el.settingsModal) el.settingsModal.onclick=(evt)=>{ if(evt.target===el.settingsModal) closeSettingsModal(); };
  if(el.newFolderCancelBtn) el.newFolderCancelBtn.onclick=()=>closeNewFolderModal();
  if(el.newFolderCreateBtn) el.newFolderCreateBtn.onclick=()=>createFolder();
  if(el.newFolderModal) el.newFolderModal.onclick=(evt)=>{ if(evt.target===el.newFolderModal) closeNewFolderModal(); };
  if(el.newFolderNameInput) el.newFolderNameInput.onkeydown=(evt)=>{ if(evt.key==='Enter'){ evt.preventDefault(); createFolder(); } };
  el.copyBtn.onclick=()=>setClipboard('copy'); el.cutBtn.onclick=()=>setClipboard('cut'); el.pasteBtn.onclick=pasteClipboard;
  el.renameBtn.onclick=renameSelected; if(el.aiRenameBtn) el.aiRenameBtn.onclick=aiRenameAndOrganize; el.deleteBtn.onclick=deleteSelected; el.mkdirBtn.onclick=openNewFolderModal; el.openBtn.onclick=()=>openSelected(false); el.revealBtn.onclick=()=>openSelected(true);
  el.toggleTranslateBtn.onclick=toggleTranslation; el.renameTranslatedBtn.onclick=applyTranslationRename; el.undoRenameBtn.onclick=undoRename;
  el.previewBtn.onclick=previewSelected; el.extractBtn.onclick=extractText; el.summaryBtn.onclick=summarizeSelected; el.askBtn.onclick=askQuestion;
  el.saveTagsBtn.onclick=saveTags; el.searchTagsBtn.onclick=searchTags; el.propertiesBtn.onclick=loadProperties;
  if(el.permissionsBtn) el.permissionsBtn.onclick=loadPermissionsProbe;
  if(el.metadataLoadBtn) el.metadataLoadBtn.onclick=spLoadMetadataFields;
  if(el.metadataApplyBtn) el.metadataApplyBtn.onclick=spApplyMetadata;
  if(el.metadataInput) el.metadataInput.oninput=refreshMetadataValidationAndDiff;
  if(el.searchRunBtn) el.searchRunBtn.onclick=runGlobalSearch;
  if(el.searchFilterSaveBtn) el.searchFilterSaveBtn.onclick=saveCurrentSearchFilter;
  if(el.searchFilterDeleteBtn) el.searchFilterDeleteBtn.onclick=deleteSelectedSearchFilter;
  if(el.searchFilterSelect) el.searchFilterSelect.onchange=applySelectedSearchFilter;
  if(el.spSaveAuthBtn) el.spSaveAuthBtn.onclick=saveSpAuthFromPortal;
  if(el.spRefreshAuthBtn) el.spRefreshAuthBtn.onclick=refreshSpAuthPanel;
  if(el.spEmbeddedSigninBtn) el.spEmbeddedSigninBtn.onclick=startEmbeddedSharePointSignIn;
  if(el.uiVersionSelect) el.uiVersionSelect.onchange=()=>setUiVersion(el.uiVersionSelect.value);
  if(el.bulkDryRunBtn) el.bulkDryRunBtn.onclick=dryRunBulkOperation;
  if(el.bulkQueueBtn) el.bulkQueueBtn.onclick=queueBulkOperationJob;
  if(el.jobsPauseBtn) el.jobsPauseBtn.onclick=pauseActiveJob;
  if(el.jobsResumeBtn) el.jobsResumeBtn.onclick=resumeActiveJob;
  if(el.jobsCancelBtn) el.jobsCancelBtn.onclick=cancelActiveJob;
  if(el.jobsRetryFailedBtn) el.jobsRetryFailedBtn.onclick=retryFailedItems;
  if(el.jobsExportBtn) el.jobsExportBtn.onclick=exportJobsHistory;
  if(el.jobsClearFinishedBtn) el.jobsClearFinishedBtn.onclick=clearFinishedJobs;
  if(el.desktopNotifyBtn) el.desktopNotifyBtn.onclick=toggleDesktopNotifications;
  if(el.clearNotificationsBtn) el.clearNotificationsBtn.onclick=clearNotifications;
  if(el.saveShortcutsBtn) el.saveShortcutsBtn.onclick=saveShortcutsFromUi;
  if(el.resetShortcutsBtn) el.resetShortcutsBtn.onclick=resetShortcuts;
  if(el.addGlossaryBtn) el.addGlossaryBtn.onclick=addGlossaryEntry;
  if(el.addRuleBtn) el.addRuleBtn.onclick=addAutomationRule;
  if(el.applyRulesBtn) el.applyRulesBtn.onclick=applyAutomationRulesToSelection;
  if(el.pdfJumpBtn) el.pdfJumpBtn.onclick=()=>jumpToPdfPage(Number(el.pdfPageInput?.value||1));
  if(el.pdfBookmarkAddBtn) el.pdfBookmarkAddBtn.onclick=addPdfBookmark;
  el.checkoutBtn.onclick=spCheckOut; el.checkinBtn.onclick=spCheckIn; el.undoCheckoutBtn.onclick=spUndoCheckout; el.loadVersionsBtn.onclick=spLoadVersions; el.downloadVersionBtn.onclick=spDownloadVersion; el.restoreVersionBtn.onclick=spRestoreVersion;
  el.addFavoriteBtn.onclick=addFavorite; el.saveFavoriteBtn.onclick=addFavorite; el.saveLayoutBtn.onclick=saveCurrentLayout;
  if(el.newSessionBtn) el.newSessionBtn.onclick=newSession;
  if(el.duplicateSessionBtn) el.duplicateSessionBtn.onclick=duplicateSession;
  if(el.renameSessionBtn) el.renameSessionBtn.onclick=renameSession;
  if(el.closeSessionBtn) el.closeSessionBtn.onclick=closeSession;
  if(el.migrationResolveBtn) el.migrationResolveBtn.onclick=resolveMigrationInput;
  if(el.migrationResolveInput) el.migrationResolveInput.onkeydown=(e)=>{ if(e.key==='Enter') resolveMigrationInput(); };
  if(el.migrationFilterInput) el.migrationFilterInput.oninput=renderMigrationPanel;
  if(el.aiRenameFilterInput) el.aiRenameFilterInput.oninput=renderAiRenameLogPanel;
  if(el.migrationImportBtn) el.migrationImportBtn.onclick=()=>el.migrationImportInput?.click();
  if(el.migrationImportInput) el.migrationImportInput.onchange=async()=>{ const f=el.migrationImportInput.files&&el.migrationImportInput.files[0]; await importMigrationLogFile(f); el.migrationImportInput.value=''; };
  if(el.migrationClearBtn) el.migrationClearBtn.onclick=clearMigrationLog;
  if(el.relinkImportHtmlBtn) el.relinkImportHtmlBtn.onclick=()=>el.relinkImportHtmlInput?.click();
  if(el.relinkImportHtmlInput) el.relinkImportHtmlInput.onchange=async()=>{ const f=el.relinkImportHtmlInput.files&&el.relinkImportHtmlInput.files[0]; await importRelinkBookmarkFile(f); el.relinkImportHtmlInput.value=''; };
  if(el.relinkClearImportsBtn) el.relinkClearImportsBtn.onclick=clearRelinkImports;
  if(el.relinkClearExportsBtn) el.relinkClearExportsBtn.onclick=clearRelinkExports;
  if(el.migrationCopyResolvedBtn) el.migrationCopyResolvedBtn.onclick=copyResolvedMigrationValue;
  if(el.migrationOpenResolvedBtn) el.migrationOpenResolvedBtn.onclick=openResolvedMigrationValue;
  if(el.migrationExportJsonBtn) el.migrationExportJsonBtn.onclick=exportMigrationLogJson;
  if(el.migrationExportCsvBtn) el.migrationExportCsvBtn.onclick=exportMigrationLogCsv;
  if(el.aiRenameExportJsonBtn) el.aiRenameExportJsonBtn.onclick=exportAiRenameLogJson;
  if(el.aiRenameExportCsvBtn) el.aiRenameExportCsvBtn.onclick=exportAiRenameLogCsv;
  el.exportConfigBtn.onclick=exportConfig;
  el.importConfigBtn.onclick=()=>el.importConfigInput.click();
  el.importConfigInput.onchange=async()=>{ const f=el.importConfigInput.files&&el.importConfigInput.files[0]; await importConfigFromFile(f); el.importConfigInput.value=''; };
  document.addEventListener('keydown',handleGlobalShortcutKeydown);
  document.addEventListener('keydown',(e)=>{
    if(e.key==='Escape' && isSettingsModalOpen()){
      e.preventDefault();
      closeSettingsModal();
      return;
    }
    if(e.key==='Escape' && isNewFolderModalOpen()){
      e.preventDefault();
      closeNewFolderModal();
    }
  });
}

async function init(){
  wireGlobalEvents(); wirePaneEvents('left'); wirePaneEvents('right'); clearPreview();
  loadUiVersion();
  if(el.spEmbeddedSigninBtn && (!window.smxDesktop || !window.smxDesktop.isDesktop)){
    el.spEmbeddedSigninBtn.disabled=true;
    el.spEmbeddedSigninBtn.title='Available only in Electron WebShell';
  }
  await refreshSpAuthPanel();
  refreshMetadataValidationAndDiff();
  loadNotificationPrefs(); renderNotifications();
  loadShortcuts(); renderShortcuts();
  loadGlossary(); renderGlossary();
  loadTranslationLocalCache();
  loadPdfBookmarks(); renderPdfBookmarks();
  loadAutomationRules(); renderAutomationRules();
  loadSearchFilters(); renderSearchFilters(); renderSearchResults();
  loadJobsState(); renderJobs();
  loadFavorites(); loadMigrationLog(); loadRelinkState(); loadAppView(); loadAiRenameLog(); renderFavorites(); renderMigrationPanel(); renderRelinkImports(); renderRelinkExports(); renderAiRenameLogPanel(); renderAppView(); loadLayouts(); renderLayouts(); loadRecent(); renderRecent();
  loadSessions(); renderSessionTabs();
  const active = state.sessions.find(s=>s.id===state.activeSessionId) || state.sessions[0];
  await applyWorkspaceSnapshot(active.snapshot || currentWorkspaceSnapshot());
  renderSplitSessions();
  await refreshSplitView(true);
  persistSessions();
  runJobLoop();
}

init().catch(e=>setStatus(`Init failed: ${err(e)}`));
