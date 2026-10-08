// Page « Tableau de bord » : contenu différent selon le rôle (élève, responsable pédagogique, autres).
// Couleur associée à chaque catégorie de club (graphiques et pastilles).
const COULEURS_CATEGORIES = {
    scientifique: '#6C5CE7', sportif: '#22c55e', culturel: '#f59e0b',
    artistique: '#ef4444', technologique: '#3b82f6', humanitaire: '#a855f7', autre: '#6b7280',
};

// ---------- Vue générale (admin/gestionnaires) ----------

// Carte de chiffre clé avec sa variation par rapport au mois précédent.
function creerCarteStat(icone, valeur, libelle, variation) {
    const positif = variation >= 0;
    const signeVariation = positif ? '+' : '';
    const classeVariation = positif ? 'variation-positive' : 'variation-negative';
    const icoheFleche = positif ? 'bi-arrow-up-short' : 'bi-arrow-down-short';

    return `
        <div class="col-6 col-md-3">
            <div class="carte-stat">
                <div class="d-flex align-items-center gap-3 mb-2">
                    <div class="icone"><i class="bi ${icone}"></i></div>
                    <div>
                        <div class="valeur">${valeur}</div>
                        <div class="libelle">${libelle}</div>
                    </div>
                </div>
                <span class="${classeVariation}"><i class="bi ${icoheFleche}"></i>${signeVariation}${variation}% ce mois</span>
            </div>
        </div>`;
}

// Carte d'une activité à venir.
function creerCarteActivite(activite) {
    const couleur = COULEURS_CATEGORIES[activite.categorie] || '#6b7280';
    return `
        <div class="col-md-6 col-lg-4">
            <div class="d-flex align-items-start gap-2 p-2 rounded" style="background-color: var(--couleur-fond);">
                <div class="rounded-circle flex-shrink-0" style="width: 8px; height: 8px; margin-top: 6px; background-color: ${couleur};"></div>
                <div>
                    <div class="fw-medium small">${echapperHTML(activite.titre)}</div>
                    <div class="text-muted" style="font-size: 0.78rem;">${echapperHTML(activite.club)} · ${activite.date}</div>
                </div>
            </div>
        </div>`;
}

// Vue générale : chiffres clés, courbe des inscriptions, répartition des clubs, activités à venir.
async function chargerDashboardGeneral(profil) {
    document.getElementById('titre-bienvenue').textContent = `Bonjour, ${profil.prenom} 👋`;

    const stats = await appelApi('/predictions/statistiques-globales/');
    if (!stats) return;

    document.getElementById('conteneur-cartes-stats').innerHTML = [
        creerCarteStat('bi-people-fill', stats.nombre_eleves, 'Élèves', stats.variation_eleves),
        creerCarteStat('bi-diagram-3-fill', stats.nombre_clubs, 'Clubs', stats.variation_clubs),
        creerCarteStat('bi-calendar-event-fill', stats.nombre_activites, 'Activités', stats.variation_activites),
        creerCarteStat('bi-clipboard-check-fill', stats.nombre_inscriptions, 'Inscriptions', stats.variation_inscriptions),
    ].join('');

    // Graphique (Chart.js) : évolution des inscriptions sur 12 mois.
    new Chart(document.getElementById('graphique-evolution'), {
        type: 'line',
        data: {
            labels: stats.evolution_inscriptions.map(e => e.mois),
            datasets: [{
                label: 'Inscriptions', data: stats.evolution_inscriptions.map(e => e.total),
                borderColor: '#6C5CE7', backgroundColor: 'rgba(108, 92, 231, 0.1)',
                fill: true, tension: 0.35, pointRadius: 3,
            }],
        },
        options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } } },
    });

    // Graphique en anneau : nombre de clubs par catégorie.
    new Chart(document.getElementById('graphique-repartition'), {
        type: 'doughnut',
        data: {
            labels: stats.repartition_categories.map(c => c.categorie),
            datasets: [{
                data: stats.repartition_categories.map(c => c.total),
                backgroundColor: stats.repartition_categories.map(c => COULEURS_CATEGORIES[c.categorie] || '#6b7280'),
                borderWidth: 0,
            }],
        },
        options: { plugins: { legend: { position: 'bottom', labels: { boxWidth: 10, font: { size: 11 } } } } },
    });

    const conteneurActivites = document.getElementById('liste-activites-a-venir');
    conteneurActivites.innerHTML = stats.activites_a_venir.length
        ? stats.activites_a_venir.map(creerCarteActivite).join('')
        : '<div class="col-12 text-muted small">Aucune activité à venir.</div>';
}

// ---------- Vue Élève ----------

// Carte de chiffre clé pour l'élève.
function creerCarteStatEleve(icone, valeur, libelle) {
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

// Ligne d'une activité à venir de l'élève.
function ligneActiviteEleve(a) {
    return `
        <div class="d-flex justify-content-between align-items-center py-2 border-bottom">
            <div class="d-flex align-items-center gap-2">
                <div class="rounded-circle d-flex align-items-center justify-content-center" style="width:36px; height:36px; background-color: var(--couleur-primaire-claire); color: var(--couleur-primaire);">
                    <i class="bi bi-calendar-event"></i>
                </div>
                <div>
                    <div class="fw-medium small">${echapperHTML(a.titre)}</div>
                    <div class="text-muted" style="font-size:0.76rem;">${echapperHTML(a.club_nom || '')}</div>
                </div>
            </div>
            <span class="badge bg-light text-dark border">${a.date}</span>
        </div>`;
}

// Ligne d'un club de l'élève avec barre de taux de présence.
function ligneClubEleve(club, taux) {
    return `
        <div class="d-flex align-items-center gap-3 py-2 border-bottom">
            <div class="rounded-circle d-flex align-items-center justify-content-center flex-shrink-0" style="width:36px; height:36px; background-color: var(--couleur-primaire-claire); color: var(--couleur-primaire);">
                <i class="bi bi-diagram-3"></i>
            </div>
            <div class="flex-grow-1">
                <div class="fw-medium small">${echapperHTML(club.nom)}</div>
                <div class="text-muted" style="font-size:0.7rem;">Membre actif</div>
                <div class="progress mt-1" style="height: 5px;">
                    <div class="progress-bar" style="width:${taux}%; background-color: var(--couleur-primaire);"></div>
                </div>
            </div>
            <span class="small fw-semibold" style="color: var(--couleur-primaire);">${taux}%</span>
        </div>`;
}

// Ligne d'une notification récente.
function ligneNotificationEleve(n) {
    return `
        <div class="py-2 border-bottom">
            <div class="small fw-medium">${echapperHTML(n.titre)}</div>
            <div class="text-muted" style="font-size:0.74rem;">${echapperHTML(n.message.substring(0, 60))}...</div>
        </div>`;
}

// Badge de progression de l'élève (assiduité, ponctualité...).
function creerBadgeEleve(icone, titre, valeur, couleur) {
    return `
        <div class="col-6 col-md-2">
            <div class="rounded-circle d-flex align-items-center justify-content-center mx-auto mb-2" style="width:56px; height:56px; background-color: ${couleur}22; color: ${couleur};">
                <i class="bi ${icone}" style="font-size:1.4rem;"></i>
            </div>
            <div class="small fw-semibold">${titre}</div>
            <div class="text-muted" style="font-size:0.72rem;">${valeur}</div>
        </div>`;
}

// Vue élève : chiffres, niveau, prochaines activités, clubs, notifications, badges.
async function chargerDashboardEleve(profil) {
    document.getElementById('salutation-eleve').textContent = `Bonjour, ${profil.prenom} ! 👋`;

    const rapport = await appelApi(`/participations/rapport_individuel/?eleve_id=${profil.id}`);
    const inscriptionsData = await appelApi('/inscriptions/?statut=validee');
    const inscriptions = inscriptionsData.results || inscriptionsData || [];
    const notifications = await appelApi('/notifications/');
    const activitesData = await appelApi('/activites/');
    const toutesActivites = activitesData.results || activitesData || [];
    const nomsClubs = inscriptions.map(i => i.club_nom);
    const activitesAVenir = toutesActivites.filter(a => nomsClubs.includes(a.club_nom)).slice(0, 4);

    document.getElementById('cartes-stats-eleve').innerHTML = [
        creerCarteStatEleve('bi-people-fill', inscriptions.length, 'Clubs rejoints'),
        creerCarteStatEleve('bi-calendar-check', rapport.total_activites, 'Activités suivies'),
        creerCarteStatEleve('bi-star-fill', `${rapport.taux_participation}%`, 'Présences'),
        creerCarteStatEleve('bi-pie-chart-fill', `${rapport.taux_participation}%`, 'Taux de participation'),
    ].join('');

    // Niveau selon le taux de participation (≥ 80 % avancé, ≥ 50 % intermédiaire).
    const niveauEl = document.getElementById('niveau-eleve');
    if (rapport.taux_participation >= 80) niveauEl.textContent = 'Avancé';
    else if (rapport.taux_participation >= 50) niveauEl.textContent = 'Intermédiaire';
    else niveauEl.textContent = 'Débutant';

    document.getElementById('liste-prochaines-activites-eleve').innerHTML = activitesAVenir.length
        ? activitesAVenir.map(ligneActiviteEleve).join('')
        : '<div class="text-muted small py-3 text-center">Aucune activité à venir.</div>';

    const conteneurClubs = document.getElementById('liste-clubs-eleve');
    if (inscriptions.length === 0) {
        conteneurClubs.innerHTML = '<div class="text-muted small py-3 text-center">Aucun club rejoint.</div>';
    } else {
        const lignes = await Promise.all(inscriptions.slice(0, 4).map(async (i) => {
            const stats = await appelApi(`/clubs/${i.club}/statistiques/`);
            return ligneClubEleve({ nom: i.club_nom }, stats ? stats.taux_participation_moyen : 0);
        }));
        conteneurClubs.innerHTML = lignes.join('');
    }

    document.getElementById('liste-notifications-eleve').innerHTML = notifications && notifications.length
        ? notifications.slice(0, 4).map(ligneNotificationEleve).join('')
        : '<div class="text-muted small py-3 text-center">Aucune notification.</div>';

    document.getElementById('conteneur-badges-eleve').innerHTML = [
        creerBadgeEleve('bi-shield-fill-check', 'Assidu', `${rapport.total_activites} activités`, '#6C5CE7'),
        creerBadgeEleve('bi-star-fill', 'Ponctuel', `${rapport.total_presences} présences`, '#22c55e'),
        creerBadgeEleve('bi-people-fill', 'Participatif', `${inscriptions.length} clubs rejoints`, '#f59e0b'),
        creerBadgeEleve('bi-bell-fill', 'Informé', `${notifications ? notifications.length : 0} notifications`, '#3b82f6'),
    ].join('');
}

// ---------- Vue Responsable pédagogique ----------

// Carte de chiffre clé du responsable pédagogique.
function creerCarteStatProviseur(icone, valeur, libelle) {
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

// Ligne d'une activité à venir (couleur de la catégorie du club).
function ligneActiviteProviseur(activite) {
    const couleur = COULEURS_CATEGORIES[activite.categorie] || '#6b7280';
    return `
        <div class="d-flex justify-content-between align-items-center py-2 border-bottom">
            <div class="d-flex align-items-center gap-2">
                <div class="rounded-circle flex-shrink-0" style="width: 8px; height: 8px; background-color: ${couleur};"></div>
                <div>
                    <div class="fw-medium small">${echapperHTML(activite.titre)}</div>
                    <div class="text-muted" style="font-size: 0.75rem;">${activite.date}</div>
                </div>
            </div>
            <span class="badge" style="background-color: ${couleur}22; color: ${couleur};">${echapperHTML(activite.categorie)}</span>
        </div>`;
}

// Barre de taux de présence d'un club.
function barreParticipationProviseur(club) {
    const couleur = club.taux_participation >= 70 ? '#22c55e' : club.taux_participation >= 40 ? '#f59e0b' : '#ef4444';
    return `
        <div class="mb-3">
            <div class="d-flex justify-content-between mb-1">
                <span class="small fw-medium">${echapperHTML(club.nom)}</span>
                <span class="small fw-semibold">${club.taux_participation}%</span>
            </div>
            <div class="progress" style="height: 8px;">
                <div class="progress-bar" style="width: ${club.taux_participation}%; background-color: ${couleur};"></div>
            </div>
        </div>`;
}

// Ligne de statistique rapide (nouveaux clubs, activités à valider, présences, absences).
function ligneStatRapideProviseur(icone, couleur, valeur, libelle) {
    return `
        <div class="d-flex align-items-center gap-3 py-2 border-bottom">
            <div class="rounded-circle d-flex align-items-center justify-content-center flex-shrink-0" style="width: 38px; height: 38px; background-color: ${couleur}22; color: ${couleur};">
                <i class="bi ${icone}"></i>
            </div>
            <div>
                <div class="text-muted small">${libelle}</div>
                <div class="fw-bold">${valeur}</div>
            </div>
        </div>`;
}

// Ligne d'une notification récente.
function ligneNotificationProviseur(n) {
    return `
        <div class="d-flex align-items-start gap-2 py-2 border-bottom">
            <i class="bi bi-bell text-muted" style="margin-top: 2px;"></i>
            <div>
                <div class="small fw-medium">${echapperHTML(n.titre)}</div>
                <div class="text-muted" style="font-size: 0.72rem;">${tempsEcouleSimple(n.date_creation)}</div>
            </div>
        </div>`;
}

// Durée écoulée lisible (« Il y a 5 min », « Il y a 2 heures »...).
function tempsEcouleSimple(dateString) {
    const diffMs = new Date() - new Date(dateString);
    const diffMin = Math.floor(diffMs / 60000);
    if (diffMin < 60) return `Il y a ${diffMin} min`;
    const diffH = Math.floor(diffMin / 60);
    if (diffH < 24) return `Il y a ${diffH} heure${diffH > 1 ? 's' : ''}`;
    return `Il y a ${Math.floor(diffH / 24)} jour${Math.floor(diffH / 24) > 1 ? 's' : ''}`;
}

// Vue responsable pédagogique : chiffres clés, activités, participation, graphiques, notifications.
async function chargerDashboardProviseur(profil) {
    document.getElementById('salutation-proviseur').textContent = `Bonjour, ${profil.prenom} 👋`;

    const stats = await appelApi('/predictions/statistiques-globales/');
    if (!stats) return;

    document.getElementById('cartes-stats-proviseur').innerHTML = [
        creerCarteStatProviseur('bi-diagram-3-fill', stats.nombre_clubs, 'Clubs supervisés'),
        creerCarteStatProviseur('bi-calendar-event-fill', stats.activites_en_cours, 'Activités en cours'),
        creerCarteStatProviseur('bi-people-fill', stats.nombre_eleves, 'Élèves inscrits'),
        creerCarteStatProviseur('bi-graph-up', stats.taux_participation_global + '%', 'Taux de participation'),
    ].join('');

    document.getElementById('liste-activites-proviseur').innerHTML = stats.activites_a_venir.length
        ? stats.activites_a_venir.map(ligneActiviteProviseur).join('')
        : '<div class="text-muted small py-3 text-center">Aucune activité à venir.</div>';

    document.getElementById('barres-participation-proviseur').innerHTML = stats.clubs_taux_participation.length
        ? stats.clubs_taux_participation.map(barreParticipationProviseur).join('')
        : '<div class="text-muted small py-3 text-center">Pas encore de données.</div>';

    // Demandes de rattachement parent → enfant à traiter (anciens liens en attente + demandes par matricule/nom).
    const [liensAttente, demandesAttente] = await Promise.all([
        appelApi('/auth/parents/demandes_rattachement/'),
        appelApi('/auth/demandes-rattachement/?statut=en_attente'),
    ]);
    const nbRattachements = (Array.isArray(liensAttente) ? liensAttente.length : 0)
        + (Array.isArray(demandesAttente) ? demandesAttente.length : 0);

    document.getElementById('stats-rapides-proviseur').innerHTML = [
        ligneStatRapideProviseur('bi-plus-circle', '#22c55e', stats.nouveaux_clubs_mois, 'Nouveaux clubs ce mois'),
        ligneStatRapideProviseur('bi-check2-square', '#6C5CE7', stats.activites_a_valider, 'Activités à valider'),
        ligneStatRapideProviseur('bi-person-check', '#3b82f6', stats.presences_mois, 'Présences ce mois'),
        ligneStatRapideProviseur('bi-person-x', '#ef4444', stats.absences_mois, 'Absences ce mois'),
        // Lien direct vers le tableau des rattachements (page « Comptes en attente »).
        `<a href="/comptes-en-attente/#tableau-rattachements" class="text-decoration-none text-reset">
            ${ligneStatRapideProviseur('bi-link-45deg', '#f59e0b', nbRattachements, 'Demandes de rattachement parent à valider')}
         </a>`,
    ].join('');

    new Chart(document.getElementById('graphique-repartition-proviseur'), {
        type: 'doughnut',
        data: {
            labels: stats.repartition_categories.map(c => c.categorie),
            datasets: [{
                data: stats.repartition_categories.map(c => c.total),
                backgroundColor: stats.repartition_categories.map(c => COULEURS_CATEGORIES[c.categorie] || '#6b7280'),
                borderWidth: 0,
            }],
        },
        options: { plugins: { legend: { position: 'bottom', labels: { boxWidth: 10, font: { size: 10 } } } } },
    });

    new Chart(document.getElementById('graphique-evolution-proviseur'), {
        type: 'line',
        data: {
            labels: stats.evolution_inscriptions.map(e => e.mois),
            datasets: [{
                label: 'Inscriptions',
                data: stats.evolution_inscriptions.map(e => e.total),
                borderColor: '#6C5CE7',
                backgroundColor: 'transparent',
                tension: 0.35,
                pointRadius: 3,
            }],
        },
        options: {
            plugins: { legend: { display: true, position: 'bottom', labels: { boxWidth: 10, font: { size: 10 } } } },
            scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } },
        },
    });

    const notifications = await appelApi('/notifications/');
    document.getElementById('notifications-proviseur').innerHTML = notifications && notifications.length
        ? notifications.slice(0, 5).map(ligneNotificationProviseur).join('')
        : '<div class="text-muted small py-3 text-center">Aucune notification.</div>';

    // Correction : ce chargement ne se déclenchait jamais tout seul auparavant.
    chargerTableauAttenteProviseur('eleve');
}

// ---------- Tableau "Inscriptions en attente" du dashboard proviseur ----------

// Ligne d'un compte en attente (élève ou encadreur).
function ligneAttenteProviseur(compte) {
    const details = compte.role === 'eleve'
        ? `Matricule : ${echapperHTML(compte.matricule || '-')}`
        : `${echapperHTML(compte.domaine_competence || '-')} · Club : ${echapperHTML(compte.club_souhaite || '-')}`;

    return `
        <tr data-id="${compte.id}">
            <td class="fw-medium">${echapperHTML(compte.nom_complet)}</td>
            <td class="text-muted small">${details}</td>
            <td class="text-muted small">${new Date(compte.date_joined).toLocaleDateString('fr-FR')}</td>
            <td class="text-end">
                <button class="btn btn-sm btn-valider-action btn-valider-attente-proviseur" data-id="${compte.id}"><i class="bi bi-check-lg"></i></button>
                <button class="btn btn-sm btn-refuser-action btn-refuser-attente-proviseur" data-id="${compte.id}"><i class="bi bi-x-lg"></i></button>
            </td>
        </tr>`;
}

// Charge les comptes en attente du rôle choisi et branche les boutons valider/refuser.
async function chargerTableauAttenteProviseur(role = 'eleve') {
    const comptes = await appelApi(`/auth/comptes-en-attente/?role=${role}`);
    const tbody = document.getElementById('tableau-attente-proviseur');
    if (!tbody) return;

    tbody.innerHTML = comptes && comptes.length
        ? comptes.map(ligneAttenteProviseur).join('')
        : '<tr><td colspan="4" class="text-center text-muted py-3">Aucune demande en attente.</td></tr>';

    document.querySelectorAll('.btn-valider-attente-proviseur').forEach(bouton => {
        bouton.addEventListener('click', async (e) => {
            await appelApi(`/auth/comptes/${e.currentTarget.dataset.id}/valider/`, { method: 'POST' });
            chargerTableauAttenteProviseur(document.querySelector('[data-role-attente].active')?.dataset.roleAttente || 'eleve');
        });
    });
    document.querySelectorAll('.btn-refuser-attente-proviseur').forEach(bouton => {
        bouton.addEventListener('click', async (e) => {
            await appelApi(`/auth/comptes/${e.currentTarget.dataset.id}/refuser/`, { method: 'POST' });
            chargerTableauAttenteProviseur(document.querySelector('[data-role-attente].active')?.dataset.roleAttente || 'eleve');
        });
    });
}

// Onglets « Élèves / Encadreurs » du tableau des comptes en attente.
document.querySelectorAll('[data-role-attente]').forEach(bouton => {
    bouton.addEventListener('click', (e) => {
        document.querySelectorAll('[data-role-attente]').forEach(b => b.classList.remove('active'));
        e.currentTarget.classList.add('active');
        // Correction : la ligne "chargerTableauAttenteProviseur('eleve')" en double a été retirée,
        // elle écrasait systématiquement le clic sur l'onglet "Encadreurs".
        chargerTableauAttenteProviseur(e.currentTarget.dataset.roleAttente);
    });
});

// ---------- Aiguillage par rôle ----------

// Affiche la vue correspondant au rôle de l'utilisateur connecté.
async function chargerDashboard() {
    const profil = await appelApi('/auth/profil/');
    if (!profil) return;

    if (profil.role === 'eleve') {
        document.getElementById('vue-generale').classList.add('d-none');
        document.getElementById('vue-proviseur').classList.add('d-none');
        document.getElementById('vue-eleve').classList.remove('d-none');
        await chargerDashboardEleve(profil);
    } else if (profil.role === 'proviseur') {
        document.getElementById('vue-generale').classList.add('d-none');
        document.getElementById('vue-eleve').classList.add('d-none');
        document.getElementById('vue-proviseur').classList.remove('d-none');
        await chargerDashboardProviseur(profil);
    } else {
        document.getElementById('vue-proviseur').classList.add('d-none');
        document.getElementById('vue-eleve').classList.add('d-none');
        await chargerDashboardGeneral(profil);
    }
}

document.addEventListener('DOMContentLoaded', chargerDashboard);