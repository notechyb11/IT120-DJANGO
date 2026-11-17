// Compose page helpers: character counter, SMS segment counter, live preview,
// saved-contact picker, and protection against double-submitting the form.
(function () {
  'use strict';

  const form = document.getElementById('sms-form');
  if (!form) return;

  const phone = document.getElementById('id_to_number');
  const body = document.getElementById('id_body');
  const contact = document.getElementById('id_contact');
  const charCount = document.getElementById('char-count');
  const segmentCount = document.getElementById('segment-count');
  const encoding = document.getElementById('encoding');
  const previewTo = document.getElementById('preview-to');
  const previewBody = document.getElementById('preview-body');
  const sendBtn = document.getElementById('send-btn');

  let contactNumbers = {};
  try {
    contactNumbers = JSON.parse(document.getElementById('contacts-data').textContent) || {};
  } catch (e) { /* no contacts */ }

  // Same rule as the server: plain ASCII = GSM (160/153), anything else = Unicode (70/67).
  function segments(text) {
    if (!text) return 0;
    const unicode = /[^\x00-\x7F]/.test(text);
    const single = unicode ? 70 : 160;
    const multi = unicode ? 67 : 153;
    return text.length <= single ? 1 : Math.ceil(text.length / multi);
  }

  function update() {
    const text = body.value;
    charCount.textContent = text.length;
    segmentCount.textContent = segments(text);
    encoding.textContent = /[^\x00-\x7F]/.test(text) ? 'Unicode' : 'GSM';
    document.getElementById('counter').classList.toggle('text-danger', text.length > 1500);

    previewTo.textContent = phone.value.trim() || '—';
    if (text.trim()) {
      previewBody.textContent = text;  // textContent: never interprets HTML (XSS-safe)
    } else {
      previewBody.innerHTML = '<span class="text-body-secondary fst-italic">Your message will appear here.</span>';
    }
  }

  if (contact) {
    contact.addEventListener('change', function () {
      if (contactNumbers[contact.value]) {
        phone.value = contactNumbers[contact.value];
        update();
      }
    });
  }

  phone.addEventListener('input', update);
  body.addEventListener('input', update);

  form.addEventListener('submit', function () {
    sendBtn.disabled = true;
    sendBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Sending...';
  });

  update();
})();
