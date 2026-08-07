let participantsActuels = [];
let activiteSelectionneeId = null;

const LIBELLES_STATUT = { present: 'Présent', absent: 'Absent', excuse: 'Excusé', retard: 'Retard' };

function ligneParticipant(participant) {
    return `
        <tr data-inscription="${participant.inscription_id}">
            <td class="fw-medium">${echapperHTML(participant.eleve_nom)}</td>
            <td class="text-muted small">${echapperHTML(participant.classe || '-')}</td>
            <td>
                <select class="form-select form-select-sm select-statut-presence" style="width: 150px;">
                    <option value="present" ${participant.statut === 'present' ? 'selected' : ''}>Présent</option>
                    <option value="absent" ${participant.statut === 'absent' ? 'selected' : ''}>Absent</option>
                    <option value="excuse" ${participant.statut === 'excuse' ? 'selected' : ''}>Excusé</option>
                    <option value="retard" ${participant.statut === 'retard' ? 'selected' : ''}>Retard</option>
                </select>
            </td>
        </tr>`;
}

function mettreAJourCompteurs() {
    const selects = document.querySelectorAll('.select-statut-presence');
    let presents = 0, absents = 0;
    selects.forEach(s => {
        if (s.value === 'present') presents++;
        if (s.value === 'absent') absents++;
    });
    document.getElementById('compteur-presents').textContent = presents;
    document.getElementById('compteur-absents').textContent = absents;
}

async function chargerListeActivites() {
    const data = await appelApi('/activites/');
    const activites = data.results || data;
    const select = document.getElementById('select-activite-presence');
    select.innerHTML = '<option value="">Sélectionnez une activité</option>' +
        activites.map(a => `<option value="${a.id}">${echapperHTML(a.titre)} — ${echapperHTML(a.club_nom)} (${a.date})</option>`).join('');
}

async function chargerParticipants(activiteId) {
    const participants = await appelApi(`/activites/${activiteId}/participants_attendus/`);
    participantsActuels = participants || [];

    document.getElementById('conteneur-presence').classList.remove('d-none');
    document.getElementById('tableau-presences').innerHTML = participantsActuels.length
        ? participantsActuels.map(ligneParticipant).join('')
        : '<tr><td colspan="3" class="text-center text-muted py-3">Aucun élève inscrit à ce club.</td></tr>';

    document.querySelectorAll('.select-statut-presence').forEach(s => s.addEventListener('change', mettreAJourCompteurs));
    mettreAJourCompteurs();
}

document.getElementById('select-activite-presence').addEventListener('change', (e) => {
    activiteSelectionneeId = e.target.value;
    const optionTexte = e.target.options[e.target.selectedIndex].text;
    document.getElementById('titre-activite-selectionnee').textContent = optionTexte;
    if (activiteSelectionneeId) chargerParticipants(activiteSelectionneeId);
});

document.getElementById('btn-enregistrer-presences').addEventListener('click', async () => {
    const lignes = document.querySelectorAll('#tableau-presences tr[data-inscription]');
    const presences = Array.from(lignes).map(ligne => ({
        inscription: parseInt(ligne.dataset.inscription),
        statut: ligne.querySelector('.select-statut-presence').value,
    }));

    const resultat = await appelApi('/participations/enregistrer_lot/', {
        method: 'POST',
        body: JSON.stringify({ activite: activiteSelectionneeId, presences }),
    });

    if (resultat) {
        alert(resultat.message);
    }
});

document.addEventListener('DOMContentLoaded', chargerListeActivites);