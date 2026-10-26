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
        // Palette Bois&Co — identité nouveau logo
        bois: {
          50:  '#fdf8f0',
          100: '#faefd9',
          200: '#f3d9a8',
          300: '#e8bc6e',
          400: '#dc9d3e',
          500: '#c9821f',   // bois principal
          600: '#a96518',
          700: '#874e16',
          800: '#6e3e18',
          900: '#5a3418',
        },
        // Vert forêt — échantillonné pixel par pixel sur le vrai logo (vert #71BB16)
        foret: {
          50:  '#f6fced',
          100: '#e7f8d3',
          200: '#d0f1a7',
          300: '#b3e873',
          400: '#92de35',
          500: '#70b41d',   // vert exact du logo — boutons, badges actifs
          600: '#5a9118',   // hover
          700: '#477213',   // foncé
          800: '#35560e',   // très foncé
          900: '#253b0a',
        },
        // Marine — bleu-nuit exact de l'encre du logo (fonds foncés : sidebar, connexion, avatar)
        marine: {
          50:  '#f1f6f9',
          100: '#dbe8f0',
          200: '#b8d1e0',
          300: '#86b0cb',
          400: '#4d8bb2',
          500: '#376481',
          600: '#2b4e64',
          700: '#223d4f',
          800: '#1c3240',   // hover des fonds foncés
          900: '#152732',   // marine exact du logo — fond sidebar, en-tête connexion
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
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        serif: ['Georgia', 'ui-serif', 'serif'],
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
