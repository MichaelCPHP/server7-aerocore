// AeroCore — Main JavaScript
// Mobile menu, header scroll, smooth scroll, form handling

(function() {
  'use strict';

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

  // Quote form handling
  var form = document.getElementById('quote-form');
  if (form) {
    form.addEventListener('submit', function(e) {
      e.preventDefault();

      var formData = new FormData(form);
      var data = {};
      formData.forEach(function(value, key) {
        if (key !== 'photos') data[key] = value;
      });

      // For now, construct mailto link as fallback
      var subject = encodeURIComponent('Quote Request from ' + (data.name || 'Website'));
      var body = encodeURIComponent(
        'Name: ' + (data.name || '') + '\n' +
        'Company: ' + (data.company || '') + '\n' +
        'Email: ' + (data.email || '') + '\n' +
        'Phone: ' + (data.phone || '') + '\n' +
        'Material: ' + (data.material || '') + '\n' +
        'Details: ' + (data.details || '')
      );

      // Show success state
      var btn = form.querySelector('button[type="submit"]');
      var originalText = btn.textContent;
      btn.textContent = 'Sending...';
      btn.disabled = true;

      // Open mailto as a fallback contact method
      window.location.href = 'mailto:Info@AreoCore.com?subject=' + subject + '&body=' + body;

      setTimeout(function() {
        btn.textContent = 'Quote Requested!';
        btn.style.background = '#38a169';
        btn.style.borderColor = '#38a169';

        setTimeout(function() {
          btn.textContent = originalText;
          btn.style.background = '';
          btn.style.borderColor = '';
          btn.disabled = false;
          form.reset();
        }, 3000);
      }, 500);
    });
  }

  // File upload feedback
  var fileInput = document.getElementById('photos');
  var fileUpload = document.getElementById('file-upload');
  if (fileInput && fileUpload) {
    fileInput.addEventListener('change', function() {
      var count = fileInput.files.length;
      var content = fileUpload.querySelector('.file-upload-content span');
      if (content && count > 0) {
        content.textContent = count + ' file' + (count > 1 ? 's' : '') + ' selected';
      }
    });
  }

})();
