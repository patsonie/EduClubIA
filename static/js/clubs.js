let tousLesClubs = [];
let roleUtilisateur = null;

function badgeCategorieClub(categorie) {
    const couleurs = {
        scientifique: 'primary', sportif: 'success', culturel: 'warning',
        artistique: 'danger', technologique: 'info', humanitaire: 'secondary', autre: 'dark',
    };
    return couleurs[categorie] || 'secondary';
}

function creerCarteClub(club) {
    const couleur = badgeCategorieClub(club.categorie);
    const placesRestantes = club.nombre_max_membres - club.nombre_membres_actuels;

    return `
        <div class="col-md-6 col-lg-4">
            <div class="carte p-3 h-100">
                <div class="d-flex justify-content-between align-items-start mb-2">
                    <h6 class="fw-semibold mb-0">${echapperHTML(club.nom)}</h6>
                    <span class="badge bg-${couleur}-subtle text-${couleur} border">${echapperHTML(club.categorie)}</span>
                </div>
                <p class="text-muted small mb-2" style="min-height: 40px;">
                    ${club.responsable_nom ? `Responsable : ${echapperHTML(club.responsable_nom)}` : 'Aucun responsable assigné'}
                </p>
                <div class="d-flex justify-content-between align-items-center">
                    <span class="small ${placesRestantes <= 0 ? 'text-danger' : 'text-success'}">
                        ${club.nombre_membres_actuels} / ${club.nombre_max_membres} membres
                    </span>
                    <a href="/clubs/${club.id}/" class="btn btn-sm btn-outline-secondary">Voir</a>
                </div>
            </div>
        </div>`;
}

function afficherClubs(clubs) {
    const conteneur = document.getElementById('conteneur-clubs');
    if (clubs.length === 0) {
        conteneur.innerHTML = '<div class="col-12 text-center text-muted py-5">Aucun club trouvé.</div>';
        return;
    }
    conteneur.innerHTML = clubs.map(creerCarteClub).join('');
}

function filtrerClubs() {
    const recherche = document.getElementById('recherche-club').value.toLowerCase();
    const categorie = document.getElementById('filtre-categorie').value;

    const resultats = tousLesClubs.filter(c => {
        const correspondRecherche = c.nom.toLowerCase().includes(recherche);
        const correspondCategorie = !categorie || c.categorie === categorie;
        return correspondRecherche && correspondCategorie;
    });

    afficherClubs(resultats);
}

async function chargerClubs() {
    const profil = await appelApi('/auth/profil/');
    roleUtilisateur = profil?.role;

    if (['administrateur', 'proviseur'].includes(roleUtilisateur)) {
        document.getElementById('btn-nouveau-club').classList.remove('d-none');
    }

    const data = await appelApi('/clubs/');
    tousLesClubs = data.results || data;
    afficherClubs(tousLesClubs);
}

document.getElementById('recherche-club').addEventListener('input', filtrerClubs);
document.getElementById('filtre-categorie').addEventListener('change', filtrerClubs);

document.getElementById('formulaire-nouveau-club').addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const donnees = Object.fromEntries(formData);
    const alerte = document.getElementById('alerte-erreur-club');

    const resultat = await appelApi('/clubs/', {
        method: 'POST',
        body: JSON.stringify(donnees),
    });

    if (resultat && resultat.id) {
        window.location.reload();
    } else {
        alerte.textContent = "Erreur lors de la création du club. Vérifiez les champs.";
        alerte.classList.remove('d-none');
    }
});

document.addEventListener('DOMContentLoaded', chargerClubs);