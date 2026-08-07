const BADGES_PRESENCE = { present: 'success', absent: 'danger', excuse: 'warning', retard: 'info' };

async function chargerMesPresences() {
    const profil = await appelApi('/auth/profil/');
    const rapport = await appelApi(`/participations/rapport_individuel/?eleve_id=${profil.id}`);

    document.getElementById('carte-taux-presence').innerHTML = `
        <div class="col-md-4"><div class="carte-stat"><div class="valeur">${rapport.taux_participation}%</div><div class="libelle">Taux de présence</div></div></div>
        <div class="col-md-4"><div class="carte-stat"><div class="valeur">${rapport.total_presences}</div><div class="libelle">Présences</div></div></div>
        <div class="col-md-4"><div class="carte-stat"><div class="valeur">${rapport.total_activites}</div><div class="libelle">Activités totales</div></div></div>`;

    const participations = await appelApi('/participations/');
    const data = participations.results || participations;
    const tbody = document.getElementById('tableau-mes-presences');
   tbody.innerHTML = data.length
        ? data.map(p => `
            <tr>
                <td class="fw-medium">${echapperHTML(p.activite_titre)}</td>
                <td class="text-muted small">${new Date(p.date_enregistrement).toLocaleDateString('fr-FR')}</td>
                <td><span class="badge bg-${BADGES_PRESENCE[p.statut]}-subtle text-${BADGES_PRESENCE[p.statut]}">${p.statut}</span></td>
            </tr>`).join('')
        : '<tr><td colspan="3" class="text-center text-muted py-4">Aucune présence enregistrée.</td></tr>';
}
document.addEventListener('DOMContentLoaded', chargerMesPresences);
