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

    document.getElementById('champ-nom').value = profil.nom || '';
    document.getElementById('champ-prenom').value = profil.prenom || '';
    document.getElementById('champ-email').value = profil.email || '';
    document.getElementById('champ-telephone').value = profil.telephone || '';
    document.getElementById('champ-role').value = profil.role || '';
    if (profil.photo) {
        document.getElementById('apercu-photo').src = profil.photo;
    }

    if (profil.role === 'eleve') {
        document.getElementById('bloc-preferences-eleve').classList.remove('d-none');
        document.getElementById('champ-classe').value = profil.classe || '';
        document.getElementById('champ-filiere').value = profil.filiere || '';
        document.getElementById('champ-centres-interet').value = profil.centres_interet || '';
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
    const donnees = {
        nom: document.getElementById('champ-nom').value,
        prenom: document.getElementById('champ-prenom').value,
        telephone: document.getElementById('champ-telephone').value,
    };

    if (!document.getElementById('bloc-preferences-eleve').classList.contains('d-none')) {
        donnees.classe = document.getElementById('champ-classe').value;
        donnees.filiere = document.getElementById('champ-filiere').value;
        donnees.centres_interet = document.getElementById('champ-centres-interet').value;
    }

    const resultat = await appelApi('/auth/profil/', {
        method: 'PATCH',
        body: JSON.stringify(donnees),
    });

    if (resultat) {
        document.getElementById('alerte-succes-profil').classList.remove('d-none');
        setTimeout(() => document.getElementById('alerte-succes-profil').classList.add('d-none'), 3000);
    }
});

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