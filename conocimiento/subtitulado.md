Fuente: canon local de subtitulado, secciones 10–17 (destilado) · Fecha: 2026-10-20

# Subtitulado con puerta de QA

## Camino único

El texto nace de `palabras.json`, se agrupa en golpes, se renderiza con `bin/motor.py` y se revisa con `bin/qa_subtitulos.py`. Un candidato no es una entrega. La entrega aparece únicamente cuando los fallos mecánicos son cero y alguien confirma que vio la pieza completa en movimiento.

## Reglas de tiempo

- Detectar idioma por frase; fijarlo para un archivo bilingüe puede convertir el otro idioma en traducción.
- Revelar cada palabra en su inicio de voz. El bloque no debe saltar mientras crece.
- Una pausa de voz mayor a 300 ms produce pantalla limpia.
- No dejar conectores colgados al final de un golpe.
- Quitar muletillas que no cambien sentido; el subtítulo no debe ocupar toda la voz.

## Reglas de composición

- Diseñar el primer golpe con intención de apertura.
- Mantener una sola familia, peso, color y sistema de sombra por pieza.
- Usar blanco, negrita y jerarquía por tamaño en el preset público.
- Prioridad: cara, interfaz, continuidad del ancla y centro del frame.
- Si no existe una zona segura, callar el golpe y reportarlo.

## QA

El control mecánico verifica límites por golpe, pausas, orden del reveal, solapes y densidad. La revisión visual comprueba caras, interfaz, legibilidad, cortes de plano y movimiento. Sin esa revisión, el estado es NO PASA.

Las correcciones se hacen por número de golpe y se prueban de nuevo; no se cambia el preset para salvar una pieza aislada.

