const ICONES_TYPE = {
    nouvelle_activite: 'bi-calendar-plus text-primary',
    validation_inscription: 'bi-check-circle text-success',
    refus_inscription: 'bi-x-circle text-danger',
    rappel_activite: 'bi-alarm text-warning',
    recommandation_ia: 'bi-stars text-primary',
    alerte_desengagement: 'bi-exclamation-triangle text-danger',
    autre: 'bi-bell text-secondary',
};

function tempsEcoule(dateString) {
    const diffMs = new Date() - new Date(dateString);
    const diffHeures = Math.floor(diffMs / 3600000);
    if (diffHeures < 1) return "à l'instant";
    if (diffHeures < 24) return `il y a ${diffHeures}h`;
    return `il y a ${Math.floor(diffHeures / 24)}j`;
}

function ligneNotification(notif) {
    const icone = ICONES_TYPE[notif.type_notification] || ICONES_TYPE.autre;
    const classeNonLue = !notif.lu ? 'notification-non-lue' : '';

    return `
        <div class="list-group-item d-flex align-items-start gap-3 py-3 ${classeNonLue}" data-id="${notif.id}">
            <i class="bi ${icone}" style="font-size: 1.2rem; margin-top: 2px;"></i>
            <div class="flex-grow-1">
                <div class="fw-medium small">${echapperHTML(notif.titre)}</div>
                <div class="text-muted small">${echapperHTML(notif.message)}</div>
                <div class="text-muted" style="font-size: 0.75rem;">${tempsEcoule(notif.date_creation)}</div>
            </div>
            ${!notif.lu ? `<button class="btn btn-sm btn-light btn-marquer-lu">Marquer lu</button>` : ''}
        </div>`;
}

async function chargerNotifications(filtre = 'toutes') {
    const endpoint = filtre === 'non_lues' ? '/notifications/?lu=false' : '/notifications/';
    const notifications = await appelApi(endpoint);
    const conteneur = document.getElementById('liste-notifications-page');

    conteneur.innerHTML = notifications && notifications.length
        ? notifications.map(ligneNotification).join('')
        : '<div class="text-center text-muted py-5">Aucune notification.</div>';

    document.querySelectorAll('.btn-marquer-lu').forEach(bouton => {
        bouton.addEventListener('click', async (e) => {
            const id = e.target.closest('[data-id]').dataset.id;
            await appelApi(`/notifications/${id}/marquer_lu/`, { method: 'POST' });
            chargerNotifications(document.querySelector('.btn-filtre.active').dataset.filtre);
        });
    });
}

document.querySelectorAll('.btn-filtre').forEach(bouton => {
    bouton.addEventListener('click', (e) => {
        document.querySelectorAll('.btn-filtre').forEach(b => b.classList.remove('active'));
        e.target.classList.add('active');
        chargerNotifications(e.target.dataset.filtre);
    });
});

document.getElementById('btn-tout-lire').addEventListener('click', async () => {
    await appelApi('/notifications/tout_marquer_lu/', { method: 'POST' });
    chargerNotifications(document.querySelector('.btn-filtre.active').dataset.filtre);
});

document.addEventListener('DOMContentLoaded', () => chargerNotifications());