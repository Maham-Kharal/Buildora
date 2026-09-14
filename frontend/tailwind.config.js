/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#FAF7F2", // Warm Beige
        card: "#FFFFFF",
        primary: {
          DEFAULT: "#C28E64", // Construction Gold / Muted Amber
          hover: "#A8754F",
        },
        sidebar: "#1E1E1E",
      },
      borderRadius: {
        '2xl': '1rem',
      }
    },
  },
  plugins: [],
}
