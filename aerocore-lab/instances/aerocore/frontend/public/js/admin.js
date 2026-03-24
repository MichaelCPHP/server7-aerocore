/**
 * AeroCore CRM Dashboard — admin.js
 * Handles auth checks, data fetching, filtering, detail panel, and CRUD operations.
 */
(function () {
  'use strict';

  // ---------------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------------
  var submissions = [];
  var currentSort = { field: 'created_at', dir: 'desc' };
  var currentSubmissionId = null;
  var debounceTimer = null;

  // ---------------------------------------------------------------------------
  // DOM References
  // ---------------------------------------------------------------------------
  var els = {
    body: document.getElementById('submissions-body'),
    filterStatus: document.getElementById('filter-status'),
    filterSearch: document.getElementById('filter-search'),
    filterFrom: document.getElementById('filter-from'),
    filterTo: document.getElementById('filter-to'),
    panelOverlay: document.getElementById('panel-overlay'),
    detailPanel: document.getElementById('detail-panel'),
    panelClose: document.getElementById('panel-close'),
    panelBody: document.getElementById('panel-body'),
    panelTitle: document.getElementById('panel-title'),
    btnDelete: document.getElementById('btn-delete'),
    btnLogout: document.getElementById('btn-logout'),
    toast: document.getElementById('toast'),
    statTotal: document.getElementById('stat-total'),
    statNew: document.getElementById('stat-new'),
    statQuoted: document.getElementById('stat-quoted'),
    statClosed: document.getElementById('stat-closed')
  };

  // ---------------------------------------------------------------------------
  // API Helpers
  // ---------------------------------------------------------------------------
  function api(method, path, body) {
    var opts = {
      method: method,
      credentials: 'same-origin',
      headers: {}
    };
    if (body !== undefined) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }
    return fetch(path, opts).then(function (res) {
      if (res.status === 401) {
        window.location.href = '/admin/';
        return Promise.reject(new Error('Unauthorized'));
      }
      if (!res.ok) {
        return res.json().then(function (d) {
          throw new Error(d.error || 'Request failed');
        });
      }
      if (res.status === 204) return null;
      return res.json();
    });
  }

  // ---------------------------------------------------------------------------
  // Auth Check
  // ---------------------------------------------------------------------------
  function checkAuth() {
    return api('GET', '/api/auth/check').catch(function () {
      window.location.href = '/admin/';
    });
  }

  // ---------------------------------------------------------------------------
  // Stats
  // ---------------------------------------------------------------------------
  function fetchStats() {
    api('GET', '/api/submissions?status=new').then(function (data) {
      els.statNew.textContent = Array.isArray(data) ? data.length : (data && data.total != null ? data.total : '--');
    }).catch(function () { els.statNew.textContent = '--'; });

    api('GET', '/api/submissions?status=quoted').then(function (data) {
      els.statQuoted.textContent = Array.isArray(data) ? data.length : (data && data.total != null ? data.total : '--');
    }).catch(function () { els.statQuoted.textContent = '--'; });

    api('GET', '/api/submissions?status=closed').then(function (data) {
      els.statClosed.textContent = Array.isArray(data) ? data.length : (data && data.total != null ? data.total : '--');
    }).catch(function () { els.statClosed.textContent = '--'; });

    api('GET', '/api/submissions').then(function (data) {
      els.statTotal.textContent = Array.isArray(data) ? data.length : (data && data.total != null ? data.total : '--');
    }).catch(function () { els.statTotal.textContent = '--'; });
  }

  // ---------------------------------------------------------------------------
  // Fetch & Render Submissions
  // ---------------------------------------------------------------------------
  function fetchSubmissions() {
    var params = [];
    var status = els.filterStatus.value;
    var search = els.filterSearch.value.trim();
    var from = els.filterFrom.value;
    var to = els.filterTo.value;

    if (status) params.push('status=' + encodeURIComponent(status));
    if (search) params.push('search=' + encodeURIComponent(search));
    if (from) params.push('from=' + encodeURIComponent(from));
    if (to) params.push('to=' + encodeURIComponent(to));

    var url = '/api/submissions' + (params.length ? '?' + params.join('&') : '');

    els.body.innerHTML =
      '<tr><td colspan="7" class="table-empty">' +
      '<div class="loading-spinner"></div>' +
      '<p style="margin-top:12px">Loading submissions...</p>' +
      '</td></tr>';

    api('GET', url)
      .then(function (data) {
        submissions = Array.isArray(data) ? data : (data && data.submissions ? data.submissions : []);
        sortSubmissions();
        renderTable();
      })
      .catch(function () {
        els.body.innerHTML =
          '<tr><td colspan="7" class="table-empty">' +
          '<p>Failed to load submissions.</p>' +
          '</td></tr>';
      });
  }

  function sortSubmissions() {
    var field = currentSort.field;
    var dir = currentSort.dir === 'asc' ? 1 : -1;
    submissions.sort(function (a, b) {
      var va = a[field] || '';
      var vb = b[field] || '';
      if (field === 'created_at') {
        return (new Date(va) - new Date(vb)) * dir;
      }
      if (typeof va === 'string') va = va.toLowerCase();
      if (typeof vb === 'string') vb = vb.toLowerCase();
      if (va < vb) return -1 * dir;
      if (va > vb) return 1 * dir;
      return 0;
    });
  }

  function renderTable() {
    if (submissions.length === 0) {
      els.body.innerHTML =
        '<tr><td colspan="7" class="table-empty">' +
        '<div class="table-empty-icon">&#128203;</div>' +
        '<p>No submissions found</p>' +
        '</td></tr>';
      return;
    }

    var html = '';
    for (var i = 0; i < submissions.length; i++) {
      var s = submissions[i];
      var date = formatDate(s.created_at);
      var attachCount = s.attachments ? s.attachments.length : 0;
      var badgeClass = 'badge badge-' + (s.status || 'new');

      html +=
        '<tr data-id="' + escapeAttr(s.id) + '">' +
        '<td class="cell-date">' + escapeHtml(date) + '</td>' +
        '<td class="cell-name">' + escapeHtml(s.name || '--') + '</td>' +
        '<td class="cell-company">' + escapeHtml(s.company || '--') + '</td>' +
        '<td class="cell-material">' + escapeHtml(formatMaterial(s.material_type || s.material || '--')) + '</td>' +
        '<td><span class="' + badgeClass + '">' + escapeHtml(s.status || 'new') + '</span></td>' +
        '<td class="cell-attachments">' + attachCount + '</td>' +
        '<td><button class="btn-view" data-id="' + escapeAttr(s.id) + '">View</button></td>' +
        '</tr>';
    }
    els.body.innerHTML = html;
  }

  // ---------------------------------------------------------------------------
  // Detail Panel
  // ---------------------------------------------------------------------------
  function openDetail(id) {
    currentSubmissionId = id;
    els.panelBody.innerHTML =
      '<div style="text-align:center;padding:40px"><div class="loading-spinner"></div></div>';
    showPanel();

    api('GET', '/api/submissions/' + id)
      .then(function (s) {
        renderDetail(s);
      })
      .catch(function () {
        els.panelBody.innerHTML =
          '<div style="text-align:center;padding:40px;color:var(--text-muted)">Failed to load details.</div>';
      });
  }

  function renderDetail(s) {
    els.panelTitle.textContent = s.name || 'Submission Details';
    var html = '';

    // Contact Info
    html += '<div class="panel-section">';
    html += '<div class="panel-section-title">Contact Information</div>';
    html += '<div class="panel-fields">';
    html += field('Name', s.name);
    html += field('Email', s.email ? '<a href="mailto:' + escapeAttr(s.email) + '">' + escapeHtml(s.email) + '</a>' : '--', true);
    html += field('Phone', s.phone || '--');
    html += field('Company', s.company || '--');
    html += '</div></div>';

    // Material Details
    html += '<div class="panel-section">';
    html += '<div class="panel-section-title">Material Details</div>';
    html += '<div class="panel-fields">';
    html += field('Material Type', formatMaterial(s.material_type || s.material || '--'));
    html += field('Source Page', s.source_page || '--');
    html += '</div>';
    if (s.details) {
      html += '<div style="margin-top:12px">';
      html += '<div class="panel-field-label" style="margin-bottom:6px">Message / Details</div>';
      html += '<div class="panel-message">' + escapeHtml(s.details) + '</div>';
      html += '</div>';
    }
    html += '</div>';

    // Attachments
    if (s.attachments && s.attachments.length > 0) {
      html += '<div class="panel-section">';
      html += '<div class="panel-section-title">Attachments (' + s.attachments.length + ')</div>';
      html += '<div class="panel-attachments">';
      for (var i = 0; i < s.attachments.length; i++) {
        var att = s.attachments[i];
        var attId = att.id || att.attachment_id;
        var attType = att.content_type || att.type || '';
        var attName = att.filename || att.name || 'file';

        if (attType.indexOf('image/') === 0) {
          html +=
            '<a href="/api/attachments/' + escapeAttr(attId) + '" target="_blank">' +
            '<img class="attachment-thumb" src="/api/attachments/' + escapeAttr(attId) + '" alt="' + escapeAttr(attName) + '">' +
            '</a>';
        } else {
          html +=
            '<a class="attachment-file" href="/api/attachments/' + escapeAttr(attId) + '" download="' + escapeAttr(attName) + '">' +
            '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">' +
            '<path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/>' +
            '<polyline points="7 10 12 15 17 10"/>' +
            '<line x1="12" y1="15" x2="12" y2="3"/>' +
            '</svg>' +
            escapeHtml(attName) +
            '</a>';
        }
      }
      html += '</div></div>';
    }

    // UTM / Attribution
    var hasUtm = s.utm_source || s.utm_medium || s.utm_campaign || s.utm_term || s.utm_content || s.referrer || s.landing_page;
    if (hasUtm) {
      html += '<div class="panel-section">';
      html += '<div class="panel-section-title">Attribution / UTM Data</div>';
      html += '<div class="utm-grid">';
      if (s.utm_source) html += utmItem('Source', s.utm_source);
      if (s.utm_medium) html += utmItem('Medium', s.utm_medium);
      if (s.utm_campaign) html += utmItem('Campaign', s.utm_campaign);
      if (s.utm_term) html += utmItem('Term', s.utm_term);
      if (s.utm_content) html += utmItem('Content', s.utm_content);
      if (s.referrer) html += utmItem('Referrer', s.referrer);
      if (s.landing_page) html += utmItem('Landing Page', s.landing_page);
      html += '</div></div>';
    }

    // Meta
    html += '<div class="panel-section">';
    html += '<div class="panel-section-title">Metadata</div>';
    html += '<div class="panel-fields">';
    html += field('Submitted', formatDateTime(s.created_at));
    html += field('Last Updated', formatDateTime(s.updated_at));
    html += field('ID', '<span style="font-family:monospace;font-size:12px">' + escapeHtml(s.id || '--') + '</span>', true);
    html += '</div></div>';

    // Status
    html += '<div class="panel-section">';
    html += '<div class="panel-section-title">Status</div>';
    html += '<div class="panel-status-row">';
    html += '<select id="panel-status" class="panel-status-select">';
    var statuses = ['new', 'contacted', 'quoted', 'closed', 'spam'];
    for (var j = 0; j < statuses.length; j++) {
      var sel = (s.status || 'new') === statuses[j] ? ' selected' : '';
      html += '<option value="' + statuses[j] + '"' + sel + '>' +
        statuses[j].charAt(0).toUpperCase() + statuses[j].slice(1) + '</option>';
    }
    html += '</select>';
    html += '<button class="btn btn-primary btn-sm" id="btn-save-status">Update</button>';
    html += '</div></div>';

    // Notes
    html += '<div class="panel-section">';
    html += '<div class="panel-section-title">Internal Notes</div>';
    html += '<textarea id="panel-notes" class="panel-notes-area" placeholder="Add internal notes...">' +
      escapeHtml(s.notes || '') + '</textarea>';
    html += '<div class="panel-actions">';
    html += '<button class="btn btn-primary btn-sm" id="btn-save-notes">Save Notes</button>';
    html += '</div></div>';

    els.panelBody.innerHTML = html;

    // Bind panel events
    bindPanelEvents(s.id);
  }

  function bindPanelEvents(id) {
    var btnStatus = document.getElementById('btn-save-status');
    var btnNotes = document.getElementById('btn-save-notes');

    if (btnStatus) {
      btnStatus.addEventListener('click', function () {
        var statusVal = document.getElementById('panel-status').value;
        btnStatus.disabled = true;
        btnStatus.textContent = 'Saving...';
        api('PATCH', '/api/submissions/' + id, { status: statusVal })
          .then(function () {
            showToast('Status updated', 'success');
            btnStatus.disabled = false;
            btnStatus.textContent = 'Update';
            fetchSubmissions();
            fetchStats();
          })
          .catch(function (err) {
            showToast(err.message || 'Failed to update status', 'error');
            btnStatus.disabled = false;
            btnStatus.textContent = 'Update';
          });
      });
    }

    if (btnNotes) {
      btnNotes.addEventListener('click', function () {
        var notesVal = document.getElementById('panel-notes').value;
        btnNotes.disabled = true;
        btnNotes.textContent = 'Saving...';
        api('PATCH', '/api/submissions/' + id, { notes: notesVal })
          .then(function () {
            showToast('Notes saved', 'success');
            btnNotes.disabled = false;
            btnNotes.textContent = 'Save Notes';
          })
          .catch(function (err) {
            showToast(err.message || 'Failed to save notes', 'error');
            btnNotes.disabled = false;
            btnNotes.textContent = 'Save Notes';
          });
      });
    }
  }

  var panelFooter = document.getElementById('panel-footer');

  function showPanel() {
    if (panelFooter) panelFooter.style.display = '';
  }

  function closePanel() {
    currentSubmissionId = null;
    els.panelTitle.textContent = 'Details';
    els.panelBody.innerHTML =
      '<div class="sidebar-empty">' +
      '<div class="sidebar-empty-icon">&#128203;</div>' +
      '<p>Select a submission to view details</p>' +
      '</div>';
    if (panelFooter) panelFooter.style.display = 'none';
  }

  // ---------------------------------------------------------------------------
  // Delete
  // ---------------------------------------------------------------------------
  function handleDelete() {
    if (!currentSubmissionId) return;
    if (!confirm('Are you sure you want to delete this submission? This action cannot be undone.')) return;

    api('DELETE', '/api/submissions/' + currentSubmissionId)
      .then(function () {
        showToast('Submission deleted', 'success');
        closePanel();
        fetchSubmissions();
        fetchStats();
      })
      .catch(function (err) {
        showToast(err.message || 'Failed to delete submission', 'error');
      });
  }

  // ---------------------------------------------------------------------------
  // Logout
  // ---------------------------------------------------------------------------
  function handleLogout() {
    api('POST', '/api/auth/logout')
      .then(function () {
        window.location.href = '/admin/';
      })
      .catch(function () {
        window.location.href = '/admin/';
      });
  }

  // ---------------------------------------------------------------------------
  // Sorting
  // ---------------------------------------------------------------------------
  function handleSort(e) {
    var th = e.target.closest('th[data-sort]');
    if (!th) return;
    var field = th.getAttribute('data-sort');
    if (currentSort.field === field) {
      currentSort.dir = currentSort.dir === 'asc' ? 'desc' : 'asc';
    } else {
      currentSort.field = field;
      currentSort.dir = 'asc';
    }

    // Update sort icons
    var ths = document.querySelectorAll('.submissions-table th[data-sort]');
    for (var i = 0; i < ths.length; i++) {
      ths[i].classList.remove('sort-active');
      var icon = ths[i].querySelector('.sort-icon');
      if (icon) icon.innerHTML = '&#9650;';
    }
    th.classList.add('sort-active');
    var activeIcon = th.querySelector('.sort-icon');
    if (activeIcon) {
      activeIcon.innerHTML = currentSort.dir === 'asc' ? '&#9650;' : '&#9660;';
    }

    sortSubmissions();
    renderTable();
  }

  // ---------------------------------------------------------------------------
  // Utility
  // ---------------------------------------------------------------------------
  function escapeHtml(str) {
    if (str == null) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function escapeAttr(str) {
    return escapeHtml(str);
  }

  function formatDate(iso) {
    if (!iso) return '--';
    var d = new Date(iso);
    if (isNaN(d.getTime())) return '--';
    return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
  }

  function formatDateTime(iso) {
    if (!iso) return '--';
    var d = new Date(iso);
    if (isNaN(d.getTime())) return '--';
    return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' }) +
      ' at ' + d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  }

  function field(label, value, isHtml) {
    return '<div class="panel-field">' +
      '<div class="panel-field-label">' + escapeHtml(label) + '</div>' +
      '<div class="panel-field-value">' + (isHtml ? value : escapeHtml(value || '--')) + '</div>' +
      '</div>';
  }

  function formatMaterial(slug) {
    if (!slug || slug === '--') return '--';
    return slug.replace(/-/g, ' ').replace(/\b\w/g, function (c) { return c.toUpperCase(); });
  }

  function utmItem(label, value) {
    return '<div class="utm-item"><strong>' + escapeHtml(label) + '</strong>' +
      '<span>' + escapeHtml(value) + '</span></div>';
  }

  var toastTimeout;
  function showToast(message, type) {
    clearTimeout(toastTimeout);
    els.toast.textContent = message;
    els.toast.className = 'toast' + (type ? ' toast-' + type : '');
    // Force reflow to restart transition
    void els.toast.offsetWidth;
    els.toast.classList.add('visible');
    toastTimeout = setTimeout(function () {
      els.toast.classList.remove('visible');
    }, 3000);
  }

  // ---------------------------------------------------------------------------
  // Event Binding
  // ---------------------------------------------------------------------------
  function bindEvents() {
    // Filter changes
    els.filterStatus.addEventListener('change', fetchSubmissions);
    els.filterFrom.addEventListener('change', fetchSubmissions);
    els.filterTo.addEventListener('change', fetchSubmissions);

    // Debounced search
    els.filterSearch.addEventListener('input', function () {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(fetchSubmissions, 300);
    });

    // Table row clicks & view button
    els.body.addEventListener('click', function (e) {
      var btn = e.target.closest('.btn-view');
      if (btn) {
        e.stopPropagation();
        openDetail(btn.getAttribute('data-id'));
        return;
      }
      var row = e.target.closest('tr[data-id]');
      if (row) {
        openDetail(row.getAttribute('data-id'));
      }
    });

    // Table header sorting
    document.querySelector('.submissions-table thead').addEventListener('click', handleSort);

    // Panel close
    els.panelClose.addEventListener('click', closePanel);
    els.panelOverlay.addEventListener('click', closePanel);

    // Escape key closes panel
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && els.detailPanel.classList.contains('open')) {
        closePanel();
      }
    });

    // Delete
    els.btnDelete.addEventListener('click', handleDelete);

    // Logout
    els.btnLogout.addEventListener('click', handleLogout);
  }

  // ---------------------------------------------------------------------------
  // Init
  // ---------------------------------------------------------------------------
  function init() {
    checkAuth().then(function () {
      bindEvents();
      fetchStats();
      fetchSubmissions();
    });
  }

  // Wait for DOM
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
