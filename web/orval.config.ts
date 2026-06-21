import { defineConfig } from 'orval'

export default defineConfig({
  core: {
    input: './openapi.json',
    output: {
      target: './src/api/index.ts',
      client: 'react-query',
      httpClient: 'fetch',
      override: {
        mutator: {
          path: './src/lib/fetch-client.ts',
          name: 'apiFetch',
        },
      },
    },
  },
})
