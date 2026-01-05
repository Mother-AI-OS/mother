import React from 'react';
import Layout from '@theme/Layout';
import styles from './services.module.css';

function ServiceCard({title, description, features, price, cta, highlighted}) {
  return (
    <div className={`${styles.serviceCard} ${highlighted ? styles.highlighted : ''}`}>
      <h3>{title}</h3>
      <p className={styles.serviceDescription}>{description}</p>
      <ul className={styles.featureList}>
        {features.map((feature, idx) => (
          <li key={idx}>{feature}</li>
        ))}
      </ul>
      <div className={styles.price}>{price}</div>
      <a href="mailto:david@lawkraft.com?subject=Mother%20AI%20OS%20-%20Services%20Inquiry" className={styles.ctaButton}>{cta}</a>
    </div>
  );
}

function IntegrationBadge({name}) {
  return <span className={styles.badge}>{name}</span>;
}

export default function Services() {
  return (
    <Layout title="Services" description="Professional services for Mother AI OS">
      {/* Hero */}
      <section className={styles.hero}>
        <div className={styles.container}>
          <h1>Professional Services</h1>
          <p className={styles.heroSubtitle}>
            Get expert help implementing Mother AI OS in your organization.
            From quick setup to fully customized enterprise deployments.
          </p>
        </div>
      </section>

      {/* Core Services */}
      <section className={styles.section}>
        <div className={styles.container}>
          <h2>Core Services</h2>
          <div className={styles.serviceGrid}>
            <ServiceCard
              title="Implementation"
              description="Get Mother AI OS running in your environment with expert guidance."
              features={[
                'Installation & configuration',
                'Security hardening',
                'Team training session',
                'Documentation & runbooks',
                '30 days email support',
              ]}
              price="From €2,500"
              cta="Get Started"
            />
            <ServiceCard
              title="Custom Plugins"
              description="We build the integrations you need for your specific workflows."
              features={[
                'Requirements analysis',
                'Plugin development',
                'Testing & QA',
                'Documentation',
                'Maintenance included (1 year)',
              ]}
              price="From €1,500"
              cta="Discuss Your Needs"
              highlighted={true}
            />
            <ServiceCard
              title="Managed Hosting"
              description="Focus on using Mother AI OS. We handle the infrastructure."
              features={[
                'EU-hosted (GDPR compliant)',
                'Automatic updates',
                'Daily backups',
                '99.9% uptime SLA',
                'Priority support',
              ]}
              price="From €99/month"
              cta="Start Free Trial"
            />
          </div>
        </div>
      </section>

      {/* Individualization */}
      <section className={`${styles.section} ${styles.sectionAlt}`}>
        <div className={styles.container}>
          <h2>Individualization</h2>
          <p className={styles.sectionSubtitle}>
            Your stack, your rules. We customize Mother AI OS to fit your existing infrastructure.
          </p>

          <div className={styles.integrationGrid}>
            <div className={styles.integrationCategory}>
              <h3>AI / LLM Backend</h3>
              <div className={styles.badgeContainer}>
                <IntegrationBadge name="OpenAI GPT-4" />
                <IntegrationBadge name="Anthropic Claude" />
                <IntegrationBadge name="Azure OpenAI" />
                <IntegrationBadge name="AWS Bedrock" />
                <IntegrationBadge name="Local LLM (Ollama)" />
                <IntegrationBadge name="Custom Fine-tuned" />
              </div>
            </div>

            <div className={styles.integrationCategory}>
              <h3>Vector Database</h3>
              <div className={styles.badgeContainer}>
                <IntegrationBadge name="ChromaDB" />
                <IntegrationBadge name="Pinecone" />
                <IntegrationBadge name="Weaviate" />
                <IntegrationBadge name="Qdrant" />
                <IntegrationBadge name="pgvector" />
                <IntegrationBadge name="Elasticsearch" />
              </div>
            </div>

            <div className={styles.integrationCategory}>
              <h3>Cloud Infrastructure</h3>
              <div className={styles.badgeContainer}>
                <IntegrationBadge name="AWS" />
                <IntegrationBadge name="Azure" />
                <IntegrationBadge name="Google Cloud" />
                <IntegrationBadge name="Hetzner" />
                <IntegrationBadge name="On-Premise" />
                <IntegrationBadge name="Air-Gapped" />
              </div>
            </div>

            <div className={styles.integrationCategory}>
              <h3>Workflow & Tasks</h3>
              <div className={styles.badgeContainer}>
                <IntegrationBadge name="Celery" />
                <IntegrationBadge name="Apache Airflow" />
                <IntegrationBadge name="Temporal" />
                <IntegrationBadge name="AWS Step Functions" />
                <IntegrationBadge name="Prefect" />
              </div>
            </div>

            <div className={styles.integrationCategory}>
              <h3>Authentication</h3>
              <div className={styles.badgeContainer}>
                <IntegrationBadge name="OAuth2 / OIDC" />
                <IntegrationBadge name="SAML / SSO" />
                <IntegrationBadge name="Azure AD" />
                <IntegrationBadge name="Okta" />
                <IntegrationBadge name="Keycloak" />
              </div>
            </div>

            <div className={styles.integrationCategory}>
              <h3>Monitoring & Logging</h3>
              <div className={styles.badgeContainer}>
                <IntegrationBadge name="Datadog" />
                <IntegrationBadge name="Grafana" />
                <IntegrationBadge name="ELK Stack" />
                <IntegrationBadge name="Splunk" />
                <IntegrationBadge name="CloudWatch" />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Packages */}
      <section className={styles.section}>
        <div className={styles.container}>
          <h2>Enterprise Packages</h2>
          <p className={styles.sectionSubtitle}>
            Pre-configured solutions for common enterprise requirements.
          </p>

          <div className={styles.packageGrid}>
            <div className={styles.packageCard}>
              <div className={styles.packageHeader}>
                <h3>Cloud Native</h3>
                <span className={styles.packagePrice}>From €12,000</span>
              </div>
              <p>For companies migrating to cloud infrastructure.</p>
              <ul>
                <li>AWS / Azure / GCP deployment</li>
                <li>Managed vector database</li>
                <li>Cloud-native monitoring</li>
                <li>SSO integration</li>
                <li>€500/month ongoing support</li>
              </ul>
            </div>

            <div className={`${styles.packageCard} ${styles.packageHighlighted}`}>
              <div className={styles.packageBadge}>Most Popular</div>
              <div className={styles.packageHeader}>
                <h3>Privacy First</h3>
                <span className={styles.packagePrice}>From €20,000</span>
              </div>
              <p>For regulated industries: legal, healthcare, finance.</p>
              <ul>
                <li>EU-only or on-premise hosting</li>
                <li>Local LLM option (air-gap capable)</li>
                <li>Self-hosted vector database</li>
                <li>Full audit logging</li>
                <li>€1,000/month ongoing support</li>
              </ul>
            </div>

            <div className={styles.packageCard}>
              <div className={styles.packageHeader}>
                <h3>Enterprise Integration</h3>
                <span className={styles.packagePrice}>From €35,000</span>
              </div>
              <p>For large organizations with existing tooling.</p>
              <ul>
                <li>Kubernetes integration</li>
                <li>Airflow / Temporal workflows</li>
                <li>Enterprise IdP (SAML/SSO)</li>
                <li>Splunk / Datadog logging</li>
                <li>€2,500/month ongoing support</li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* Advisory */}
      <section className={`${styles.section} ${styles.sectionAlt}`}>
        <div className={styles.container}>
          <h2>Ongoing Advisory</h2>
          <p className={styles.sectionSubtitle}>
            Fractional AI architect for your team. Strategic guidance without full-time overhead.
          </p>

          <div className={styles.advisoryGrid}>
            <div className={styles.advisoryCard}>
              <h3>Essentials</h3>
              <div className={styles.advisoryPrice}>€1,500<span>/month</span></div>
              <ul>
                <li>4 hours per month</li>
                <li>Async support (email/Slack)</li>
                <li>Quarterly architecture review</li>
                <li>Priority bug fixes</li>
              </ul>
            </div>

            <div className={styles.advisoryCard}>
              <h3>Growth</h3>
              <div className={styles.advisoryPrice}>€3,500<span>/month</span></div>
              <ul>
                <li>10 hours per month</li>
                <li>Weekly sync call</li>
                <li>Priority response (24hr)</li>
                <li>Plugin development guidance</li>
              </ul>
            </div>

            <div className={styles.advisoryCard}>
              <h3>Scale</h3>
              <div className={styles.advisoryPrice}>€7,500<span>/month</span></div>
              <ul>
                <li>20 hours per month</li>
                <li>Embedded in your team</li>
                <li>Architecture decisions</li>
                <li>Direct access to founder</li>
              </ul>
            </div>
          </div>
        </div>
      </section>

      {/* About / Trust */}
      <section className={styles.section}>
        <div className={styles.container}>
          <div className={styles.aboutSection}>
            <div className={styles.aboutContent}>
              <h2>Why Work With Us</h2>
              <p>
                Mother AI OS was built by <strong>David Sanker</strong>, a lawyer and AI engineer
                with a unique perspective on enterprise software.
              </p>
              <ul className={styles.credentialsList}>
                <li><strong>Legal expertise:</strong> Partner at Hucke & Sanker (Cologne, NY, Brighton)</li>
                <li><strong>Enterprise experience:</strong> Legal Knowledge Engineer at Cleary Gottlieb</li>
                <li><strong>Technical depth:</strong> Built Mother AI OS from the ground up</li>
                <li><strong>Compliance focus:</strong> Understands regulated industries</li>
              </ul>
              <p>
                When you work with us, you're working with the creator of the platform.
                No middlemen, no support tiers - direct access to expertise.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className={styles.ctaSection}>
        <div className={styles.container}>
          <h2>Ready to Get Started?</h2>
          <p>Tell us about your project and we'll find the right solution.</p>
          <div className={styles.ctaButtons}>
            <a
              href="mailto:david@lawkraft.com?subject=Mother%20AI%20OS%20-%20Services%20Inquiry"
              className={styles.ctaPrimary}
            >
              Schedule a Call
            </a>
            <a
              href="https://github.com/Mother-AI-OS/mother"
              className={styles.ctaSecondary}
            >
              View on GitHub
            </a>
          </div>
        </div>
      </section>
    </Layout>
  );
}
