async function chargerClubsEnfant(eleveId) {
    const conteneur = document.getElementById('conteneur-clubs-enfant');
    conteneur.innerHTML = '<div class="col-12 text-center text-muted py-5">Chargement...</div>';

    const data = await appelApi(`/inscriptions/?eleve=${eleveId}&statut=validee`);
    const inscriptions = data.results || data;

    conteneur.innerHTML = inscriptions.length
        ? inscriptions.map(i => `
            <div class="col-md-6 col-lg-4">
                <div class="carte p-3 h-100">
                    <h6 class="fw-semibold mb-1">${echapperHTML(i.club_nom)}</h6>
                    <div class="text-muted small mb-2">Depuis le ${new Date(i.date_inscription).toLocaleDateString('fr-FR')}</div>
                    <a href="/clubs/${i.club}/" class="btn btn-sm btn-outline-secondary">Voir le club</a>
                </div>
            </div>`).join('')
        : '<div class="col-12 text-center text-muted py-5">Aucun club rejoint pour le moment.</div>';
}

async function initialiserSelectEnfantsClubs() {
    const dashboard = await appelApi('/auth/dashboard-parent/');
    const select = document.getElementById('select-enfant-clubs');

    if (!dashboard || dashboard.nombre_enfants === 0) {
        document.getElementById('conteneur-clubs-enfant').innerHTML =
            '<div class="col-12 text-center text-muted py-5">Aucun enfant associé à votre compte.</div>';
        return;
    }

    select.innerHTML = dashboard.enfants.map(e => `<option value="${e.id}">${e.nom_complet}</option>`).join('');
    select.addEventListener('change', (e) => chargerClubsEnfant(e.target.value));
    chargerClubsEnfant(dashboard.enfants[0].id);
}

document.addEventListener('DOMContentLoaded', initialiserSelectEnfantsClubs);