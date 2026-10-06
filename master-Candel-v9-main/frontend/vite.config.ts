import config from "./plugins/vite.config.ts";

export default (environment: Parameters<typeof config>[0]) => config(environment);
