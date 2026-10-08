// Page « Mes clubs » : contenu différent selon le rôle.
// - Encadreur : le club qu'il encadre, avec accès à sa fiche et aux demandes d'inscription.
// - Élève : ses clubs (membre ou demande en attente), avec annulation / désinscription.

// ---------- Encadreur : son club ----------

async function afficherClubEncadreur(profil, conteneur) {
    document.getElementById('titre-mes-clubs').textContent = 'Mon club';
    const clubEncadre = profil.club_encadre_details;
    if (!clubEncadre) {
        conteneur.innerHTML = `
            <div class="col-12 text-center text-muted py-5">
                Vous n'encadrez aucun club pour le moment.<br>
                <a href="/profil/">Choisissez votre club dans votre profil</a>.
            </div>`;
        return;
    }

    // Détail du club et nombre de demandes d'inscription à traiter.
    const [club, demandes] = await Promise.all([
        appelApi(`/clubs/${clubEncadre.id}/`),
        appelApi(`/inscriptions/?club=${clubEncadre.id}&statut=en_attente`),
    ]);
    if (!club || !club.id) {
        conteneur.innerHTML = '<div class="col-12 text-center text-muted py-5">Impossible de charger votre club.</div>';
        return;
    }
    const nbDemandes = Array.isArray(demandes) ? demandes.length : ((demandes && demandes.results) || []).length;

    conteneur.innerHTML = `
        <div class="col-lg-8">
            <div class="carte p-4">
                <div class="d-flex justify-content-between align-items-start flex-wrap gap-2 mb-2">
                    <h5 class="fw-bold mb-0">${echapperHTML(club.nom)}</h5>
                    <span class="badge bg-primary-subtle text-primary">${echapperHTML(club.categorie)}</span>
                </div>
                <div class="small text-muted mb-3">Statut : ${echapperHTML(club.statut)}</div>
                <p class="text-muted small" style="white-space: pre-line;">${echapperHTML(club.description)}</p>
                <div class="row g-3 mb-3">
                    <div class="col-6"><div class="carte-stat"><div class="valeur">${club.nombre_membres_actuels} / ${club.nombre_max_membres}</div><div class="libelle">Membres</div></div></div>
                    <div class="col-6"><div class="carte-stat"><div class="valeur">${nbDemandes}</div><div class="libelle">Demandes d'inscription en attente</div></div></div>
                </div>
                <div class="d-flex gap-2 flex-wrap">
                    <a href="/clubs/${club.id}/" class="btn btn-primaire-app"><i class="bi bi-eye me-1"></i>Consulter le club</a>
                    <a href="/inscriptions/" class="btn btn-outline-secondary"><i class="bi bi-clipboard-check me-1"></i>Traiter les inscriptions</a>
                </div>
            </div>
        </div>`;
}

// ---------- Élève : ses clubs et ses demandes ----------

async function afficherClubsEleve(conteneur) {
    document.getElementById('lien-tous-les-clubs').classList.remove('d-none');
    const reponse = await appelApi('/inscriptions/');
    const inscriptions = ((reponse && (reponse.results || reponse)) || [])
        .filter(i => i.statut === 'validee' || i.statut === 'en_attente');

    if (!inscriptions.length) {
        conteneur.innerHTML = `
            <div class="col-12 text-center text-muted py-5">
                Vous n'êtes inscrit à aucun club pour le moment.<br>
                <a href="/clubs/">Parcourez les clubs</a> et cliquez sur « S'inscrire ».
            </div>`;
        return;
    }

    // Une carte par club : badge « Membre » ou « En attente » et bouton correspondant.
    conteneur.innerHTML = inscriptions.map(i => {
        const enAttente = i.statut === 'en_attente';
        return `
        <div class="col-md-6 col-lg-4">
            <div class="carte p-3 h-100">
                <div class="d-flex justify-content-between align-items-start mb-1">
                    <h6 class="fw-semibold mb-0">${echapperHTML(i.club_nom)}</h6>
                    <span class="badge ${enAttente ? 'bg-warning-subtle text-warning' : 'bg-success-subtle text-success'}">
                        ${enAttente ? 'En attente' : 'Membre'}
                    </span>
                </div>
                <div class="text-muted small mb-2">Année scolaire : ${echapperHTML(i.annee_scolaire_libelle)}</div>
                <a href="/clubs/${i.club}/" class="btn btn-sm btn-outline-secondary">Voir le club</a>
                <button class="btn btn-sm btn-outline-danger btn-quitter-club" data-inscription="${i.id}" data-attente="${enAttente}">
                    <i class="bi bi-person-dash me-1"></i>${enAttente ? 'Annuler ma demande' : 'Se désinscrire'}
                </button>
            </div>
        </div>`;
    }).join('');

    // Désinscription / annulation : l'inscription passe à « annulée » et la place se libère.
    conteneur.querySelectorAll('.btn-quitter-club').forEach(bouton => {
        bouton.addEventListener('click', async () => {
            const question = bouton.dataset.attente === 'true' ? 'Annuler votre demande ?' : 'Quitter ce club ?';
            if (!confirm(question)) return;
            const resultat = await appelApi(`/inscriptions/${bouton.dataset.inscription}/se_desinscrire/`, { method: 'POST' });
            if (resultat && resultat.id) chargerMesClubs();
            else alert("Désinscription impossible. Réessayez plus tard.");
        });
    });
}

// ---------- Aiguillage selon le rôle ----------

async function chargerMesClubs() {
    const conteneur = document.getElementById('conteneur-mes-clubs');
    const profil = await appelApi('/auth/profil/');
    if (!profil) return;
    if (profil.role === 'encadreur') return afficherClubEncadreur(profil, conteneur);
    return afficherClubsEleve(conteneur);
}

document.addEventListener('DOMContentLoaded', chargerMesClubs);
