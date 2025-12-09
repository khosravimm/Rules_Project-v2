/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        slate: {
          950: "#0b1220",
        },
        emerald: {
          450: "#3cc689",
        },
        amber: {
          450: "#f59f0b",
        },
      },
      fontFamily: {
        sans: ["'Manrope'", "'Inter'", "system-ui", "sans-serif"],
      },
      boxShadow: {
        panel: "0 10px 40px rgba(0,0,0,0.08)",
      },
    },
  },
  plugins: [],
};
