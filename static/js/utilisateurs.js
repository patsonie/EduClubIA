// Page « Utilisateurs » (administration) : liste, recherche, suspension et réactivation des comptes.
// Libellés des rôles et couleurs des statuts.
const LIBELLES_ROLE_ADMIN = {
    administrateur: 'Administrateur', proviseur: 'Responsable pédagogique',
    encadreur: 'Encadreur', eleve: 'Élève', parent: "Parent d'élève",
};
const BADGES_STATUT_ADMIN = { valide: 'success', en_attente: 'warning', refuse: 'danger', suspendu: 'secondary' };

// Ligne d'un utilisateur ; l'administrateur ne peut pas être suspendu depuis cette page.
function ligneUtilisateurAdmin(u) {
    const couleurStatut = BADGES_STATUT_ADMIN[u.statut_validation] || 'secondary';
    const dateFormatee = new Date(u.date_joined).toLocaleDateString('fr-FR');

    const actionSuspension = u.statut_validation === 'suspendu'
        ? `<button class="btn btn-sm btn-outline-success btn-reactiver" data-id="${u.id}" title="Réactiver"><i class="bi bi-arrow-counterclockwise"></i></button>`
        : `<button class="btn btn-sm btn-outline-secondary btn-suspendre" data-id="${u.id}" title="Suspendre"><i class="bi bi-slash-circle"></i></button>`;

    return `
        <tr>
            <td class="fw-medium">${echapperHTML(u.nom_complet)}</td>
            <td class="text-muted small">${echapperHTML(u.email)}</td>
            <td><span class="badge bg-primary-subtle text-primary">${LIBELLES_ROLE_ADMIN[u.role] || u.role}</span></td>
            <td><span class="badge bg-${couleurStatut}-subtle text-${couleurStatut}">${u.statut_validation}</span></td>
            <td class="text-muted small">${dateFormatee}</td>
            <td>${u.role !== 'administrateur' ? actionSuspension : ''}</td>
        </tr>`;
}

// Branche les boutons suspendre/réactiver.
function attacherActionsUtilisateurs() {
    document.querySelectorAll('.btn-suspendre').forEach(bouton => {
        bouton.addEventListener('click', async (e) => {
            await appelApi(`/auth/utilisateurs/${e.currentTarget.dataset.id}/suspendre/`, { method: 'POST' });
            chargerUtilisateurs();
        });
    });
    document.querySelectorAll('.btn-reactiver').forEach(bouton => {
        bouton.addEventListener('click', async (e) => {
            await appelApi(`/auth/utilisateurs/${e.currentTarget.dataset.id}/reactiver/`, { method: 'POST' });
            chargerUtilisateurs();
        });
    });
}

// Charge la liste selon la recherche et les filtres choisis.
async function chargerUtilisateurs() {
    const recherche = document.getElementById('recherche-utilisateur').value;
    const role = document.getElementById('filtre-role-utilisateur').value;
    const statut = document.getElementById('filtre-statut-utilisateur').value;

    const params = new URLSearchParams();
    if (recherche) params.append('search', recherche);
    if (role) params.append('role', role);
    if (statut) params.append('statut_validation', statut);

    const data = await appelApi(`/auth/utilisateurs/?${params.toString()}`);
    const utilisateurs = data.results || data;
    const tbody = document.getElementById('tableau-utilisateurs');

    tbody.innerHTML = utilisateurs && utilisateurs.length
        ? utilisateurs.map(ligneUtilisateurAdmin).join('')
        : '<tr><td colspan="6" class="text-center text-muted py-4">Aucun utilisateur trouvé.</td></tr>';

    attacherActionsUtilisateurs();
}

// Recherche lancée 300 ms après la dernière frappe (évite une requête par lettre).
let delaiRecherche;
document.getElementById('recherche-utilisateur').addEventListener('input', () => {
    clearTimeout(delaiRecherche);
    delaiRecherche = setTimeout(chargerUtilisateurs, 300);
});
document.getElementById('filtre-role-utilisateur').addEventListener('change', chargerUtilisateurs);
document.getElementById('filtre-statut-utilisateur').addEventListener('change', chargerUtilisateurs);

document.addEventListener('DOMContentLoaded', chargerUtilisateurs);