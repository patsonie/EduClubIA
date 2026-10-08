// Page « Comptes en attente » : demandes de rattachement parent → enfant, validées par un gestionnaire.
// Deux sources : les liens en attente (anciennes demandes) et les demandes par matricule ou par nom.

// ---------- Ancien format : lien parent ↔ élève en attente ----------

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

// ---------- Demande par matricule ou par nom : le gestionnaire choisit l'élève ----------

function ligneDemandeNominative(demande) {
    const date = demande.date_creation ? new Date(demande.date_creation).toLocaleDateString('fr-FR') : '-';
    const contact = [demande.parent_email, demande.parent_telephone].filter(Boolean).map(echapperHTML).join('<br>');
    const candidats = demande.eleves_candidats || [];
    // Liste des élèves possibles (élève trouvé par matricule, matricules proches ou noms proches).
    // Si elle est vide, le gestionnaire recherche lui-même l'élève avec le champ en dessous.
    const choix = `
        <select class="form-select form-select-sm mt-1 choix-eleve-demande">
            ${candidats.length
                ? candidats.map(optionEleve).join('')
                : '<option value="">Aucun élève proposé : recherchez-le ci-dessous</option>'}
        </select>
        <input type="search" class="form-control form-control-sm mt-1 recherche-eleve-demande"
               placeholder="Rechercher un élève (nom ou matricule)" aria-label="Rechercher un élève">`;
    const precisions = [demande.classe && `Classe indiquée : ${echapperHTML(demande.classe)}`,
                        demande.message && `« ${echapperHTML(demande.message)} »`].filter(Boolean).join('<br>');
    return `
        <tr>
            <td class="fw-medium">${echapperHTML(demande.parent_nom)}</td>
            <td class="small text-muted">${contact}</td>
            <td>${echapperHTML(demande.type_lien_eleve || '-')}</td>
            <td>
                <div class="small">Demande : <strong>${echapperHTML(demande.nom_complet_enfant)}</strong></div>
                ${precisions ? `<div class="text-muted small">${precisions}</div>` : ''}
                ${choix}
            </td>
            <td class="small text-muted">${date}</td>
            <td>
                <div class="d-flex gap-2 justify-content-end flex-wrap">
                    <button class="btn btn-sm btn-valider-action btn-accepter-demande" data-demande="${demande.id}">
                        <i class="bi bi-check-lg me-1"></i>Valider
                    </button>
                    <button class="btn btn-sm btn-refuser-action btn-refuser-demande" data-demande="${demande.id}">
                        <i class="bi bi-x-lg me-1"></i>Refuser
                    </button>
                </div>
            </td>
        </tr>`;
}

// ---------- Chargement du tableau ----------

async function chargerRattachements() {
    const tbody = document.getElementById('tableau-rattachements');
    if (!tbody) return;
    const [liens, demandes] = await Promise.all([
        appelApi('/auth/parents/demandes_rattachement/'),
        appelApi('/auth/demandes-rattachement/?statut=en_attente'),
    ]);
    const lignes = [
        ...(Array.isArray(liens) ? liens.map(ligneRattachement) : []),
        ...(Array.isArray(demandes) ? demandes.map(ligneDemandeNominative) : []),
    ];
    tbody.innerHTML = lignes.length
        ? lignes.join('')
        : '<tr><td colspan="6" class="text-center text-muted py-4">Aucune demande de rattachement en attente.</td></tr>';
}

// ---------- Actions ----------

/** Lien en attente : valider (lier_enfant) ou refuser (refuser_rattachement). */
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

/** Option de la liste des élèves : « Nom — matricule (classe) ». */
function optionEleve(e) {
    const classe = e.classe ? ` (${echapperHTML(e.classe)})` : '';
    return `<option value="${e.id}">${echapperHTML(e.nom_complet)} — ${echapperHTML(e.matricule || 's/ matricule')}${classe}</option>`;
}

/** Premier message lisible d'une réponse d'erreur de l'API. */
function messageErreurDemande(resultat) {
    if (!resultat) return "Le serveur n'a pas répondu. Réessayez.";
    const valeur = resultat.detail || resultat.error || Object.values(resultat)[0];
    return (Array.isArray(valeur) ? valeur.join(' ') : valeur) || "Action impossible.";
}

/** Demande par matricule/nom : accepter avec l'élève choisi, ou refuser. */
async function traiterDemande(bouton, action) {
    const corps = {};
    if (action === 'accepter') {
        const choix = bouton.closest('tr').querySelector('.choix-eleve-demande');
        if (!choix || !choix.value) {
            alert("Choisissez d'abord l'élève concerné (recherchez-le par son nom ou son matricule).");
            return;
        }
        if (!confirm(`Rattacher ce parent à ${choix.selectedOptions[0].text} ?`)) return;
        corps.enfant = Number(choix.value);
    } else if (!confirm('Refuser cette demande de rattachement ?')) {
        return;
    }
    bouton.disabled = true;
    const resultat = await appelApi(`/auth/demandes-rattachement/${bouton.dataset.demande}/${action}/`, {
        method: 'POST',
        body: JSON.stringify(corps),
    });
    // Succès : la demande renvoyée a changé de statut ; sinon on affiche l'erreur du serveur.
    if (!resultat || !['acceptee', 'refusee'].includes(resultat.statut)) {
        alert(messageErreurDemande(resultat));
        bouton.disabled = false;
        return;
    }
    chargerRattachements();
}

// Recherche manuelle d'un élève (300 ms après la dernière frappe) : remplit la liste de choix.
let delaiRechercheEleve;
document.addEventListener('input', (e) => {
    if (!e.target.classList.contains('recherche-eleve-demande')) return;
    const champ = e.target;
    clearTimeout(delaiRechercheEleve);
    delaiRechercheEleve = setTimeout(async () => {
        const terme = champ.value.trim();
        if (terme.length < 2) return;
        const data = await appelApi(`/auth/utilisateurs/?role=eleve&search=${encodeURIComponent(terme)}`);
        const eleves = (data && (data.results || data)) || [];
        const liste = champ.closest('td').querySelector('.choix-eleve-demande');
        liste.innerHTML = Array.isArray(eleves) && eleves.length
            ? eleves.slice(0, 20).map(optionEleve).join('')
            : '<option value="">Aucun élève trouvé pour cette recherche</option>';
    }, 300);
});

document.addEventListener('click', (e) => {
    const bouton = e.target.closest(
        '.btn-valider-rattachement, .btn-refuser-rattachement, .btn-accepter-demande, .btn-refuser-demande'
    );
    if (!bouton) return;
    if (bouton.classList.contains('btn-accepter-demande')) return traiterDemande(bouton, 'accepter');
    if (bouton.classList.contains('btn-refuser-demande')) return traiterDemande(bouton, 'refuser');
    traiterRattachement(bouton, bouton.classList.contains('btn-valider-rattachement') ? 'lier_enfant' : 'refuser_rattachement');
});

document.addEventListener('DOMContentLoaded', chargerRattachements);
