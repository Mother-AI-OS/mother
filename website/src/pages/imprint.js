import React from 'react';
import Layout from '@theme/Layout';

export default function Imprint() {
  return (
    <Layout
      title="Imprint"
      description="Legal imprint for Mother AI OS — Hucke & Sanker Ltd., Brighton, UK."
    >
      <main className="container margin-vert--xl" style={{maxWidth: '700px'}}>
        <h1>Imprint</h1>

        <section style={{marginBottom: '2rem'}}>
          <h2>Legal Entity</h2>
          <p>
            <strong>Hucke &amp; Sanker Ltd.</strong><br />
            15-17 Middle Street<br />
            BN1-1AL Brighton<br />
            United Kingdom
          </p>
        </section>

        <section style={{marginBottom: '2rem'}}>
          <h2>Contact</h2>
          <p>
            Email: <a href="mailto:mail@mother-os.info">mail@mother-os.info</a>
          </p>
        </section>

        <section style={{marginBottom: '2rem'}}>
          <h2>Responsible for Content</h2>
          <p>David Sanker, Hucke &amp; Sanker Ltd.</p>
        </section>

        <section style={{marginBottom: '2rem'}}>
          <h2>Platform / Service</h2>
          <p>
            Mother AI OS is published and maintained by Hucke &amp; Sanker Ltd.
            The source code is licensed under the Apache 2.0 License.
          </p>
        </section>
      </main>
    </Layout>
  );
}
