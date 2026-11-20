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
        // Palette Bois&Co — alignée sur le site officiel bois-co.ma (logo + charte réelle)
        // Vert de marque — exact du site officiel (#6CC600), repris aussi comme "bois"
        // pour unifier les deux familles d'accent historiques sur une seule identité verte.
        bois: {
          50:  '#f3fce6',
          100: '#e2f8c2',
          200: '#c7f091',
          300: '#a3e659',
          400: '#87d92e',
          500: '#6cc600',   // vert exact du site officiel
          600: '#5aa800',
          700: '#478300',
          800: '#366500',
          900: '#274a00',
        },
        // Vert forêt — même vert de marque que "bois", conservé comme alias historique
        foret: {
          50:  '#f3fce6',
          100: '#e2f8c2',
          200: '#c7f091',
          300: '#a3e659',
          400: '#87d92e',
          500: '#6cc600',   // vert exact du site officiel — boutons, badges actifs
          600: '#5aa800',   // hover
          700: '#478300',   // foncé
          800: '#366500',   // très foncé
          900: '#274a00',
        },
        // Marine — bleu-nuit exact du site officiel (#112534 : nav, texte du logo, fonds foncés)
        marine: {
          50:  '#eef3f6',
          100: '#d7e3ea',
          200: '#aec7d4',
          300: '#7ea3b7',
          400: '#4d7891',
          500: '#335a70',
          600: '#26485c',
          700: '#1c3747',
          800: '#162c39',
          900: '#112534',   // marine exact du site officiel — fond sidebar, en-tête connexion
        },
        // Bronze — orange de marque du site officiel (#F06D22), accent secondaire chaleureux
        bronze: {
          50:  '#fef3ec',
          100: '#fde1cc',
          200: '#fac199',
          300: '#f69d66',
          400: '#f3843f',
          500: '#f06d22',   // orange exact du site officiel
          600: '#cc551a',
          700: '#a34315',
          800: '#7d3412',
          900: '#5c270e',
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
        sans: ['"Plus Jakarta Sans"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        serif: ['"Cormorant Garamond"', 'ui-serif', 'serif'],
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
