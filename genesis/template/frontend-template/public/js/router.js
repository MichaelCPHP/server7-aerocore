import { renderHome } from './components/home.js';
import { api } from './api.js';

export function go(path, replace) {
  if (replace) history.replaceState(null, '', path);
  else history.pushState(null, '', path);
  route();
}

export function route() {
  const app = document.getElementById('app');
  renderHome(app);
}

export async function initApp() {
  const resp = await api('/api/lab');
  const lab = resp?.data || resp;
  if (lab) {
    document.getElementById('nav-name').textContent = lab.name || 'Lab';
    document.getElementById('nav-icon').textContent = lab.icon || '⚗';
    document.getElementById('footer-name').textContent = lab.name || 'Lab';
    document.title = lab.name || 'Lab';
  }
  window.addEventListener('popstate', route);
  window.app = { go };
  window._appRoute = route;
  route();
}
