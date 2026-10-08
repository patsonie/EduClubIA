/**
 * Améliorations d'accessibilité et d'états de chargement communes à toutes les pages.
 * - associe chaque <label> sans attribut `for` à son champ ;
 * - donne un nom accessible aux champs restants (placeholder, première option, name) ;
 * - nomme les boutons de fermeture ;
 * - rend les messages « Chargement... » visibles (spinner) et annoncés aux lecteurs d'écran.
 */
(function () {
    // Types de champs concernés et compteur pour créer des identifiants uniques.
    const SELECTEUR_CHAMP = 'input:not([type=hidden]):not([type=checkbox]):not([type=radio]), select, textarea';
    let compteur = 0;

    // Trouve le champ associé à un libellé (élément suivant ou dans le même bloc).
    function trouverChamp(label) {
        const suivant = label.nextElementSibling;
        if (suivant) {
            const champ = suivant.matches(SELECTEUR_CHAMP) ? suivant : suivant.querySelector(SELECTEUR_CHAMP);
            if (champ) return champ;
        }
        return label.parentElement ? label.parentElement.querySelector(SELECTEUR_CHAMP) : null;
    }

    // Relie les libellés à leurs champs et donne un nom lisible aux champs et boutons qui n'en ont pas.
    function associerLibelles() {
        document.querySelectorAll('label:not([for])').forEach((label) => {
            if (label.querySelector('input, select, textarea')) return; // libellé englobant
            const champ = trouverChamp(label);
            if (!champ) return;
            if (!champ.id) champ.id = `champ-auto-${++compteur}`;
            label.setAttribute('for', champ.id);
        });

        document.querySelectorAll(SELECTEUR_CHAMP).forEach((champ) => {
            if (champ.getAttribute('aria-label') || champ.closest('label')) return;
            if (champ.id && document.querySelector(`label[for="${CSS.escape(champ.id)}"]`)) return;
            const nom = champ.getAttribute('placeholder')
                || (champ.options && champ.options[0] && champ.options[0].text.trim())
                || champ.getAttribute('name');
            if (nom) champ.setAttribute('aria-label', nom);
        });

        document.querySelectorAll('.btn-close:not([aria-label])').forEach((bouton) => {
            bouton.setAttribute('aria-label', 'Fermer');
        });
    }

    // Remplace le texte « Chargement... » par un indicateur animé annoncé aux lecteurs d'écran.
    function ameliorerEtatsChargement() {
        document.querySelectorAll('td, div, li, p').forEach((element) => {
            if (element.children.length > 0) return;
            const texte = element.textContent.trim();
            if (!/^Chargement/.test(texte)) return;
            element.setAttribute('role', 'status');
            element.setAttribute('aria-live', 'polite');
            element.textContent = '';
            const spinner = document.createElement('span');
            spinner.className = 'spinner-border spinner-border-sm me-2';
            spinner.setAttribute('aria-hidden', 'true');
            element.appendChild(spinner);
            element.appendChild(document.createTextNode(texte));
        });
    }

    // Lance les deux améliorations dès que la page est prête.
    function initialiser() {
        associerLibelles();
        ameliorerEtatsChargement();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initialiser);
    } else {
        initialiser();
    }
})();
