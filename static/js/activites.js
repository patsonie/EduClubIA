let toutesLesActivites = [];

const BADGES_STATUT = {
    planifiee: 'warning', validee: 'primary', en_cours: 'info',
    terminee: 'success', annulee: 'danger',
};

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

function afficherActivites(activites) {
    const tbody = document.getElementById('tableau-activites');
    tbody.innerHTML = activites.length
        ? activites.map(ligneActivite).join('')
        : '<tr><td colspan="6" class="text-center text-muted py-4">Aucune activité trouvée.</td></tr>';
}

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

async function remplirSelectClubs() {
    const data = await appelApi('/clubs/');
    const clubs = data.results || data;
    const select = document.getElementById('select-club-activite');
    select.innerHTML = clubs.map(c => `<option value="${c.id}">${c.nom}</option>`).join('');
}

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

document.getElementById('recherche-activite').addEventListener('input', filtrerActivites);
document.getElementById('filtre-statut-activite').addEventListener('change', filtrerActivites);

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