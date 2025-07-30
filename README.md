# Trading Automático con Bonos en Cocos

Este repositorio contiene un conjunto de scripts en Python para operar automáticamente bonos del mercado argentino utilizando la API de **Cocos Capital**. Aparte consigue vaores de caja desde **PPI**. 
Las operaciones se basan en el monitoreo de precios, detección de oportunidades de arbitraje, y ejecución de órdenes de compra/venta en tiempo real.

 🧠 ¿Qué hace este sistema?

- Extrae precios en tiempo real de múltiples activos utilizando la API de Cocos.
- Guarda los datos en una base de datos PostgreSQL para análisis y backtesting.
- Ejecuta estrategias de trading automático (por ejemplo, arbitraje de ratios).
- Soporta logging por archivo para cada estrategia o script ejecutado.
- Emite alertas sonoras cuando se detectan oportunidades.
- Cuando se detecta una oportunidad de arbitraje, opera automaticamente

---

 ⚙️ Requisitos

- Python ≥ 3.8
- PostgreSQL (base de datos `prices`)
- `.env` con las claves necesarias:

CLAVE_SECRETA_COCOS=...
CLAVE_PUBLICA_PPI=...
CLAVE_PRIVADA_PPI=...
CLAVE_POSGRES=...

Ejemplo para guardar ofertas y demandas durante el horario de mercado. Escribir en terminal: python operar_precios.py

---

🛠️ Funcionalidades destacadas

- Sistema multihilo para lectura de precios en paralelo.
- Recuperación automática ante errores de token (401).
- Cálculo dinámico de ratio mínimo usando función calculate_daily_rate().
- Logging individual por estrategia.
- Alerta sonora configurable ante oportunidades de trading (auto_beep()).

---

🧾 Notas adicionales

- La lógica de órdenes está pensada para operar volúmenes mínimos y evitar slippage.
- La ejecución está restringida a horario de mercado argentino (11 a 17 hs).
- La base de datos almacena históricos con timestamps y count incremental por ronda.
