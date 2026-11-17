# Run the debugger locally · Abrir el depurador en local

From the repository root, run the following command. Desde la raíz del repositorio, ejecuta este comando.

```sh
python -m http.server 8000 --directory docs
```

[English](http://localhost:8000/) · [Español](http://localhost:8000/?lang=es)

## Replay data · Datos reproducidos

The demo uses six recorded responses and condensed tool traces from the [Gujarat Finance Accounts study](../../studies/gujarat-volume-i/README.md). The excerpts preserve the line numbers of the converted Markdown. The page runs in the browser and needs no API key.

La demo usa seis respuestas registradas y trazas resumidas del [estudio de las cuentas de Gujarat](../../studies/gujarat-volume-i/README.md). Los extractos conservan la numeración de líneas del Markdown convertido. La página funciona en el navegador sin clave de API.

To regenerate the snapshot from the original run files. Para regenerar los datos a partir de las ejecuciones originales.

```sh
python studies/gujarat-volume-i/export_debugger.py \
  data/corpora/gujarat-live/gujarat-vol-i.md \
  runs/gujarat-read-bm25-002/results.jsonl \
  runs/gujarat-controls-001/results.jsonl
```

## GitHub Pages

In the repository's **Settings → Pages**, select **Deploy from a branch**, **main** and **/docs**, then save.

En **Settings → Pages** del repositorio, selecciona **Deploy from a branch**, **main** y **/docs** y guarda.
