/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#0A0A0F",
        surface: "#111118",
        sidebar: "#0D0D14",
        accent: "#6366F1",
        primary: "#6366F1",
        success: "#10B981",
        warning: "#F59E0B",
        danger: "#EF4444",
        error: "#EF4444",
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'system-ui', 'sans-serif'],
      },
      textColor: {
        primary: "#F1F5F9",
        secondary: "#94A3B8",
        muted: "#475569",
      },
      backgroundColor: {
        dark: "#0A0A0F",
        darker: "#111118",
      },
      boxShadow: {
        premium: "0 20px 25px -5px rgba(0, 0, 0, 0.5)",
        card: "0 10px 15px -3px rgba(0, 0, 0, 0.3)",
      },
    },
  },
  plugins: [],
}

