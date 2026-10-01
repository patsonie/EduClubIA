const API_BASE = window.location.origin + '/api';
let roleSelectionne = null;
let typeEncadreurSelectionne = null;

const formulaire = document.getElementById('formulaire-inscription');
const zoneDepotProviseur = document.getElementById('zone-depot-proviseur');
const champFichierProviseur = document.getElementById('champ-justificatif-proviseur');
const texteDepotProviseur = document.getElementById('texte-depot-proviseur');
const conteneurInterets = document.getElementById('conteneur-interets');
const boutonCreer = document.getElementById('btn-creer-compte');

// ---------- Messages d'erreur ----------

function afficherErreur(message) {
    const alerte = document.getElementById('alerte-erreur-inscription');
    alerte.textContent = message;
    alerte.classList.remove('d-none');
    alerte.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

function effacerErreurs() {
    document.getElementById('alerte-erreur-inscription').classList.add('d-none');
    formulaire.querySelectorAll('.erreur-champ').forEach(e => e.remove());
    formulaire.querySelectorAll('.is-invalid').forEach(e => e.classList.remove('is-invalid'));
}

/** Affiche un message sous le champ concerné ; retourne false si le champ est introuvable. */
function erreurChamp(champ, message) {
    if (!champ) return false;
    champ.classList.add('is-invalid');
    const cible = champ.closest('.zone-depot-fichier') || champ;
    const p = document.createElement('div');
    p.className = 'erreur-champ';
    p.textContent = message;
    cible.insertAdjacentElement('afterend', p);
    return true;
}

// ---------- Champs : seuls ceux du rôle choisi sont actifs (évite les doublons de "matricule") ----------

function activerChampsDuRole() {
    document.querySelectorAll('.champs-role').forEach(bloc => {
        const actif = bloc.id === `champs-${roleSelectionne}`;
        bloc.classList.toggle('d-none', !actif);
        bloc.querySelectorAll('input, select').forEach(c => { c.disabled = !actif; });
    });
    const estEleve = roleSelectionne === 'eleve';
    document.getElementById('section-interets').classList.toggle('d-none', !estEleve);
    document.getElementById('numero-section-securite').textContent = estEleve ? '4' : '3';
}
activerChampsDuRole();

function champ(nom) {
    return formulaire.querySelector(`[name="${nom}"]:not(:disabled)`);
}

function valeur(nom) {
    const c = champ(nom);
    return c ? c.value.trim() : '';
}

// ---------- Sélection du rôle ----------

document.querySelectorAll('.carte-role[data-role]').forEach(carte => {
    carte.addEventListener('click', () => {
        document.querySelectorAll('.carte-role[data-role]').forEach(c => c.classList.remove('selectionnee'));
        carte.classList.add('selectionnee');
        roleSelectionne = carte.dataset.role;
        activerChampsDuRole();
    });
});

// ---------- Type d'encadreur ----------

document.querySelectorAll('.carte-role[data-type-encadreur]').forEach(carte => {
    carte.addEventListener('click', () => {
        document.querySelectorAll('.carte-role[data-type-encadreur]').forEach(c => c.classList.remove('selectionnee'));
        carte.classList.add('selectionnee');
        typeEncadreurSelectionne = carte.dataset.typeEncadreur;

        const messageStatut = document.getElementById('message-statut-encadreur');
        messageStatut.innerHTML = typeEncadreurSelectionne === 'professionnel'
            ? '<i class="bi bi-info-circle me-1"></i>Votre demande sera examinée par l\'administration après vérification du justificatif.'
            : '<i class="bi bi-info-circle me-1"></i>Votre inscription a été enregistrée. Comme encadreur vacataire, votre compte doit être validé par le responsable pédagogique avant son activation (justificatif facultatif).';
    });
});

// ---------- Indicateurs de force du mot de passe ----------

function verifierMotDePasse() {
    const valeurMdp = document.getElementById('champ-password').value;
    const criteres = {
        'ind-longueur': valeurMdp.length >= 8,
        'ind-majuscule': /[A-Z]/.test(valeurMdp),
        'ind-chiffre': /[0-9]/.test(valeurMdp),
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

// ---------- Validation côté client (le serveur revalide tout) ----------

function validerFormulaire() {
    const erreurs = []; // [champ, message]
    const requis = (nom, message = 'Ce champ est obligatoire.') => {
        if (!valeur(nom)) erreurs.push([champ(nom), message]);
    };

    ['nom', 'prenom', 'email', 'telephone', 'date_naissance', 'genre'].forEach(n => requis(n));

    if (!roleSelectionne) {
        erreurs.push([document.querySelector('.carte-role[data-role]'), 'Veuillez sélectionner un rôle.']);
    } else if (roleSelectionne === 'eleve') {
        requis('matricule', 'Le matricule scolaire est requis.');
        requis('classe');
    } else if (roleSelectionne === 'parent') {
        requis('type_lien_eleve', 'Veuillez préciser votre lien avec l\'élève.');
    } else if (roleSelectionne === 'encadreur') {
        if (!typeEncadreurSelectionne) {
            erreurs.push([document.querySelector('.carte-role[data-type-encadreur]'), 'Veuillez préciser le type d\'encadreur.']);
        } else if (typeEncadreurSelectionne === 'professionnel') {
            requis('matricule_encadreur', 'Le matricule professionnel est requis.');
        }
        requis('fonction');
        requis('domaine_competence');
    } else if (roleSelectionne === 'proviseur') {
        requis('matricule');
        requis('fonction');
        requis('etablissement', 'Le nom de l\'établissement est obligatoire.');
        if (!champFichierProviseur.files.length) {
            erreurs.push([champFichierProviseur, 'L\'acte de nomination est obligatoire pour ce rôle.']);
        }
    }

    if (!verifierMotDePasse()) {
        erreurs.push([champ('password'), 'Le mot de passe ne respecte pas tous les critères de sécurité.']);
    } else if (valeur('password') !== valeur('password2')) {
        erreurs.push([champ('password2'), 'Les mots de passe ne correspondent pas.']);
    }
    ['check-conditions', 'check-confidentialite'].forEach(id => {
        const c = document.getElementById(id);
        if (!c.checked) erreurs.push([c, 'Cette acceptation est obligatoire.']);
    });

    return erreurs;
}

// ---------- Soumission ----------

function chargement(actif) {
    boutonCreer.disabled = actif;
    boutonCreer.querySelector('.texte-bouton').classList.toggle('d-none', actif);
    boutonCreer.querySelector('.texte-chargement').classList.toggle('d-none', !actif);
}

function construireDonnees() {
    const donnees = {
        nom: valeur('nom'), prenom: valeur('prenom'), email: valeur('email'),
        telephone: valeur('telephone'), date_naissance: valeur('date_naissance'), genre: valeur('genre'),
        role: roleSelectionne, password: valeur('password'), password2: valeur('password2'),
    };
    let fichier = null;

    if (roleSelectionne === 'eleve') {
        donnees.matricule = valeur('matricule');
        donnees.classe = valeur('classe');
        donnees.interets = lireInteretsSelectionnes(conteneurInterets);
    } else if (roleSelectionne === 'parent') {
        donnees.type_lien_eleve = valeur('type_lien_eleve');
        donnees.matricule_enfant = valeur('matricule_enfant');
    } else if (roleSelectionne === 'encadreur') {
        donnees.type_encadreur = typeEncadreurSelectionne;
        donnees.matricule = valeur('matricule_encadreur');
        donnees.fonction = valeur('fonction');
        donnees.domaine_competence = valeur('domaine_competence');
        donnees.club_souhaite = valeur('club_souhaite');
        const f = champ('justificatif');
        fichier = f && f.files[0] ? f.files[0] : null;
    } else if (roleSelectionne === 'proviseur') {
        donnees.matricule = valeur('matricule');
        donnees.fonction = valeur('fonction');
        donnees.service_responsabilite = valeur('service_responsabilite');
        donnees.etablissement = valeur('etablissement');
        fichier = champFichierProviseur.files[0];
    }
    return { donnees, fichier };
}

async function envoyer(donnees, fichier) {
    if (fichier && fichier.size > 0) {
        const corps = new FormData();
        Object.entries(donnees).forEach(([cle, v]) => {
            if (Array.isArray(v)) v.forEach(x => corps.append(cle, x));
            else if (v !== null && v !== undefined) corps.append(cle, v);
        });
        corps.append('justificatif', fichier);
        // Pas de Content-Type manuel : le navigateur ajoute la boundary multipart.
        return fetch(`${API_BASE}/auth/register/`, { method: 'POST', body: corps });
    }
    return fetch(`${API_BASE}/auth/register/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(donnees),
    });
}

/** Rattache les erreurs renvoyées par l'API aux champs ; le reste va dans l'alerte générale. */
function afficherErreursServeur(resultat) {
    const generales = [];
    Object.entries(resultat || {}).forEach(([nom, messages]) => {
        const texte = Array.isArray(messages) ? messages.join(' ') : String(messages);
        const nomChamp = nom === 'matricule' && roleSelectionne === 'encadreur' ? 'matricule_encadreur'
            : nom === 'justificatif' && roleSelectionne === 'proviseur' ? 'justificatif_proviseur' : nom;
        const cible = formulaire.querySelector(`[name="${nomChamp}"]:not(:disabled)`);
        if (!erreurChamp(cible, texte)) generales.push(texte);
    });
    if (generales.length) afficherErreur(generales.join(' '));
    const premiere = formulaire.querySelector('.is-invalid');
    if (premiere) premiere.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

formulaire.addEventListener('submit', async (e) => {
    e.preventDefault();
    if (boutonCreer.disabled) return; // anti double-clic
    effacerErreurs();

    const erreurs = validerFormulaire();
    if (erreurs.length) {
        erreurs.forEach(([c, message]) => erreurChamp(c, message));
        const premiere = formulaire.querySelector('.is-invalid');
        if (premiere) premiere.scrollIntoView({ behavior: 'smooth', block: 'center' });
        afficherErreur('Veuillez corriger les champs signalés.');
        return;
    }

    const { donnees, fichier } = construireDonnees();
    chargement(true);
    try {
        const reponse = await envoyer(donnees, fichier);
        let resultat = null;
        try { resultat = await reponse.json(); } catch (_) { /* corps non JSON */ }

        if (!reponse.ok) {
            if (reponse.status >= 500 || !resultat) {
                afficherErreur("Une erreur serveur est survenue. Vos informations sont conservées, réessayez dans un instant.");
            } else {
                afficherErreursServeur(resultat);
            }
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
        afficherErreur("Impossible de contacter le serveur. Vos informations sont conservées.");
    } finally {
        chargement(false);
    }
});

// ---------- Centres d'intérêt ----------

async function chargerCentresInteret() {
    try {
        const reponse = await fetch(`${API_BASE}/auth/interets/`);
        const centres = reponse.ok ? await reponse.json() : [];
        afficherPucesInterets(conteneurInterets, Array.isArray(centres) ? centres : []);
    } catch (_) {
        conteneurInterets.innerHTML = '<p class="text-muted small mb-0">Centres d\'intérêt indisponibles : vous pourrez les choisir depuis votre profil.</p>';
    }
}
chargerCentresInteret();

// ---------- Zone de dépôt du justificatif pour le responsable pédagogique ----------

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
