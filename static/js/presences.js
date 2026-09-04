// Références aux éléments de l'interface et à l'activité courante.
let activiteSelectionneeId = null;

const selectActivite = document.getElementById('select-activite-presence');
const conteneurPresence = document.getElementById('conteneur-presence');
const tableauPresences = document.getElementById('tableau-presences');
const boutonEnregistrer = document.getElementById('btn-enregistrer-presences');
const etatChargement = document.getElementById('etat-chargement-presences');
const etatEnregistrement = document.getElementById('etat-enregistrement-presences');

// Construit une ligne de tableau pour un élève inscrit à l'activité.
function ligneParticipant(participant) {
    const statut = participant.statut || 'present';
    return `
        <tr class="ligne-participant" data-inscription="${participant.inscription_id}">
            <td class="fw-medium">${echapperHTML(participant.eleve_nom)}</td>
            <td class="text-muted small">${echapperHTML(participant.classe || 'Non renseignée')}</td>
            <td class="text-lg-end">
                <select class="form-select form-select-sm select-statut-presence ms-lg-auto" aria-label="Statut de présence de ${echapperHTML(participant.eleve_nom)}" style="max-width: 180px;">
                    <option value="present" ${statut === 'present' ? 'selected' : ''}>Présent</option>
                    <option value="absent" ${statut === 'absent' ? 'selected' : ''}>Absent</option>
                    <option value="retard" ${statut === 'retard' ? 'selected' : ''}>En retard</option>
                    <option value="excuse" ${statut === 'excuse' ? 'selected' : ''}>Absence excusée</option>
                </select>
            </td>
        </tr>`;
}

// Met à jour le résumé à partir des sélections actuelles.
function mettreAJourCompteurs() {
    const statuts = Array.from(document.querySelectorAll('.select-statut-presence')).map(select => select.value);
    document.getElementById('compteur-presents').textContent = statuts.filter(statut => statut === 'present').length;
    document.getElementById('compteur-absents').textContent = statuts.filter(statut => statut === 'absent').length;
    document.getElementById('compteur-autres').textContent = statuts.filter(statut => statut === 'retard' || statut === 'excuse').length;
}

// Affiche un retour discret après une action utilisateur.
function afficherEtat(message, classe = 'text-muted') {
    etatEnregistrement.textContent = message;
    etatEnregistrement.className = `etat-enregistrement small mb-0 ${classe}`;
}

// Charge les activités proposées dans la liste déroulante.
async function chargerListeActivites() {
    etatChargement.textContent = 'Chargement des activités…';
    const data = await appelApi('/activites/');
    if (!data) return;

    const activites = data.results || data;
    selectActivite.innerHTML = '<option value="">Sélectionnez une activité</option>' + activites.map(activite =>
        `<option value="${activite.id}">${echapperHTML(activite.titre)} — ${echapperHTML(activite.club_nom)} (${echapperHTML(activite.date)})</option>`
    ).join('');
    etatChargement.textContent = activites.length
        ? `${activites.length} activité(s) disponible(s).`
        : 'Aucune activité disponible.';
}

// Récupère les élèves attendus et initialise leurs statuts.
async function chargerParticipants(activiteId) {
    boutonEnregistrer.disabled = true;
    tableauPresences.innerHTML = '<tr><td colspan="3" class="text-center text-muted py-4"><span class="spinner-border spinner-border-sm me-2" aria-hidden="true"></span>Chargement des élèves…</td></tr>';
    conteneurPresence.classList.remove('d-none');
    afficherEtat('');

    const participants = await appelApi(`/activites/${activiteId}/participants_attendus/`);
    if (!participants) return;

    tableauPresences.innerHTML = participants.length
        ? participants.map(ligneParticipant).join('')
        : '<tr><td colspan="3" class="text-center text-muted py-4">Aucun élève validé n’est inscrit au club de cette activité.</td></tr>';
    boutonEnregistrer.disabled = participants.length === 0;
    document.querySelectorAll('.select-statut-presence').forEach(select => select.addEventListener('change', mettreAJourCompteurs));
    mettreAJourCompteurs();
}

// Recharge la liste lorsque le responsable choisit une activité.
selectActivite.addEventListener('change', async event => {
    activiteSelectionneeId = event.target.value;
    const option = event.target.options[event.target.selectedIndex];
    document.getElementById('titre-activite-selectionnee').textContent = activiteSelectionneeId ? option.textContent : '—';

    if (!activiteSelectionneeId) {
        conteneurPresence.classList.add('d-none');
        return;
    }
    await chargerParticipants(activiteSelectionneeId);
});

// Envoie tous les statuts en une seule requête à l'API.
boutonEnregistrer.addEventListener('click', async () => {
    const presences = Array.from(document.querySelectorAll('#tableau-presences tr[data-inscription]')).map(ligne => ({
        inscription: Number(ligne.dataset.inscription),
        statut: ligne.querySelector('.select-statut-presence').value,
    }));
    if (!activiteSelectionneeId || !presences.length) return;

    boutonEnregistrer.disabled = true;
    afficherEtat('Enregistrement en cours…');
    const resultat = await appelApi('/participations/enregistrer_lot/', {
        method: 'POST',
        body: JSON.stringify({ activite: activiteSelectionneeId, presences }),
    });
    boutonEnregistrer.disabled = false;

    if (resultat?.message) {
        afficherEtat(resultat.message, 'text-success');
    } else {
        afficherEtat('L’enregistrement a échoué. Veuillez réessayer.', 'text-danger');
    }
});

// Lance le chargement initial une fois la page prête.
document.addEventListener('DOMContentLoaded', chargerListeActivites);
