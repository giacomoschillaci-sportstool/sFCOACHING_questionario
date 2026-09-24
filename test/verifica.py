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


FINGI_SUPABASE_CONDIZIONALE = """
  window.__rpc = [];
  window.__domandeProva = [
    {id:'d1', testo:'Quante ore hai dormito?', tipo:'scelta', opzioni:['Poco','Bene'], condizione:null, attiva:true},
    {id:'d2', testo:'Hai dolori?', tipo:'si_no', opzioni:null, condizione:null, attiva:true},
    {id:'d3', testo:'Descrivi i dolori', tipo:'testo', opzioni:null,
     condizione:{domanda_id:'d2', valore:'sì'}, attiva:true},
    {id:'d4', testo:'Ti senti pronto per allenarti oggi?', tipo:'si_no', opzioni:null, condizione:null, attiva:true}
  ];
  window.__questionarioProva = {id:'q1', nome:'Prova', domande_ids:['d1','d2','d3','d4']};
  window.supabase = { createClient: () => ({
    rpc: (nome, args) => {
      window.__rpc.push({nome, args});
      if (nome === 'verifica_atleta')
        return Promise.resolve({data:[{id:'a1', nome:'Atleta Prova'}], error:null});
      if (nome === 'invia_risposta') return Promise.resolve({data:null, error:null});
      if (nome === 'storico_risposte') return Promise.resolve({data:[], error:null});
      return Promise.resolve({data:null, error:null});
    },
    from: (tabella) => ({
      select: () => Promise.resolve({
        data: tabella === 'domande' ? window.__domandeProva : [window.__questionarioProva], error:null })
    })
  })};
"""


# I click sui bottoni sono sempre scoped dentro #questionario: "text=No" da solo
# è ambiguo perché intercetta anche l'h1 "Questionario mattutino" (contiene "no"
# dentro "mattutino", e text= non quotato fa match per sottostringa, case-insensitive).


@controllo
def il_questionario_salta_la_domanda_condizionata_se_non_serve(pagina, contesto):
    pagina.add_init_script(FINGI_SUPABASE_CONDIZIONALE)
    pagina.goto((RADICE / "index.html").as_uri() + "?t=token-valido")
    pagina.wait_for_timeout(300)
    pagina.fill("#campoEmail", "atleta@test.invalid")
    pagina.click("#bVerifica")
    pagina.wait_for_timeout(300)

    # prima domanda: scelta
    assert "dormito" in pagina.locator("#questionario").inner_text().lower()
    pagina.click("#questionario >> text=Bene")
    pagina.wait_for_timeout(200)

    # seconda: sì/no, rispondo "no" -> la terza (condizionata a "sì") va saltata
    assert "dolori" in pagina.locator("#questionario").inner_text().lower()
    pagina.click("#questionario >> text=No")
    pagina.wait_for_timeout(200)

    # non deve chiedere "descrivi i dolori": deve essere già sulla quarta domanda
    testo = pagina.locator("#questionario").inner_text().lower()
    assert "descrivi i dolori" not in testo, testo
    assert "pronto per allenarti" in testo, testo


@controllo
def il_questionario_chiede_la_domanda_condizionata_se_serve(pagina, contesto):
    pagina.add_init_script(FINGI_SUPABASE_CONDIZIONALE)
    pagina.goto((RADICE / "index.html").as_uri() + "?t=token-valido")
    pagina.wait_for_timeout(300)
    pagina.fill("#campoEmail", "atleta@test.invalid")
    pagina.click("#bVerifica")
    pagina.wait_for_timeout(300)
    pagina.click("#questionario >> text=Bene")
    pagina.wait_for_timeout(200)
    pagina.click("#questionario >> text=Sì")
    pagina.wait_for_timeout(200)
    assert "descrivi i dolori" in pagina.locator("#questionario").inner_text().lower()


FINGI_SUPABASE_GIA_RISPOSTO = FINGI_SUPABASE.replace(
    "if (nome === 'storico_risposte') return Promise.resolve({data:[], error:null});",
    """if (nome === 'storico_risposte') return Promise.resolve({data:[
         {id:'r1', data: new Date().toISOString().slice(0,10),
          risposte:{d1:'sì'}, creato_il:new Date().toISOString()}
       ], error:null});"""
)


@controllo
def se_ha_gia_risposto_oggi_mostra_sola_lettura(pagina, contesto):
    pagina.add_init_script(FINGI_SUPABASE_GIA_RISPOSTO)
    pagina.goto((RADICE / "index.html").as_uri() + "?t=token-valido")
    pagina.wait_for_timeout(300)
    pagina.fill("#campoEmail", "atleta@test.invalid")
    pagina.click("#bVerifica")
    pagina.wait_for_timeout(300)

    testo = pagina.locator("#questionario").inner_text().lower()
    assert "già" in testo or "oggi" in testo, testo
    assert pagina.locator("[data-valore]").count() == 0, "non deve mostrare un modulo compilabile"


@controllo
def completare_il_questionario_lo_invia(pagina, contesto):
    # FINGI_SUPABASE (Task 4) ha una sola domanda ('d1', sì/no): un click la completa.
    pagina.add_init_script(FINGI_SUPABASE)
    pagina.goto((RADICE / "index.html").as_uri() + "?t=token-valido")
    pagina.wait_for_timeout(300)
    pagina.fill("#campoEmail", "atleta@test.invalid")
    pagina.click("#bVerifica")
    pagina.wait_for_timeout(300)
    pagina.click("text=Sì")
    pagina.wait_for_timeout(300)

    chiamate = pagina.evaluate("() => window.__rpc.filter(r => r.nome === 'invia_risposta')")
    assert len(chiamate) == 1, chiamate
    assert chiamate[0]["args"]["p_risposte"]["d1"] == "sì", chiamate
    assert "inviat" in pagina.locator("#questionario").inner_text().lower()


FINGI_SUPABASE_QUESTIONARIO_ROTTO = """
  window.__rpc = [];
  window.supabase = { createClient: () => ({
    rpc: (nome, args) => {
      window.__rpc.push({nome, args});
      if (nome === 'verifica_atleta')
        return Promise.resolve({data:[{id:'a1', nome:'Atleta Prova'}], error:null});
      if (nome === 'storico_risposte') return Promise.resolve({data:[], error:null});
      return Promise.resolve({data:null, error:null});
    },
    from: (tabella) => ({
      select: () => tabella === 'questionari'
        ? Promise.resolve({data:null, error:{message:'boom'}})
        : Promise.resolve({data:[], error:null})
    })
  })};
"""


@controllo
def questionario_non_disponibile_mostra_errore_non_pagina_vuota(pagina, contesto):
    # caricaQuestionarioAttivo() fallisce (la select su 'questionari' torna un
    # errore): prima del fix la riga successiva leggeva questionari[0] su
    # undefined e la pagina restava vuota, con #questionario visibile ma
    # senza contenuto. Ora deve mostrare una card di errore onesta.
    pagina.add_init_script(FINGI_SUPABASE_QUESTIONARIO_ROTTO)
    pagina.goto((RADICE / "index.html").as_uri() + "?t=token-valido")
    pagina.wait_for_timeout(300)
    pagina.fill("#campoEmail", "atleta@test.invalid")
    pagina.click("#bVerifica")
    pagina.wait_for_timeout(300)

    assert not pagina.locator("#questionario").is_hidden()
    testo = pagina.locator("#questionario").inner_text().lower()
    assert "controlla la connessione" in testo, f"pagina senza messaggio d'errore: {testo!r}"
    assert pagina.locator("[data-valore]").count() == 0, "non deve mostrare un modulo, il questionario non si è caricato"


FINGI_SUPABASE_RETE_ROTTA = """
  window.__rpc = [];
  window.supabase = { createClient: () => ({
    rpc: (nome, args) => {
      window.__rpc.push({nome, args});
      if (nome === 'verifica_atleta') return Promise.reject(new TypeError('rete non disponibile'));
      return Promise.resolve({data:null, error:null});
    },
    from: () => ({ select: () => Promise.resolve({data: [], error: null}) })
  })};
"""


@controllo
def email_con_errore_di_rete_non_dice_email_non_riconosciuta(pagina, contesto):
    # verifica_atleta fallisce per un motivo di rete (non perché l'email è
    # sbagliata): il messaggio deve dirlo, non spacciare un errore di rete
    # per "email non riconosciuta".
    pagina.add_init_script(FINGI_SUPABASE_RETE_ROTTA)
    pagina.goto((RADICE / "index.html").as_uri() + "?t=token-valido")
    pagina.wait_for_timeout(300)
    pagina.fill("#campoEmail", "atleta@test.invalid")
    pagina.click("#bVerifica")
    pagina.wait_for_timeout(300)
    assert not pagina.locator("#erroreEmail").is_hidden()
    testo = pagina.locator("#erroreEmail").inner_text().lower()
    assert "non riconosciuta" not in testo, testo
    assert "connessione" in testo, testo


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
