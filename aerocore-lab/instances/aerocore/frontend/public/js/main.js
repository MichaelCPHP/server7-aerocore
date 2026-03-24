// AeroCore — Main JavaScript
// Mobile menu, header scroll, smooth scroll, form handling
// Conversion tracking added by AeroCore Ads Lab Agent — 2026-03-23

(function() {
  'use strict';

  // --- Google Ads Conversion Tracking (AW-18034797214) ---
  // Fires gtag conversion events for quote form, phone clicks, and email clicks
  function trackConversion(sendTo, callback) {
    if (typeof gtag === 'function') {
      gtag('event', 'conversion', {
        'send_to': sendTo,
        'event_callback': function() {
          if (typeof callback === 'function') callback();
        }
      });
      // Fallback if gtag doesn't fire callback within 1s
      setTimeout(function() {
        if (typeof callback === 'function') callback();
      }, 1000);
    } else {
      if (typeof callback === 'function') callback();
    }
  }

  // --- UTM Parameter Capture ---
  // Capture UTM params on landing and persist across pages via sessionStorage
  var utmKeys = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'gclid'];
  var params = new URLSearchParams(window.location.search);
  utmKeys.forEach(function(key) {
    var val = params.get(key);
    if (val) sessionStorage.setItem(key, val);
  });

  function getStoredUtmParams() {
    var stored = {};
    utmKeys.forEach(function(key) {
      var val = sessionStorage.getItem(key);
      if (val) stored[key] = val;
    });
    return stored;
  }

  // Mobile Navigation Toggle
  const toggle = document.getElementById('nav-toggle');
  const navLinks = document.getElementById('nav-links');

  if (toggle && navLinks) {
    toggle.addEventListener('click', function() {
      toggle.classList.toggle('active');
      navLinks.classList.toggle('open');
    });

    // Close menu when a link is clicked
    navLinks.querySelectorAll('.nav-link').forEach(function(link) {
      link.addEventListener('click', function() {
        toggle.classList.remove('active');
        navLinks.classList.remove('open');
      });
    });
  }

  // Header scroll effect
  const header = document.getElementById('header');
  if (header) {
    var lastScroll = 0;
    window.addEventListener('scroll', function() {
      var scrollY = window.pageYOffset || document.documentElement.scrollTop;
      if (scrollY > 20) {
        header.classList.add('scrolled');
      } else {
        header.classList.remove('scrolled');
      }
      lastScroll = scrollY;
    }, { passive: true });
  }

  // Smooth scroll for anchor links
  document.querySelectorAll('a[href^="#"]').forEach(function(anchor) {
    anchor.addEventListener('click', function(e) {
      var targetId = this.getAttribute('href');
      if (targetId === '#') return;
      var target = document.querySelector(targetId);
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });

  // Quote form handling — works on main contact page and landing pages
  // Submits via API with mailto as fallback
  function setupQuoteForm(formId) {
    var form = document.getElementById(formId);
    if (!form) return;
    form.addEventListener('submit', function(e) {
      e.preventDefault();

      // Show sending state
      var btn = form.querySelector('button[type="submit"]');
      btn.textContent = 'Sending...';
      btn.disabled = true;

      // Build FormData from form (includes files automatically)
      var formData = new FormData(form);

      // Append UTM params as individual fields
      var utmData = getStoredUtmParams();
      var utmFields = ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'gclid'];
      utmFields.forEach(function(key) {
        if (utmData[key]) formData.append(key, utmData[key]);
      });

      // Append source page
      formData.append('source', window.location.pathname);

      // Submit to Cloudflare Pages Function, fall back to mailto
      fetch('/api/quote', {
        method: 'POST',
        body: formData
      }).then(function(res) {
        if (!res.ok) throw new Error('API error');
        return res.json();
      }).then(function(result) {
        if (!result.ok) throw new Error(result.error || 'Submission failed');
        // Success — fire conversion event then redirect
        trackConversion('AW-18034797214/XN5TCMfnjo4cEJ7V1JdD', function() {
          window.location.href = '/contact/thank-you/';
        });
      }).catch(function() {
        // Fallback: construct mailto link
        var name = formData.get('name') || '';
        var company = formData.get('company') || '';
        var email = formData.get('email') || '';
        var phone = formData.get('phone') || '';
        var material = formData.get('material') || '';
        var details = formData.get('details') || '';
        var utmLine = '';
        var utmEntries = Object.keys(utmData);
        if (utmEntries.length > 0) {
          utmLine = '\n\n--- Ad Attribution ---\n' +
            utmEntries.map(function(k) { return k + ': ' + utmData[k]; }).join('\n');
        }
        var subject = encodeURIComponent('Quote Request from ' + (name || 'Website'));
        var body = encodeURIComponent(
          'Name: ' + name + '\n' +
          'Company: ' + company + '\n' +
          'Email: ' + email + '\n' +
          'Phone: ' + phone + '\n' +
          'Material: ' + material + '\n' +
          'Details: ' + details + '\n' +
          'Source Page: ' + window.location.pathname +
          utmLine
        );
        window.location.href = 'mailto:Info@AreoCore.com?subject=' + subject + '&body=' + body;
        setTimeout(function() {
          window.location.href = '/contact/thank-you/';
        }, 500);
      });
    });
  }
  setupQuoteForm('quote-form');
  setupQuoteForm('lp-quote-form');

  // --- Phone call click tracking ---
  document.querySelectorAll('a[href^="tel:"]').forEach(function(link) {
    link.addEventListener('click', function() {
      trackConversion('AW-18034797214/iX9QCM3njo4cEJ7V1JdD');
    });
  });

  // --- Email click tracking ---
  document.querySelectorAll('a[href^="mailto:"]').forEach(function(link) {
    link.addEventListener('click', function() {
      trackConversion('AW-18034797214/zORLCNDnjo4cEJ7V1JdD');
    });
  });

  // File upload feedback
  var fileInput = document.getElementById('file-input');
  if (fileInput) {
    var fileUploadWrap = fileInput.closest('.file-upload');
    fileInput.addEventListener('change', function() {
      var count = fileInput.files.length;
      var content = fileUploadWrap ? fileUploadWrap.querySelector('.file-upload-content span') : null;
      if (content && count > 0) {
        content.textContent = count + ' file' + (count > 1 ? 's' : '') + ' selected';
      }
    });
  }

})();
