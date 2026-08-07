async function chargerMesActivites() {
    const inscriptions = await appelApi('/inscriptions/?statut=validee');
    const mesInscriptions = inscriptions.results || inscriptions;
    const clubsIds = mesInscriptions.map(i => i.club);

    const toutesActivites = await appelApi('/activites/');
    const activites = (toutesActivites.results || toutesActivites)
        .filter(a => clubsIds.some(id => mesInscriptions.find(i => i.club === id && i.club_nom)))
        .filter(a => mesInscriptions.some(i => i.club_nom === a.club_nom));

    const tbody = document.getElementById('tableau-mes-activites');
    tbody.innerHTML = activites.length
        ? activites.map(a => `
            <tr>
                <td class="fw-medium">${echapperHTML(a.titre)}</td>
                <td class="text-muted small">${echapperHTML(a.club_nom)}</td>
                <td class="text-muted small">${a.date}</td>
                <td class="text-muted small">${echapperHTML(a.lieu)}</td>
            </tr>`).join('')
        : '<tr><td colspan="4" class="text-center text-muted py-4">Aucune activité à venir.</td></tr>';
}
document.addEventListener('DOMContentLoaded', chargerMesActivites);