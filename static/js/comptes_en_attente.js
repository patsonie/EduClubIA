let compteIdEnCoursDeRefus = null;
const LIBELLES_ROLES_ATTENTE = { eleve: 'Élève', encadreur: 'Encadreur', proviseur: 'Responsable pédagogique' };

function detailsCompte(compte) {
    if (compte.role === 'eleve') {
        return `Matricule : ${compte.matricule || '-'}`;
    }
    if (compte.role === 'encadreur') {
        const type = compte.type_encadreur === 'professionnel' ? 'Professionnel' : 'Vacataire';
        const justif = compte.justificatif
            ? `<a href="#" class="btn-voir-justificatif" data-id="${compte.id}">Voir le justificatif</a>`
            : '<span class="text-muted">Aucun justificatif</span>';
        return `${type} · ${compte.domaine_competence || '-'} · ${justif}`;
    }
    if (compte.role === 'proviseur') {
        return `${compte.fonction || '-'} · ${compte.service_responsabilite || '-'}`;
    }
    return '-';
}

function ligneCompteAttente(compte) {
    return `
        <tr data-id="${compte.id}">
            <td class="fw-medium">${echapperHTML(compte.nom_complet)}</td>
            <td class="text-muted small">${echapperHTML(compte.email)}</td>
            <td><span class="badge bg-primary-subtle text-primary">${LIBELLES_ROLES_ATTENTE[compte.role] || compte.role}</span></td>
            <td class="text-muted small">${detailsCompte(compte)}</td>
            <td class="text-end">
                <div class="d-flex gap-2 justify-content-end flex-wrap">
                    <button class="btn btn-sm btn-valider-action btn-valider-compte" data-id="${compte.id}">
                        <i class="bi bi-check-lg me-1"></i>Valider
                    </button>
                    <button class="btn btn-sm btn-refuser-action btn-ouvrir-refus" data-id="${compte.id}">
                        <i class="bi bi-x-lg me-1"></i>Refuser
                    </button>
                </div>
            </td>
        </tr>`;
}

async function chargerComptesEnAttente(role = '') {
    const endpoint = role ? `/auth/comptes-en-attente/?role=${role}` : '/auth/comptes-en-attente/';
    const comptes = await appelApi(endpoint);
    const tbody = document.getElementById('tableau-comptes-attente');

    tbody.innerHTML = comptes && comptes.length
        ? comptes.map(ligneCompteAttente).join('')
        : '<tr><td colspan="5" class="text-center text-muted py-4">Aucun compte en attente.</td></tr>';

    document.querySelectorAll('.btn-valider-compte').forEach(bouton => {
        bouton.addEventListener('click', async (e) => {
            const id = e.currentTarget.dataset.id;
            await appelApi(`/auth/comptes/${id}/valider/`, { method: 'POST' });
            chargerComptesEnAttente(document.querySelector('.btn-filtre.active').dataset.role);
        });
    });

    document.querySelectorAll('.btn-envoyer-code').forEach(bouton => {
        bouton.addEventListener('click', async (e) => {
            const id = e.currentTarget.dataset.id;
            const resultat = await appelApi(`/auth/comptes/${id}/envoyer_code/`, { method: 'POST' });
            if (resultat) alert(resultat.message);
            chargerComptesEnAttente(document.querySelector('.btn-filtre.active').dataset.role);
        });
    });

    document.querySelectorAll('.btn-regenerer-code').forEach(bouton => {
        bouton.addEventListener('click', async (e) => {
            const id = e.currentTarget.dataset.id;
            const resultat = await appelApi(`/auth/comptes/${id}/regenerer_code/`, { method: 'POST' });
            if (resultat) alert(resultat.message);
            chargerComptesEnAttente(document.querySelector('.btn-filtre.active').dataset.role);
        });
    });

    document.querySelectorAll('.btn-ouvrir-refus').forEach(bouton => {
        bouton.addEventListener('click', (e) => {
            compteIdEnCoursDeRefus = e.currentTarget.dataset.id;
            new bootstrap.Modal(document.getElementById('modalRefus')).show();
        });
    });
}

document.getElementById('btn-confirmer-refus').addEventListener('click', async () => {
    const motif = document.getElementById('champ-motif-refus').value;
    await appelApi(`/auth/comptes/${compteIdEnCoursDeRefus}/refuser/`, {
        method: 'POST',
        body: JSON.stringify({ motif }),
    });
    bootstrap.Modal.getInstance(document.getElementById('modalRefus')).hide();
    document.getElementById('champ-motif-refus').value = '';
    chargerComptesEnAttente(document.querySelector('.btn-filtre.active').dataset.role);
});

document.querySelectorAll('.btn-filtre').forEach(bouton => {
    bouton.addEventListener('click', (e) => {
        document.querySelectorAll('.btn-filtre').forEach(b => b.classList.remove('active'));
        e.currentTarget.classList.add('active');
        chargerComptesEnAttente(e.currentTarget.dataset.role);
    });
});

document.addEventListener('DOMContentLoaded', () => chargerComptesEnAttente());


document.addEventListener('click', async (e) => {
    if (!e.target.classList.contains('btn-voir-justificatif')) return;
    e.preventDefault();
    const id = e.target.dataset.id;
    const token = obtenirToken();

    const reponse = await fetch(`http://127.0.0.1:8000/api/auth/justificatif/${id}/`, {
        headers: { 'Authorization': `Bearer ${token}` },
    });

    if (!reponse.ok) {
        alert("Impossible d'accéder à ce document.");
        return;
    }

    const blob = await reponse.blob();
    const url = window.URL.createObjectURL(blob);
    window.open(url, '_blank');
});

const BADGES_STATUT_ATTENTE = {
    en_attente: 'warning', code_envoye: 'info', code_valide: 'primary', refuse: 'danger',
};

function actionsProviseur(compte) {
    const boutonEnvoyer = `<button class="btn btn-sm btn-valider-action btn-envoyer-code" data-id="${compte.id}"><i class="bi bi-send me-1"></i>Envoyer le code</button>`;
    const boutonRegenerer = `<button class="btn btn-sm btn-light btn-regenerer-code" data-id="${compte.id}"><i class="bi bi-arrow-repeat me-1"></i>Régénérer</button>`;
    const boutonValider = `<button class="btn btn-sm btn-valider-action btn-valider-compte" data-id="${compte.id}" ${compte.statut_validation !== 'code_valide' ? 'disabled title="Le code doit d\'abord être validé par le responsable pédagogique"' : ''}><i class="bi bi-check-lg me-1"></i>Valider le compte</button>`;
    const boutonRefuser = `<button class="btn btn-sm btn-refuser-action btn-ouvrir-refus" data-id="${compte.id}"><i class="bi bi-x-lg me-1"></i>Refuser</button>`;

    if (compte.statut_validation === 'en_attente') return `<div class="d-flex gap-2 flex-wrap justify-content-end">${boutonEnvoyer}${boutonRefuser}</div>`;
    if (compte.statut_validation === 'code_envoye') return `<div class="d-flex gap-2 flex-wrap justify-content-end">${boutonRegenerer}${boutonRefuser}</div>`;
    if (compte.statut_validation === 'code_valide') return `<div class="d-flex gap-2 flex-wrap justify-content-end">${boutonValider}${boutonRefuser}</div>`;
    return '<span class="text-muted small">-</span>';
}

function ligneCompteAttente(compte) {
    const estProviseur = compte.role === 'proviseur';
    const couleurStatut = BADGES_STATUT_ATTENTE[compte.statut_validation] || 'secondary';

    const colonneCode = estProviseur
        ? `<td class="small">${compte.code_validation_compte ? `<code>${echapperHTML(compte.code_validation_compte)}</code>` : '-'}</td>`
        : '';

    const actions = estProviseur
        ? actionsProviseur(compte)
        : `<div class="d-flex gap-2 justify-content-end flex-wrap">
             <button class="btn btn-sm btn-valider-action btn-valider-compte" data-id="${compte.id}"><i class="bi bi-check-lg me-1"></i>Valider</button>
             <button class="btn btn-sm btn-refuser-action btn-ouvrir-refus" data-id="${compte.id}"><i class="bi bi-x-lg me-1"></i>Refuser</button>
           </div>`;

    return `
        <tr data-id="${compte.id}">
            <td class="fw-medium">${echapperHTML(compte.nom_complet)}</td>
            <td class="text-muted small">${echapperHTML(compte.email)}</td>
            <td><span class="badge bg-primary-subtle text-primary">${LIBELLES_ROLES_ATTENTE[compte.role] || compte.role}</span></td>
            <td class="text-muted small">${detailsCompte(compte)}</td>
            ${estProviseur ? colonneCode : '<td></td>'}
            <td><span class="badge bg-${couleurStatut}-subtle text-${couleurStatut}">${compte.statut_validation}</span></td>
            <td>${actions}</td>
        </tr>`;
}