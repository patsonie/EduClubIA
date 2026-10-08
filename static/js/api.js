// Outils communs à toutes les pages connectées (chargé par base.html) :
// appels à l'API avec le jeton JWT, menu selon le rôle, déconnexion, thème, protection XSS.
// Adresse de base de l'API (même domaine que le site).
const API_BASE = window.location.origin + '/api';

// Jeton d'accès JWT conservé dans le navigateur après la connexion.
function obtenirToken() {
    return localStorage.getItem('access_token');
}

// Évite de lancer plusieurs renouvellements de jeton en même temps.
let rafraichissementEnCours = null;

/** Obtient un nouvel access token à partir du refresh token (rotation incluse). */
async function rafraichirToken() {
    const refresh = localStorage.getItem('refresh_token');
    if (!refresh) return false;
    if (!rafraichissementEnCours) {
        rafraichissementEnCours = (async () => {
            try {
                const reponse = await fetch(`${API_BASE}/auth/refresh/`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ refresh }),
                });
                if (!reponse.ok) return false;
                const donnees = await reponse.json();
                localStorage.setItem('access_token', donnees.access);
                if (donnees.refresh) localStorage.setItem('refresh_token', donnees.refresh);
                return true;
            } catch (e) {
                return false;
            } finally {
                setTimeout(() => { rafraichissementEnCours = null; }, 0);
            }
        })();
    }
    return rafraichissementEnCours;
}

// Efface les jetons et renvoie vers la page de connexion.
function redirigerVersConnexion() {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    window.location.href = '/connexion/';
}

// Fonction centrale pour appeler l'API : ajoute le jeton, gère l'expiration (401)
// et renvoie la réponse JSON. Utilisée par tous les scripts de pages.
async function appelApi(endpoint, options = {}, dejaRafraichi = false) {
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
        // Token expiré : une seule tentative de renouvellement avant de renvoyer à la connexion.
        if (!dejaRafraichi && await rafraichirToken()) {
            return appelApi(endpoint, options, true);
        }
        redirigerVersConnexion();
        return null;
    }

    try {
        return await reponse.json();
    } catch (e) {
        // Réponse sans corps JSON (204, erreur serveur HTML...)
        return reponse.ok ? {} : { error: `Erreur ${reponse.status}` };
    }
}

// Affiche uniquement le menu latéral correspondant au rôle de l'utilisateur.
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

// En-tête de page : nom et initiales de l'utilisateur, menu du rôle, badge des notifications non lues.
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

// Bouton « Déconnexion ».
document.getElementById('lien-deconnexion')?.addEventListener('click', async (e) => {
    e.preventDefault();
    // Révocation côté serveur du refresh token (blacklist), puis nettoyage local.
    const refresh = localStorage.getItem('refresh_token');
    if (refresh) {
        try {
            await fetch(`${API_BASE}/auth/logout/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${obtenirToken()}`,
                },
                body: JSON.stringify({ refresh }),
            });
        } catch (err) { /* déconnexion locale malgré tout */ }
    }
    redirigerVersConnexion();
});

document.addEventListener('DOMContentLoaded', initialiserEntete);

// Met en évidence, dans le menu latéral, le lien de la page actuelle.
function surlignerLienActif() {
    const cheminActuel = window.location.pathname;
    document.querySelectorAll('.sidebar .nav-link').forEach(lien => {
        if (lien.getAttribute('href') === cheminActuel) {
            lien.classList.add('active');
        }
    });
}

document.addEventListener('DOMContentLoaded', surlignerLienActif);

// Thème clair/sombre mémorisé dans le navigateur.
function appliquerThemeInitial() {
    const themeSauvegarde = localStorage.getItem('theme') || 'clair';
    const icone = document.getElementById('icone-theme');
    if (themeSauvegarde === 'sombre') {
        document.documentElement.setAttribute('data-theme', 'dark');
        document.documentElement.setAttribute('data-bs-theme', 'dark');
        if (icone) icone.className = 'bi bi-sun-fill';
    } else {
        document.documentElement.removeAttribute('data-theme');
        document.documentElement.removeAttribute('data-bs-theme');
        if (icone) icone.className = 'bi bi-moon-fill';
    }
}

// Menu latéral sur mobile : ouverture/fermeture du tiroir.
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

// Rend tous les tableaux défilables horizontalement sur petit écran.
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
