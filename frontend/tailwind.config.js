/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        sleep: {
          deep: '#1a237e',
          light: '#64b5f6',
          rem: '#7b1fa2',
          wake: '#ffab00',
          primary: '#2196f3',
        },
      },
    },
  },
  plugins: [],
}
