const API_BASE = 'http://127.0.0.1:8000/api';
let etapeActuelle = 1;
let roleSelectionne = null;
let typeEncadreurSelectionne = null;
const zoneDepotProviseur = document.getElementById('zone-depot-proviseur');
const champFichierProviseur = document.getElementById('champ-justificatif-proviseur');
const texteDepotProviseur = document.getElementById('texte-depot-proviseur');

function allerAEtape(numero) {
    document.querySelectorAll('.etape-contenu').forEach(e => e.classList.add('d-none'));
    document.querySelector(`.etape-contenu[data-etape="${numero}"]`).classList.remove('d-none');

    document.querySelectorAll('.etape-progression').forEach(e => {
        const n = parseInt(e.dataset.etape);
        e.classList.remove('active', 'complete');
        if (n < numero) e.classList.add('complete');
        if (n === numero) e.classList.add('active');
    });

    etapeActuelle = numero;
    if (numero === 4) construireRecapitulatif();
    window.scrollTo(0, 0);
}

document.querySelectorAll('.btn-etape-suivante').forEach(bouton => {
    bouton.addEventListener('click', () => {
        if (!validerEtape(etapeActuelle)) return;
        allerAEtape(parseInt(bouton.dataset.suivante));
    });
});
document.querySelectorAll('.btn-etape-precedente').forEach(bouton => {
    bouton.addEventListener('click', () => allerAEtape(parseInt(bouton.dataset.precedente)));
});

function afficherErreur(message) {
    const alerte = document.getElementById('alerte-erreur-inscription');
    alerte.textContent = message;
    alerte.classList.remove('d-none');
    window.scrollTo(0, 0);
}
function masquerErreur() {
    document.getElementById('alerte-erreur-inscription').classList.add('d-none');
}

function validerEtape(numero) {
    masquerErreur();
    if (numero === 1) {
        const champs = document.querySelectorAll('.etape-contenu[data-etape="1"] [required]');
        for (const champ of champs) {
            if (!champ.value) { afficherErreur("Veuillez remplir tous les champs obligatoires."); return false; }
        }
        return true;
    }
    if (numero === 2) {
        if (!roleSelectionne) { afficherErreur("Veuillez sélectionner un rôle."); return false; }
        if (roleSelectionne === 'encadreur' && !typeEncadreurSelectionne) {
            afficherErreur("Veuillez préciser le type d'encadreur."); return false;
        }
        if (roleSelectionne === 'proviseur' && (!champFichierProviseur || champFichierProviseur.files.length === 0)) {
            afficherErreur("L'acte de nomination est obligatoire pour ce rôle.");
            return false;
        }
        return true;
    }
    return true;
}

// --- Sélection du rôle ---
document.querySelectorAll('.carte-role[data-role]').forEach(carte => {
    carte.addEventListener('click', () => {
        document.querySelectorAll('.carte-role[data-role]').forEach(c => c.classList.remove('selectionnee'));
        carte.classList.add('selectionnee');
        roleSelectionne = carte.dataset.role;

        document.querySelectorAll('.champs-role').forEach(c => c.classList.add('d-none'));
        document.getElementById(`champs-${roleSelectionne}`)?.classList.remove('d-none');
    });
});

// --- Sélection du type d'encadreur ---
document.querySelectorAll('.carte-role[data-type-encadreur]').forEach(carte => {
    carte.addEventListener('click', () => {
        document.querySelectorAll('.carte-role[data-type-encadreur]').forEach(c => c.classList.remove('selectionnee'));
        carte.classList.add('selectionnee');
        typeEncadreurSelectionne = carte.dataset.typeEncadreur;

        const ligneMatricule = document.getElementById('ligne-matricule-encadreur');
        const ligneJustificatif = document.getElementById('ligne-justificatif-encadreur');
        const messageStatut = document.getElementById('message-statut-encadreur');

        if (typeEncadreurSelectionne === 'professionnel') {
            ligneMatricule.querySelector('input').required = true;
            ligneJustificatif.classList.remove('d-none');
            messageStatut.innerHTML = '<i class="bi bi-info-circle me-1"></i>Votre demande sera examinée par l\'administration après vérification du justificatif.';
        } else {
            ligneMatricule.querySelector('input').required = false;
            ligneJustificatif.classList.remove('d-none');
            messageStatut.innerHTML = '<i class="bi bi-info-circle me-1"></i>Votre inscription a été enregistrée. Comme encadreur vacataire, votre compte doit être validé par le responsable pédagogique avant son activation (justificatif facultatif).';
        }
    });
});

// --- Indicateurs de force du mot de passe ---
function verifierMotDePasse() {
    const valeur = document.getElementById('champ-password').value;
    const criteres = {
        'ind-longueur': valeur.length >= 8,
        'ind-majuscule': /[A-Z]/.test(valeur),
        'ind-chiffre': /[0-9]/.test(valeur),
    };
    Object.entries(criteres).forEach(([id, valide]) => {
        const el = document.getElementById(id);
        el.classList.toggle('valide', valide);
        el.classList.toggle('invalide', !valide);
        el.querySelector('i').className = valide ? 'bi bi-check-circle-fill' : 'bi bi-circle';
    });
    return Object.values(criteres).every(Boolean);
}
document.getElementById('champ-password').addEventListener('input', verifierMotDePasse);

document.getElementById('btn-vers-confirmation').addEventListener('click', () => {
    masquerErreur();
    const password = document.getElementById('champ-password').value;
    const password2 = document.getElementById('champ-password2').value;

    if (!verifierMotDePasse()) { afficherErreur("Le mot de passe ne respecte pas tous les critères de sécurité."); return; }
    if (password !== password2) { afficherErreur("Les mots de passe ne correspondent pas."); return; }
    if (!document.getElementById('check-conditions').checked || !document.getElementById('check-confidentialite').checked) {
        afficherErreur("Veuillez accepter les conditions d'utilisation et la politique de confidentialité.");
        return;
    }
    allerAEtape(4);
});

// --- Récapitulatif ---
const LIBELLES_ROLES = { eleve: 'Élève', parent: "Parent d'élève", encadreur: 'Encadreur', proviseur: 'Responsable pédagogique' };

function construireRecapitulatif() {
    const form = document.getElementById('formulaire-inscription');
    const data = new FormData(form);
    const conteneur = document.getElementById('recapitulatif-inscription');

    let lignes = [
        ['Nom complet', `${data.get('prenom')} ${data.get('nom')}`],
        ['Email', data.get('email')],
        ['Téléphone', data.get('telephone')],
        ['Rôle', LIBELLES_ROLES[roleSelectionne] || '-'],
    ];

    if (roleSelectionne === 'encadreur') {
        lignes.push(['Type', typeEncadreurSelectionne === 'professionnel' ? 'Professionnel' : 'Vacataire']);
        lignes.push(['Domaine', data.get('domaine_competence') || '-']);
        lignes.push(['Justificatif', data.get('justificatif') && data.get('justificatif').name ? data.get('justificatif').name : 'Non fourni']);
        lignes.push(['Statut', typeEncadreurSelectionne === 'professionnel'
            ? 'En attente de validation par l\'administration'
            : 'En attente de validation par le responsable pédagogique']);
    } else if (roleSelectionne === 'eleve') {
        lignes.push(['Matricule', data.get('matricule') || '-']);
        lignes.push(['Classe', data.get('classe') || '-']);
        lignes.push(['Statut', 'En attente de validation']);
    } else if (roleSelectionne === 'proviseur') {
        lignes.push(['Statut', 'En attente de validation par un administrateur']);
    } else if (roleSelectionne === 'parent') {
        lignes.push(['Lien avec l\'élève', data.get('type_lien_eleve') || '-']);
        lignes.push(['Statut', 'Actif — vous pourrez associer votre enfant ensuite']);
    }

    conteneur.innerHTML = lignes.map(([libelle, valeur]) => `
        <div class="ligne-recap">
            <span class="libelle-recap">${libelle}</span>
            <span class="valeur-recap">${valeur}</span>
        </div>`).join('');
}

// --- Soumission finale ---
document.getElementById('formulaire-inscription').addEventListener('submit', async (e) => {
    e.preventDefault();
    masquerErreur();

    const form = e.target;
    const formDataOriginal = new FormData(form);

    const donnees = {
        nom: formDataOriginal.get('nom'), prenom: formDataOriginal.get('prenom'),
        email: formDataOriginal.get('email'), telephone: formDataOriginal.get('telephone'),
        date_naissance: formDataOriginal.get('date_naissance'), genre: formDataOriginal.get('genre'),
        role: roleSelectionne, password: formDataOriginal.get('password'), password2: formDataOriginal.get('password2'),
    };

    let fichierJustificatif = null;

    if (roleSelectionne === 'eleve') {
        donnees.matricule = formDataOriginal.get('matricule');
        donnees.classe = formDataOriginal.get('classe');
    } else if (roleSelectionne === 'parent') {
        donnees.type_lien_eleve = formDataOriginal.get('type_lien_eleve');
        donnees.matricule_enfant = formDataOriginal.get('matricule_enfant');
    } else if (roleSelectionne === 'encadreur') {
        donnees.type_encadreur = typeEncadreurSelectionne;
        donnees.matricule = formDataOriginal.get('matricule_encadreur');
        donnees.fonction = formDataOriginal.get('fonction');
        donnees.domaine_competence = formDataOriginal.get('domaine_competence');
        donnees.club_souhaite = formDataOriginal.get('club_souhaite');
        fichierJustificatif = formDataOriginal.get('justificatif');
    } else if (roleSelectionne === 'proviseur') {
        donnees.matricule = formDataOriginal.get('matricule');
        donnees.fonction = formDataOriginal.get('fonction');
        donnees.service_responsabilite = formDataOriginal.get('service_responsabilite');
        donnees.etablissement = formDataOriginal.get('etablissement');
        fichierJustificatif = champFichierProviseur.files[0];
    }

    try {
        let reponse;

        if (fichierJustificatif && fichierJustificatif.size > 0) {
            // Envoi en multipart/form-data pour transporter le fichier
            const formDataEnvoi = new FormData();
            Object.entries(donnees).forEach(([cle, valeur]) => {
                if (valeur !== null && valeur !== undefined) formDataEnvoi.append(cle, valeur);
            });
            formDataEnvoi.append('justificatif', fichierJustificatif);

            reponse = await fetch(`${API_BASE}/auth/register/`, {
                method: 'POST',
                body: formDataEnvoi, // Pas de Content-Type manuel : le navigateur le définit avec la boundary correcte
            });
        } else {
            reponse = await fetch(`${API_BASE}/auth/register/`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(donnees),
            });
        }

        const resultat = await reponse.json();

        if (!reponse.ok) {
            const premierChamp = Object.keys(resultat)[0];
            const message = Array.isArray(resultat[premierChamp]) ? resultat[premierChamp][0] : resultat[premierChamp];
            afficherErreur(message || "Une erreur est survenue lors de l'inscription.");
            return;
        }

        if (resultat.access) {
            localStorage.setItem('access_token', resultat.access);
            localStorage.setItem('refresh_token', resultat.refresh);
            window.location.href = '/';
        } else if (roleSelectionne === 'proviseur') {
            window.location.href = `/validation-compte/?email=${encodeURIComponent(donnees.email)}`;
        } else {
            alert(resultat.message);
            window.location.href = '/connexion/';
        }
    } catch (err) {
        afficherErreur("Impossible de contacter le serveur.");
    }
});

// --- Zone de dépôt du justificatif pour le responsable pédagogique ---
if (zoneDepotProviseur) {
    zoneDepotProviseur.addEventListener('click', () => champFichierProviseur.click());

    ['dragover', 'dragleave', 'drop'].forEach(evt => {
        zoneDepotProviseur.addEventListener(evt, (e) => e.preventDefault());
    });
    zoneDepotProviseur.addEventListener('dragover', () => zoneDepotProviseur.classList.add('survole'));
    zoneDepotProviseur.addEventListener('dragleave', () => zoneDepotProviseur.classList.remove('survole'));
    zoneDepotProviseur.addEventListener('drop', (e) => {
        zoneDepotProviseur.classList.remove('survole');
        if (e.dataTransfer.files.length) {
            champFichierProviseur.files = e.dataTransfer.files;
            afficherFichierCharge();
        }
    });
    champFichierProviseur.addEventListener('change', afficherFichierCharge);

    function afficherFichierCharge() {
        if (champFichierProviseur.files.length) {
            zoneDepotProviseur.classList.add('fichier-charge');
            texteDepotProviseur.textContent = `✓ ${champFichierProviseur.files[0].name}`;
        }
    }
}