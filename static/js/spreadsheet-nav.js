/**
 * Navigation façon tableur : flèches ↑/↓ (et Entrée) pour passer d'un champ numérique au
 * suivant/précédent dans une colonne de saisie. Ajouter la classe .js-spreadsheet-nav aux
 * <input> concernés — l'ordre de navigation suit l'ordre d'apparition dans le DOM.
 */
(function () {
  function wireUp() {
    var inputs = Array.prototype.slice.call(document.querySelectorAll('.js-spreadsheet-nav'));
    inputs.forEach(function (input, idx) {
      if (input.dataset.spreadsheetNavWired) return;
      input.dataset.spreadsheetNavWired = '1';
      input.addEventListener('keydown', function (e) {
        var target = null;
        if (e.key === 'ArrowDown' || e.key === 'Enter') {
          target = inputs[idx + 1];
        } else if (e.key === 'ArrowUp') {
          target = inputs[idx - 1];
        }
        if (target) {
          e.preventDefault();
          target.focus();
          target.select();
        }
      });
    });
  }

  document.addEventListener('DOMContentLoaded', wireUp);
  document.addEventListener('htmx:afterSwap', wireUp);
})();
