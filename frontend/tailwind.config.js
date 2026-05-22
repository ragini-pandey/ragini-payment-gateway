/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        serif: ['"Fraunces"', "ui-serif", "Georgia", "serif"],
        sans: ['"Inter"', "ui-sans-serif", "system-ui", "sans-serif"],
      },
      colors: {
        ivory: "#FBF7F0",
        cream: "#F5EEDF",
        parchment: "#E9DFC9",
        saffron: {
          DEFAULT: "#C8612A",
          50: "#FBEFE5",
          100: "#F6DDC6",
          500: "#C8612A",
          600: "#B0521F",
          700: "#8E411A",
        },
        gold: "#D4A24C",
        ink: "#2A1F14",
        muted: "#6B5A47",
      },
      boxShadow: {
        soft: "0 1px 2px rgba(42, 31, 20, 0.04), 0 8px 24px rgba(42, 31, 20, 0.06)",
        lift: "0 4px 12px rgba(42, 31, 20, 0.08), 0 16px 40px rgba(42, 31, 20, 0.10)",
      },
      borderRadius: {
        "2xl": "1rem",
        "3xl": "1.5rem",
      },
      keyframes: {
        "fade-in": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "fade-in": "fade-in 0.5s ease-out both",
      },
    },
  },
  plugins: [],
};
