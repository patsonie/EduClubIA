// Page « Calendrier » : activités du mois affiché, sous forme de grille.
const NOMS_MOIS = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin', 'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre'];
const JOURS_SEMAINE = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'];

// Mois affiché et activités correspondantes.
let dateAffichee = new Date();
let activitesDuMois = [];

// Couleur des pastilles selon le statut de l'activité.
const COULEURS_STATUT_CAL = {
    planifiee: 'bg-warning-subtle text-warning', validee: 'bg-primary-subtle text-primary',
    en_cours: 'bg-info-subtle text-info', terminee: 'bg-success-subtle text-success',
    annulee: 'bg-danger-subtle text-danger',
};

// Garde les activités du mois affiché.
async function chargerActivitesDuMois(annee, mois) {
    const data = await appelApi('/activites/');
    const toutes = data.results || data;
    activitesDuMois = toutes.filter(a => {
        const d = new Date(a.date);
        return d.getFullYear() === annee && d.getMonth() === mois;
    });
}

// Construit la grille du mois (semaines commençant le lundi).
function construireGrille() {
    const annee = dateAffichee.getFullYear();
    const mois = dateAffichee.getMonth();
    document.getElementById('titre-mois-calendrier').textContent = `${NOMS_MOIS[mois]} ${annee}`;

    const grille = document.getElementById('grille-calendrier');
    grille.innerHTML = JOURS_SEMAINE.map(j => `<div class="jour-entete">${j}</div>`).join('');

    // Décalage du premier jour (lundi = 0).
    const premierJourMois = new Date(annee, mois, 1);
    let decalage = premierJourMois.getDay() - 1;
    if (decalage < 0) decalage = 6;

    const nbJoursMois = new Date(annee, mois + 1, 0).getDate();
    const nbJoursMoisPrecedent = new Date(annee, mois, 0).getDate();
    const aujourdhui = new Date();

    // Cases du mois précédent, du mois en cours et du mois suivant pour compléter les semaines.
    const cases = [];
    for (let i = decalage; i > 0; i--) {
        cases.push({ jour: nbJoursMoisPrecedent - i + 1, horsMois: true });
    }
    for (let j = 1; j <= nbJoursMois; j++) {
        cases.push({ jour: j, horsMois: false });
    }
    while (cases.length % 7 !== 0) {
        cases.push({ jour: cases.length - (decalage + nbJoursMois) + 1, horsMois: true });
    }

    // Une case par jour, avec ses activités.
    cases.forEach(c => {
        const estAujourdhui = !c.horsMois && c.jour === aujourdhui.getDate() && mois === aujourdhui.getMonth() && annee === aujourdhui.getFullYear();
        const dateJourStr = `${annee}-${String(mois + 1).padStart(2, '0')}-${String(c.jour).padStart(2, '0')}`;
        const activitesJour = !c.horsMois ? activitesDuMois.filter(a => a.date === dateJourStr) : [];

        const pastilles = activitesJour.map(a => `
            <div class="activite-pastille ${COULEURS_STATUT_CAL[a.statut] || 'bg-secondary-subtle text-secondary'}" title="${echapperHTML(a.titre)} - ${echapperHTML(a.club_nom || '')}">
                ${echapperHTML(a.titre)}
            </div>`).join('');

        grille.innerHTML += `
            <div class="jour-case ${c.horsMois ? 'hors-mois' : ''} ${estAujourdhui ? 'aujourdhui' : ''}">
                <div class="jour-numero">${c.jour}</div>
                ${pastilles}
            </div>`;
    });
}

// Recharge les activités puis redessine la grille.
async function actualiserCalendrier() {
    await chargerActivitesDuMois(dateAffichee.getFullYear(), dateAffichee.getMonth());
    construireGrille();
}

// Navigation : mois précédent, mois suivant, aujourd'hui.
document.getElementById('btn-mois-precedent').addEventListener('click', () => {
    dateAffichee.setMonth(dateAffichee.getMonth() - 1);
    actualiserCalendrier();
});
document.getElementById('btn-mois-suivant').addEventListener('click', () => {
    dateAffichee.setMonth(dateAffichee.getMonth() + 1);
    actualiserCalendrier();
});
document.getElementById('btn-aujourdhui').addEventListener('click', () => {
    dateAffichee = new Date();
    actualiserCalendrier();
});

document.addEventListener('DOMContentLoaded', actualiserCalendrier);
