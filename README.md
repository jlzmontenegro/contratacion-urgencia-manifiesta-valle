# Contratación por urgencia manifiesta · Sismo del 10 de agosto de 2026

Tablero de seguimiento a la contratación pública derivada del sismo del 10 de agosto de 2026
en **Santiago de Cali y el Valle del Cauca**, construido sobre los datos abiertos de SECOP II.

👉 **[Ver el tablero](https://jlzmontenegro.github.io/contratacion-urgencia-manifiesta-valle/)**

## Marco normativo

| Acto | Autoridad | Contenido |
|---|---|---|
| Decreto 4112.010.20.0963 del 10-ago-2026 | Alcaldía de Cali | Calamidad pública, 6 meses |
| Decreto 4112.010.20.0964 del 10-ago-2026 | Alcaldía de Cali | Urgencia manifiesta, contratación directa (art. 42 Ley 80 de 1993) |
| Decreto 1.03.01-1070 del 10-ago-2026 | Gobernación del Valle | Calamidad pública, 6 meses, contratación por art. 66 Ley 1523 de 2012 |

El artículo 43 de la Ley 80 de 1993 y el 66 de la Ley 1523 de 2012 someten esta contratación
a control fiscal inmediato. Este tablero facilita ese seguimiento y el control ciudadano al
que convoca el artículo cuarto del Decreto 0964.

## Fuentes

Datos abiertos de datos.gov.co, consultados en vivo desde el navegador:

| Fuente | Dataset | Campo de fecha |
|---|---|---|
| Contratos electrónicos | [`jbjy-vk9h`](https://www.datos.gov.co/d/jbjy-vk9h) | `fecha_de_firma` |
| Procesos de contratación | [`p6dx-8zbt`](https://www.datos.gov.co/d/p6dx-8zbt) | `fecha_de_publicacion_del` |

Ventana de seguimiento: desde las **00:00 del 10 de agosto de 2026** y por al menos 6 meses.

## Contenido del repositorio

| Archivo | Para qué sirve |
|---|---|
| `index.html` | El tablero. Archivo autónomo: sin dependencias ni librerías externas. Se puede descargar, enviar por correo o abrir con doble clic y sigue funcionando |
| `colector.py` | Recolector opcional que guarda el histórico diario, detecta modificaciones sobre contratos ya publicados y genera reportes |
| `config.json` | NIT vigilados, palabras clave y umbrales de alerta, editables sin tocar el código |
| `LEEME.md` | Documentación completa: barridos, criterios de clasificación y advertencias sobre la fuente |

## Alcance

Los indicadores cuentan **únicamente entidades de Cali y del Valle del Cauca, incluidos sus
municipios**. Si no hay contratación relacionada en ese territorio, marcan cero. La
contratación relacionada de otras regiones del país se muestra aparte, como referencia.

## Advertencias sobre los datos

- SECOP II publica con aproximadamente **un día de rezago**.
- Los registros **se corrigen después de publicados** (valor, plazo, estado, liquidación).
- No toda la contratación de urgencia se marca como tal en la modalidad, por lo que el
  tablero también busca por palabras clave en el objeto contractual.
- El campo `descripcion_del_proceso` viene recortado cerca de los 300 caracteres; el objeto
  completo está en `objeto_del_contrato`. Se consultan ambos.

Esta es una herramienta de consulta de datos públicos. Las cifras deben verificarse en
SECOP II antes de usarse como evidencia; cada registro del tablero enlaza a su expediente.
