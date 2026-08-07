function carteRecommandationParent(reco, rang) {
    const medailles = ['🥇', '🥈', '🥉'];
    const medaille = rang < 3 ? medailles[rang] : '';
    const couleur = reco.score >= 70 ? '#22c55e' : reco.score >= 40 ? '#f59e0b' : '#ef4444';

    return `
        <div class="col-md-6 col-lg-4">
            <div class="carte p-4 h-100">
                <div class="d-flex justify-content-between align-items-start mb-2">
                    <h6 class="fw-semibold mb-0">${medaille} ${echapperHTML(reco.club_nom)}</h6>
                    <span class="badge" style="background-color: ${couleur}22; color: ${couleur};">${reco.score}%</span>
                </div>
                <p class="text-muted small mb-0">${echapperHTML(reco.explication)}</p>
            </div>
        </div>`;
}

async function chargerRecommandationsEnfant(eleveId) {
    const conteneur = document.getElementById('conteneur-recommandations-parent');
    conteneur.innerHTML = '<div class="col-12 text-center text-muted py-5">Chargement...</div>';

    const recommandations = await appelApi(`/recommandations/?eleve_id=${eleveId}`);
    conteneur.innerHTML = recommandations && recommandations.length
        ? recommandations.map(carteRecommandationParent).join('')
        : '<div class="col-12 text-center text-muted py-5">Aucune recommandation disponible pour cet enfant.</div>';
}

async function initialiserSelectEnfants() {
    const dashboard = await appelApi('/auth/dashboard-parent/');
    const select = document.getElementById('select-enfant-reco');

    if (!dashboard || dashboard.nombre_enfants === 0) {
        document.getElementById('conteneur-recommandations-parent').innerHTML =
            '<div class="col-12 text-center text-muted py-5">Aucun enfant associé à votre compte.</div>';
        return;
    }

    select.innerHTML = dashboard.enfants.map(e => `<option value="${e.id}">${e.nom_complet}</option>`).join('');
    select.addEventListener('change', (e) => chargerRecommandationsEnfant(e.target.value));
    chargerRecommandationsEnfant(dashboard.enfants[0].id);
}

document.addEventListener('DOMContentLoaded', initialiserSelectEnfants);
