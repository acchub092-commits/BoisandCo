/* Hope AppMobile — Chiffrage terrain (PWA). Vanilla JS, routage par hash, aucune dépendance. */
(function () {
  'use strict';

  const API_BASE = '/api/v1';
  const STORAGE_TOKEN = 'hope_chiffrage_token';
  const STORAGE_USER = 'hope_chiffrage_user';

  const app = document.getElementById('app');

  // ---------------------------------------------------------------------
  // Session
  // ---------------------------------------------------------------------
  function getToken() {
    try { return localStorage.getItem(STORAGE_TOKEN); } catch (e) { return null; }
  }
  function getUser() {
    try { return JSON.parse(localStorage.getItem(STORAGE_USER) || 'null'); } catch (e) { return null; }
  }
  function setSession(token, user) {
    try {
      localStorage.setItem(STORAGE_TOKEN, token);
      localStorage.setItem(STORAGE_USER, JSON.stringify(user));
    } catch (e) { /* stockage indisponible (navigation privée) — session non persistée */ }
  }
  function clearSession() {
    try {
      localStorage.removeItem(STORAGE_TOKEN);
      localStorage.removeItem(STORAGE_USER);
    } catch (e) { /* ignore */ }
  }

  // ---------------------------------------------------------------------
  // Appels API
  // ---------------------------------------------------------------------
  async function api(path, options) {
    options = options || {};
    const headers = options.headers || {};
    const token = getToken();
    if (token) headers['Authorization'] = 'Token ' + token;
    if (options.json !== undefined) {
      headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(options.json);
    }
    let response;
    try {
      response = await fetch(API_BASE + path, { ...options, headers });
    } catch (e) {
      throw new Error('OFFLINE');
    }
    if (response.status === 401) {
      clearSession();
      location.hash = '#/login';
      throw new Error('Session expirée — reconnectez-vous.');
    }
    if (response.status === 204) return null;
    let data = null;
    try { data = await response.json(); } catch (e) { /* pas de corps JSON */ }
    if (!response.ok) {
      const msg = (data && (data.detail || firstError(data))) || `Erreur (${response.status})`;
      throw new Error(msg);
    }
    return data;
  }

  function firstError(data) {
    for (const key in data) {
      const v = data[key];
      if (Array.isArray(v) && v.length) return v[0];
      if (typeof v === 'string') return v;
    }
    return null;
  }

  // ---------------------------------------------------------------------
  // Aides UI
  // ---------------------------------------------------------------------
  function escapeHtml(value) {
    if (value === null || value === undefined) return '';
    return String(value)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
  function toast(message, kind) {
    const el = document.createElement('div');
    el.className = 'toast ' + (kind || 'info');
    el.textContent = message;
    document.body.appendChild(el);
    requestAnimationFrame(() => el.classList.add('show'));
    setTimeout(() => { el.classList.remove('show'); setTimeout(() => el.remove(), 300); }, 3500);
  }
  function formatDate(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    return d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' });
  }
  function formatDateTime(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    return d.toLocaleDateString('fr-FR') + ' ' + d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
  }
  function formatMontant(v) {
    if (v === null || v === undefined) return null;
    const n = parseFloat(v);
    return n.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' MAD';
  }
  // ---------------------------------------------------------------------
  // Icônes (SVG ligne, cohérentes avec l'interface desktop — jamais d'emoji)
  // ---------------------------------------------------------------------
  const ICONS = {
    back: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/>',
    logout: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/>',
    camera: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 17a4 4 0 100-8 4 4 0 000 8z"/>',
    paperclip: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"/>',
    bell: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"/>',
    plus: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>',
    warning: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"/>',
    close: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>',
    wifiOff: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M18.364 5.636a9 9 0 010 12.728m-3.536-3.536a4 4 0 010-5.656m-6.364 0a9 9 0 00-1.5 10.5M3 3l18 18M9.88 9.88a4 4 0 004.24 4.24"/>',
    inbox: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12h4l2 3h6l2-3h4M5 12l1.5-6.5A2 2 0 018.44 4h7.12a2 2 0 011.94 1.5L19 12m-14 0v6a2 2 0 002 2h10a2 2 0 002-2v-6"/>',
    document: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>',
    search: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-4.35-4.35M17 10a7 7 0 11-14 0 7 7 0 0114 0z"/>',
    table: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 10h18M3 14h18M3 6h18v12H3V6z"/>',
    grid: '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 5h6v6H4V5zm10 0h6v6h-6V5zM4 15h6v6H4v-6zm10 0h6v6h-6v-6z"/>',
  };
  function icon(name, cls) {
    return `<svg class="icon-svg${cls ? ' ' + cls : ''}" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">${ICONS[name]}</svg>`;
  }

  function fileKind(name) {
    const ext = (name || '').split('.').pop().toLowerCase();
    if (ext === 'pdf') return { ext, cls: 'file-pdf' };
    if (['xls', 'xlsx', 'csv'].includes(ext)) return { ext, cls: 'file-xls' };
    if (['doc', 'docx'].includes(ext)) return { ext, cls: 'file-doc' };
    return { ext: ext || 'fichier', cls: 'file-generic' };
  }
  function isImage(fileOrName) {
    if (fileOrName instanceof File) return fileOrName.type.startsWith('image/');
    const ext = (fileOrName || '').split('.').pop().toLowerCase();
    return ['jpg', 'jpeg', 'png', 'gif', 'webp', 'heic', 'heif', 'bmp'].includes(ext);
  }
  const STATUT_COLORS = {
    amber: '#d97706', blue: '#2563eb', red: '#dc2626', orange: '#ea580c',
    indigo: '#4f46e5', purple: '#7c3aed', foret: '#4f7d14', ardoise: '#64748b',
  };

  // ---------------------------------------------------------------------
  // Routeur
  // ---------------------------------------------------------------------
  const routes = [
    { pattern: /^#\/login$/, handler: viewLogin },
    { pattern: /^#\/nouvelle$/, handler: viewNouvelle },
    { pattern: /^#\/detail\/(\d+)$/, handler: viewDetail },
    { pattern: /^#\/notifications$/, handler: viewNotifications },
    { pattern: /^#\/?$/, handler: viewListe },
  ];

  async function render() {
    const hash = location.hash || '#/';
    const user = getUser();
    if (!getToken() && hash !== '#/login') {
      location.hash = '#/login';
      return;
    }
    if (getToken() && hash === '#/login') {
      location.hash = '#/';
      return;
    }
    for (const route of routes) {
      const match = hash.match(route.pattern);
      if (match) {
        try {
          await route.handler(...match.slice(1));
        } catch (e) {
          if (e.message === 'OFFLINE') {
            app.innerHTML = offlineTemplate();
          } else {
            toast(e.message, 'error');
          }
        }
        return;
      }
    }
    location.hash = '#/';
  }

  function offlineTemplate() {
    return `
      <div class="topbar"><span>Hope AppMobile</span></div>
      <div class="empty-state">
        <p>${icon('wifiOff')} Pas de connexion réseau.</p>
        <p class="muted">Vérifiez votre connexion puis réessayez.</p>
        <button class="btn-primary" onclick="location.reload()">Réessayer</button>
      </div>`;
  }

  window.addEventListener('hashchange', render);
  window.addEventListener('DOMContentLoaded', render);

  // ---------------------------------------------------------------------
  // Écran : connexion
  // ---------------------------------------------------------------------
  function viewLogin() {
    const year = new Date().getFullYear();
    app.innerHTML = `
      <div class="login-screen">
        <div class="login-brand">
          <img src="/static/chiffrage_mobile/logo-new.png" class="login-wordmark" alt="Bois&amp;Co">
          <p class="login-hope-label">Hope AppMobile</p>
        </div>

        <div class="login-card">
          <div class="login-card-head">
            <h1>Connexion</h1>
            <p>Accédez à votre espace de gestion</p>
          </div>
          <form id="login-form" class="form login-card-body">
            <label>Identifiant<input type="text" name="username" autocomplete="username" required></label>
            <label>Mot de passe<input type="password" name="password" autocomplete="current-password" required></label>
            <button type="submit" class="btn-primary login-submit">
              Se connecter
              <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"/></svg>
            </button>
            <p id="login-error" class="field-error" hidden></p>
          </form>
        </div>

        <p class="login-footer">Hope AppMobile · Bois&amp;Co © ${year}</p>
      </div>`;
    const form = document.getElementById('login-form');
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const fd = new FormData(form);
      const errorEl = document.getElementById('login-error');
      errorEl.hidden = true;
      const btn = form.querySelector('button');
      btn.disabled = true;
      btn.textContent = 'Connexion…';
      try {
        const data = await api('/auth/login/', {
          method: 'POST',
          json: { username: fd.get('username'), password: fd.get('password') },
        });
        setSession(data.token, data.user);
        location.hash = '#/';
      } catch (err) {
        errorEl.textContent = err.message;
        errorEl.hidden = false;
      } finally {
        btn.disabled = false;
        btn.innerHTML = 'Se connecter <svg class="icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"/></svg>';
      }
    });
  }

  // ---------------------------------------------------------------------
  // Écran : liste des demandes
  // ---------------------------------------------------------------------
  function skeletonList(n) {
    return `<div class="skeleton-list">` + Array.from({ length: n || 4 }).map(() => '<div class="skeleton-card"></div>').join('') + `</div>`;
  }

  function canCreateDemande(user) {
    return !!user && (user.role === 'COMMERCIAL' || user.role === 'MANAGER');
  }

  function getListViewMode() {
    try { return localStorage.getItem('hope_chiffrage_view_mode') || 'cards'; } catch (e) { return 'cards'; }
  }
  function setListViewMode(mode) {
    try { localStorage.setItem('hope_chiffrage_view_mode', mode); } catch (e) { /* ignore */ }
  }

  let listSearchTimer = null;

  async function viewListe() {
    const user = getUser();
    const showFab = canCreateDemande(user);
    app.innerHTML = topbar(user) + `
      <div class="screen-body">
        <div class="list-toolbar">
          <div class="search-box">
            ${icon('search')}
            <input type="search" id="list-search" placeholder="Référence ou client…">
          </div>
          <button type="button" class="view-toggle-btn" id="view-toggle-btn" title="Changer d'affichage"></button>
        </div>
        <div id="liste-results">${skeletonList()}</div>
      </div>` + (showFab ? fab() : '');
    wireTopbar();
    if (showFab) wireFab();

    const toggleBtn = document.getElementById('view-toggle-btn');
    const syncToggleIcon = () => {
      toggleBtn.innerHTML = getListViewMode() === 'cards' ? icon('table') : icon('grid');
    };
    syncToggleIcon();
    toggleBtn.addEventListener('click', () => {
      setListViewMode(getListViewMode() === 'cards' ? 'table' : 'cards');
      syncToggleIcon();
      loadListResults(document.getElementById('list-search').value.trim());
    });

    const searchInput = document.getElementById('list-search');
    searchInput.addEventListener('input', () => {
      clearTimeout(listSearchTimer);
      listSearchTimer = setTimeout(() => loadListResults(searchInput.value.trim()), 350);
    });

    await loadListResults('');
  }

  async function loadListResults(query) {
    const user = getUser();
    const showFab = canCreateDemande(user);
    const container = document.getElementById('liste-results');
    if (!container) return;
    container.innerHTML = skeletonList();

    let data;
    try {
      data = await api('/chiffrage/demandes/' + (query ? '?q=' + encodeURIComponent(query) : ''));
    } catch (err) {
      container.innerHTML = `<p class="field-error">${escapeHtml(err.message)}</p>`;
      return;
    }
    const items = data.results || data;
    const banner = notifBannerTemplate();

    if (!items.length) {
      container.innerHTML = banner + (query
        ? `<div class="empty-state">${icon('inbox', 'icon-xl')}<p>Aucun résultat pour « ${escapeHtml(query)} ».</p></div>`
        : showFab
          ? `<div class="empty-state">${icon('inbox', 'icon-xl')}<p>Aucune demande pour l'instant.</p><p class="muted">Touchez « Nouvelle demande » pour en créer une.</p></div>`
          : `<div class="empty-state">${icon('inbox', 'icon-xl')}<p>Aucune demande pour l'instant.</p></div>`);
      wireNotifBanner();
      return;
    }

    items.sort((a, b) => actionScore(b) - actionScore(a));
    container.innerHTML = banner + (getListViewMode() === 'table' ? tableTemplate(items) : `<div class="card-list">${items.map(cardTemplate).join('')}</div>`);
    wireNotifBanner();
    container.querySelectorAll('[data-goto]').forEach((el) => {
      el.addEventListener('click', () => { location.hash = '#/detail/' + el.dataset.goto; });
    });
  }

  function actionScore(d) {
    return (d.peut_valider_dc || d.peut_valider_dg || d.peut_valider_rm || d.peut_traiter_methodes) ? 1 : 0;
  }

  function tableTemplate(items) {
    const showCommercial = items.some((d) => d.commercial);
    return `
      <div class="table-scroll">
        <table class="demandes-table">
          <thead>
            <tr>
              <th>Demande</th>
              <th>Client</th>
              <th>Statut</th>
              ${showCommercial ? '<th>Commercial</th>' : ''}
              <th>Délai</th>
            </tr>
          </thead>
          <tbody>
            ${items.map((d) => {
              const color = STATUT_COLORS[d.statut_color] || '#64748b';
              return `
                <tr data-goto="${d.id}" class="${actionScore(d) ? 'row-action' : ''}">
                  <td><span class="ref">${escapeHtml(d.reference)}</span></td>
                  <td>${escapeHtml(d.client_nom)}</td>
                  <td><span class="badge" style="background:${color}1a;color:${color}">${escapeHtml(d.statut_display)}</span></td>
                  ${showCommercial ? `<td>${d.commercial ? escapeHtml(d.commercial.full_name) : '—'}</td>` : ''}
                  <td class="${d.is_retard ? 'cell-retard' : ''}">${formatDate(d.delai_souhaite)}</td>
                </tr>`;
            }).join('')}
          </tbody>
        </table>
      </div>`;
  }

  function notifBannerTemplate() {
    const dismissed = (() => { try { return localStorage.getItem('hope_chiffrage_notif_dismissed') === '1'; } catch (e) { return false; } })();
    const supported = 'Notification' in window && 'serviceWorker' in navigator && 'PushManager' in window;
    if (!supported || dismissed || Notification.permission !== 'default') {
      if (supported && Notification.permission === 'granted') subscribeToPush();
      return '';
    }
    return `
      <div class="notif-banner" id="notif-banner">
        ${icon('bell', 'icon-lg')}
        <p><strong>Activer les notifications</strong>Soyez alerté instantanément dès qu'une demande attend votre action.</p>
        <button type="button" class="btn-primary" id="notif-enable-btn" style="padding:9px 14px;font-size:0.85rem;">Activer</button>
      </div>`;
  }

  function wireNotifBanner() {
    const btn = document.getElementById('notif-enable-btn');
    if (!btn) return;
    btn.addEventListener('click', async () => {
      await subscribeToPush();
      try { localStorage.setItem('hope_chiffrage_notif_dismissed', '1'); } catch (e) { /* ignore */ }
      const banner = document.getElementById('notif-banner');
      if (banner) banner.remove();
    });
  }

  function cardTemplate(d) {
    const color = STATUT_COLORS[d.statut_color] || '#64748b';
    const montant = formatMontant(d.montant_ht);
    const actionRequise = actionScore(d) === 1;
    return `
      <div class="demande-card ${actionRequise ? 'demande-card-action' : ''}" data-goto="${d.id}">
        <div class="demande-card-top">
          <span class="ref">${escapeHtml(d.reference)}</span>
        </div>
        <p class="client">${escapeHtml(d.client_nom)}</p>
        ${d.commercial ? `<p class="muted" style="margin:-6px 0 8px;font-size:0.78rem;">Soumis par ${escapeHtml(d.commercial.full_name)}</p>` : ''}
        <div class="demande-card-bottom">
          <span class="badge" style="background:${color}1a;color:${color}">${escapeHtml(d.statut_display)}</span>
          ${actionRequise ? `<span class="chip chip-action">${icon('warning', 'icon-xs')} Action requise</span>` : ''}
          ${d.is_retard ? '<span class="chip chip-red">En retard</span>' : ''}
          ${montant ? `<span class="chip chip-green">${montant}</span>` : ''}
        </div>
        <p class="muted" style="font-size:0.74rem;margin:6px 0 0;">${formatDate(d.created_at)}</p>
      </div>`;
  }

  // ---------------------------------------------------------------------
  // Écran : nouvelle demande
  // ---------------------------------------------------------------------
  let selectedPhotos = [];

  function viewNouvelle() {
    selectedPhotos = [];
    app.innerHTML = topbar(getUser(), true) + `
      <div class="screen-body">
        <h2>Nouvelle demande de chiffrage</h2>
        <form id="create-form" class="form">
          <label>Nom du client *<input type="text" name="client_nom" required></label>
          <label>Référence affaire<input type="text" name="client_ref_affaire"></label>
          <label>Description commerciale *<textarea name="description" rows="3" required></textarea></label>
          <label>Délai souhaité<input type="date" name="delai_souhaite"></label>
          <label>Urgence
            <select name="urgence">
              <option value="STANDARD">Standard</option>
              <option value="URGENT">Urgent</option>
              <option value="CRITIQUE">Critique</option>
            </select>
          </label>
          <label>Finitions souhaitées<textarea name="finitions" rows="2"></textarea></label>
          <label>Kits / références produits<textarea name="kits_references" rows="2"></textarea></label>
          <label>Quantités estimées<textarea name="quantites_estimees" rows="2"></textarea></label>
          <label>Contraintes techniques<textarea name="contraintes_techniques" rows="2"></textarea></label>
          <label>Commentaires libres<textarea name="commentaires" rows="2"></textarea></label>
          <label>Lien de téléchargement (plans, photos existantes…)<input type="url" name="lien_telechargement" placeholder="https://…"></label>

          <div class="photo-picker">
            <label class="form-label" style="font-size:0.84rem;font-weight:600;color:var(--marine-soft);">Pièces jointes (photos, PDF, Excel…)</label>
            <div class="attach-buttons">
              <label class="btn-secondary photo-trigger">
                ${icon('camera')} Prendre une photo
                <input type="file" id="camera-input" accept="image/*" capture="environment" hidden>
              </label>
              <label class="btn-secondary photo-trigger">
                ${icon('paperclip')} Joindre un fichier
                <input type="file" id="file-input" accept="image/*,application/pdf,.xls,.xlsx,.doc,.docx,.csv" multiple hidden>
              </label>
            </div>
            <div id="photo-preview" class="photo-preview"></div>
          </div>

          <button type="submit" class="btn-primary">Soumettre la demande</button>
          <p id="create-error" class="field-error" hidden></p>
        </form>
      </div>`;
    wireTopbar();

    const preview = document.getElementById('photo-preview');
    const onFilesPicked = (input) => {
      selectedPhotos = selectedPhotos.concat(Array.from(input.files));
      input.value = '';
      renderPhotoPreview(preview);
    };
    document.getElementById('camera-input').addEventListener('change', (e) => onFilesPicked(e.target));
    document.getElementById('file-input').addEventListener('change', (e) => onFilesPicked(e.target));

    const form = document.getElementById('create-form');
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const errorEl = document.getElementById('create-error');
      errorEl.hidden = true;
      const fd = new FormData(form);
      const payload = {
        client_nom: fd.get('client_nom'),
        client_ref_affaire: fd.get('client_ref_affaire'),
        description: fd.get('description'),
        delai_souhaite: fd.get('delai_souhaite') || null,
        urgence: fd.get('urgence'),
        finitions: fd.get('finitions'),
        kits_references: fd.get('kits_references'),
        quantites_estimees: fd.get('quantites_estimees'),
        contraintes_techniques: fd.get('contraintes_techniques'),
        commentaires: fd.get('commentaires'),
        lien_telechargement: fd.get('lien_telechargement'),
      };
      const btn = form.querySelector('button[type="submit"]');
      btn.disabled = true;
      btn.textContent = 'Envoi…';
      try {
        const demande = await api('/chiffrage/demandes/', { method: 'POST', json: payload });
        if (selectedPhotos.length) {
          const photoFd = new FormData();
          selectedPhotos.forEach((f) => photoFd.append('fichiers', f));
          await api(`/chiffrage/demandes/${demande.id}/photos/`, { method: 'POST', body: photoFd });
        }
        toast('Demande ' + demande.reference + ' envoyée.', 'success');
        location.hash = '#/detail/' + demande.id;
      } catch (err) {
        errorEl.textContent = err.message;
        errorEl.hidden = false;
        btn.disabled = false;
        btn.textContent = 'Soumettre la demande';
      }
    });
  }

  function renderPhotoPreview(container) {
    container.innerHTML = selectedPhotos.map((file, idx) => {
      if (isImage(file)) {
        return `
          <div class="photo-thumb" data-idx="${idx}">
            <img src="${URL.createObjectURL(file)}" alt="">
            <button type="button" class="photo-remove" data-remove="${idx}">${icon('close')}</button>
          </div>`;
      }
      const kind = fileKind(file.name);
      return `
        <div class="file-chip ${kind.cls}" data-idx="${idx}" style="position:relative;">
          <span class="ext-icon">${icon('document')}</span>
          <span class="name">${escapeHtml(file.name)}</span>
          <button type="button" class="photo-remove" data-remove="${idx}">${icon('close')}</button>
        </div>`;
    }).join('');
    container.querySelectorAll('[data-remove]').forEach((btn) => {
      btn.addEventListener('click', () => {
        selectedPhotos.splice(parseInt(btn.dataset.remove, 10), 1);
        renderPhotoPreview(container);
      });
    });
  }

  // ---------------------------------------------------------------------
  // Écran : notifications
  // ---------------------------------------------------------------------
  async function viewNotifications() {
    app.innerHTML = topbar(getUser(), true) + `
      <div class="screen-body">
        <div class="list-toolbar">
          <h2 style="margin:0;flex:1;">Notifications</h2>
          <button type="button" class="btn-secondary" id="mark-all-read-btn" style="font-size:0.78rem;padding:8px 12px;">Tout marquer comme lu</button>
        </div>
        <div id="notif-results">${skeletonList(5)}</div>
      </div>`;
    wireTopbar();

    document.getElementById('mark-all-read-btn').addEventListener('click', async () => {
      try {
        await api('/notifications/read-all/', { method: 'POST' });
        refreshBellBadge();
        loadNotificationResults();
      } catch (err) {
        toast(err.message, 'error');
      }
    });

    await loadNotificationResults();
  }

  async function loadNotificationResults() {
    const container = document.getElementById('notif-results');
    if (!container) return;
    let data;
    try {
      data = await api('/notifications/');
    } catch (err) {
      container.innerHTML = `<p class="field-error">${escapeHtml(err.message)}</p>`;
      return;
    }
    const items = data.results || data;
    if (!items.length) {
      container.innerHTML = `<div class="empty-state">${icon('bell', 'icon-xl')}<p>Aucune notification.</p></div>`;
      return;
    }
    container.innerHTML = `<div class="notif-list">` + items.map(notificationItemTemplate).join('') + `</div>`;
    container.querySelectorAll('[data-notif-id]').forEach((el) => {
      el.addEventListener('click', async () => {
        const notifId = el.dataset.notifId;
        const mobileUrl = el.dataset.url;
        try { await api(`/notifications/${notifId}/read/`, { method: 'POST' }); } catch (e) { /* non bloquant */ }
        const hashIndex = mobileUrl.indexOf('#');
        location.hash = hashIndex >= 0 ? mobileUrl.slice(hashIndex) : '#/';
      });
    });
  }

  function notificationItemTemplate(n) {
    return `
      <div class="notif-item ${n.is_read ? '' : 'notif-unread'}" data-notif-id="${n.id}" data-url="${escapeHtml(n.mobile_url)}">
        ${!n.is_read ? '<span class="notif-dot"></span>' : ''}
        <div class="notif-content">
          <p class="notif-title">${escapeHtml(n.title)}</p>
          <p class="notif-message">${escapeHtml(n.message)}</p>
          <p class="notif-meta muted">${n.sender_name ? escapeHtml(n.sender_name) + ' — ' : ''}${formatDateTime(n.created_at)}</p>
        </div>
      </div>`;
  }

  // ---------------------------------------------------------------------
  // Écran : détail d'une demande
  // ---------------------------------------------------------------------
  async function viewDetail(id) {
    app.innerHTML = topbar(getUser(), true) + `<div id="detail-body" class="screen-body">${skeletonList(3)}</div>`;
    wireTopbar();
    const d = await api(`/chiffrage/demandes/${id}/`);
    const body = document.getElementById('detail-body');
    const color = STATUT_COLORS[d.statut_color] || '#64748b';
    const montant = formatMontant(d.montant_ht);

    body.innerHTML = `
      <div class="detail-head">
        <span class="ref">${escapeHtml(d.reference)}</span>
        <span class="badge" style="background:${color}22;color:${color}">${escapeHtml(d.statut_display)}</span>
      </div>
      <h2>${escapeHtml(d.client_nom)}</h2>

      <div class="result-box ${montant ? 'result-ready' : 'result-pending'}">
        ${montant
          ? `<p class="result-label">Montant validé</p><p class="result-value">${montant}</p>`
          : `<p class="result-label">Résultat</p><p class="result-value muted">En attente de validation</p>`}
      </div>

      ${d.peut_valider_dc ? actionPanelTemplate('dc') : ''}
      ${d.peut_valider_dg ? actionPanelTemplate('dg') : ''}
      ${d.peut_valider_rm ? actionPanelTemplate('rm') : ''}
      ${d.peut_traiter_methodes ? methodesPanelTemplate(d) : ''}

      <section class="detail-section">
        <h3>Détails</h3>
        <dl class="detail-grid">
          <dt>Assigné à</dt><dd>${d.assigned_to ? escapeHtml(d.assigned_to.full_name) : '—'}</dd>
          <dt>Référence affaire</dt><dd>${escapeHtml(d.client_ref_affaire) || '—'}</dd>
          <dt>Délai souhaité</dt><dd>${formatDate(d.delai_souhaite)}</dd>
          <dt>Urgence</dt><dd>${escapeHtml(d.urgence_display)}</dd>
          <dt>Description</dt><dd>${escapeHtml(d.description)}</dd>
          ${d.finitions ? `<dt>Finitions</dt><dd>${escapeHtml(d.finitions)}</dd>` : ''}
          ${d.kits_references ? `<dt>Kits / réf.</dt><dd>${escapeHtml(d.kits_references)}</dd>` : ''}
          ${d.quantites_estimees ? `<dt>Quantités</dt><dd>${escapeHtml(d.quantites_estimees)}</dd>` : ''}
          ${d.contraintes_techniques ? `<dt>Contraintes</dt><dd>${escapeHtml(d.contraintes_techniques)}</dd>` : ''}
          ${d.commentaires ? `<dt>Commentaires</dt><dd>${escapeHtml(d.commentaires)}</dd>` : ''}
          ${d.lien_telechargement ? `<dt>Lien de téléchargement</dt><dd><a href="${escapeHtml(d.lien_telechargement)}" target="_blank" rel="noopener">${escapeHtml(d.lien_telechargement)}</a></dd>` : ''}
          ${d.statut === 'REVISION_DEMANDEE' && d.revision_motif ? `<dt>Motif de révision</dt><dd>${escapeHtml(d.revision_motif)}</dd>` : ''}
        </dl>
      </section>

      <section class="detail-section">
        <h3>Suivi (${d.historique.length})</h3>
        <div class="timeline-list">
          ${d.historique.map(timelineTemplate).join('') || '<p class="muted">Aucun suivi pour l\'instant.</p>'}
        </div>
      </section>

      <section class="detail-section">
        <h3>Pièces jointes (${d.fichiers.length})</h3>
        <div class="photo-grid" id="photo-grid">
          ${d.fichiers.map(fichierGridItemTemplate).join('') || '<p class="muted">Aucune pièce jointe.</p>'}
        </div>
        <div class="attach-buttons">
          <label class="btn-secondary photo-trigger">
            ${icon('camera')} Photo
            <input type="file" id="add-camera-input" accept="image/*" capture="environment" hidden>
          </label>
          <label class="btn-secondary photo-trigger">
            ${icon('paperclip')} Fichier
            <input type="file" id="add-file-input" accept="image/*,application/pdf,.xls,.xlsx,.doc,.docx,.csv" multiple hidden>
          </label>
        </div>
      </section>

      <section class="detail-section">
        <h3>Messages (${d.messages.length})</h3>
        <div class="message-list" id="message-list">
          ${d.messages.map(messageTemplate).join('') || '<p class="muted">Aucun message.</p>'}
        </div>
        <form id="message-form" class="message-form">
          <textarea name="contenu" rows="2" placeholder="Écrire un message…" required></textarea>
          <button type="submit" class="btn-primary">Envoyer</button>
        </form>
      </section>

      <div id="lightbox" class="lightbox" hidden>
        <button type="button" class="lightbox-close" id="lightbox-close">${icon('close')}</button>
        <img id="lightbox-img" src="" alt="">
      </div>`;

    body.querySelectorAll('[data-url]').forEach((btn) => {
      btn.addEventListener('click', () => {
        if (btn.dataset.image === '1') {
          document.getElementById('lightbox-img').src = btn.dataset.url;
          document.getElementById('lightbox').hidden = false;
        } else {
          window.open(btn.dataset.url, '_blank');
        }
      });
    });
    document.getElementById('lightbox-close').addEventListener('click', () => {
      document.getElementById('lightbox').hidden = true;
    });

    const uploadFiles = async (files) => {
      if (!files.length) return;
      const fd = new FormData();
      files.forEach((f) => fd.append('fichiers', f));
      try {
        await api(`/chiffrage/demandes/${id}/photos/`, { method: 'POST', body: fd });
        toast('Pièce(s) jointe(s) ajoutée(s).', 'success');
        viewDetail(id);
      } catch (err) {
        toast(err.message, 'error');
      }
    };
    document.getElementById('add-camera-input').addEventListener('change', (e) => uploadFiles(Array.from(e.target.files)));
    document.getElementById('add-file-input').addEventListener('change', (e) => uploadFiles(Array.from(e.target.files)));

    const msgForm = document.getElementById('message-form');
    msgForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const fd = new FormData(msgForm);
      const contenu = fd.get('contenu').trim();
      if (!contenu) return;
      const btn = msgForm.querySelector('button');
      btn.disabled = true;
      try {
        await api(`/chiffrage/demandes/${id}/messages/`, { method: 'POST', json: { contenu } });
        viewDetail(id);
      } catch (err) {
        toast(err.message, 'error');
        btn.disabled = false;
      }
    });

    if (d.peut_valider_dc) wireActionPanel('dc', id);
    if (d.peut_valider_dg) wireActionPanel('dg', id);
    if (d.peut_valider_rm) wireActionPanel('rm', id);
    if (d.peut_traiter_methodes) wireMethodesPanel(d, id);
  }

  const ACTION_PANEL_OPTIONS = {
    dc: [
      { value: 'valider', label: 'Valider — transmettre aux Méthodes', motif: false },
      { value: 'retourner', label: 'Retourner au commercial (compléments)', motif: true },
      { value: 'rejeter', label: 'Rejeter définitivement', motif: true },
    ],
    dg: [
      { value: 'valider', label: 'Valider le devis', motif: false },
      { value: 'revision', label: 'Demander une révision aux Méthodes', motif: true },
      { value: 'refuser', label: 'Refuser et archiver', motif: true },
    ],
    rm: [
      { value: 'approuver', label: 'Approuver — transmettre à la DG', motif: false },
      { value: 'rejeter', label: 'Retourner au méthodiste (corrections)', motif: true },
    ],
  };
  const ACTION_PANEL_TITLES = {
    dc: 'Décision — Directeur Commercial',
    dg: 'Décision — Direction Générale',
    rm: 'Décision — Responsable Méthodes',
  };

  function actionPanelTemplate(kind) {
    const title = ACTION_PANEL_TITLES[kind];
    const options = ACTION_PANEL_OPTIONS[kind];
    return `
      <div class="action-panel">
        <h3>${title}</h3>
        <form id="action-form-${kind}" class="form">
          <select name="action" id="action-select-${kind}">
            ${options.map((o) => `<option value="${o.value}">${escapeHtml(o.label)}</option>`).join('')}
          </select>
          <textarea name="motif" id="action-motif-${kind}" rows="2" placeholder="Motif (obligatoire pour cette option)" hidden></textarea>
          <button type="submit" class="btn-primary">Confirmer</button>
          <p class="field-error" id="action-error-${kind}" hidden></p>
        </form>
      </div>`;
  }

  function wireActionPanel(kind, id) {
    const options = ACTION_PANEL_OPTIONS[kind];
    const select = document.getElementById(`action-select-${kind}`);
    const motifEl = document.getElementById(`action-motif-${kind}`);
    const form = document.getElementById(`action-form-${kind}`);
    const errorEl = document.getElementById(`action-error-${kind}`);

    const syncMotifVisibility = () => {
      const opt = options.find((o) => o.value === select.value);
      motifEl.hidden = !opt.motif;
    };
    select.addEventListener('change', syncMotifVisibility);
    syncMotifVisibility();

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      errorEl.hidden = true;
      const opt = options.find((o) => o.value === select.value);
      const motif = motifEl.value.trim();
      if (opt.motif && !motif) {
        errorEl.textContent = 'Un motif est requis pour cette option.';
        errorEl.hidden = false;
        return;
      }
      const btn = form.querySelector('button');
      btn.disabled = true;
      btn.textContent = 'Envoi…';
      try {
        await api(`/chiffrage/demandes/${id}/action-${kind}/`, {
          method: 'POST', json: { action: select.value, motif },
        });
        toast('Décision enregistrée.', 'success');
        viewDetail(id);
      } catch (err) {
        errorEl.textContent = err.message;
        errorEl.hidden = false;
        btn.disabled = false;
        btn.textContent = 'Confirmer';
      }
    });
  }

  const JALON_OPTIONS = [
    { value: 'ANALYSE', label: 'Analyse en cours' },
    { value: 'CHIFFRAGE', label: 'Chiffrage en cours' },
    { value: 'REVISION', label: 'En révision interne' },
  ];

  function methodesPanelTemplate(d) {
    return `
      <div class="action-panel">
        <h3>Traitement — Service Méthodes</h3>

        <div class="form" style="margin-bottom:16px;">
          <label>Jalon
            <select id="methodes-jalon">
              ${JALON_OPTIONS.map((o) => `<option value="${o.value}" ${d.jalon === o.value ? 'selected' : ''}>${o.label}</option>`).join('')}
            </select>
          </label>
        </div>

        <div class="form" style="margin-bottom:16px;">
          <label>Montant HT (MAD) — invisible du commercial tant que la DG n'a pas validé
            <input type="number" step="0.01" min="0" id="methodes-montant" value="${d.montant_ht !== null && d.montant_ht !== undefined ? d.montant_ht : ''}">
          </label>
          <button type="button" class="btn-secondary" id="methodes-montant-save">${icon('document')} Enregistrer le montant</button>
        </div>

        <form id="methodes-devis-form" class="form">
          <label>Chiffrage détaillé (interne) *<input type="file" id="methodes-fichier-detail" accept=".pdf,.xls,.xlsx,.doc,.docx" required></label>
          <label>Devis sans détail (transmis au client) *<input type="file" id="methodes-fichier-public" accept=".pdf,.xls,.xlsx,.doc,.docx" required></label>
          <button type="submit" class="btn-primary">Soumettre le devis au Responsable Méthodes</button>
          <p class="field-error" id="methodes-error" hidden></p>
        </form>
      </div>`;
  }

  function wireMethodesPanel(d, id) {
    document.getElementById('methodes-jalon').addEventListener('change', async (e) => {
      try {
        await api(`/chiffrage/demandes/${id}/jalon/`, { method: 'POST', json: { jalon: e.target.value } });
        toast('Jalon mis à jour.', 'success');
      } catch (err) {
        toast(err.message, 'error');
      }
    });

    document.getElementById('methodes-montant-save').addEventListener('click', async () => {
      const value = document.getElementById('methodes-montant').value;
      try {
        await api(`/chiffrage/demandes/${id}/montant/`, { method: 'POST', json: { montant_ht: value } });
        toast('Montant enregistré.', 'success');
      } catch (err) {
        toast(err.message, 'error');
      }
    });

    const form = document.getElementById('methodes-devis-form');
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const errorEl = document.getElementById('methodes-error');
      errorEl.hidden = true;
      const detail = document.getElementById('methodes-fichier-detail').files[0];
      const pub = document.getElementById('methodes-fichier-public').files[0];
      if (!detail || !pub) {
        errorEl.textContent = 'Les deux fichiers sont obligatoires.';
        errorEl.hidden = false;
        return;
      }
      const fd = new FormData();
      fd.append('fichier_detail', detail);
      fd.append('fichier_public', pub);
      const btn = form.querySelector('button');
      btn.disabled = true;
      btn.textContent = 'Envoi…';
      try {
        await api(`/chiffrage/demandes/${id}/soumettre-devis/`, { method: 'POST', body: fd });
        toast('Devis soumis au Responsable Méthodes.', 'success');
        viewDetail(id);
      } catch (err) {
        errorEl.textContent = err.message;
        errorEl.hidden = false;
        btn.disabled = false;
        btn.textContent = 'Soumettre le devis au Responsable Méthodes';
      }
    });
  }

  function fichierGridItemTemplate(f) {
    if (isImage(f.nom)) {
      return `<button type="button" class="photo-grid-item" data-url="${f.fichier_url}" data-image="1"><img src="${f.fichier_url}" alt=""></button>`;
    }
    const kind = fileKind(f.nom);
    return `
      <button type="button" class="photo-grid-item file-tile ${kind.cls}" data-url="${f.fichier_url}" data-image="0">
        <span class="ext-icon">${icon('document')}</span>
        <span class="name">${escapeHtml(f.nom)}</span>
        <span class="size muted">${escapeHtml(f.taille_human)}</span>
      </button>`;
  }

  function timelineTemplate(h) {
    return `
      <div class="timeline-item">
        <div class="timeline-dot"></div>
        <div class="timeline-content">
          <p class="timeline-action">${escapeHtml(h.action)}</p>
          ${h.detail ? `<p class="timeline-detail">${escapeHtml(h.detail)}</p>` : ''}
          <p class="timeline-meta muted">${escapeHtml(h.auteur ? h.auteur.full_name : 'Système')} — ${formatDateTime(h.created_at)}</p>
        </div>
      </div>`;
  }

  function messageTemplate(m) {
    return `
      <div class="message-item">
        <div class="message-meta"><strong>${escapeHtml(m.auteur ? m.auteur.full_name : '—')}</strong><span class="muted">${formatDateTime(m.created_at)}</span></div>
        <p>${escapeHtml(m.contenu)}</p>
      </div>`;
  }

  // ---------------------------------------------------------------------
  // Topbar / FAB communs
  // ---------------------------------------------------------------------
  // Repère de marque en SVG vectoriel (jamais une image raster) — certains navigateurs
  // Android (mode sombre forcé) assombrissent/inversent les <img> à fond clair dans la page,
  // ce qui rendait l'icône PNG méconnaissable. Un SVG avec des couleurs explicites y échappe.
  const BRAND_MARK_SVG = `
    <svg class="topbar-logo-svg" viewBox="0 0 40 40" aria-hidden="true">
      <text x="7" y="27" font-family="'Segoe UI', Arial, sans-serif" font-size="19" font-weight="800" fill="#221f20">B</text>
      <text x="17.5" y="27" font-family="'Segoe UI', Arial, sans-serif" font-size="19" font-weight="800" fill="#8ec155">&amp;</text>
      <text x="27" y="27" font-family="'Segoe UI', Arial, sans-serif" font-size="19" font-weight="800" fill="#221f20">C</text>
    </svg>`;

  function topbar(user, withBack) {
    return `
      <div class="topbar">
        ${withBack ? `<button class="back-btn" id="back-btn">${icon('back')}</button>` : `<span class="topbar-logo">${BRAND_MARK_SVG}</span>`}
        <span>Hope AppMobile</span>
        <button class="bell-btn" id="bell-btn" title="Notifications">
          ${icon('bell')}
          <span class="bell-badge" id="bell-badge" hidden>0</span>
        </button>
        <button class="logout-btn" id="logout-btn" title="Déconnexion">${icon('logout')}</button>
      </div>`;
  }
  function wireTopbar() {
    const back = document.getElementById('back-btn');
    if (back) back.addEventListener('click', () => { location.hash = '#/'; });
    const bell = document.getElementById('bell-btn');
    if (bell) bell.addEventListener('click', () => { location.hash = '#/notifications'; });
    refreshBellBadge();
    const logout = document.getElementById('logout-btn');
    if (logout) logout.addEventListener('click', async () => {
      await unsubscribeFromPush();
      try { await api('/auth/logout/', { method: 'POST' }); } catch (e) { /* on efface quand même la session locale */ }
      clearSession();
      location.hash = '#/login';
    });
  }

  async function refreshBellBadge() {
    const badge = document.getElementById('bell-badge');
    if (!badge) return;
    try {
      const data = await api('/notifications/unread-count/');
      if (data.count > 0) {
        badge.textContent = data.count > 99 ? '99+' : String(data.count);
        badge.hidden = false;
      } else {
        badge.hidden = true;
      }
    } catch (e) { /* badge non critique */ }
  }
  function fab() {
    return `<button class="fab" id="fab-nouvelle">${icon('plus')} Nouvelle demande</button>`;
  }
  function wireFab() {
    const btn = document.getElementById('fab-nouvelle');
    if (btn) btn.addEventListener('click', () => { location.hash = '#/nouvelle'; });
  }

  // ---------------------------------------------------------------------
  // Notifications push (Web Push / VAPID) — effet « comme WhatsApp »
  // ---------------------------------------------------------------------
  function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const rawData = atob(base64);
    return Uint8Array.from([...rawData].map((c) => c.charCodeAt(0)));
  }

  async function subscribeToPush() {
    if (!('serviceWorker' in navigator) || !('PushManager' in window) || !window.VAPID_PUBLIC_KEY) return;
    try {
      const permission = await Notification.requestPermission();
      if (permission !== 'granted') return;
      const registration = await navigator.serviceWorker.ready;
      let subscription = await registration.pushManager.getSubscription();
      if (!subscription) {
        subscription = await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(window.VAPID_PUBLIC_KEY),
        });
      }
      await api('/notifications/push-subscribe/', { method: 'POST', json: subscription.toJSON() });
    } catch (e) {
      /* notifications non bloquantes — l'app reste utilisable sans push */
    }
  }

  async function unsubscribeFromPush() {
    if (!('serviceWorker' in navigator)) return;
    try {
      const registration = await navigator.serviceWorker.ready;
      const subscription = await registration.pushManager.getSubscription();
      if (subscription) {
        await api('/notifications/push-unsubscribe/', { method: 'POST', json: { endpoint: subscription.endpoint } });
        await subscription.unsubscribe();
      }
    } catch (e) { /* ignore */ }
  }

  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/m/chiffrage/service-worker.js').then(() => {
        if (getToken()) subscribeToPush();
      }).catch(() => {
        /* installation non critique — l'app reste utilisable sans cache */
      });
    });
  }
})();
