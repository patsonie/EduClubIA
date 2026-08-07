const API_BASE = 'http://127.0.0.1:8000/api';

function obtenirToken() {
    return localStorage.getItem('access_token');
}

async function appelApi(endpoint, options = {}) {
    const token = obtenirToken();
    const reponse = await fetch(`${API_BASE}${endpoint}`, {
        ...options,
        headers: {
            'Content-Type': 'application/json',
            'Authorization': token ? `Bearer ${token}` : '',
            ...options.headers,
        },
    });

    if (reponse.status === 401) {
        window.location.href = '/connexion/';
        return null;
    }

    return reponse.json();
}

function afficherMenuSelonRole(role) {
    document.querySelectorAll('.menu-administrateur, .menu-proviseur, .menu-encadreur, .menu-eleve, .menu-parent')
        .forEach(el => el.classList.add('d-none'));

    const classeMenu = {
        administrateur: '.menu-administrateur',
        proviseur: '.menu-proviseur',
        encadreur: '.menu-encadreur',
        eleve: '.menu-eleve',
        parent: '.menu-parent',
    }[role];

    if (classeMenu) {
        document.querySelector(classeMenu)?.classList.remove('d-none');
    }
}

async function initialiserEntete() {
    const profil = await appelApi('/auth/profil/');
    if (!profil) return;

    document.getElementById('nom-utilisateur-connecte').textContent = profil.nom_complet;
    const initiales = document.getElementById('initiales-utilisateur');
    if (initiales) {
        initiales.textContent = `${profil.prenom[0] || ''}${profil.nom[0] || ''}`.toUpperCase();
    }
    afficherMenuSelonRole(profil.role);

    const notifications = await appelApi('/notifications/?lu=false');
    if (notifications && notifications.length > 0) {
        const badge = document.getElementById('badge-notifications');
        badge.textContent = notifications.length;
        badge.classList.remove('d-none');
    }
}

document.getElementById('lien-deconnexion')?.addEventListener('click', async (e) => {
    e.preventDefault();
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    window.location.href = '/connexion/';
});

document.addEventListener('DOMContentLoaded', initialiserEntete);

function surlignerLienActif() {
    const cheminActuel = window.location.pathname;
    document.querySelectorAll('.sidebar .nav-link').forEach(lien => {
        if (lien.getAttribute('href') === cheminActuel) {
            lien.classList.add('active');
        }
    });
}

document.addEventListener('DOMContentLoaded', surlignerLienActif);

function appliquerThemeInitial() {
    const themeSauvegarde = localStorage.getItem('theme') || 'clair';
    const icone = document.getElementById('icone-theme');
    if (themeSauvegarde === 'sombre') {
        document.documentElement.setAttribute('data-theme', 'dark');
        if (icone) icone.className = 'bi bi-sun-fill';
    } else {
        document.documentElement.removeAttribute('data-theme');
        if (icone) icone.className = 'bi bi-moon-fill';
    }
}

function initialiserSidebarMobile() {
    const sidebar = document.getElementById('sidebar-menu');
    const overlay = document.getElementById('overlay-sidebar');
    const btnOuvrir = document.getElementById('btn-ouvrir-sidebar');
    const btnFermer = document.getElementById('btn-fermer-sidebar');

    function ouvrirSidebar() {
        sidebar?.classList.add('ouverte');
        overlay?.classList.add('actif');
    }
    function fermerSidebar() {
        sidebar?.classList.remove('ouverte');
        overlay?.classList.remove('actif');
    }

    btnOuvrir?.addEventListener('click', ouvrirSidebar);
    btnFermer?.addEventListener('click', fermerSidebar);
    overlay?.addEventListener('click', fermerSidebar);

    // Ferme automatiquement le tiroir après avoir cliqué un lien (navigation mobile fluide)
    document.querySelectorAll('.sidebar .nav-link').forEach(lien => {
        lien.addEventListener('click', fermerSidebar);
    });
}

document.addEventListener('DOMContentLoaded', initialiserSidebarMobile);

function rendreTableauxResponsives() {
    document.querySelectorAll('table.table').forEach(table => {
        if (table.parentElement.classList.contains('table-responsive')) return;
        const enveloppe = document.createElement('div');
        enveloppe.className = 'table-responsive';
        table.parentNode.insertBefore(enveloppe, table);
        enveloppe.appendChild(table);
    });
}

document.addEventListener('DOMContentLoaded', rendreTableauxResponsives);

/**
 * Échappe les caractères HTML dangereux d'une chaîne avant insertion via innerHTML.
 * À utiliser systématiquement pour tout texte venant de l'API (créé par un utilisateur :
 * nom de club, description, message de chat, titre d'activité, etc.), afin d'empêcher
 * l'injection de scripts malveillants (XSS stocké).
 */
function echapperHTML(texte) {
    if (texte === null || texte === undefined) return '';
    const div = document.createElement('div');
    div.textContent = String(texte);
    return div.innerHTML;
}