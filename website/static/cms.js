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

  document.querySelectorAll('input[type="file"]').forEach(input => {
    const preview = input.closest('.cmsImageField')?.querySelector('[data-image-preview]');
    if (!preview) return;
    let previewUrl;
    input.addEventListener('change', () => {
      preview.replaceChildren();
      if (previewUrl) URL.revokeObjectURL(previewUrl);
      const file = input.files?.[0];
      if (!file || !file.type.startsWith('image/')) return;
      previewUrl = URL.createObjectURL(file);
      const image = document.createElement('img');
      image.src = previewUrl;
      image.alt = 'Selected image preview';
      preview.append(image);
    });
  });

  document.querySelectorAll('[data-confirm]').forEach(control => {
    control.addEventListener('click', event => {
      if (!window.confirm(control.dataset.confirm)) event.preventDefault();
    });
  });
});
