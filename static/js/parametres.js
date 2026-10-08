// ---------- Bascule entre les onglets ----------

document.querySelectorAll('.btn-onglet-param').forEach(bouton => {
    bouton.addEventListener('click', (e) => {
        document.querySelectorAll('.btn-onglet-param').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('[id^="onglet-"]').forEach(o => o.classList.add('d-none'));
        e.currentTarget.classList.add('active');
        document.getElementById(e.currentTarget.dataset.cible).classList.remove('d-none');
    });
});

// ---------- Chargement des données du profil ----------

async function chargerProfil() {
    const profil = await appelApi('/auth/profil/');
    if (!profil) return;

    // En-tête
    document.getElementById('entete-nom').textContent = profil.nom_complet || '';
    document.getElementById('entete-email').textContent = profil.email || '';
    document.getElementById('entete-role').textContent = profil.role_libelle || profil.role || '';
    if (profil.photo) {
        document.getElementById('apercu-photo').src = profil.photo;
    }

    // Informations personnelles
    document.getElementById('champ-nom').value = profil.nom || '';
    document.getElementById('champ-prenom').value = profil.prenom || '';
    document.getElementById('champ-email').value = profil.email || '';
    document.getElementById('champ-telephone').value = profil.telephone || '';
    document.getElementById('champ-date-naissance').value = profil.date_naissance || '';

    // Informations complémentaires : seuls les champs du rôle (et les valeurs présentes) sont affichés
    const valeurs = {
        'champ-etablissement': profil.etablissement, 'champ-matricule': profil.matricule,
        'champ-classe': profil.classe, 'champ-filiere': profil.filiere,
        'champ-type-encadreur': profil.type_encadreur_libelle, 'champ-fonction': profil.fonction,
        'champ-domaine': profil.domaine_competence, 'champ-service': profil.service_responsabilite,
        'champ-profession': profil.profession, 'champ-lien': profil.type_lien_eleve,
    };
    Object.entries(valeurs).forEach(([id, v]) => { document.getElementById(id).value = v || ''; });

    const section = document.getElementById('section-complementaire');
    document.querySelectorAll('[data-roles]').forEach(bloc => {
        bloc.classList.toggle('d-none', !bloc.dataset.roles.split(' ').includes(profil.role));
    });
    document.querySelectorAll('[data-affiche-si]').forEach(bloc => {
        bloc.classList.toggle('d-none', !profil[bloc.dataset.afficheSi]);
    });
    section.classList.toggle('d-none', !section.querySelector('.col-md-6:not(.d-none)'));

    if (profil.role === 'encadreur') {
        // Seul endroit où l'encadreur peut changer de club (un club n'a qu'un encadreur).
        const liste = document.getElementById('champ-club-encadre');
        const clubs = await appelApi('/auth/clubs-disponibles/');
        liste.innerHTML = profil.club_encadre_details ? '' : '<option value="">Aucun club</option>';
        (Array.isArray(clubs) ? clubs : []).forEach(c => liste.add(new Option(c.nom, c.id)));
        liste.value = profil.club_encadre_details ? String(profil.club_encadre_details.id) : '';
        liste.dataset.initial = liste.value;
    }

    if (profil.role === 'eleve') {
        document.getElementById('bloc-preferences-eleve').classList.remove('d-none');
        const centres = await appelApi('/auth/interets/');
        afficherPucesInterets(
            document.getElementById('conteneur-interets'),
            Array.isArray(centres) ? centres : [],
            profil.interets,
        );
    }

    const preferences = await appelApi('/notifications/preferences/');
    if (preferences) {
        document.getElementById('pref-internes').checked = preferences.notifications_internes;
        document.getElementById('pref-email').checked = preferences.notifications_email;
        document.getElementById('pref-sms').checked = preferences.notifications_sms;
    }
}

document.getElementById('champ-photo').addEventListener('change', (e) => {
    const fichier = e.target.files[0];
    if (fichier) {
        document.getElementById('apercu-photo').src = URL.createObjectURL(fichier);
    }
});

// ---------- Formulaire : mise à jour du profil ----------

document.getElementById('formulaire-profil').addEventListener('submit', async (e) => {
    e.preventDefault();
    const form = e.target;
    const bouton = document.getElementById('btn-enregistrer-profil');
    if (bouton.disabled) return; // anti double-clic
    const alerteSucces = document.getElementById('alerte-succes-profil');
    const alerteErreur = document.getElementById('alerte-erreur-profil');
    alerteSucces.classList.add('d-none');
    alerteErreur.classList.add('d-none');
    form.querySelectorAll('.erreur-champ').forEach(x => x.remove());
    form.querySelectorAll('.is-invalid').forEach(x => x.classList.remove('is-invalid'));

    // Champs modifiables visibles (les champs en lecture seule n'ont pas de "name")
    const donnees = {};
    form.querySelectorAll('input[name]').forEach(c => {
        if (!c.closest('.d-none')) donnees[c.name] = c.value.trim();
    });
    if (!donnees.nom || !donnees.prenom) {
        [['nom', donnees.nom], ['prenom', donnees.prenom]].forEach(([n, v]) => {
            if (!v) marquerErreurProfil(n, 'Ce champ est obligatoire.');
        });
        return;
    }
    if (donnees.date_naissance === '') donnees.date_naissance = null;
    // Club de l'encadreur : envoyé seulement s'il a changé.
    const listeClub = document.getElementById('champ-club-encadre');
    if (!listeClub.closest('.d-none') && listeClub.value && listeClub.value !== listeClub.dataset.initial) {
        if (!confirm('Changer de club libère votre club actuel pour un autre encadreur. Continuer ?')) return;
        donnees.club_encadre = Number(listeClub.value);
    }
    if (!document.getElementById('bloc-preferences-eleve').classList.contains('d-none')) {
        donnees.interets = lireInteretsSelectionnes(document.getElementById('conteneur-interets'));
    }

    bouton.disabled = true;
    bouton.querySelector('.texte-bouton').classList.add('d-none');
    bouton.querySelector('.texte-chargement').classList.remove('d-none');

    // La photo (fichier) part en multipart ; le reste en JSON.
    const fichier = document.getElementById('champ-photo').files[0];
    if (fichier) {
        const envoi = new FormData();
        envoi.append('photo', fichier);
        try {
            const r = await fetch(`${API_BASE}/auth/profil/`, {
                method: 'PATCH',
                headers: { 'Authorization': `Bearer ${obtenirToken()}` }, // pas de Content-Type : boundary auto
                body: envoi,
            });
            const corps = await r.json().catch(() => ({}));
            if (!r.ok) {
                afficherErreursProfil(corps);
                finChargementProfil(bouton);
                return;
            }
            if (corps.photo) document.getElementById('apercu-photo').src = corps.photo;
            document.getElementById('champ-photo').value = '';
        } catch (_) {
            alerteErreur.textContent = "Impossible d'envoyer la photo. Vérifiez votre connexion.";
            alerteErreur.classList.remove('d-none');
            finChargementProfil(bouton);
            return;
        }
    }

    const resultat = await appelApi('/auth/profil/', {
        method: 'PATCH',
        body: JSON.stringify(donnees),
    });
    finChargementProfil(bouton);

    if (resultat && resultat.id) {
        // Profil actualisé : on réaffiche ce que le serveur a réellement enregistré.
        document.getElementById('entete-nom').textContent = resultat.nom_complet || '';
        const nomHeader = document.getElementById('nom-utilisateur-connecte');
        if (nomHeader) nomHeader.textContent = resultat.nom_complet || '';
        if (resultat.club_encadre_details) listeClub.dataset.initial = String(resultat.club_encadre_details.id);
        alerteSucces.classList.remove('d-none');
        setTimeout(() => alerteSucces.classList.add('d-none'), 3000);
    } else if (resultat) {
        afficherErreursProfil(resultat);
    }
});

function finChargementProfil(bouton) {
    bouton.disabled = false;
    bouton.querySelector('.texte-bouton').classList.remove('d-none');
    bouton.querySelector('.texte-chargement').classList.add('d-none');
}

function marquerErreurProfil(nom, message) {
    const champ = document.querySelector(`#formulaire-profil [name="${nom}"]`);
    if (!champ) return false;
    champ.classList.add('is-invalid');
    const p = document.createElement('div');
    p.className = 'erreur-champ small text-danger mt-1';
    p.textContent = message;
    champ.insertAdjacentElement('afterend', p);
    return true;
}

/** Erreurs de l'API : sous le champ concerné si possible, sinon dans l'alerte générale. */
function afficherErreursProfil(erreurs) {
    const generales = [];
    Object.entries(erreurs || {}).forEach(([nom, messages]) => {
        const texte = Array.isArray(messages) ? messages.join(' ') : String(messages);
        if (!marquerErreurProfil(nom, texte)) generales.push(texte);
    });
    if (generales.length) {
        const alerte = document.getElementById('alerte-erreur-profil');
        alerte.textContent = generales.join(' ');
        alerte.classList.remove('d-none');
    }
}

// ---------- Formulaire : changement de mot de passe ----------

document.getElementById('formulaire-mot-de-passe').addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const donnees = Object.fromEntries(formData);
    const alerteErreur = document.getElementById('alerte-erreur-mdp');
    const alerteSucces = document.getElementById('alerte-succes-mdp');
    alerteErreur.classList.add('d-none');

    const resultat = await appelApi('/auth/changer-mot-de-passe/', {
        method: 'POST',
        body: JSON.stringify(donnees),
    });

    if (resultat && resultat.message) {
        alerteSucces.classList.remove('d-none');
        e.target.reset();
    } else {
        alerteErreur.textContent = "Vérifiez votre ancien mot de passe et réessayez.";
        alerteErreur.classList.remove('d-none');
    }
});

// ---------- Formulaire : préférences de notification ----------

document.getElementById('formulaire-preferences').addEventListener('submit', async (e) => {
    e.preventDefault();
    const donnees = {
        notifications_internes: document.getElementById('pref-internes').checked,
        notifications_email: document.getElementById('pref-email').checked,
        notifications_sms: document.getElementById('pref-sms').checked,
    };

    await appelApi('/notifications/preferences/', {
        method: 'PUT',
        body: JSON.stringify(donnees),
    });
    alert('Préférences enregistrées.');
});

// ---------- Initialisation ----------

document.addEventListener('DOMContentLoaded', chargerProfil);