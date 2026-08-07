function creerCarteStatMini(icone, valeur, libelle) {
    return `
        <div class="col-6 col-md-3">
            <div class="carte-stat">
                <div class="d-flex align-items-center gap-3">
                    <div class="icone"><i class="bi ${icone}"></i></div>
                    <div>
                        <div class="valeur">${valeur}</div>
                        <div class="libelle">${libelle}</div>
                    </div>
                </div>
            </div>
        </div>`;
}

function creerCarteActiviteClub(activite) {
    const badges = {
        planifiee: 'warning', validee: 'primary', en_cours: 'info',
        terminee: 'success', annulee: 'danger',
    };
    return `
        <div class="col-md-6">
            <div class="d-flex justify-content-between align-items-center p-3 rounded" style="background-color: var(--couleur-fond);">
                <div>
                    <div class="fw-medium small">${echapperHTML(activite.titre)}</div>
                    <div class="text-muted" style="font-size: 0.78rem;">${activite.date} à ${activite.heure} · ${echapperHTML(activite.lieu)}</div>
                </div>
                <span class="badge bg-${badges[activite.statut] || 'secondary'}-subtle text-${badges[activite.statut] || 'secondary'}">${activite.statut}</span>
            </div>
        </div>`;
}

async function chargerDetailClub() {
    const club = await appelApi(`/clubs/${CLUB_ID}/`);
    if (!club) return;

    document.getElementById('fil-ariane-club').textContent = club.nom;

    document.getElementById('entete-club').innerHTML = `
        <div class="d-flex justify-content-between align-items-start flex-wrap gap-3">
            <div>
                <div class="d-flex align-items-center gap-2 mb-1">
                    <h4 class="fw-bold mb-0">${echapperHTML(club.nom)}</h4>
                    <span class="badge bg-success-subtle text-success">${echapperHTML(club.statut)}</span>
                </div>
                <span class="badge bg-primary-subtle text-primary mb-2">${echapperHTML(club.categorie)}</span>
                <p class="text-muted mb-1" style="max-width: 600px;">${echapperHTML(club.description)}</p>
                <div class="small text-muted">Responsable : ${echapperHTML(club.responsable_nom || 'Non assigné')}</div>
            </div>
            <div class="text-end">
                <div class="fw-bold" style="font-size: 1.4rem; color: var(--couleur-primaire);">${club.nombre_membres_actuels} / ${club.nombre_max_membres}</div>
                <div class="small text-muted">Membres</div>
            </div>
        </div>`;

    const membres = await appelApi(`/clubs/${CLUB_ID}/membres/`);
    const tableauMembres = document.getElementById('tableau-membres');
    tableauMembres.innerHTML = membres && membres.length
        ? membres.map(ligneMembre).join('')
        : '<tr><td colspan="4" class="text-center text-muted py-3">Aucun membre pour l\'instant.</td></tr>';

    document.querySelectorAll('.btn-retirer-membre').forEach(bouton => {
        bouton.addEventListener('click', async (e) => {
            if (!confirm('Retirer cet élève du club ?')) return;
            const eleveId = e.currentTarget.dataset.eleve;
            await appelApi(`/clubs/${CLUB_ID}/retirer_membre/`, {
                method: 'POST',
                body: JSON.stringify({ eleve_id: eleveId }),
            });
            chargerDetailClub();
        });
    });

    const activites = await appelApi(`/activites/?club=${CLUB_ID}`);
    const listeActivites = document.getElementById('liste-activites-club');
    const activitesArray = activites.results || activites;
    listeActivites.innerHTML = activitesArray.length
        ? activitesArray.map(creerCarteActiviteClub).join('')
        : '<div class="col-12 text-center text-muted py-3">Aucune activité pour ce club.</div>';

    const stats = await appelApi(`/clubs/${CLUB_ID}/statistiques/`);
    if (stats) {
        document.getElementById('conteneur-stats-club').innerHTML = [
            creerCarteStatMini('bi-calendar-event', stats.nombre_activites, 'Activités totales'),
            creerCarteStatMini('bi-check-circle', stats.activites_terminees, 'Terminées'),
            creerCarteStatMini('bi-clock', stats.activites_a_venir, 'À venir'),
            creerCarteStatMini('bi-graph-up', stats.taux_participation_moyen + '%', 'Taux de présence'),
        ].join('');
    }
}

document.addEventListener('DOMContentLoaded', chargerDetailClub);

function ligneMembre(m) {
    return `
        <tr data-eleve="${m.id}">
            <td class="fw-medium">${echapperHTML(m.nom_complet)}</td>
            <td>${echapperHTML(m.classe || '-')}</td>
            <td class="text-muted small">${new Date(m.date_inscription).toLocaleDateString('fr-FR')}</td>
            <td>
                <button class="btn btn-sm btn-outline-danger btn-retirer-membre" data-eleve="${m.id}" title="Retirer du club">
                    <i class="bi bi-person-dash"></i>
                </button>
            </td>
        </tr>`;
}