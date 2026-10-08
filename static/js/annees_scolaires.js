// Page « Années scolaires » (administrateur et responsable pédagogique) :
// création, activation, désactivation et suppression des années scolaires.

/** Premier message lisible d'une réponse d'erreur de l'API. */
function messageErreurAnnee(resultat, defaut) {
    if (!resultat) return defaut;
    const valeur = resultat.detail || resultat.error || resultat.non_field_errors || Object.values(resultat)[0];
    return (Array.isArray(valeur) ? valeur.join(' ') : valeur) || defaut;
}

/** Date AAAA-MM-JJ affichée au format français. */
function dateFr(texte) {
    return texte ? new Date(texte + 'T00:00:00').toLocaleDateString('fr-FR') : '-';
}

// Ligne d'une année : boutons selon son état (active → désactiver ; sinon → activer, supprimer).
function ligneAnnee(annee) {
    const statut = annee.est_active
        ? '<span class="badge bg-success-subtle text-success">Active</span>'
        : '<span class="badge bg-secondary-subtle text-secondary">Inactive</span>';
    const actions = annee.est_active
        ? `<button class="btn btn-sm btn-refuser-action btn-action-annee" data-action="desactiver" data-id="${annee.id}">
               <i class="bi bi-pause-circle me-1"></i>Désactiver
           </button>`
        : `<button class="btn btn-sm btn-valider-action btn-action-annee" data-action="activer" data-id="${annee.id}">
               <i class="bi bi-play-circle me-1"></i>Activer
           </button>
           <button class="btn btn-sm btn-light btn-action-annee" data-action="supprimer" data-id="${annee.id}" title="Supprimer">
               <i class="bi bi-trash"></i>
           </button>`;
    return `
        <tr>
            <td class="fw-medium">${echapperHTML(annee.libelle)}</td>
            <td class="small text-muted">${dateFr(annee.date_debut)}</td>
            <td class="small text-muted">${dateFr(annee.date_fin)}</td>
            <td>${statut}</td>
            <td><div class="d-flex gap-2 justify-content-end flex-wrap">${actions}</div></td>
        </tr>`;
}

// Charge les années et met à jour le bandeau (année active ou inscriptions fermées).
async function chargerAnnees() {
    const data = await appelApi('/annees-scolaires/');
    const annees = (data && (data.results || data)) || [];
    const tbody = document.getElementById('tableau-annees');
    tbody.innerHTML = annees.length
        ? annees.map(ligneAnnee).join('')
        : '<tr><td colspan="5" class="text-center text-muted py-4">Aucune année scolaire. Créez-en une pour ouvrir les inscriptions.</td></tr>';

    const active = annees.find(a => a.est_active);
    const bandeau = document.getElementById('bandeau-annee-active');
    bandeau.className = `alert ${active ? 'alert-success' : 'alert-warning'}`;
    bandeau.innerHTML = active
        ? `<i class="bi bi-check-circle me-2"></i>Année active : <strong>${echapperHTML(active.libelle)}</strong>. Les inscriptions aux clubs sont ouvertes.`
        : '<i class="bi bi-exclamation-triangle me-2"></i>Aucune année scolaire active : les élèves ne peuvent pas s\'inscrire aux clubs.';
}

// Actions sur une année (activer, désactiver, supprimer) avec confirmation.
const QUESTIONS_ACTION = {
    activer: "Activer cette année ? Les inscriptions des années précédentes seront archivées.",
    desactiver: "Désactiver cette année ? Les élèves ne pourront plus s'inscrire aux clubs.",
    supprimer: "Supprimer cette année scolaire ?",
};

document.addEventListener('click', async (e) => {
    const bouton = e.target.closest('.btn-action-annee');
    if (!bouton) return;
    const { action, id } = bouton.dataset;
    if (!confirm(QUESTIONS_ACTION[action])) return;
    bouton.disabled = true;
    const resultat = action === 'supprimer'
        ? await appelApi(`/annees-scolaires/${id}/`, { method: 'DELETE' })
        : await appelApi(`/annees-scolaires/${id}/${action}/`, { method: 'POST' });
    if (resultat && (resultat.error || resultat.detail)) alert(messageErreurAnnee(resultat, "Action impossible."));
    chargerAnnees();
});

// Création d'une année, activée tout de suite si la case est cochée.
document.getElementById('formulaire-nouvelle-annee').addEventListener('submit', async (e) => {
    e.preventDefault();
    const f = e.target;
    const alerte = document.getElementById('alerte-erreur-annee');
    alerte.classList.add('d-none');
    const donnees = {
        libelle: f.libelle.value.trim(), date_debut: f.date_debut.value, date_fin: f.date_fin.value,
    };
    if (!donnees.libelle || !donnees.date_debut || !donnees.date_fin) {
        alerte.textContent = 'Renseignez le libellé et les deux dates.';
        alerte.classList.remove('d-none');
        return;
    }
    const resultat = await appelApi('/annees-scolaires/', { method: 'POST', body: JSON.stringify(donnees) });
    if (!resultat || !resultat.id) {
        alerte.textContent = messageErreurAnnee(resultat, "Création impossible. Vérifiez les champs.");
        alerte.classList.remove('d-none');
        return;
    }
    if (document.getElementById('champ-activer-annee').checked) {
        await appelApi(`/annees-scolaires/${resultat.id}/activer/`, { method: 'POST' });
    }
    bootstrap.Modal.getInstance(document.getElementById('modalNouvelleAnnee'))?.hide();
    f.reset();
    chargerAnnees();
});

document.addEventListener('DOMContentLoaded', chargerAnnees);
