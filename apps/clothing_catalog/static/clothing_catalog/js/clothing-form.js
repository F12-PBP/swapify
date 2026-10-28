(() => {
  const form = document.querySelector('[data-clothing-form]');
  if (!form) return;

  const input = form.querySelector('[data-clothing-photo]');
  const preview = form.querySelector('[data-photo-preview]');
  const prompt = form.querySelector('[data-photo-prompt]');
  const status = form.querySelector('[data-photo-status]');
  const drop = form.querySelector('[data-photo-drop]');
  const submit = form.querySelector('button[type="submit"]');
  const submitLabel = submit.textContent;
  let previewUrl;

  const showPhoto = () => {
    const file = input.files[0];
    input.setCustomValidity('');
    if (!file) return;
    const valid = ['image/jpeg', 'image/png', 'image/webp'].includes(file.type) && file.size <= 5 * 1024 * 1024;
    if (!valid) {
      const message = 'Choose a JPG, PNG, or WebP image up to 5 MB.';
      input.setCustomValidity(message);
      status.textContent = message;
      input.reportValidity();
      return;
    }
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = URL.createObjectURL(file);
    preview.src = previewUrl;
    preview.hidden = false;
    prompt.hidden = true;
    status.textContent = `${file.name} — choose another file to replace it.`;
  };
  input.addEventListener('change', showPhoto);
  drop.addEventListener('dragover', (event) => event.preventDefault());
  drop.addEventListener('drop', (event) => {
    event.preventDefault();
    if (event.dataTransfer.files.length !== 1) {
      status.textContent = 'Choose one photo for this piece.';
      return;
    }
    input.files = event.dataTransfer.files;
    showPhoto();
  });

  const draftFields = ['name', 'description', 'type', 'size', 'condition', 'exchange_methods'];
  const draftKey = form.dataset.draftKey;
  try {
    const draft = JSON.parse(sessionStorage.getItem(draftKey) || 'null');
    sessionStorage.removeItem(draftKey);
    if (draft) {
      for (const field of form.elements) {
        if (!draftFields.includes(field.name)) continue;
        const values = draft[field.name] || [];
        if (field.type === 'checkbox') field.checked = values.includes(field.value);
        else field.value = values[0] || '';
      }
      window.SwapDropdown?.sync(form);
      const notice = form.querySelector('[data-draft-notice]');
      notice.textContent = 'Your item details were kept. Please choose your photo again before saving.';
      notice.hidden = false;
    }
  } catch {}

  form.querySelector('[data-update-location]').addEventListener('click', () => {
    try {
      const data = new FormData(form);
      const draft = Object.fromEntries(draftFields.map((name) => [name, data.getAll(name)]));
      sessionStorage.setItem(draftKey, JSON.stringify(draft));
    } catch {}
  });

  form.addEventListener('submit', (event) => {
    for (const field of form.querySelectorAll('[data-dropdown-enhanced] input')) {
      if (!field.value) {
        event.preventDefault();
        field.closest('details').querySelector('summary').focus();
        status.textContent = 'Choose a category, size, and condition before saving.';
        return;
      }
    }
    if (!form.querySelector('[name="exchange_methods"]:checked')) {
      event.preventDefault();
      form.querySelector('[name="exchange_methods"]').focus();
      status.textContent = 'Choose at least one exchange method.';
      return;
    }
    if (form.dataset.submitting === 'true') {
      event.preventDefault();
      return;
    }
    form.dataset.submitting = 'true';
    form.setAttribute('aria-busy', 'true');
    submit.disabled = true;
    submit.textContent = submit.dataset.submittingLabel;
  });
  window.addEventListener('pageshow', () => {
    delete form.dataset.submitting;
    form.removeAttribute('aria-busy');
    submit.disabled = false;
    submit.textContent = submitLabel;
  });
})();
