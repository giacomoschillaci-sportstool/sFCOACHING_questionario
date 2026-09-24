# Questionario mattutino — Profilo Metabolico

Pagina pubblica che l'atleta apre ogni giorno dal telefono per compilare
il questionario mattutino. Nessun login: il link contiene un token
privato, generato dal tool locale del coach (repository `sFCOACHING`).

Fa parte del progetto "Profilo Metabolico" — la spec completa è in
`docs/superpowers/specs/2026-09-23-questionario-m2h-design.md` in quel
repository.

## Sviluppo locale

Nessuna build: `index.html` + `questionario.js` sono script classici.
Per lavorarci: `python -m http.server 8000` in questa cartella, poi apri
`http://localhost:8000/?t=<un token valido>`.

## Scale RPE e QGR10

Le due scale sono strumenti pubblicati: la pagina mostra le immagini
ORIGINALI del coach (`immagini/rpe_cr10.png`, `immagini/qgr10.png`,
pagina 2 dei suoi PDF "istruzioni per l'uso"), non una ricostruzione. Non
vanno ridisegnate né ritoccate: se il coach cambia scala, si sostituisce
il file e si aggiorna la domanda sul database.

## Test

```
python test/verifica.py
```

Playwright, `fetch` finto: non tocca mai il progetto Supabase vero.
