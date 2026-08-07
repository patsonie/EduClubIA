const NOMS_MOIS_P = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin', 'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre'];
const JOURS_SEMAINE_P = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'];

let dateAfficheeParent = new Date();
let enfantSelectionneId = null;
let activitesEnfantMois = [];

async function chargerActivitesEnfantMois(eleveId, annee, mois) {
    const dashboard = await appelApi('/auth/dashboard-parent/');
    const enfant = dashboard.enfants.find(e => String(e.id) === String(eleveId));
    if (!enfant) { activitesEnfantMois = []; return; }

    activitesEnfantMois = enfant.activites_a_venir.filter(a => {
        const d = new Date(a.date);
        return d.getFullYear() === annee && d.getMonth() === mois;
    });
}

function construireGrilleParent() {
    const annee = dateAfficheeParent.getFullYear();
    const mois = dateAfficheeParent.getMonth();
    document.getElementById('titre-mois-calendrier-parent').textContent = `${NOMS_MOIS_P[mois]} ${annee}`;

    const grille = document.getElementById('grille-calendrier-parent');
    grille.innerHTML = JOURS_SEMAINE_P.map(j => `<div class="jour-entete">${j}</div>`).join('');

    const premierJourMois = new Date(annee, mois, 1);
    let decalage = premierJourMois.getDay() - 1;
    if (decalage < 0) decalage = 6;

    const nbJoursMois = new Date(annee, mois + 1, 0).getDate();
    const nbJoursMoisPrecedent = new Date(annee, mois, 0).getDate();
    const aujourdhui = new Date();

    const cases = [];
    for (let i = decalage; i > 0; i--) cases.push({ jour: nbJoursMoisPrecedent - i + 1, horsMois: true });
    for (let j = 1; j <= nbJoursMois; j++) cases.push({ jour: j, horsMois: false });
    while (cases.length % 7 !== 0) cases.push({ jour: cases.length, horsMois: true });

    cases.forEach(c => {
        const estAujourdhui = !c.horsMois && c.jour === aujourdhui.getDate() && mois === aujourdhui.getMonth() && annee === aujourdhui.getFullYear();
        const dateJourStr = `${annee}-${String(mois + 1).padStart(2, '0')}-${String(c.jour).padStart(2, '0')}`;
        const activitesJour = !c.horsMois ? activitesEnfantMois.filter(a => a.date === dateJourStr) : [];
        const pastilles = activitesJour.map(a => `
            <div class="activite-pastille ${COULEURS_STATUT_CAL[a.statut] || 'bg-secondary-subtle text-secondary'}" title="${echapperHTML(a.titre)} - ${echapperHTML(a.club_nom || '')}">
                ${echapperHTML(a.titre)}
            </div>`).join('');
            
        grille.innerHTML += `
            <div class="jour-case ${c.horsMois ? 'hors-mois' : ''} ${estAujourdhui ? 'aujourdhui' : ''}">
                <div class="jour-numero">${c.jour}</div>${pastilles}
            </div>`;
    });
}

async function actualiserCalendrierParent() {
    if (!enfantSelectionneId) return;
    await chargerActivitesEnfantMois(enfantSelectionneId, dateAfficheeParent.getFullYear(), dateAfficheeParent.getMonth());
    construireGrilleParent();
}

document.getElementById('btn-mois-precedent-parent').addEventListener('click', () => {
    dateAfficheeParent.setMonth(dateAfficheeParent.getMonth() - 1);
    actualiserCalendrierParent();
});
document.getElementById('btn-mois-suivant-parent').addEventListener('click', () => {
    dateAfficheeParent.setMonth(dateAfficheeParent.getMonth() + 1);
    actualiserCalendrierParent();
});

async function initialiserSelectEnfantsCalendrier() {
    const dashboard = await appelApi('/auth/dashboard-parent/');
    const select = document.getElementById('select-enfant-calendrier');

    if (!dashboard || dashboard.nombre_enfants === 0) return;

    select.innerHTML = dashboard.enfants.map(e => `<option value="${e.id}">${e.nom_complet}</option>`).join('');
    enfantSelectionneId = dashboard.enfants[0].id;
    select.addEventListener('change', (e) => {
        enfantSelectionneId = e.target.value;
        actualiserCalendrierParent();
    });
    actualiserCalendrierParent();
}

document.addEventListener('DOMContentLoaded', initialiserSelectEnfantsCalendrier);