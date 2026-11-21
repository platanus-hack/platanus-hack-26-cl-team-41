# SolidCraft – brazo robótico y base móvil

Diseños paramétricos hechos en [SolidCraft](https://github.com/tangency-labs/solidcraft) 0.45.

| Carpeta | Contenido |
|---|---|
| `brazo_robotico/` | Primera versión del brazo: 4 × MG995 + 2 × SG90, eslabones en horquilla abierta |
| `brazo_compacto/` | Brazo compacto y cerrado (eslabones redondeados con tapa), con URDF para simulación |
| `base_movil/` | Base móvil de 4 ruedas: brushless 1750 KV (5") con reducción 80:1 en 3 etapas, chasis para la electrónica |
| `scripts/` | Generadores en Python que construyen cada diseño a través del servidor MCP de SolidCraft |

Cada carpeta tiene el diseño `.sc` (editable en SolidCraft), un `.step` del conjunto y los `.stl` de las piezas para imprimir.

## Base móvil – resumen

- Reducción por rueda: 12T→60T (m1) · 12T→48T (m1,25) · 12T→48T (m1,25) = **80:1**, ~1 m/s con ruedas de Ø100 en 3S.
- Chasis 242 × 220 × 113 mm, tapa con el patrón del brazo (4 × M4 a Ø150).
- Tornillería por rueda: 2 × M4×50 con tuerca, 4 × M3 (motor), 3 × M3×10 (módulo a pared), 1 × M3 + arandela (eje).

## Regenerar un diseño

Con SolidCraft abierto con `--control 27878`:

```
python scripts/brazo_compacto.py 1 > s.json && python scripts/mcp_client.py s.json
```

(cada script se ejecuta por etapas; ver el bloque `stage ==` al final de cada uno).
