import { defineConfig } from "@trigger.dev/sdk/v3";

export default defineConfig({
  project: "tradeup-jobs",
  runtime: "node",
  logLevel: "log",
  maxDuration: 300, // 5 minutes max per task
  retries: {
    enabledInDev: true,
    default: {
      maxAttempts: 3,
      minTimeout: 1000,
      maxTimeout: 10000,
      factor: 2,
    },
  },
  dirs: ["./src/tasks"],
});
