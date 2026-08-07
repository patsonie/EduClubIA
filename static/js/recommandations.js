function jaugeScore(score) {
    const couleur = score >= 70 ? '#22c55e' : score >= 40 ? '#f59e0b' : '#ef4444';
    return `
        <div class="d-flex align-items-center gap-2 mb-1">
            <div class="flex-grow-1 rounded-pill" style="height: 6px; background-color: #eee;">
                <div class="rounded-pill" style="height: 6px; width: ${score}%; background-color: ${couleur};"></div>
            </div>
            <span class="fw-semibold small" style="color: ${couleur};">${score}%</span>
        </div>`;
}

function carteRecommandation(reco, rang) {
    const medailles = ['🥇', '🥈', '🥉'];
    const medaille = rang < 3 ? medailles[rang] : '';

    return `
        <div class="col-md-6 col-lg-4">
            <div class="carte p-4 h-100">
                <div class="d-flex justify-content-between align-items-start mb-2">
                    <h6 class="fw-semibold mb-0">${medaille} ${echapperHTML(reco.club_nom)}</h6>
                    <span class="badge bg-primary-subtle text-primary">${echapperHTML(reco.club_categorie)}</span>
                </div>
                ${jaugeScore(reco.score)}
                <p class="text-muted small mt-2 mb-3">${echapperHTML(reco.explication)}</p>
                <a href="/clubs/${reco.club}/" class="btn btn-sm btn-primaire-app w-100">Découvrir ce club</a>
            </div>
        </div>`;
}

async function chargerRecommandations() {
    const recommandations = await appelApi('/recommandations/');
    const conteneur = document.getElementById('conteneur-recommandations');

    if (!recommandations || recommandations.length === 0) {
        conteneur.innerHTML = `
            <div class="col-12 text-center text-muted py-5">
                <i class="bi bi-emoji-neutral" style="font-size: 2rem;"></i>
                <p class="mt-2">Aucune recommandation disponible pour l'instant.<br>
                Complétez vos centres d'intérêt dans <a href="/parametres/">votre profil</a> pour obtenir des suggestions personnalisées.</p>
            </div>`;
        return;
    }

    conteneur.innerHTML = recommandations.map((r, i) => carteRecommandation(r, i)).join('');
}

document.addEventListener('DOMContentLoaded', chargerRecommandations);
