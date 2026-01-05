import clsx from 'clsx';
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import Layout from '@theme/Layout';
import Heading from '@theme/Heading';

import styles from './index.module.css';

function HomepageHeader() {
  const {siteConfig} = useDocusaurusContext();
  return (
    <header className={clsx('hero hero--primary', styles.heroBanner)}>
      <div className="container">
        <Heading as="h1" className="hero__title">
          {siteConfig.title}
        </Heading>
        <p className="hero__subtitle">{siteConfig.tagline}</p>
        <div className={styles.buttons}>
          <Link
            className="button button--secondary button--lg"
            to="/docs/getting-started/installation">
            Get Started
          </Link>
          <Link
            className="button button--outline button--lg"
            style={{marginLeft: '1rem', color: 'white', borderColor: 'white'}}
            href="https://github.com/Mother-AI-OS/mother">
            View on GitHub
          </Link>
        </div>
      </div>
    </header>
  );
}

function Terminal() {
  return (
    <div className="terminal">
      <div className="terminal-header">
        <div className="terminal-dot red"></div>
        <div className="terminal-dot yellow"></div>
        <div className="terminal-dot green"></div>
      </div>
      <div className="terminal-content">
        <div><span className="terminal-prompt">$ </span><span className="terminal-command">mother serve</span></div>
        <div className="terminal-output">🚀 Mother AI OS running at http://localhost:8080</div>
        <div style={{marginTop: '1rem'}}><span className="terminal-prompt">$ </span><span className="terminal-command">curl -X POST localhost:8080/command \</span></div>
        <div className="terminal-command">  -d '{"{"}"command": "List Python files in src"{"}"}'</span></div>
        <div className="terminal-output" style={{marginTop: '0.5rem'}}>
          Found 12 Python files in ./src:<br/>
          - main.py (245 lines)<br/>
          - agent.py (189 lines)<br/>
          - plugins.py (312 lines)<br/>
          ...
        </div>
      </div>
    </div>
  );
}

const FeatureList = [
  {
    title: 'Natural Language Interface',
    icon: '💬',
    description: 'Talk to your system in plain English. Mother translates your commands into tool executions automatically.',
  },
  {
    title: 'Plugin Architecture',
    icon: '🔌',
    description: 'Extend functionality with PyPI-installable plugins. Create your own in minutes with our simple SDK.',
  },
  {
    title: 'Security First',
    icon: '🔒',
    description: 'Permission-based capability system. Every action is validated before execution.',
  },
  {
    title: 'Multiple Backends',
    icon: '⚡',
    description: 'Python, CLI, Docker, or HTTP execution. Choose the right backend for each task.',
  },
  {
    title: 'Production Ready',
    icon: '🚀',
    description: 'FastAPI server with REST API, streaming support, and comprehensive error handling.',
  },
  {
    title: 'Open Source',
    icon: '❤️',
    description: 'MIT licensed. Free to use, modify, and distribute. Community-driven development.',
  },
];

function Feature({icon, title, description}) {
  return (
    <div className={clsx('col col--4')}>
      <div className="feature-card">
        <div className="feature-icon">{icon}</div>
        <Heading as="h3">{title}</Heading>
        <p>{description}</p>
      </div>
    </div>
  );
}

function HomepageFeatures() {
  return (
    <section className={styles.features}>
      <div className="container">
        <div className="row">
          {FeatureList.map((props, idx) => (
            <Feature key={idx} {...props} />
          ))}
        </div>
      </div>
    </section>
  );
}

function Stats() {
  return (
    <section className={styles.stats}>
      <div className="container">
        <div className="stats-section">
          <div className="stat-item">
            <div className="stat-value">1,096</div>
            <div className="stat-label">Tests Passing</div>
          </div>
          <div className="stat-item">
            <div className="stat-value">74%</div>
            <div className="stat-label">Code Coverage</div>
          </div>
          <div className="stat-item">
            <div className="stat-value">3</div>
            <div className="stat-label">Built-in Plugins</div>
          </div>
          <div className="stat-item">
            <div className="stat-value">MIT</div>
            <div className="stat-label">License</div>
          </div>
        </div>
      </div>
    </section>
  );
}

function BuiltInPlugins() {
  const plugins = [
    {
      name: 'filesystem',
      description: 'Read, write, and manage files and directories',
      commands: ['read_file', 'write_file', 'list_directory', 'copy_file', 'move_file'],
    },
    {
      name: 'shell',
      description: 'Execute shell commands and scripts safely',
      commands: ['run_command', 'run_script', 'get_env', 'system_info'],
    },
    {
      name: 'web',
      description: 'HTTP requests, downloads, and URL parsing',
      commands: ['fetch', 'get', 'post', 'download', 'extract_links'],
    },
  ];

  return (
    <section className={styles.plugins}>
      <div className="container">
        <Heading as="h2" className="text--center" style={{marginBottom: '2rem'}}>
          Built-in Plugins
        </Heading>
        <div className="row">
          {plugins.map((plugin, idx) => (
            <div key={idx} className="col col--4">
              <div className="feature-card">
                <Heading as="h3">{plugin.name}</Heading>
                <p>{plugin.description}</p>
                <code style={{fontSize: '0.8rem'}}>
                  {plugin.commands.join(', ')}
                </code>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function QuickStart() {
  return (
    <section className={styles.quickstart}>
      <div className="container">
        <Heading as="h2" className="text--center" style={{marginBottom: '2rem'}}>
          Quick Start
        </Heading>
        <div className="row">
          <div className="col col--6 col--offset-3">
            <pre style={{background: '#1a1a2e', padding: '1.5rem', borderRadius: '8px'}}>
              <code className="language-bash">
{`# Install Mother AI OS
pip install mother-ai-os

# Configure your API key
export ANTHROPIC_API_KEY=sk-ant-...

# Start the server
mother serve

# Send a command
curl -X POST localhost:8080/command \\
  -H "Content-Type: application/json" \\
  -d '{"command": "List files in current directory"}'`}
              </code>
            </pre>
          </div>
        </div>
        <div className="text--center" style={{marginTop: '2rem'}}>
          <Link
            className="button button--primary button--lg"
            to="/docs/getting-started/installation">
            Read the Full Guide
          </Link>
        </div>
      </div>
    </section>
  );
}

function CTA() {
  return (
    <section className={styles.cta}>
      <div className="container text--center">
        <Heading as="h2">Ready to Get Started?</Heading>
        <p style={{fontSize: '1.2rem', marginBottom: '2rem'}}>
          Join developers building the future of AI-powered automation.
        </p>
        <div>
          <Link
            className="button button--primary button--lg"
            to="/docs/getting-started/installation">
            Install Now
          </Link>
          <Link
            className="button button--outline button--lg"
            style={{marginLeft: '1rem'}}
            href="https://github.com/Mother-AI-OS/mother">
            Star on GitHub
          </Link>
        </div>
      </div>
    </section>
  );
}

export default function Home() {
  const {siteConfig} = useDocusaurusContext();
  return (
    <Layout
      title="Home"
      description={siteConfig.tagline}>
      <HomepageHeader />
      <main>
        <div className="container" style={{marginTop: '-3rem', position: 'relative', zIndex: 1}}>
          <Terminal />
        </div>
        <Stats />
        <HomepageFeatures />
        <BuiltInPlugins />
        <QuickStart />
        <CTA />
      </main>
    </Layout>
  );
}
