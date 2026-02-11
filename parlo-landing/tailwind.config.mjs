/** @type {import('tailwindcss').Config} */
export default {
  content: ['./src/**/*.{astro,html,js,jsx,md,mdx,svelte,ts,tsx,vue}'],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#7C3AED',
          dark: '#6D28D9',
        },
        secondary: '#3B82F6',
        accent: '#F97316',
        whatsapp: '#25D366',
        bg: {
          DEFAULT: '#FAFAFA',
          light: '#FFFFFF',
        },
        text: {
          DEFAULT: '#1F2937',
          light: '#6B7280',
        },
        border: '#E5E7EB',
      },
      fontFamily: {
        heading: ['Outfit', 'sans-serif'],
        body: ['Plus Jakarta Sans', 'sans-serif'],
      },
      keyframes: {
        fadeIn: {
          from: { opacity: '0', transform: 'translateY(20px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        'fade-in': 'fadeIn 0.6s ease-out forwards',
        'fade-in-delay-1': 'fadeIn 0.8s ease-out 0.2s forwards',
        'fade-in-delay-2': 'fadeIn 1s ease-out 0.4s forwards',
        'fade-in-delay-3': 'fadeIn 1.2s ease-out 0.6s forwards',
        'fade-in-delay-4': 'fadeIn 1.4s ease-out 0.8s forwards',
      },
    },
  },
  plugins: [],
};
