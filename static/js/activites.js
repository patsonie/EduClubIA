// Page « Activités » : liste, recherche, filtre par statut et création (gestionnaires).
let toutesLesActivites = [];

// Couleur des badges selon le statut de l'activité.
const BADGES_STATUT = {
    planifiee: 'warning', validee: 'primary', en_cours: 'info',
    terminee: 'success', annulee: 'danger',
};

// Ligne du tableau d'une activité.
function ligneActivite(activite) {
    const couleur = BADGES_STATUT[activite.statut] || 'secondary';
    return `
        <tr>
            <td class="fw-medium">${echapperHTML(activite.titre)}</td>
            <td class="text-muted small">${echapperHTML(activite.club_nom)}</td>
            <td class="text-muted small">${activite.date}</td>
            <td class="text-muted small">${echapperHTML(activite.lieu)}</td>
            <td><span class="badge bg-${couleur}-subtle text-${couleur}">${echapperHTML(activite.statut)}</span></td>
            <td><a href="/activites/${activite.id}/" class="btn btn-sm btn-outline-secondary">Voir</a></td>
        </tr>`;
}

// Affiche la liste (ou un message si elle est vide).
function afficherActivites(activites) {
    const tbody = document.getElementById('tableau-activites');
    tbody.innerHTML = activites.length
        ? activites.map(ligneActivite).join('')
        : '<tr><td colspan="6" class="text-center text-muted py-4">Aucune activité trouvée.</td></tr>';
}

// Filtre côté navigateur par titre et par statut.
function filtrerActivites() {
    const recherche = document.getElementById('recherche-activite').value.toLowerCase();
    const statut = document.getElementById('filtre-statut-activite').value;

    const resultats = toutesLesActivites.filter(a => {
        const correspondRecherche = a.titre.toLowerCase().includes(recherche);
        const correspondStatut = !statut || a.statut === statut;
        return correspondRecherche && correspondStatut;
    });
    afficherActivites(resultats);
}

// Remplit la liste des clubs du formulaire de création.
async function remplirSelectClubs() {
    const data = await appelApi('/clubs/');
    const clubs = data.results || data;
    const select = document.getElementById('select-club-activite');
    select.innerHTML = clubs.map(c => `<option value="${c.id}">${c.nom}</option>`).join('');
}

// Charge les activités ; le bouton « Nouvelle activité » n'apparaît que pour les gestionnaires.
async function chargerActivites() {
    const profil = await appelApi('/auth/profil/');
    if (profil && ['administrateur', 'proviseur', 'encadreur'].includes(profil.role)) {
        document.getElementById('btn-nouvelle-activite').classList.remove('d-none');
        remplirSelectClubs();
    }

    const data = await appelApi('/activites/');
    toutesLesActivites = data.results || data;
    afficherActivites(toutesLesActivites);
}

// Recherche et filtre en direct.
document.getElementById('recherche-activite').addEventListener('input', filtrerActivites);
document.getElementById('filtre-statut-activite').addEventListener('change', filtrerActivites);

// Formulaire de création d'une activité.
document.getElementById('formulaire-nouvelle-activite').addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const donnees = Object.fromEntries(formData);
    const alerte = document.getElementById('alerte-erreur-activite');

    const resultat = await appelApi('/activites/', {
        method: 'POST',
        body: JSON.stringify(donnees),
    });

    if (resultat && resultat.id) {
        window.location.reload();
    } else {
        alerte.textContent = "Erreur lors de la création. Vérifiez les champs.";
        alerte.classList.remove('d-none');
    }
});

document.addEventListener('DOMContentLoaded', chargerActivites);