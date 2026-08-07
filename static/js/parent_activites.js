const BADGES_ACTIVITE_PARENT = { planifiee: 'warning', validee: 'primary', en_cours: 'info', terminee: 'success', annulee: 'danger' };

async function chargerActivitesEnfant(eleveId) {
    const dashboard = await appelApi('/auth/dashboard-parent/');
    const enfant = dashboard.enfants.find(e => String(e.id) === String(eleveId));
    const tbody = document.getElementById('tableau-activites-enfant');

    if (!enfant || enfant.activites_a_venir.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted py-4">Aucune activité à venir.</td></tr>';
        return;
    }

    tbody.innerHTML = enfant.activites_a_venir.map(a => `
        <tr>
            <td class="fw-medium">${echapperHTML(a.titre)}</td>
            <td class="text-muted small">-</td>
            <td class="text-muted small">${a.date}</td>
            <td class="text-muted small">${echapperHTML(a.lieu)}</td>
            <td><span class="badge bg-primary-subtle text-primary">à venir</span></td>
        </tr>`).join('');
}

async function initialiserSelectEnfantsActivites() {
    const dashboard = await appelApi('/auth/dashboard-parent/');
    const select = document.getElementById('select-enfant-activites');

    if (!dashboard || dashboard.nombre_enfants === 0) {
        document.getElementById('tableau-activites-enfant').innerHTML =
            '<tr><td colspan="5" class="text-center text-muted py-4">Aucun enfant associé.</td></tr>';
        return;
    }

    select.innerHTML = dashboard.enfants.map(e => `<option value="${e.id}">${e.nom_complet}</option>`).join('');
    select.addEventListener('change', (e) => chargerActivitesEnfant(e.target.value));
    chargerActivitesEnfant(dashboard.enfants[0].id);
}

document.addEventListener('DOMContentLoaded', initialiserSelectEnfantsActivites);