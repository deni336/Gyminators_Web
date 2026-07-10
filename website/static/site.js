document.addEventListener('DOMContentLoaded', () => {
  const button = document.querySelector('.menub');
  const navigation = document.querySelector('.mobileNav');
  if (!button || !navigation) return;

  const close = () => {
    navigation.classList.remove('show');
    button.setAttribute('aria-expanded', 'false');
    button.setAttribute('aria-label', 'Open navigation');
  };

  button.addEventListener('click', () => {
    const opening = !navigation.classList.contains('show');
    navigation.classList.toggle('show', opening);
    button.setAttribute('aria-expanded', String(opening));
    button.setAttribute('aria-label', opening ? 'Close navigation' : 'Open navigation');
  });
  navigation.querySelectorAll('a').forEach(link => link.addEventListener('click', close));
  document.addEventListener('keydown', event => { if (event.key === 'Escape') close(); });
});
