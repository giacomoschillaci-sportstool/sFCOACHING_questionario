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
  const { data, error } = await sb.rpc('verifica_atleta', { p_token: token, p_email: email });
  if (error || !data || data.length === 0) return null;
  return data[0];   // {id, nome}
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

    const atleta = await verificaEmail(token, email);
    if (!atleta){
      erroreEmail.textContent = 'Email non riconosciuta per questo link.';
      erroreEmail.hidden = false;
      return;
    }
    segnaDispositivoVerificato(token);
    box.hidden = true;
    await mostraQuestionario(token);
  };
}

async function mostraQuestionario(token){
  // Il contenuto vero (domande, logica condizionale, invio) arriva nei
  // Task 5 e 6. Per ora un placeholder minimo, sufficiente a verificare
  // che l'accesso funzioni.
  const box = document.getElementById('questionario');
  box.hidden = false;
  box.innerHTML = '<div class="card"><p>Accesso confermato. Il questionario di oggi arriva nel prossimo passo.</p></div>';
}

avvia();
