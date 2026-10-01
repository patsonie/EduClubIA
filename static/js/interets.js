// Puces de centres d'intérêt, partagées par la page Profil et la page d'inscription.

function echapperHtmlInteret(texte) {
    const div = document.createElement('div');
    div.textContent = texte == null ? '' : String(texte);
    return div.innerHTML;
}

/** Affiche les centres groupés par catégorie sous forme de puces à cocher. */
function afficherPucesInterets(conteneur, centres, idsSelectionnes = []) {
    const selection = new Set((idsSelectionnes || []).map(Number));
    const groupes = {};
    (centres || []).forEach(c => { (groupes[c.categorie || 'Autres'] ||= []).push(c); });

    const noms = Object.keys(groupes);
    if (!noms.length) {
        conteneur.innerHTML = '<p class="text-muted small mb-0">Aucun centre d\'intérêt disponible pour le moment.</p>';
        return;
    }

    conteneur.classList.add('groupe-interets');
    conteneur.innerHTML = noms.map(categorie => `
        <div class="titre-categorie-interet">${echapperHtmlInteret(categorie)}</div>
        <div class="puces-interets">
            ${groupes[categorie].map(c => `
                <label class="puce-interet ${selection.has(c.id) ? 'selectionnee' : ''}" title="${echapperHtmlInteret(c.description)}">
                    <input type="checkbox" value="${c.id}" ${selection.has(c.id) ? 'checked' : ''}>
                    <i class="bi bi-check-lg"></i>${echapperHtmlInteret(c.nom)}
                </label>`).join('')}
        </div>`).join('');

    conteneur.querySelectorAll('.puce-interet input').forEach(champ => {
        champ.addEventListener('change', () => {
            champ.closest('.puce-interet').classList.toggle('selectionnee', champ.checked);
        });
    });
}

/** Identifiants (entiers) des centres cochés. */
function lireInteretsSelectionnes(conteneur) {
    return Array.from(conteneur.querySelectorAll('.puce-interet input:checked')).map(c => Number(c.value));
}
