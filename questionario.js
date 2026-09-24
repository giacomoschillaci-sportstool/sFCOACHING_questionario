/* =========================================================================
   Questionario mattutino — pagina pubblica.

   Nessun login: il link contiene un token; alla prima apertura su un
   dispositivo si verifica l'email associata (funzione RPC verifica_atleta,
   mai una query diretta sulla tabella atleti — vedi la spec, sezione 5.2).
   Una volta verificato, il token resta in localStorage: le aperture
   successive sullo stesso dispositivo non richiedono più nulla.
   ========================================================================= */

const URL_SUPABASE = 'https://ccotkevblasndkczlifz.supabase.co';
const CHIAVE_SUPABASE = 'sb_publishable_e3IHAxhI8yQ3DPjdvS8n5Q_XHoQDawR';
const sb = supabase.createClient(URL_SUPABASE, CHIAVE_SUPABASE);

const CHIAVE_LOCALSTORAGE = 'questionario.verificato';

function leggiToken(){
  return new URLSearchParams(location.search).get('t');
}

function dispositivoVerificato(token){
  try { return localStorage.getItem(CHIAVE_LOCALSTORAGE) === token; } catch (e) { return false; }
}

function segnaDispositivoVerificato(token){
  try { localStorage.setItem(CHIAVE_LOCALSTORAGE, token); } catch (e) { /* localStorage non disponibile: si richiederà di nuovo */ }
}

async function verificaEmail(token, email){
  // Il contratto distingue "non trovato perché l'email non corrisponde" da
  // "non trovato perché la chiamata è fallita" (rete assente, Supabase giù):
  // sono due situazioni diverse per l'atleta, che merita un messaggio onesto
  // e non "email non riconosciuta" quando il problema è solo la connessione.
  let risposta;
  try {
    risposta = await sb.rpc('verifica_atleta', { p_token: token, p_email: email });
  } catch (e) {
    return { trovato: false, erroreRete: true };
  }
  const { data, error } = risposta;
  if (error) return { trovato: false, erroreRete: true };
  if (!data || data.length === 0) return { trovato: false, erroreRete: false };
  return { trovato: true, atleta: data[0] };   // atleta: {id, nome}
}

function mostraErrore(testo){
  document.getElementById('testoErroreLink').textContent = testo;
  document.getElementById('erroreLink').hidden = false;
}

async function avvia(){
  const token = leggiToken();
  if (!token){
    mostraErrore('Link non valido: manca il codice di accesso.');
    return;
  }

  if (dispositivoVerificato(token)){
    await mostraQuestionario(token);
    return;
  }

  const box = document.getElementById('formEmail');
  box.hidden = false;
  document.getElementById('bVerifica').onclick = async () => {
    const email = document.getElementById('campoEmail').value.trim();
    const erroreEmail = document.getElementById('erroreEmail');
    erroreEmail.hidden = true;
    if (!email){ erroreEmail.textContent = 'Scrivi la tua email.'; erroreEmail.hidden = false; return; }

    const esito = await verificaEmail(token, email);
    if (!esito.trovato){
      erroreEmail.textContent = esito.erroreRete
        ? "Non riesco a verificare l'email: controlla la connessione e riprova."
        : 'Email non riconosciuta per questo link.';
      erroreEmail.hidden = false;
      return;
    }
    segnaDispositivoVerificato(token);
    box.hidden = true;
    await mostraQuestionario(token);
  };
}

let statoQuestionario = null;   // {questionario, domande, indice, risposte, token}

async function caricaQuestionarioAttivo(){
  // Senza controlli, un errore Supabase o un questionario mancante lascia
  // `questionari[0]` undefined e la riga sotto va in eccezione non gestita:
  // la pagina resta vuota, senza modo di capire cosa è successo. Qui invece
  // solleviamo un errore esplicito che il chiamante (mostraQuestionario)
  // trasforma in un messaggio leggibile.
  const { data: questionari, error: erroreQuestionari } = await sb.from('questionari').select('*');
  if (erroreQuestionari || !questionari || questionari.length === 0){
    throw new Error('nessun questionario disponibile');
  }
  const questionario = questionari[0];
  const { data: tutteLeDomande, error: erroreDomande } = await sb.from('domande').select('*');
  if (erroreDomande || !tutteLeDomande){
    throw new Error('domande non disponibili');
  }
  const perId = Object.fromEntries(tutteLeDomande.map(d => [d.id, d]));
  const domande = questionario.domande_ids.map(id => perId[id]).filter(d => d && d.attiva !== false);
  return { questionario, domande };
}

function domandaVisibile(domanda, risposteFinora){
  if (!domanda.condizione) return true;
  const valoreDato = risposteFinora[domanda.condizione.domanda_id];
  if (valoreDato == null) return false;
  return String(valoreDato).toLowerCase() === String(domanda.condizione.valore).toLowerCase();
}

function prossimaDomandaVisibile(){
  const { domande, indice, risposte } = statoQuestionario;
  let i = indice;
  while (i < domande.length && !domandaVisibile(domande[i], risposte)) i++;
  return i;
}

async function mostraQuestionario(token){
  const box = document.getElementById('questionario');
  box.hidden = false;

  const oggi = new Date().toISOString().slice(0, 10);
  let rispostaDiOggi = null;
  try {
    const { data: storico, error } = await sb.rpc('storico_risposte', { p_token: token, p_da: oggi, p_a: oggi });
    if (error) throw error;
    rispostaDiOggi = (storico || []).find(r => r.data === oggi);
  } catch (e) {
    // Se lo storico non si legge (rete assente, Supabase giù) non blocchiamo
    // l'atleta: si comporta come se non avesse ancora risposto oggi. Nel
    // caso peggiore risponde due volte, ma invia_risposta aggiorna la
    // risposta del giorno invece di duplicarla (vincolo unique atleta+data),
    // quindi non è pericoloso — solo silenzioso, come da disegno originale.
    rispostaDiOggi = null;
  }

  if (rispostaDiOggi){
    box.innerHTML = `<div class="card"><p>Hai già risposto oggi. Grazie!</p></div>`;
    return;
  }

  try {
    const { questionario, domande } = await caricaQuestionarioAttivo();
    statoQuestionario = { questionario, domande, indice: 0, risposte: {}, token };
    statoQuestionario.indice = prossimaDomandaVisibile();
    renderDomanda();
  } catch (e) {
    box.innerHTML = `<div class="card"><p class="errore">Non riesco a caricare la pagina. Controlla la connessione e ricarica.</p></div>`;
  }
}

async function inviaRisposteRaccolte(){
  const box = document.getElementById('questionario');
  const { questionario, risposte, token } = statoQuestionario;
  const oggi = new Date().toISOString().slice(0, 10);

  box.innerHTML = `<div class="card"><p>Invio in corso…</p></div>`;
  const { error } = await sb.rpc('invia_risposta', {
    p_token: token, p_questionario_id: questionario.id, p_data: oggi, p_risposte: risposte });

  if (error){
    // Il testo digitato resta in `statoQuestionario.risposte`, nulla si perde:
    // basta far ripremere l'invio.
    box.innerHTML = `<div class="card"><p class="errore">Invio non riuscito, controlla la connessione.</p>
      <p><button class="btn primary" id="bRiprova">Riprova</button></p></div>`;
    document.getElementById('bRiprova').onclick = inviaRisposteRaccolte;
    return;
  }

  box.innerHTML = `<div class="card"><p>Risposta inviata. Grazie!</p></div>`;
}

function renderDomanda(){
  const box = document.getElementById('questionario');
  const { domande, indice } = statoQuestionario;

  if (indice >= domande.length){
    inviaRisposteRaccolte();
    return;
  }

  const d = domande[indice];
  let campo = '';
  if (d.tipo === 'scelta'){
    campo = (d.opzioni || []).map(o => `<button class="btn" data-valore="${o}">${o}</button>`).join(' ');
  } else if (d.tipo === 'si_no'){
    campo = `<button class="btn" data-valore="sì">Sì</button> <button class="btn" data-valore="no">No</button>`;
  } else if (d.tipo === 'testo'){
    campo = `<input type="text" id="campoRisposta"><p><button class="btn primary" id="bAvanti">Avanti</button></p>`;
  } else if (d.tipo === 'numero'){
    campo = `<input type="number" id="campoRisposta"><p><button class="btn primary" id="bAvanti">Avanti</button></p>`;
  } else if (d.tipo === 'scala_rpe' || d.tipo === 'scala_prs'){
    const { min, max, ancore } = d.opzioni || { min: 0, max: 10, ancore: {} };
    const bottoni = [];
    for (let n = min; n <= max; n++) bottoni.push(`<button data-valore="${n}">${n}</button>`);
    campo = `<div class="scala">${bottoni.join('')}</div>`;
    if (ancore) campo += `<div class="ancora">${Object.entries(ancore).map(([n,t]) => `${n}: ${t}`).join(' · ')}</div>`;
  }

  box.innerHTML = `<div class="card"><p>${d.testo}</p>${campo}</div>`;

  box.querySelectorAll('[data-valore]').forEach(b => b.onclick = () => rispondi(b.dataset.valore));
  const bAvanti = document.getElementById('bAvanti');
  if (bAvanti) bAvanti.onclick = () => rispondi(document.getElementById('campoRisposta').value);
}

function rispondi(valore){
  const { domande, indice } = statoQuestionario;
  const d = domande[indice];
  statoQuestionario.risposte[d.id] = valore;
  statoQuestionario.indice = indice + 1;
  statoQuestionario.indice = prossimaDomandaVisibile();
  renderDomanda();
}

avvia();
