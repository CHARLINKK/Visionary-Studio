import js from "@eslint/js";

export default [
  js.configs.recommended,
  {
    languageOptions: {
      ecmaVersion: 2021,
      sourceType: "module",
      globals: {
        window: "readonly",
        document: "readonly",
        console: "readonly",
        setTimeout: "readonly",
        clearTimeout: "readonly",
        Math: "readonly",
        require: "readonly"
      }
    },
    rules: {
      "no-undef": "error",
      "no-unused-vars": "off"
    }
  }
];
