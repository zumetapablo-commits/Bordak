# Buscador de fincas rústicas en Gipuzkoa

Revisa cada 2 h varias inmobiliarias y Cocampo. Busca terreno rústico, bordas, casetas,
caseríos, fincas rústicas y huertas de **≤ 250.000 €** a **≤ 15 km de la costa**.
Puntúa cada anuncio según su cercanía a Zarautz y a spots de surf y el tiempo desde
Tolosa, y manda un correo solo con los **anuncios nuevos**.

## Cómo funciona
- `src/fincas/sources/`: un módulo por web. Cada uno recorre el listado y, solo para
  anuncios nuevos o con cambio de precio, la ficha.
- `src/fincas/http.py`: respeta robots.txt y deja como mínimo 1 s entre peticiones al
  mismo host.
- `src/fincas/geo/`: busca la ubicación primero en las coordenadas del anuncio, luego con
  Nominatim (cacheado en SQLite) y, si no hay más, usa el centroide del municipio. En ese
  último caso la ubicación se marca como aproximada (≈ en el correo). La distancia a la
  costa se calcula contra `natural=coastline` de OSM en EPSG:25830.
- `state/fincas.sqlite`: anuncios vistos, histórico de precios y caché de geocodificación.
  El workflow lo commitea tras cada ejecución.
- `config.yaml`: filtros, pesos de la puntuación y fuentes activas.

## Puesta en marcha
1. `pip install -e .[dev]` y `pytest`.
2. `python scripts/build_geodata.py`: genera `data/coastline_gipuzkoa.geojson` y
   `data/municipios.csv` con tiempos OSRM a Tolosa. Commitea el resultado.
3. Secrets del repo: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_TO`.
   Con Gmail: `smtp.gmail.com`, `587` y una contraseña de aplicación.
4. `fincas test-email` en local, o lanza el workflow a mano.
5. Primera carga: lanza el workflow con `seed = true` para no recibir todos los anuncios
   existentes de golpe.

## Comandos
```
fincas run --dry-run            # ejecución real sin guardar ni enviar
fincas run --source cocampo     # una sola fuente
fincas run --seed               # marca todo como visto
fincas test-email
```
