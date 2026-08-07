let salonActuelId = null;
let socketActuel = null;
let utilisateurConnecteId = null;

function ligneSalon(salon) {
    return `
        <div class="salon-item" data-id="${salon.id}">
            <div class="fw-medium small">${echapperHTML(salon.nom_affiche)}</div>
            <div class="text-muted" style="font-size: 0.78rem;">
                ${salon.dernier_message ? echapperHTML(salon.dernier_message.contenu.substring(0, 40)) : 'Aucun message'}
            </div>
        </div>`;
}

function bulleMessage(message) {
    const estMoi = message.expediteur_id === utilisateurConnecteId || message.expediteur === utilisateurConnecteId;
    return `
        <div class="bulle-message ${estMoi ? 'bulle-envoyee' : 'bulle-recue'}">
            ${!estMoi ? `<div class="small fw-semibold mb-1">${echapperHTML(message.expediteur_nom)}</div>` : ''}
            <div>${echapperHTML(message.contenu)}</div>
        </div>`;
}

async function chargerSalons() {
    const profil = await appelApi('/auth/profil/');
    utilisateurConnecteId = profil?.id;

    const salons = await appelApi('/messagerie/salons/');
    const conteneur = document.getElementById('liste-salons-conteneur');

    conteneur.innerHTML = salons && salons.length
        ? salons.map(ligneSalon).join('')
        : '<div class="text-center text-muted py-4 small">Aucune conversation.</div>';

    document.querySelectorAll('.salon-item').forEach(item => {
        item.addEventListener('click', () => ouvrirSalon(item.dataset.id, item.querySelector('.fw-medium').textContent));
    });
}

async function ouvrirSalon(salonId, nomSalon) {
    salonActuelId = salonId;
    document.querySelectorAll('.salon-item').forEach(i => i.classList.remove('actif'));
    document.querySelector(`.salon-item[data-id="${salonId}"]`)?.classList.add('actif');

    document.getElementById('entete-conversation').innerHTML = `<span class="fw-semibold">${echapperHTML(nomSalon)}</span>`;
    document.getElementById('zone-saisie').classList.remove('d-none');

    const messages = await appelApi(`/messagerie/salons/${salonId}/messages/`);
    const zoneMessages = document.getElementById('zone-messages');
    zoneMessages.innerHTML = messages && messages.length
        ? messages.map(bulleMessage).join('')
        : '<div class="text-center text-muted small py-4">Aucun message. Démarrez la conversation !</div>';
    zoneMessages.scrollTop = zoneMessages.scrollHeight;

    connecterWebSocket(salonId);
}

function connecterWebSocket(salonId) {
    if (socketActuel) socketActuel.close();

    const token = obtenirToken();
    socketActuel = new WebSocket(`ws://127.0.0.1:8000/ws/messagerie/${salonId}/?token=${token}`);

    socketActuel.onmessage = (event) => {
        const message = JSON.parse(event.data);
        const zoneMessages = document.getElementById('zone-messages');
        zoneMessages.insertAdjacentHTML('beforeend', bulleMessage(message));
        zoneMessages.scrollTop = zoneMessages.scrollHeight;
    };

    socketActuel.onerror = () => console.warn('Connexion WebSocket indisponible pour ce salon.');
}

document.getElementById('formulaire-message').addEventListener('submit', (e) => {
    e.preventDefault();
    const champ = document.getElementById('champ-message');
    const contenu = champ.value.trim();
    if (!contenu || !socketActuel || socketActuel.readyState !== WebSocket.OPEN) return;

    socketActuel.send(JSON.stringify({ contenu }));
    champ.value = '';
});

document.addEventListener('DOMContentLoaded', chargerSalons);

document.getElementById('btn-retour-conversation')?.addEventListener('click', () => {
    document.querySelector('.conteneur-messagerie')?.classList.remove('conversation-ouverte');
    if (socketActuel) { socketActuel.close(); socketActuel = null; }
});