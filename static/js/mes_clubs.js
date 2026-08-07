async function chargerMesClubs() {
    const inscriptions = await appelApi('/inscriptions/?statut=validee');
    const data = inscriptions.results || inscriptions;
    const conteneur = document.getElementById('conteneur-mes-clubs');

    if (!data || data.length === 0) {
        conteneur.innerHTML = '<div class="col-12 text-center text-muted py-5">Vous n\'êtes inscrit à aucun club pour le moment.</div>';
        return;
    }

    conteneur.innerHTML = data.map(i => `
        <div class="col-md-6 col-lg-4">
            <div class="carte p-3 h-100">
                <h6 class="fw-semibold mb-1">${echapperHTML(i.club_nom)}</h6>
                <div class="text-muted small mb-2">Année scolaire : ${echapperHTML(i.annee_scolaire_libelle)}</div>
                <a href="/clubs/${i.club}/" class="btn btn-sm btn-outline-secondary">Voir le club</a>
            </div>
        </div>`).join('');
}
document.addEventListener('DOMContentLoaded', chargerMesClubs);
