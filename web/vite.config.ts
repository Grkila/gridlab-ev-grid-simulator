import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({plugins:[react()],build:{rollupOptions:{input:{app:'index.html',presentation:'presentation.html'}}},server:{port:5173,proxy:{'/api':'http://127.0.0.1:8517'}}});
