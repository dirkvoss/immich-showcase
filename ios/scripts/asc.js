#!/usr/bin/env node
// Kleiner Zugang zu App Store Connect ohne Fremdpakete (nur Node).  Zugangsdaten: scripts/release.env (KEY_ID, ISSUER_ID, TEAM_ID).
//   node scripts/asc.js profil     legt das App-Store-Verteilungsprofil an und installiert es lokal
//   node scripts/asc.js app        zeigt den App-Eintrag (Name, Bundle-ID, Builds)
'use strict';
const fs = require('fs'), path = require('path'), crypto = require('crypto'), https = require('https'), os = require('os');
const BUNDLE_ID = 'com.dirk-voss.showcase', PROFIL_NAME = 'Showcase Immich App Store';
// App und Erweiterungen: je App-ID ein eigenes App-Store-Profil
const PROFILE = [
  { bundle: BUNDLE_ID, name: PROFIL_NAME, titel: 'Frameside' },
  { bundle: BUNDLE_ID + '.teilen', name: 'Showcase Immich Teilen App Store', titel: 'Frameside Teilen' },
  { bundle: BUNDLE_ID + '.widget', name: 'Showcase Immich Widget App Store', titel: 'Frameside Widget' },
];

const env = {};
for (const z of fs.readFileSync(path.join(__dirname, 'release.env'), 'utf8').split('\n')) { const t = z.match(/^([A-Z_]+)=(.+)$/); if (t) env[t[1]] = t[2].trim(); }
const SCHLUESSEL = fs.readFileSync(env.SCHLUESSEL || `${os.homedir()}/.appstoreconnect/private_keys/AuthKey_${env.KEY_ID}.p8`, 'utf8');
const b64 = x => Buffer.from(x).toString('base64').replace(/=/g, '').replace(/\+/g, '-').replace(/\//g, '_');
function token() {
  const jetzt = Math.floor(Date.now() / 1000);
  const u = `${b64(JSON.stringify({ alg: 'ES256', kid: env.KEY_ID, typ: 'JWT' }))}.${b64(JSON.stringify({ iss: env.ISSUER_ID, iat: jetzt, exp: jetzt + 900, aud: 'appstoreconnect-v1' }))}`;
  const sig = crypto.sign('SHA256', Buffer.from(u), { key: SCHLUESSEL, dsaEncoding: 'ieee-p1363' });
  return `${u}.${b64(sig)}`;
}
function ruf(methode, pfad, koerper) {
  return new Promise((gut, schlecht) => {
    const daten = koerper ? Buffer.from(JSON.stringify(koerper)) : null;
    const kopf = { Authorization: `Bearer ${token()}` };
    if (daten) { kopf['Content-Type'] = 'application/json'; kopf['Content-Length'] = daten.length; }
    const a = https.request({ hostname: 'api.appstoreconnect.apple.com', path: pfad, method: methode, headers: kopf }, r => {
      let t = ''; r.on('data', s => (t += s)); r.on('end', () => {
        let j = {}; try { j = t ? JSON.parse(t) : {}; } catch { j = { raw: t }; }
        if (r.statusCode >= 400) schlecht(new Error(`${methode} ${pfad} → ${r.statusCode}: ${(j.errors || []).map(f => f.detail || f.title).join(' | ') || t.slice(0, 300)}`)); else gut(j);
      });
    });
    a.on('error', schlecht); if (daten) a.write(daten); a.end();
  });
}

async function profil() {
  const zert = (await ruf('GET', '/v1/certificates?filter[certificateType]=DISTRIBUTION&limit=50')).data.filter(c => new Date(c.attributes.expirationDate) > new Date());
  if (!zert.length) throw new Error('Kein gueltiges Apple-Distribution-Zertifikat gefunden');
  const ordner = `${os.homedir()}/Library/Developer/Xcode/UserData/Provisioning Profiles`;
  fs.mkdirSync(ordner, { recursive: true });
  for (const p of PROFILE) {
    let bundle = (await ruf('GET', `/v1/bundleIds?filter[identifier]=${p.bundle}`)).data.find(b => b.attributes.identifier === p.bundle);
    if (!bundle) {
      bundle = (await ruf('POST', '/v1/bundleIds', { data: { type: 'bundleIds', attributes: { identifier: p.bundle, name: p.titel, platform: 'IOS' } } })).data;
      console.log(`App-ID ${p.bundle} angelegt`);
    }
    const vorhanden = (await ruf('GET', `/v1/profiles?filter[name]=${encodeURIComponent(p.name)}&limit=10`)).data;
    for (const v of vorhanden) { console.log('Altes Profil wird ersetzt:', v.id); await ruf('DELETE', `/v1/profiles/${v.id}`); }
    const neu = (await ruf('POST', '/v1/profiles', { data: { type: 'profiles', attributes: { name: p.name, profileType: 'IOS_APP_STORE' },
      relationships: { bundleId: { data: { type: 'bundleIds', id: bundle.id } }, certificates: { data: zert.map(c => ({ type: 'certificates', id: c.id })) } } } })).data;
    const datei = path.join(ordner, `${neu.attributes.uuid}.mobileprovision`);
    fs.writeFileSync(datei, Buffer.from(neu.attributes.profileContent, 'base64'));
    console.log(`Profil "${p.name}" angelegt (UUID ${neu.attributes.uuid}), gueltig bis ${neu.attributes.expirationDate.slice(0, 10)}`);
  }
}

async function app() {
  const a = (await ruf('GET', `/v1/apps?filter[bundleId]=${BUNDLE_ID}`)).data[0];
  if (!a) { console.log(`Kein App-Eintrag fuer ${BUNDLE_ID}. Bitte in App Store Connect anlegen (siehe ios/README.md).`); return; }
  console.log(`App: ${a.attributes.name} | ${a.attributes.bundleId} | SKU ${a.attributes.sku} | id ${a.id}`);
  const b = (await ruf('GET', `/v1/builds?filter[app]=${a.id}&sort=-uploadedDate&limit=5`)).data;
  console.log('Builds:', b.map(x => `${x.attributes.version} (${x.attributes.processingState})`).join(', ') || 'noch keine');
}

({ profil, app }[process.argv[2]] || (() => { console.log('Befehle: profil | app'); return Promise.resolve(); }))().catch(e => { console.error('FEHLER:', e.message); process.exit(1); });
