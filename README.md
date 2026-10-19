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

## Fuentes
| Fuente | Estado | Cómo se lee |
|---|---|---|
| Cocampo | ✅ | JSON-LD del listado de Gipuzkoa + coordenadas de la ficha |
| Moldatu Home | ✅ | HTML de inmuebles.moldatuhome.com; robots.txt prohíbe paginar, se usan las páginas por municipio |
| SIRO | ✅ | Catálogo público (Supabase) que usa su propia web; ahora sin anuncios rústicos |
| Egaña, Flysch, Adoshome | ⏸ | Falta la web correcta (`adoshomes.com` es de Barcelona; `flysch.es` es turismo) |
| Milanuncios, Wallapop | ⛔ | Responden 403 a cualquier robot (Wallapop incluso a robots.txt); no se fuerza |

Los anuncios con precio «a consultar» que cumplen la distancia se avisan en un bloque aparte
(`filters.include_price_on_request` en `config.yaml`).

## Puesta en marcha
1. `pip install -e .[dev]` y `pytest`.
2. Datos geográficos: ya están en `data/`. Para regenerarlos, lanza el workflow
   «Generar datos geográficos» (extracto OSM de Geofabrik + tiempos OSRM a Tolosa).
3. Secrets del repo: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_TO`.
   Con Gmail: `smtp.gmail.com`, `587` y una contraseña de aplicación.
4. `fincas test-email` en local, o lanza el workflow a mano.
5. La primera ejecución marca como vistos los anuncios existentes sin enviar correo.
   El workflow «Prueba en seco» ejecuta todo sin guardar ni enviar y deja el registro y
   una vista previa del correo en la rama `pruebas`.

## Comandos
```
fincas run --dry-run            # ejecución real sin guardar ni enviar
fincas run --source cocampo     # una sola fuente
fincas run --seed               # marca todo como visto
fincas test-email
```
