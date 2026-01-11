/**
 * GraphQL configuration for IDE tooling and type generation.
 *
 * This enables autocomplete and validation for the input.graphql file
 * in VS Code with the GraphQL extension.
 */
module.exports = {
  projects: {
    default: {
      schema: 'https://shopify.dev/docs/api/functions/reference/order-discounts/graphql/input.graphql',
      documents: ['src/**/*.graphql'],
    },
  },
};
