// Page « Rapports » (gestionnaires) : statistiques par club, export PDF et entraînement de l'IA.
// Ligne d'un club ; couleur du taux de présence (vert ≥ 70 %, orange ≥ 40 %, rouge sinon).
function ligneRapportClub(c) {
    const couleurTaux = c.taux_participation >= 70 ? 'success' : c.taux_participation >= 40 ? 'warning' : 'danger';
    return `
        <tr>
            <td class="fw-medium">${echapperHTML(c.nom)}</td>
            <td><span class="badge bg-primary-subtle text-primary">${echapperHTML(c.categorie)}</span></td>
            <td>${c.nombre_membres}</td>
            <td>${c.nombre_activites}</td>
            <td><span class="badge bg-${couleurTaux}-subtle text-${couleurTaux}">${c.taux_participation}%</span></td>
        </tr>`;
}

// Charge le rapport (tous les clubs ou un seul) et remplit les cartes et le tableau.
async function chargerRapport(clubId = '') {
    const endpoint = clubId ? `/predictions/rapport-detaille/?club=${clubId}` : '/predictions/rapport-detaille/';
    const rapport = await appelApi(endpoint);
    if (!rapport) return;

    document.getElementById('cartes-rapport').innerHTML = `
        <div class="col-md-4"><div class="carte-stat"><div class="valeur">${rapport.total_clubs}</div><div class="libelle">Clubs actifs</div></div></div>
        <div class="col-md-4"><div class="carte-stat"><div class="valeur">${rapport.total_inscriptions}</div><div class="libelle">Inscriptions totales</div></div></div>
        <div class="col-md-4"><div class="carte-stat"><div class="valeur">${rapport.taux_participation_global}%</div><div class="libelle">Taux de participation global</div></div></div>`;

    document.getElementById('tableau-rapport-clubs').innerHTML = rapport.clubs.length
        ? rapport.clubs.map(ligneRapportClub).join('')
        : '<tr><td colspan="5" class="text-center text-muted py-4">Aucune donnée disponible.</td></tr>';
}

// Remplit la liste de choix des clubs.
async function remplirSelectClubsRapport() {
    const data = await appelApi('/clubs/');
    const clubs = data.results || data;
    const select = document.getElementById('select-club-rapport');
    select.innerHTML = '<option value="">Tous les clubs</option>' +
        clubs.map(c => `<option value="${c.id}">${c.nom}</option>`).join('');
}

// Changement de club et bouton d'impression.
document.getElementById('select-club-rapport').addEventListener('change', (e) => chargerRapport(e.target.value));
document.getElementById('btn-imprimer-rapport').addEventListener('click', () => window.print());

document.addEventListener('DOMContentLoaded', () => {
    remplirSelectClubsRapport();
    chargerRapport();
});

// Le même bouton télécharge aussi la version PDF générée par le serveur.
document.getElementById('btn-imprimer-rapport').addEventListener('click', telechargerRapportPDF);

// Télécharge le PDF avec le jeton d'accès, puis déclenche l'enregistrement du fichier.
async function telechargerRapportPDF() {
    const clubId = document.getElementById('select-club-rapport').value;
    const endpoint = clubId
        ? `/predictions/rapport-detaille/pdf/?club=${clubId}`
        : '/predictions/rapport-detaille/pdf/';

    const token = obtenirToken();
    const reponse = await fetch(`${window.location.origin}/api${endpoint}`, {
        headers: { 'Authorization': `Bearer ${token}` },
    });

    if (!reponse.ok) {
        alert("Erreur lors de la génération du PDF.");
        return;
    }

    const blob = await reponse.blob();
    const url = window.URL.createObjectURL(blob);
    const lien = document.createElement('a');
    lien.href = url;
    lien.download = 'rapport_clubs.pdf';
    document.body.appendChild(lien);
    lien.click();
    lien.remove();
    window.URL.revokeObjectURL(url);
}


// Affiche le résultat du dernier entraînement des modèles IA.
async function chargerDernierEntrainement() {
    const historique = await appelApi('/ia/historique-entrainement/');
    const conteneur = document.getElementById('statut-entrainement-ia');
    if (!historique || historique.length === 0) {
        conteneur.textContent = "Aucun entraînement effectué pour l'instant.";
        return;
    }
    const dernier = historique[0];
    const couleur = dernier.statut === 'succes' ? 'success' : 'danger';
    conteneur.innerHTML = `Dernier entraînement : <span class="text-${couleur} fw-medium">${dernier.statut}</span> — ${echapperHTML(dernier.type_declenchement)} — ${new Date(dernier.date_entrainement).toLocaleString('fr-FR')} (${dernier.duree_secondes}s)`;
}

// Bouton « Réentraîner maintenant » (administrateur).
document.getElementById('btn-reentrainer-ia')?.addEventListener('click', async (e) => {
    e.target.disabled = true;
    e.target.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Entraînement en cours...';

    const resultat = await appelApi('/ia/reentrainement/', {
        method: 'POST',
        body: JSON.stringify({ type_declenchement: 'manuel' }),
    });

    e.target.disabled = false;
    e.target.innerHTML = '<i class="bi bi-arrow-repeat me-1"></i>Réentraîner maintenant';

    if (resultat && resultat.message) {
        alert(`${resultat.message} (${resultat.duree_secondes}s)`);
        chargerDernierEntrainement();
    } else {
        alert("Erreur lors de l'entraînement. Vérifiez qu'il y a assez de données (clubs, inscriptions, activités terminées).");
    }
});

document.addEventListener('DOMContentLoaded', chargerDernierEntrainement);