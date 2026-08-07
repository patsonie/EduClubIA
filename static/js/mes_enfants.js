function badgeCategorie(categorie) {
    const couleurs = {
        scientifique: 'primary', sportif: 'success', culturel: 'warning',
        artistique: 'danger', technologique: 'info', humanitaire: 'secondary',
    };
    return `<span class="badge bg-${couleurs[categorie] || 'secondary'}-subtle text-${couleurs[categorie] || 'secondary'} border">${categorie}</span>`;
}

function creerCarteEnfant(enfant) {
    const clubsHtml = enfant.clubs.length
        ? enfant.clubs.map(c => `<span class="me-1 mb-1 d-inline-block">${badgeCategorie(c.categorie)} ${echapperHTML(c.nom)}</span>`).join('')
        : '<span class="text-muted small">Aucun club rejoint pour le moment.</span>';

    const activitesHtml = enfant.activites_a_venir.length
        ? enfant.activites_a_venir.map(a => `
            <li class="list-group-item px-0 d-flex justify-content-between align-items-center">
                <div>
                    <div class="fw-medium small">${echapperHTML(a.titre)}</div>
                    <div class="text-muted" style="font-size: 0.78rem;">${echapperHTML(a.lieu)} · ${a.heure}</div>
                </div>
                <span class="badge bg-light text-dark border">${a.date}</span>
            </li>`).join('')
        : '<li class="list-group-item px-0 text-muted small">Aucune activité à venir.</li>';

    const tauxPresence = enfant.taux_presence !== null ? `${enfant.taux_presence}%` : 'N/A';
    const couleurTaux = enfant.taux_presence === null ? 'secondary' : (enfant.taux_presence >= 75 ? 'success' : enfant.taux_presence >= 50 ? 'warning' : 'danger');

    const recommandationsHtml = enfant.recommandations.length
        ? enfant.recommandations.slice(0, 3).map(r => `
            <li class="list-group-item px-0">
                <div class="d-flex justify-content-between">
                    <span class="fw-medium small">${echapperHTML(r.club)}</span>
                    <span class="badge bg-primary-subtle text-primary">${r.score}%</span>
                </div>
                <div class="text-muted" style="font-size: 0.78rem;">${echapperHTML(r.explication)}</div>
            </li>`).join('')
        : '<li class="list-group-item px-0 text-muted small">Aucune recommandation pour l\'instant.</li>';

    return `
        <div class="col-lg-6">
            <div class="carte p-4 h-100">
                <div class="d-flex justify-content-between align-items-start mb-3">
                    <div>
                        <h5 class="fw-semibold mb-0">${echapperHTML(enfant.nom_complet)}</h5>
                        <span class="text-muted small">${echapperHTML(enfant.classe || 'Classe non renseignée')}</span>
                    </div>
                    <div class="text-center">
                        <div class="fw-bold text-${couleurTaux}">${tauxPresence}</div>
                        <div class="text-muted" style="font-size: 0.72rem;">Présence</div>
                    </div>
                </div>
                <div class="mb-3">
                    <div class="fw-medium small text-muted mb-1">CLUBS</div>
                    ${clubsHtml}
                </div>
                <div class="mb-3">
                    <div class="fw-medium small text-muted mb-1">ACTIVITÉS À VENIR</div>
                    <ul class="list-group list-group-flush">${activitesHtml}</ul>
                </div>
                <div>
                    <div class="fw-medium small text-muted mb-1">RECOMMANDATIONS IA</div>
                    <ul class="list-group list-group-flush">${recommandationsHtml}</ul>
                </div>
            </div>
        </div>`;
}

async function chargerMesEnfants() {
    const data = await appelApi('/auth/dashboard-parent/');
    const conteneur = document.getElementById('conteneur-enfants');

    if (!data || data.nombre_enfants === 0) {
        conteneur.innerHTML = `
            <div class="col-12 text-center text-muted py-5">
                <i class="bi bi-emoji-neutral" style="font-size: 2rem;"></i>
                <p class="mt-2">Aucun enfant n'est encore associé à votre compte.<br>Contactez l'administration pour lier votre profil à celui de votre enfant.</p>
            </div>`;
        return;
    }

    conteneur.innerHTML = data.enfants.map(creerCarteEnfant).join('');
}

document.addEventListener('DOMContentLoaded', chargerMesEnfants);