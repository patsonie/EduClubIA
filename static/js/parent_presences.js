const BADGES_PRESENCE_PARENT = { present: 'success', absent: 'danger', excuse: 'warning', retard: 'info' };

async function chargerPresencesEnfant(eleveId) {
    const rapport = await appelApi(`/participations/rapport_individuel/?eleve_id=${eleveId}`);
    document.getElementById('carte-taux-presence-enfant').innerHTML = `
        <div class="col-md-4"><div class="carte-stat"><div class="valeur">${rapport.taux_participation}%</div><div class="libelle">Taux de présence</div></div></div>
        <div class="col-md-4"><div class="carte-stat"><div class="valeur">${rapport.total_presences}</div><div class="libelle">Présences</div></div></div>
        <div class="col-md-4"><div class="carte-stat"><div class="valeur">${rapport.total_activites}</div><div class="libelle">Activités totales</div></div></div>`;

    const data = await appelApi(`/participations/?inscription__eleve=${eleveId}`);
    const participations = data.results || data;
    const tbody = document.getElementById('tableau-presences-enfant');

    tbody.innerHTML = participations.length
        ? participations.map(p => `
            <tr>
                <td class="fw-medium">${echapperHTML(p.activite_titre)}</td>
                <td class="text-muted small">${new Date(p.date_enregistrement).toLocaleDateString('fr-FR')}</td>
                <td><span class="badge bg-${BADGES_PRESENCE_PARENT[p.statut]}-subtle text-${BADGES_PRESENCE_PARENT[p.statut]}">${p.statut}</span></td>
            </tr>`).join('')
        : '<tr><td colspan="3" class="text-center text-muted py-4">Aucune présence enregistrée.</td></tr>';
}

async function initialiserSelectEnfantsPresences() {
    const dashboard = await appelApi('/auth/dashboard-parent/');
    const select = document.getElementById('select-enfant-presences');

    if (!dashboard || dashboard.nombre_enfants === 0) {
        document.getElementById('tableau-presences-enfant').innerHTML =
            '<tr><td colspan="3" class="text-center text-muted py-4">Aucun enfant associé.</td></tr>';
        return;
    }

    select.innerHTML = dashboard.enfants.map(e => `<option value="${e.id}">${e.nom_complet}</option>`).join('');
    select.addEventListener('change', (e) => chargerPresencesEnfant(e.target.value));
    chargerPresencesEnfant(dashboard.enfants[0].id);
}

document.addEventListener('DOMContentLoaded', initialiserSelectEnfantsPresences);