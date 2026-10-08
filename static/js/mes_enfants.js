// Page « Mes enfants » (parent) : fiche de chaque enfant rattaché et demandes de rattachement.
// Badge coloré de la catégorie d'un club.
function badgeCategorie(categorie) {
    const couleurs = {
        scientifique: 'primary', sportif: 'success', culturel: 'warning',
        artistique: 'danger', technologique: 'info', humanitaire: 'secondary',
    };
    return `<span class="badge bg-${couleurs[categorie] || 'secondary'}-subtle text-${couleurs[categorie] || 'secondary'} border">${categorie}</span>`;
}

// Carte d'un enfant : clubs, activités à venir, taux de présence et recommandations IA.
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

// Charge le tableau de bord du parent (enfants dont le lien est validé).
async function chargerMesEnfants() {
    const data = await appelApi('/auth/dashboard-parent/');
    const conteneur = document.getElementById('conteneur-enfants');

    // Bandeau des demandes de rattachement encore en attente.
    const bandeau = document.getElementById('bandeau-demandes');
    if (data && data.demandes_en_attente && data.demandes_en_attente.length) {
        bandeau.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>Rattachement en attente de validation par le responsable pédagogique pour : '
            + data.demandes_en_attente.map(echapperHTML).join(', ') + '.';
        bandeau.classList.remove('d-none');
    } else {
        bandeau.classList.add('d-none');
    }

    if (!data || data.nombre_enfants === 0) {
        conteneur.innerHTML = `
            <div class="col-12 text-center text-muted py-5">
                <i class="bi bi-emoji-neutral" style="font-size: 2rem;"></i>
                <p class="mt-2">Aucun enfant n'est encore associé à votre compte.<br>Utilisez le formulaire « Rattacher mon enfant » ci-dessus.</p>
            </div>`;
        return;
    }

    conteneur.innerHTML = data.enfants.map(creerCarteEnfant).join('');
}

// ---------- Formulaires de demande de rattachement ----------

/** Affiche le résultat d'une demande sous le formulaire (vert : envoyée, rouge : erreur). */
function afficherRetourRattachement(texte, succes) {
    const zone = document.getElementById('retour-rattachement');
    zone.textContent = texte;
    zone.className = `small mt-3 ${succes ? 'text-success' : 'text-danger'}`;
}

/** Premier message lisible d'une réponse d'erreur de l'API. */
function messageErreurRattachement(resultat) {
    if (!resultat) return "Envoi impossible. Réessayez plus tard.";
    const valeur = resultat.detail || resultat.error || Object.values(resultat)[0];
    return (Array.isArray(valeur) ? valeur.join(' ') : valeur) || "Envoi impossible.";
}

/** Envoie le formulaire vers l'API puis rafraîchit le bandeau des demandes. */
async function envoyerDemandeRattachement(formulaire, adresse, donnees, succesAttendu) {
    const bouton = formulaire.querySelector('button[type="submit"]');
    bouton.disabled = true;
    const resultat = await appelApi(adresse, { method: 'POST', body: JSON.stringify(donnees) });
    bouton.disabled = false;
    if (resultat && succesAttendu(resultat)) {
        afficherRetourRattachement(resultat.message || "Demande envoyée au responsable pédagogique.", true);
        formulaire.reset();
        chargerMesEnfants();
    } else {
        afficherRetourRattachement(messageErreurRattachement(resultat), false);
    }
}

// Par matricule : la réponse est toujours la même (le serveur ne dit pas si le matricule existe).
document.getElementById('rattachement-matricule').addEventListener('submit', (e) => {
    e.preventDefault();
    const matricule = e.target.matricule.value.trim();
    if (!matricule) return afficherRetourRattachement("Indiquez le matricule de votre enfant.", false);
    envoyerDemandeRattachement(e.target, '/auth/mes-enfants/associer/', { matricule }, r => Boolean(r.message));
});

// Par nom : le responsable pédagogique retrouvera l'élève dans l'établissement.
document.getElementById('rattachement-nom').addEventListener('submit', (e) => {
    e.preventDefault();
    const f = e.target;
    const donnees = {
        nom_complet_enfant: f.nom_complet_enfant.value.trim(),
        classe: f.classe.value.trim(),
        message: f.message.value.trim(),
    };
    if (!donnees.nom_complet_enfant) return afficherRetourRattachement("Indiquez le nom et le prénom de votre enfant.", false);
    envoyerDemandeRattachement(f, '/auth/demandes-rattachement/', donnees, r => Boolean(r.id));
});

document.addEventListener('DOMContentLoaded', chargerMesEnfants);