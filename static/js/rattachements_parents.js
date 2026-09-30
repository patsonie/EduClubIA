function ligneRattachement(demande) {
    const date = demande.date_creation ? new Date(demande.date_creation).toLocaleDateString('fr-FR') : '-';
    const contact = [demande.parent_email, demande.parent_telephone].filter(Boolean).map(echapperHTML).join('<br>');
    const eleve = `${echapperHTML(demande.enfant_nom)}<div class="text-muted small">`
        + `Matricule : ${echapperHTML(demande.enfant_matricule || '-')} · Classe : ${echapperHTML(demande.enfant_classe || '-')}</div>`;
    return `
        <tr>
            <td class="fw-medium">${echapperHTML(demande.parent_nom)}</td>
            <td class="small text-muted">${contact}</td>
            <td>${echapperHTML(demande.type_lien_eleve || '-')}</td>
            <td>${eleve}</td>
            <td class="small text-muted">${date}</td>
            <td>
                <div class="d-flex gap-2 justify-content-end flex-wrap">
                    <button class="btn btn-sm btn-valider-action btn-valider-rattachement"
                            data-parent="${demande.parent}" data-enfant="${demande.enfant}">
                        <i class="bi bi-check-lg me-1"></i>Valider
                    </button>
                    <button class="btn btn-sm btn-refuser-action btn-refuser-rattachement"
                            data-parent="${demande.parent}" data-enfant="${demande.enfant}">
                        <i class="bi bi-x-lg me-1"></i>Refuser
                    </button>
                </div>
            </td>
        </tr>`;
}

async function chargerRattachements() {
    const demandes = await appelApi('/auth/parents/demandes_rattachement/');
    const tbody = document.getElementById('tableau-rattachements');
    if (!tbody) return;

    tbody.innerHTML = Array.isArray(demandes) && demandes.length
        ? demandes.map(ligneRattachement).join('')
        : '<tr><td colspan="6" class="text-center text-muted py-4">Aucune demande de rattachement en attente.</td></tr>';
}

async function traiterRattachement(bouton, action) {
    const { parent, enfant } = bouton.dataset;
    if (action === 'refuser_rattachement' && !confirm('Refuser cette demande de rattachement ?')) return;
    bouton.disabled = true;
    const resultat = await appelApi(`/auth/parents/${parent}/${action}/`, {
        method: 'POST',
        body: JSON.stringify({ enfant: Number(enfant) }),
    });
    if (resultat && resultat.error) alert(resultat.error);
    chargerRattachements();
}

document.addEventListener('click', (e) => {
    const bouton = e.target.closest('.btn-valider-rattachement, .btn-refuser-rattachement');
    if (!bouton) return;
    traiterRattachement(bouton, bouton.classList.contains('btn-valider-rattachement') ? 'lier_enfant' : 'refuser_rattachement');
});

document.addEventListener('DOMContentLoaded', chargerRattachements);
