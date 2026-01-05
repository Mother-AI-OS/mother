/** @type {import('@docusaurus/plugin-content-docs').SidebarsConfig} */
const sidebars = {
  tutorialSidebar: [
    'intro',
    {
      type: 'category',
      label: 'Getting Started',
      items: [
        'getting-started/installation',
        'getting-started/configuration',
        'getting-started/first-command',
      ],
    },
    {
      type: 'category',
      label: 'Core Concepts',
      items: [
        'concepts/how-it-works',
        'concepts/plugin-system',
        'concepts/security',
      ],
    },
    {
      type: 'category',
      label: 'Plugins',
      items: [
        'plugins/built-in',
        'plugins/creating-plugins',
        'plugins/publishing',
      ],
    },
    {
      type: 'category',
      label: 'API Reference',
      items: [
        'api/rest-endpoints',
        'api/python-sdk',
      ],
    },
    {
      type: 'category',
      label: 'Deployment',
      items: [
        'deployment/self-hosted',
        'deployment/docker',
      ],
    },
  ],
};

export default sidebars;
