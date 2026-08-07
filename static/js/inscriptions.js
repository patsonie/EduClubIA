const BADGES_STATUT_INSCRIPTION = {
    en_attente: 'warning', validee: 'success', refusee: 'danger',
    annulee: 'secondary', archivee: 'dark',
};

function ligneInscription(inscription) {
    const couleur = BADGES_STATUT_INSCRIPTION[inscription.statut] || 'secondary';
    const dateFormatee = new Date(inscription.date_inscription).toLocaleDateString('fr-FR');

    const actions = inscription.statut === 'en_attente'
        ? `
            <button class="btn btn-sm btn-success btn-valider-inscription" data-id="${inscription.id}"><i class="bi bi-check-lg"></i></button>
            <button class="btn btn-sm btn-danger btn-refuser-inscription" data-id="${inscription.id}"><i class="bi bi-x-lg"></i></button>`
        : '<span class="text-muted small">-</span>';

    return `
        <tr>
            <td class="fw-medium">${echapperHTML(inscription.eleve_nom)}</td>
            <td class="text-muted small">${echapperHTML(inscription.club_nom)}</td>
            <td class="text-muted small">${dateFormatee}</td>
            <td><span class="badge bg-${couleur}-subtle text-${couleur}">${inscription.statut}</span></td>
            <td>${actions}</td>
        </tr>`;
}

function attacherActionsInscriptions(statutActuel) {
    document.querySelectorAll('.btn-valider-inscription').forEach(bouton => {
        bouton.addEventListener('click', async (e) => {
            const id = e.currentTarget.dataset.id;
            await appelApi(`/inscriptions/${id}/valider/`, { method: 'POST' });
            chargerInscriptions(statutActuel);
        });
    });
    document.querySelectorAll('.btn-refuser-inscription').forEach(bouton => {
        bouton.addEventListener('click', async (e) => {
            const id = e.currentTarget.dataset.id;
            await appelApi(`/inscriptions/${id}/refuser/`, { method: 'POST' });
            chargerInscriptions(statutActuel);
        });
    });
}

async function chargerInscriptions(statut = 'en_attente') {
    const endpoint = statut ? `/inscriptions/?statut=${statut}` : '/inscriptions/';
    const data = await appelApi(endpoint);
    const inscriptions = data.results || data;
    const tbody = document.getElementById('tableau-inscriptions');

    tbody.innerHTML = inscriptions && inscriptions.length
        ? inscriptions.map(ligneInscription).join('')
        : '<tr><td colspan="5" class="text-center text-muted py-4">Aucune inscription trouvée.</td></tr>';

    attacherActionsInscriptions(statut);
}

document.querySelectorAll('.btn-filtre').forEach(bouton => {
    bouton.addEventListener('click', (e) => {
        document.querySelectorAll('.btn-filtre').forEach(b => b.classList.remove('active'));
        e.currentTarget.classList.add('active');
        chargerInscriptions(e.currentTarget.dataset.statut);
    });
});

document.addEventListener('DOMContentLoaded', () => chargerInscriptions());