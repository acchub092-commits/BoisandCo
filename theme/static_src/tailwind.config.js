/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    // Templates Django
    '../../templates/**/*.html',
    '../../apps/**/templates/**/*.html',
    '../../theme/templates/**/*.html',
    // JS Alpine.js inline
    '../../static/js/**/*.js',
  ],
  theme: {
    extend: {
      colors: {
        // Palette Bois&Co — valeurs exactes de la charte graphique officielle
        // (Pantone 368 C / RVB 115,183,43 — vérifié aussi par échantillonnage du logo réel).
        // "bois" reprend le même vert de marque que "foret" pour unifier les deux familles
        // d'accent historiques sur une seule identité verte.
        bois: {
          50:  '#f3fbe9',
          100: '#e3f5cb',
          200: '#c8ec9a',
          300: '#a5e063',
          400: '#8fd046',
          500: '#73b72b',   // vert exact de la charte (Pantone 368 C)
          600: '#5c9622',
          700: '#48761b',
          800: '#395c16',
          900: '#2a4310',
        },
        // Vert forêt — même vert de marque que "bois", conservé comme alias historique
        foret: {
          50:  '#f3fbe9',
          100: '#e3f5cb',
          200: '#c8ec9a',
          300: '#a5e063',
          400: '#8fd046',
          500: '#73b72b',   // vert exact de la charte — boutons, badges actifs
          600: '#5c9622',   // hover
          700: '#48761b',   // foncé
          800: '#395c16',   // très foncé
          900: '#2a4310',
        },
        // Marine — bleu-nuit exact de la charte (Pantone 289 XGC / RVB 29,52,72)
        marine: {
          50:  '#eef2f4',
          100: '#d7e0e5',
          200: '#aec0cb',
          300: '#7f9aa9',
          400: '#51717f',   // gris bleuté — variante secondaire de la charte
          500: '#3b5768',
          600: '#2c4455',
          700: '#233847',
          800: '#1d2e3b',
          900: '#1d3448',   // marine exact de la charte — fond sidebar, en-tête connexion
        },
        // Terracotta — couleur secondaire de la charte (variante alternative du logo)
        bronze: {
          50:  '#fbf0ed',
          100: '#f4d9d0',
          200: '#e8b4a3',
          300: '#da8a70',
          400: '#cc6c4f',
          500: '#bf583e',   // terracotta exact de la charte (Pantone 7619 C)
          600: '#9f4631',
          700: '#7d3726',
          800: '#602a1d',
          900: '#471f16',
        },
        // Crème — couleur texte du logo
        creme: {
          50:  '#fdfcf9',
          100: '#faf5ee',
          200: '#f2e8d5',   // crème exact du logo
          300: '#e6d4b6',
          400: '#d4ba90',
          500: '#be9d68',
          600: '#a07f4d',
          700: '#81643c',
          800: '#634c2e',
          900: '#4d3a23',
        },
        ardoise: {
          50:  '#f6f7f8',
          100: '#eaecef',
          200: '#d3d8de',
          300: '#adb5bf',
          400: '#7f8d9b',
          500: '#5d6e7e',
          600: '#4a5869',
          700: '#3d4857',
          800: '#343d4a',
          900: '#2e353f',
        },
      },
      fontFamily: {
        // Plus Jakarta Sans — unique police de la charte graphique officielle Bois&Co.
        sans: ['"Plus Jakarta Sans"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        'card':       '0 2px 8px 0 rgba(0,0,0,0.07)',
        'card-hover': '0 6px 20px 0 rgba(0,0,0,0.12)',
        'sidebar':    '4px 0 24px 0 rgba(0,0,0,0.18)',
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography'),
  ],
}
