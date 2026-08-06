/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: "#0B1C24",
          soft: "#16303C",
        },
        mist: "#E8EEF2",
        foam: "#F4F8FA",
        teal: {
          DEFAULT: "#0F766E",
          bright: "#14B8A6",
          deep: "#0D5C56",
        },
        amber: {
          DEFAULT: "#D97706",
          soft: "#F59E0B",
        },
      },
      fontFamily: {
        display: ['"Syne"', "system-ui", "sans-serif"],
        sans: ['"Manrope"', "system-ui", "sans-serif"],
      },
      boxShadow: {
        lift: "0 18px 50px -24px rgba(11, 28, 36, 0.45)",
      },
      keyframes: {
        fadeUp: {
          "0%": { opacity: "0", transform: "translateY(18px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        drift: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-10px)" },
        },
      },
      animation: {
        fadeUp: "fadeUp 0.7s ease-out both",
        drift: "drift 7s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
