document.addEventListener('DOMContentLoaded', () => {
  const form = document.querySelector('[data-cms-form]');
  let formIsDirty = false;
  let formIsSubmitting = false;

  if (form) {
    form.addEventListener('input', () => { formIsDirty = true; });
    form.addEventListener('change', () => { formIsDirty = true; });
    form.addEventListener('submit', () => {
      formIsSubmitting = true;
      form.setAttribute('aria-busy', 'true');
    });
    window.addEventListener('beforeunload', event => {
      if (!formIsDirty || formIsSubmitting) return;
      event.preventDefault();
      event.returnValue = '';
    });
  }

  document.querySelectorAll('[data-image-control]').forEach(control => {
    const input = control.querySelector('[data-image-input]');
    const clear = control.querySelector('[data-image-clear]');
    const current = control.querySelector('[data-current-image]');
    const preview = control.querySelector('[data-image-preview]');
    const previewImage = control.querySelector('[data-image-preview-image]');
    const details = control.querySelector('[data-image-details]');
    const status = control.querySelector('[data-image-status]');
    const allowedTypes = new Set(['image/jpeg', 'image/png', 'image/webp']);

    if (!input || !preview || !previewImage || !details || !status) return;

    const resetPreview = () => {
      preview.hidden = true;
      previewImage.removeAttribute('src');
      details.textContent = '';
    };

    const showStatus = (message, isError = false) => {
      status.textContent = message;
      status.classList.toggle('isError', isError);
    };

    input.addEventListener('change', () => {
      resetPreview();
      current?.classList.remove('isPendingRemoval', 'isBeingReplaced');
      if (clear) clear.checked = false;

      const file = input.files?.[0];
      if (!file) {
        showStatus('');
        return;
      }
      if (file.type && !allowedTypes.has(file.type)) {
        showStatus('Choose a JPEG, PNG, or WebP picture.', true);
        return;
      }
      if (file.size > 8 * 1024 * 1024) {
        showStatus('This file is larger than 8 MB. Choose a smaller picture.', true);
        return;
      }

      const reader = new FileReader();
      reader.addEventListener('error', () => {
        showStatus('The selected file could not be previewed. Choose another picture.', true);
      });
      reader.addEventListener('load', () => {
        previewImage.addEventListener('error', () => {
          resetPreview();
          showStatus('The selected file is not a readable picture.', true);
        }, { once: true });
        previewImage.addEventListener('load', () => {
          const size = file.size < 1024 * 1024
            ? `${Math.ceil(file.size / 1024)} KB`
            : `${(file.size / (1024 * 1024)).toFixed(1)} MB`;
          details.textContent = `${file.name} · ${previewImage.naturalWidth}×${previewImage.naturalHeight} · ${size}`;
          preview.hidden = false;
          current?.classList.add('isBeingReplaced');
          showStatus(current
            ? 'This picture will replace the current one when you save.'
            : 'This picture will be uploaded when you save.');
        }, { once: true });
        previewImage.src = reader.result;
      });
      reader.readAsDataURL(file);
    });

    clear?.addEventListener('change', () => {
      resetPreview();
      input.value = '';
      current?.classList.toggle('isPendingRemoval', clear.checked);
      current?.classList.remove('isBeingReplaced');
      showStatus(clear.checked
        ? 'The current picture will be removed when you save. Uncheck this box to keep it.'
        : 'The current picture will be kept.');
    });

    if (clear?.checked) {
      current?.classList.add('isPendingRemoval');
      showStatus('The current picture will be removed when you save. Uncheck this box to keep it.');
    }
  });

  document.querySelectorAll('[data-confirm]').forEach(control => {
    control.addEventListener('click', event => {
      if (!window.confirm(control.dataset.confirm)) event.preventDefault();
    });
  });
});
