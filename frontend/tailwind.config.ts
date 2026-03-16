import type { Config } from 'tailwindcss';
import { getTailwindExtend } from './src/lib/theme.config';

const config: Config = {
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: { extend: getTailwindExtend() },
  plugins: [],
};
export default config;
