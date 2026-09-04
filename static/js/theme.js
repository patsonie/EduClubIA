// Application immédiate du thème sauvegardé, avant le rendu de la page (évite le flash).
(function appliquerThemeImmediatement() {
    const theme = localStorage.getItem('theme') || 'clair';
    if (theme === 'sombre') {
        document.documentElement.setAttribute('data-theme', 'dark');
        document.documentElement.setAttribute('data-bs-theme', 'dark');
    }
})();

// Câblage du bouton (s'il existe sur la page) une fois le DOM prêt.
function initialiserBoutonTheme() {
    const bouton = document.getElementById('btn-theme-toggle');
    const icone = document.getElementById('icone-theme');
    const themeActuel = localStorage.getItem('theme') || 'clair';

    if (icone) {
        icone.className = themeActuel === 'sombre' ? 'bi bi-sun-fill' : 'bi bi-moon-fill';
    }

    bouton?.addEventListener('click', () => {
        const estSombre = document.documentElement.getAttribute('data-theme') === 'dark';

        if (estSombre) {
            document.documentElement.removeAttribute('data-theme');
            document.documentElement.removeAttribute('data-bs-theme');
            localStorage.setItem('theme', 'clair');
            if (icone) icone.className = 'bi bi-moon-fill';
        } else {
            document.documentElement.setAttribute('data-theme', 'dark');
            document.documentElement.setAttribute('data-bs-theme', 'dark');
            localStorage.setItem('theme', 'sombre');
            if (icone) icone.className = 'bi bi-sun-fill';
        }
    });
}

document.addEventListener('DOMContentLoaded', initialiserBoutonTheme);
