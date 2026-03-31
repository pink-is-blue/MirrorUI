import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const isPagesBuild = process.env.GITHUB_ACTIONS === 'true'

export default defineConfig({
	base: isPagesBuild ? '/MirrorUI/' : '/',
	plugins: [react()],
	server: {
		port: 5173,
		host: true,
		proxy: {
			'/api': 'http://localhost:8000',
			'/docs': 'http://localhost:8000',
			'/openapi.json': 'http://localhost:8000',
		},
	},
})
