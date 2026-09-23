#!/usr/bin/env python3
"""Prove della pagina questionario. Playwright, fetch finto: mai contro Supabase vero."""

import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

RADICE = Path(__file__).resolve().parent.parent
CONTROLLI = []


def controllo(f):
    CONTROLLI.append(f)
    return f


# La libreria Supabase vera arriva da CDN con un <script> nell'HTML, caricato
# DOPO l'init script di Playwright: se la lasciassimo passare sovrascriverebbe
# il window.supabase finto (stesso nome globale) e i controlli finirebbero per
# chiamare il progetto Supabase vero. La blocchiamo sempre e la sostituiamo con
# uno stub innocuo che non tocca window.supabase se un controllo l'ha già
# preparato con add_init_script(FINGI_SUPABASE).
STUB_LIBRERIA_SUPABASE = (
    "window.supabase = window.supabase || { createClient: () => ({"
    "  rpc: () => Promise.resolve({data: [], error: null}),"
    "  from: () => ({ select: () => Promise.resolve({data: [], error: null}) })"
    "}) };"
)


def apri(motore):
    browser = motore.chromium.launch()
    contesto = browser.new_context(viewport={"width": 390, "height": 844})
    contesto.route(
        "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/dist/umd/supabase.js",
        lambda route: route.fulfill(status=200, content_type="application/javascript",
                                     body=STUB_LIBRERIA_SUPABASE),
    )
    # difesa in profondità: nessuna chiamata deve mai raggiungere il progetto vero
    contesto.route("https://ccotkevblasndkczlifz.supabase.co/**", lambda route: route.abort())
    pagina = contesto.new_page()
    errori = []
    pagina.on("pageerror", lambda e: errori.append(str(e)))
    pagina.on("console", lambda m: errori.append(m.text) if m.type == "error" else None)
    return browser, contesto, pagina, errori


FINGI_SUPABASE = """
  window.__rpc = [];
  window.__domandeProva = [{id:'d1', testo:'Come va?', tipo:'si_no', opzioni:null, condizione:null, attiva:true}];
  window.__questionarioProva = {id:'q1', nome:'Prova', domande_ids:['d1']};
  window.supabase = { createClient: () => ({
    rpc: (nome, args) => {
      window.__rpc.push({nome, args});
      if (nome === 'verifica_atleta'){
        if (args.p_token === 'token-valido' && args.p_email.toLowerCase() === 'atleta@test.invalid')
          return Promise.resolve({data:[{id:'a1', nome:'Atleta Prova'}], error:null});
        return Promise.resolve({data:[], error:null});
      }
      if (nome === 'storico_risposte') return Promise.resolve({data:[], error:null});
      if (nome === 'invia_risposta') return Promise.resolve({data:null, error:null});
      return Promise.resolve({data:null, error:null});
    },
    from: (tabella) => ({
      select: () => Promise.resolve({
        data: tabella === 'domande' ? window.__domandeProva : [window.__questionarioProva], error:null })
    })
  })};
"""


@controllo
def link_senza_token_mostra_errore(pagina, contesto):
    pagina.goto((RADICE / "index.html").as_uri())
    pagina.wait_for_timeout(300)
    assert not pagina.locator("#erroreLink").is_hidden()


@controllo
def email_giusta_sblocca_e_ricorda_il_dispositivo(pagina, contesto):
    pagina.add_init_script(FINGI_SUPABASE)
    pagina.goto((RADICE / "index.html").as_uri() + "?t=token-valido")
    pagina.wait_for_timeout(300)
    assert not pagina.locator("#formEmail").is_hidden()

    pagina.fill("#campoEmail", "atleta@test.invalid")
    pagina.click("#bVerifica")
    pagina.wait_for_timeout(300)
    assert pagina.locator("#formEmail").is_hidden()
    assert not pagina.locator("#questionario").is_hidden()

    ricordato = pagina.evaluate("() => localStorage.getItem('questionario.verificato')")
    assert ricordato == "token-valido", ricordato

    # ricarico: stavolta niente form email, va dritto al questionario
    pagina.reload()
    pagina.wait_for_timeout(300)
    assert pagina.locator("#formEmail").is_hidden()
    assert not pagina.locator("#questionario").is_hidden()


@controllo
def email_sbagliata_mostra_errore_e_non_ricorda_nulla(pagina, contesto):
    pagina.add_init_script(FINGI_SUPABASE)
    pagina.goto((RADICE / "index.html").as_uri() + "?t=token-valido")
    pagina.wait_for_timeout(300)
    pagina.fill("#campoEmail", "sconosciuto@test.invalid")
    pagina.click("#bVerifica")
    pagina.wait_for_timeout(300)
    assert not pagina.locator("#erroreEmail").is_hidden()
    assert pagina.locator("#questionario").is_hidden()


def main(nomi):
    scelti = [c for c in CONTROLLI if not nomi or c.__name__ in nomi]
    falliti = 0
    with sync_playwright() as motore:
        for c in scelti:
            browser, contesto, pagina, errori = apri(motore)
            try:
                c(pagina, contesto)
                assert not errori, f"errori nella pagina: {errori[:3]}"
                print(f"  ok       {c.__name__}")
            except AssertionError as e:
                falliti += 1
                print(f"  FALLITO  {c.__name__}: {e}")
            finally:
                browser.close()
    print("\n" + ("FALLITO - %d su %d" % (falliti, len(scelti)) if falliti
                  else "TUTTO A POSTO - %d controlli" % len(scelti)))
    return 1 if falliti else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
