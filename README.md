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

## Test

```
python test/verifica.py
```

Playwright, `fetch` finto: non tocca mai il progetto Supabase vero.
