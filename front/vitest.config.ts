import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    environmentOptions: {
      jsdom: {
        url: "http://localhost:3001/",
      },
    },
    setupFiles: ["./src/test-setup.ts"],
  },
});
